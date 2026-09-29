#!/usr/bin/env node
// ui-smoke.mjs —— 用**真实浏览器**跑一遍界面（命令行驱动，零新增依赖）
//
// 为什么要它：HTTP 冒烟只能证明接口对，证明不了"页面上的按钮点了真的有反应"。
// 之前这在文档里是一条已知限制（"无浏览器端点击级自动化测试"），这个工具就是来消掉它的。
//
// 怎么做到零依赖：Node 22 自带全局 WebSocket，浏览器自带 CDP（DevTools Protocol）。
// 用系统 Edge/Chrome 的 --headless=new + --remote-debugging-port，通过 CDP 在页面里
// 执行 JS（点击按钮、读 DOM），不需要 Playwright/Puppeteer，也不需要装 Electron。
//
// 用法：node tools/ui-smoke.mjs [--keep]   （--keep 保留浏览器窗口便于肉眼观察）
import { spawn } from 'node:child_process'
import { mkdtempSync, rmSync, existsSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { bootHost, stopHost } from '../src/boot.mjs'

let failed = 0
const ok = (cond, msg, extra = '') => {
  if (cond) console.log('  [ok] ' + msg)
  else { failed++; console.log('  [FAIL] ' + msg + (extra ? ' -> ' + extra : '')) }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const BROWSERS = [
  process.env.POMODMER_BROWSER,
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  process.env.LOCALAPPDATA ? join(process.env.LOCALAPPDATA, 'Google/Chrome/Application/chrome.exe') : null,
  '/usr/bin/google-chrome', '/usr/bin/chromium', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
].filter(Boolean)
const bin = BROWSERS.find((p) => existsSync(p))
if (!bin) {
  console.log('  [info] 没找到 Edge/Chrome，跳过界面验收（可用 POMODMER_BROWSER=<路径> 指定）')
  process.exit(0)
}

const profile = mkdtempSync(join(tmpdir(), 'pom-ui-'))
const portFile = join(profile, 'DevToolsActivePort')
const browser = spawn(bin, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore' })

// 等浏览器把实际端口写进 DevToolsActivePort
let port = null
for (let i = 0; i < 60 && !port; i++) {
  await sleep(200)
  if (existsSync(portFile)) {
    const first = readFileSync(portFile, 'utf8').split('\n')[0].trim()
    if (first) port = first
  }
}
if (!port) {
  console.log('  [FAIL] 浏览器没起来（拿不到 DevTools 端口）')
  browser.kill()
  rmSync(profile, { recursive: true, force: true })
  process.exit(1)
}

// 页面级 WebSocket 直连：不搞 Target/session 那一套，够用且简单。
// 但必须等浏览器**真的能接受目标**：DevToolsActivePort 文件出现得比 HTTP 端点就绪早，
// 早一步调 /json/new 会偶发失败（实测过一次：整轮验收因此以未捕获异常收场、退出码 1 而没有任何断言）。
const hasBrowserEndpoint = async () => {
  try {
    const r = await fetch(`http://127.0.0.1:${port}/json/version`)
    return r.ok
  } catch {
    return false
  }
}
let endpointReady = false
for (let i = 0; i < 50 && !endpointReady; i++) {
  endpointReady = await hasBrowserEndpoint()
  if (!endpointReady) await sleep(200)
}
if (!endpointReady) {
  console.log('  [FAIL] 浏览器 DevTools 端点未就绪')
  browser.kill()
  for (let i = 0; i < 3; i++) { try { rmSync(profile, { recursive: true, force: true }); break } catch { await sleep(400) } }
  process.exit(1)
}

const newPage = async (url) => {
  let lastErr = null
  for (let i = 0; i < 15; i++) {
    for (const method of ['PUT', 'GET']) {
      try {
        const r = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, { method })
        if (r.ok) return await r.json()
        lastErr = new Error(`${method} /json/new -> HTTP ${r.status}`)
      } catch (e) {
        lastErr = e
      }
    }
    await sleep(300)
  }
  throw new Error('无法创建页面标签：' + (lastErr ? lastErr.message : '未知原因'))
}

const ctx = await bootHost({})
const appUrl = ctx.http.url
console.log(`=== 界面验收（真实浏览器：${bin.split('\\').pop()}）===`)
console.log(`  应用地址 ${appUrl}`)

const target = await newPage(appUrl)
const ws = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej })

// 兜底：任何未捕获异常都要**算作失败**（而不是打一行字然后照旧 ALL PASS）。
// 这里只标记，不抢着 exit：让主流程跑完自己的清理与汇总，避免"异常与正常收尾赛跑"
// 导致明明出了问题、退出码却是 0。
let bailed = false
const bail = (e) => {
  if (bailed) return
  bailed = true
  failed++
  console.log('  [FAIL] 界面验收过程异常 ->', e && (e.stack || e.message || e))
}
process.on('uncaughtException', bail)
process.on('unhandledRejection', bail)

let msgId = 0
const waiting = new Map()
const consoleErrors = []
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data)
  if (m.id && waiting.has(m.id)) {
    const { resolve } = waiting.get(m.id)
    waiting.delete(m.id)
    resolve(m)
  }
  if (m.method === 'Runtime.exceptionThrown') {
    consoleErrors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text)
  }
  if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
    consoleErrors.push(m.params.args.map((a) => a.value).join(' '))
  }
}
const send = (method, params = {}) => new Promise((resolve) => {
  const id = ++msgId
  waiting.set(id, { resolve })
  ws.send(JSON.stringify({ id, method, params }))
})
// 在页面里求值：awaitPromise 让 async 表达式也能直接用
const evaluate = async (expr) => {
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })
  if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || '页面求值异常')
  return r.result?.result?.value
}

await send('Runtime.enable')
await send('Page.enable')
await sleep(1200) // 等首屏渲染 + SSE 连接

// 1) 首屏
ok(await evaluate(`!!document.querySelector('#btnToggle') && !!document.querySelector('#time')`), '页面加载出关键元素（计时区 + 控制按钮）')
const title = await evaluate('document.title')
ok(/pomodmer/i.test(title), '页面标题正确', title)
const t0 = await evaluate(`document.querySelector('#time').textContent`)
ok(/^\d{1,3}:\d{2}$/.test(t0), '倒计时已渲染（形如 25:00）', t0)

// 2) 按钮真的能点：开始 -> 文案变暂停、倒计时开始走
await evaluate(`document.querySelector('#btnToggle').click()`)
await sleep(2200)
const label = await evaluate(`document.querySelector('#btnToggle').textContent`)
ok(/暂停|继续/.test(label), '点「开始」后按钮文案变化（说明点击事件绑定生效）', label)
const t1 = await evaluate(`document.querySelector('#time').textContent`)
const t2 = await (async () => { await sleep(1500); return evaluate(`document.querySelector('#time').textContent`) })()
ok(t1 !== t2, '倒计时在走（SSE tick 真的推动了界面）', `${t1} -> ${t2}`)

// 3) 服务端能力探测与按钮状态一致（装了 Python 的机器上导出按钮应可用）
const avail = await evaluate(`fetch('/api/report').then(r=>r.json()).then(d=>d.available)`)
const xlsxDisabled = await evaluate(`document.querySelector('#btnExportXlsx').disabled`)
ok(avail === true ? xlsxDisabled === false : xlsxDisabled === true,
  'xlsx 按钮可用性与服务端能力探测一致', `available=${avail} disabled=${xlsxDisabled}`)
const note = await evaluate(`document.querySelector('#reportNote').textContent.trim()`)
ok(avail === true ? note === '' : note.length > 0, '能力说明文案与探测结果一致', note || '(空)')

// 4) 任务清单：输入 + 点添加 -> 列表出现该项（走真实 API）
const taskName = '界面验收-' + Date.now()
await evaluate(`(() => { const i = document.querySelector('#taskTitle'); i.value = ${JSON.stringify(taskName)}; return i.value })()`)
await evaluate(`document.querySelector('#btnAddTask').click()`)
await sleep(900)
const hasTask = await evaluate(`document.querySelector('#taskList').textContent.includes(${JSON.stringify(taskName)})`)
ok(hasTask, '输入任务名点「添加」后列表出现该项（表单链路通）')

// 5) 回灌预览：用 CDP 直接给 file input 塞文件（等价于用户选文件）
const xlsx = join(profile, 'ui-fixture.xlsx')
writeFileSync(xlsx, Buffer.from(await (await fetch(appUrl.replace(/\/$/, '') + '/api/export?format=xlsx')).arrayBuffer()))
if (avail === true) {
  const doc = await send('DOM.getDocument', { depth: -1 })
  const node = await send('DOM.querySelector', { nodeId: doc.result.root.nodeId, selector: '#fileImportXlsx' })
  await send('DOM.setFileInputFiles', { nodeId: node.result.nodeId, files: [xlsx] })
  await sleep(1800)
  const hint = await evaluate(`document.querySelector('#ioHint').textContent`)
  const applyVisible = await evaluate(`!document.querySelector('#btnApplyXlsx').hidden`)
  ok(/预览/.test(hint) && applyVisible, '塞入 xlsx 后前端走完预览并显示「确认导入」', hint)
  await evaluate(`document.querySelector('#btnApplyXlsx').click()`)
  await sleep(2000)
  const done = await evaluate(`document.querySelector('#ioHint').textContent`)
  ok(/导入完成|全部跳过|导入/.test(done), '点「确认导入」后拿到结果回显', done)
} else {
  console.log('  [info] 本机没启用表格能力，跳过回灌的界面验收')
}

// 6) 月报与自定义区间按钮（P6 新增入口）
await evaluate(`document.querySelector('#btnMonth').click()`)
await sleep(2500)
const monHint = await evaluate(`document.querySelector('#ioHint').textContent`)
ok(/已导出 pomodmer-month-/.test(monHint), '点「导出月报 xlsx」→ 完成并回显文件名', monHint)

// 区间为空时先自动填好最近 7 天（确认后再点一次才导出）—— 避免"点了没反应"的困惑
await evaluate(`document.querySelector('#btnRange').click()`)
await sleep(400)
const filled = await evaluate(`document.querySelector('#rangeFrom').value + '~' + document.querySelector('#rangeTo').value`)
ok(/^\d{4}-\d{2}-\d{2}~\d{4}-\d{2}-\d{2}$/.test(filled), '区间为空时自动填好最近 7 天', filled)
await evaluate(`document.querySelector('#btnRange').click()`)
await sleep(2500)
const rangeHint = await evaluate(`document.querySelector('#ioHint').textContent`)
ok(/已导出 pomodmer-range-/.test(rangeHint), '再点一次 → 区间报表完成并回显', rangeHint)

// 7) 全程没有前端 JS 报错
ok(consoleErrors.length === 0, '页面无 JS 异常/console.error', consoleErrors.slice(0, 2).join(' | '))

await stopHost()
ws.close()
if (!process.argv.includes('--keep')) {
  // 关浏览器要等它真的退出：立刻删 profile 会撞上 Crashpad 还占着的文件（EBUSY），
  // 而且"清理失败"绝不该让一次全绿的验收变成退出码 1。
  const exited = new Promise((r) => {
    browser.once('exit', r)
    setTimeout(r, 3000)
  })
  browser.kill()
  await exited
  for (let i = 0; i < 3; i++) {
    try { rmSync(profile, { recursive: true, force: true }); break } catch { await sleep(500) }
  }
} else {
  console.log('  [info] --keep：浏览器与临时 profile 保留在 ' + profile)
}
console.log('\n=== 结果 ===')
console.log(failed === 0 ? '  ALL PASS' : '  FAILED: ' + failed + ' 项')
process.exit(failed === 0 ? 0 : 1)
