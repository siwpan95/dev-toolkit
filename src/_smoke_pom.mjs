// _smoke_pom.mjs —— 番茄钟端到端冒烟（走真实 HTTP，不 mock）
// 覆盖：启动 -> 状态 -> 设置 -> 开始/暂停冻结/继续 -> 到点自动流转 -> 跳过/作废 -> 任务 CRUD
//       -> 会话落库 -> 静态资源与穿越防护 -> SSE -> 重启恢复（进程被杀不静默补时）
// 数据落 os.tmpdir()，端口由系统分配（port: 0），不污染真实 data/store.json、不抢端口。
import { bootHost, stopHost, resolveConfigPath } from './boot.mjs'
import { probeTableWorker } from './plugins/table.mjs'
import { spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, writeFileSync, existsSync, copyFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import http from 'node:http'

let failed = 0
const ok = (cond, msg, extra = '') => {
  if (cond) console.log('  [ok] ' + msg)
  else { failed++; console.log('  [FAIL] ' + msg + (extra ? ' -> ' + extra : '')) }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function get(url) {
  return new Promise((res, rej) => {
    http.get(url, (r) => {
      let body = ''
      r.on('data', (c) => { body += c })
      r.on('end', () => res({ status: r.statusCode, body, headers: r.headers }))
    }).on('error', rej)
  })
}

function req(url, method, payload) {
  return new Promise((res, rej) => {
    const u = new URL(url)
    const data = payload === undefined ? null : JSON.stringify(payload)
    const r = http.request({
      // 必须带上 query：只发 pathname 会把 ?format=xlsx 这类参数悄悄丢掉，
      // 于是"断言 501"的用例实际打到了另一条路由上（假红/假绿都可能）。
      hostname: u.hostname, port: u.port, path: u.pathname + u.search, method,
      headers: data ? { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) } : {},
    }, (resp) => {
      let body = ''
      resp.on('data', (c) => { body += c })
      resp.on('end', () => res({ status: resp.statusCode, body }))
    })
    r.on('error', rej)
    if (data) r.write(data)
    r.end()
  })
}

// 二进制下载：按 Buffer 收（不能像 req 那样当字符串拼，否则 xlsx 会被 UTF-8 解码毁掉），
// 落盘后再交给 openpyxl 读回来验证内容。
function download(url, destPath) {
  return new Promise((res, rej) => {
    const u = new URL(url)
    http.get({ hostname: u.hostname, port: u.port, path: u.pathname + u.search }, (resp) => {
      const chunks = []
      resp.on('data', (c) => chunks.push(c))
      resp.on('end', () => {
        const buf = Buffer.concat(chunks)
        writeFileSync(destPath, buf)
        res({ status: resp.statusCode, headers: resp.headers, bytes: buf.length })
      })
    }).on('error', rej)
  })
}

// 二进制上传（xlsx 回灌）：把文件原样作为请求体发出去，服务端按原始字节收。
function postBinary(url, filePath) {
  const buf = readFileSync(filePath)
  const u = new URL(url)
  return new Promise((res, rej) => {
    const r = http.request({
      hostname: u.hostname, port: u.port, path: u.pathname + u.search, method: 'POST',
      headers: { 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Content-Length': buf.length },
    }, (resp) => {
      let body = ''
      resp.on('data', (c) => { body += c })
      resp.on('end', () => res({ status: resp.statusCode, body }))
    })
    r.on('error', rej)
    r.write(buf)
    r.end()
  })
}
const postBinaryRaw = (url, buf) => {
  const u = new URL(url)
  return new Promise((res, rej) => {
    const r = http.request({
      hostname: u.hostname, port: u.port, path: u.pathname + u.search, method: 'POST',
      headers: { 'Content-Type': 'application/octet-stream', 'Content-Length': buf.length },
    }, (resp) => {
      let body = ''
      resp.on('data', (c) => { body += c })
      resp.on('end', () => res({ status: resp.statusCode, body }))
    })
    r.on('error', rej)
    r.write(buf)
    r.end()
  })
}

const json = async (p) => { const r = await p; return { status: r.status, data: r.body ? JSON.parse(r.body) : null, raw: r.body } }

async function waitFor(url, pred, timeoutMs = 15000, step = 200) {
  const t0 = Date.now()
  let last = null
  while (Date.now() - t0 < timeoutMs) {
    const { data } = await json(get(url))
    last = data.runtime
    if (pred(data)) return data
    await sleep(step)
  }
  return last ? { runtime: last, __timeout: true } : null
}

async function main() {
  const dir = mkdtempSync(join(tmpdir(), 'pomodmer-smoke-'))
  const storeFile = join(dir, 'store.json').replace(/\\/g, '/')
  const cfgFile = join(dir, 'cordis.smoke.json')
  writeFileSync(cfgFile, JSON.stringify({
    entries: [
      { id: 'store', name: './src/plugins/store.mjs', config: { file: storeFile } },
      { id: 'timer', name: './src/plugins/timer.mjs' },
      { id: 'http', name: './src/plugins/http.mjs', config: { host: '127.0.0.1', port: 0, open: false } },
    ],
  }, null, 2))

  console.log('\n=== 1. 启动宿主 ===')
  const ctx = await bootHost({ config: cfgFile })
  const base = ctx.http.url.replace(/\/$/, '')
  ok(!!ctx.store && !!ctx.timer && !!ctx.http, '三个服务插件均挂载 ctx.store / ctx.timer / ctx.http')
  ok(/^http:\/\/127\.0\.0\.1:\d+$/.test(base), '服务仅监听 127.0.0.1 -> ' + base)

  console.log('\n=== 2. 初始状态 ===')
  let s = (await json(get(base + '/api/state'))).data
  ok(s.runtime.phase === 'idle', '初始 phase=idle', s.runtime.phase)
  ok(s.runtime.remainingMs === 25 * 60 * 1000, '初始剩余 = 25 分钟', String(s.runtime.remainingMs))
  ok(s.settings.longEvery === 4, '默认每 4 个番茄长休', String(s.settings.longEvery))

  console.log('\n=== 3. 设置生效（缩短以便实测到点流转）===')
  s = (await json(req(base + '/api/settings', 'PATCH', {
    focusMs: 3000, shortMs: 2000, longMs: 2000, longEvery: 2, autoStartBreak: false, autoStartFocus: false,
  }))).data
  ok(s.settings.focusMs === 3000, 'focusMs 改为 3s', String(s.settings.focusMs))
  ok(s.runtime.remainingMs === 3000, 'idle 状态剩余跟随新设置', String(s.runtime.remainingMs))
  const bad = await json(req(base + '/api/settings', 'PATCH', { focusMs: 10 }))
  ok(bad.data.settings.focusMs === 3000, '非法值(<1s)被拒绝，设置不变', String(bad.data.settings.focusMs))

  console.log('\n=== 4. 开始 / 暂停冻结 / 继续 ===')
  s = (await json(req(base + '/api/timer/start', 'POST'))).data
  ok(s.phase === 'focus' && s.running === true, 'start -> focus 且 running', s.phase + '/' + s.running)
  await sleep(1200)
  s = (await json(get(base + '/api/state'))).data.runtime
  const r1 = s.remainingMs
  ok(r1 < 2000 && r1 > 500, '运行中剩余随时间递减（~1.8s）', String(r1))
  const paused = (await json(req(base + '/api/timer/pause', 'POST'))).data
  ok(paused.running === false, 'pause -> running=false')
  await sleep(1000)
  const after = (await json(get(base + '/api/state'))).data.runtime
  ok(Math.abs(after.remainingMs - paused.remainingMs) < 50, '暂停后 1s 剩余时间**冻结**（服务端权威，不靠前端计数）',
    paused.remainingMs + ' -> ' + after.remainingMs)
  const resumed = (await json(req(base + '/api/timer/resume', 'POST'))).data
  ok(resumed.running === true && resumed.remainingMs <= paused.remainingMs, 'resume -> 继续倒计时', String(resumed.remainingMs))

  console.log('\n=== 5. 到点自动流转 focus -> short（长休阈值 longEvery=2）===')
  let st = await waitFor(base + '/api/state', (d) => d.runtime.phase === 'short', 12000)
  ok(st && !st.__timeout && st.runtime.phase === 'short', '第一个番茄结束自动进入短休息', st && st.runtime.phase)
  ok(st && st.runtime.round === 1, 'round 计为 1', st && String(st.runtime.round))
  let sess = (await json(get(base + '/api/sessions'))).data.sessions
  ok(sess.length === 1 && sess[0].type === 'focus' && sess[0].completed === true, '落库 1 条已完成 focus 会话', JSON.stringify(sess[0] || {}))

  console.log('\n=== 6. 跳过 / 作废 ===')
  const skipped = (await json(req(base + '/api/timer/skip', 'POST'))).data
  ok(skipped.phase === 'focus', '短休息 skip -> 回到 focus（不计番茄）', skipped.phase)
  const beforeVoid = (await json(get(base + '/api/state'))).data
  const voided = (await json(req(base + '/api/timer/void', 'POST', { reason: 'void' }))).data
  ok(voided.phase === 'focus' && voided.running === false, '作废 -> 当前番茄归零并停在 focus', voided.phase)
  ok(voided.round === beforeVoid.runtime.round, '作废不改变已完成的 round', String(voided.round))
  sess = (await json(get(base + '/api/sessions'))).data.sessions
  ok(sess.some((x) => x.reason === 'void' && x.completed === false), '落库 1 条作废会话（completed=false）')

  console.log('\n=== 6b. 长休息触发（longEvery=2，第 2 个番茄后进入 long）===')
  await json(req(base + '/api/timer/start', 'POST'))
  const lb = await waitFor(base + '/api/state', (d) => d.runtime.phase === 'long', 12000)
  ok(lb && !lb.__timeout && lb.runtime.phase === 'long', '第 2 个番茄结束 -> 长休息', lb && lb.runtime.phase)
  ok(lb && lb.runtime.round === 2, 'round 计为 2', lb && String(lb.runtime.round))
  await json(req(base + '/api/timer/reset', 'POST'))

  console.log('\n=== 7. 任务 CRUD ===')
  const t1 = (await json(req(base + '/api/tasks', 'POST', { title: '冒烟任务', estimate: 2 }))).data.task
  ok(!!t1 && t1.title === '冒烟任务', '新增任务成功', JSON.stringify(t1))
  const del = await json(req(base + '/api/tasks/' + t1.id, 'DELETE'))
  ok(del.status === 200, '删除任务成功')
  ok((await json(req(base + '/api/tasks/' + t1.id, 'DELETE'))).status === 404, '删除不存在的任务 -> 404')

  console.log('\n=== 8. 静态资源与路径穿越防护 ===')
  const idx = await get(base + '/')
  ok(idx.status === 200 && idx.body.includes('Pomodmer'), 'GET / 返回 index.html')
  const appjs = await get(base + '/app.js')
  ok(appjs.status === 200 && appjs.headers['content-type'].includes('javascript'), 'GET /app.js 返回 JS 且 MIME 正确')
  const trav = await get(base + '/%2e%2e%2fpackage.json')
  ok(trav.status === 403, '路径穿越被拒绝 -> 403', String(trav.status))
  const nope = await json(get(base + '/api/nope'))
  ok(nope.status === 404, '未知 API -> 404', String(nope.status))
  // 表格能力不在场时（本清单不含 table/report），探测接口必须说清"为什么没有"：
  // 只回一个环境变量名是不够的 —— 现在自动探测才是默认路径，用户需要知道是没装、还是被关。
  const rep0 = await json(req(base + '/api/report', 'GET'))
  ok(rep0.status === 200 && rep0.data.available === false, '未挂报表插件时 /api/report 探测为不可用')
  ok(typeof rep0.data.hint === 'string' && rep0.data.hint.length > 0, '探测接口给出可读原因', rep0.data.hint)
  // 全量 xlsx 导出走同一条能力开关：能力不在场时必须 501 + 同一份可读原因，而不是 500 或空响应
  const xlsx0 = await json(req(base + '/api/export?format=xlsx', 'GET'))
  ok(xlsx0.status === 501 && typeof xlsx0.data.error === 'string' && xlsx0.data.error.length > 0,
    '未挂报表插件时 /api/export?format=xlsx -> 501 + 可读原因', xlsx0.status + ' ' + (xlsx0.data.error || ''))
  // JSON 导出不受影响（备用备份路径必须始终可用）
  const json0 = await json(req(base + '/api/export', 'GET'))
  ok(json0.status === 200 && json0.data.app === 'pomodmer', 'JSON 导出在全量 xlsx 加入后仍正常')

  console.log('\n=== 9. SSE 推送 ===')
  // tick 只在"正在计时"时推送（暂停时状态静止，本就不该有 tick）——先让番茄跑起来
  await json(req(base + '/api/timer/start', 'POST'))
  const sse = await new Promise((res) => {
    const r = http.get(base + '/api/events', (resp) => {
      let buf = ''
      resp.on('data', (c) => { buf += c.toString() })
      resp.on('end', () => res(buf))
      resp.on('close', () => res(buf))
      setTimeout(() => { resp.destroy() }, 3500)
    })
    r.on('error', () => res(''))
  })
  ok(sse.includes('event: hello'), 'SSE 连接即下发 hello 快照')
  ok(sse.includes('event: tick'), 'SSE 每秒推送 tick（前端只渲染不计时）')
  ok(sse.includes('data: {'), 'SSE data 为 JSON')
  const pausedSse = await new Promise((res) => {
    req(base + '/api/timer/pause', 'POST').then(() => {
      const r = http.get(base + '/api/events', (resp) => {
        let buf = ''
        resp.on('data', (c) => { buf += c.toString() })
        resp.on('close', () => res(buf))
        setTimeout(() => { resp.destroy() }, 2500)
      })
      r.on('error', () => res(''))
    })
  })
  ok(!pausedSse.includes('event: tick'), '暂停期间不再推送 tick（状态静止，无事件可推）')

  console.log('\n=== 9b. P1：任务归属（番茄记到当前任务头上）===')
  const tk = (await json(req(base + '/api/tasks', 'POST', { title: '写 P1 代码', estimate: 3 }))).data.task
  await json(req(base + '/api/tasks/current', 'PATCH', { taskId: tk.id }))
  const stCur = (await json(get(base + '/api/state'))).data
  ok(stCur.runtime.currentTaskId === tk.id, '设置当前任务生效', String(stCur.runtime.currentTaskId))
  await json(req(base + '/api/timer/start', 'POST'))
  await waitFor(base + '/api/state', (d) => d.runtime.phase !== 'focus', 12000)
  const tkAfter = (await json(get(base + '/api/state'))).data.tasks.find((t) => t.id === tk.id)
  ok(tkAfter && tkAfter.spent === 1, '番茄完成后任务 spent 自增 1（实际/预估 1/3）', tkAfter && String(tkAfter.spent))

  console.log('\n=== 9c. P1：中断记录（计划外事件）===')
  const it1 = (await json(req(base + '/api/unplanned', 'POST', { kind: 'external', note: '同事敲门' }))).data.item
  ok(it1.kind === 'external' && it1.note === '同事敲门', '记录外部中断', JSON.stringify(it1))
  const it2 = (await json(req(base + '/api/unplanned', 'POST', { kind: 'weird', note: '' }))).data.item
  ok(it2.kind === 'internal', '非法 kind 归一化为 internal', it2.kind)
  const ul = (await json(get(base + '/api/unplanned'))).data.unplanned
  ok(ul.length === 2 && ul[0].id === it2.id, '列表按时间倒序返回 2 条', String(ul.length))
  ok((await json(req(base + '/api/unplanned/' + it1.id, 'DELETE'))).status === 200, '删除中断记录成功')
  ok((await json(req(base + '/api/unplanned/' + it1.id, 'DELETE'))).status === 404, '重复删除 -> 404')

  console.log('\n=== 9d. P1：统计（今日/连续天数/最近 7 天/热力图/每任务）===')
  const stt = (await json(get(base + '/api/stats?days=7&weeks=12'))).data
  ok(Array.isArray(stt.recent) && stt.recent.length === 7, 'recent = 最近 7 天（补齐空天）', String(stt.recent && stt.recent.length))
  ok(Array.isArray(stt.heat) && stt.heat.length === 84, 'heat = 12 周 × 7 天 = 84 格', String(stt.heat && stt.heat.length))
  ok(typeof stt.streak === 'number', 'streak 为数字', String(stt.streak))
  ok(Array.isArray(stt.byTask) && stt.byTask.some((t) => t.id === tk.id && t.spent === 1), 'byTask 含该任务且 spent=1')
  ok(stt.today && typeof stt.today.completed === 'number', 'today 统计存在')

  console.log('\n=== 9e. P1：导出 / 导入 ===')
  const dayMs = 86400000
  const mkSession = (offsetDays) => ({
    id: 'x' + offsetDays, type: 'focus', taskId: null, plannedMs: 1500000,
    startAt: Date.now() - offsetDays * dayMs, endAt: Date.now() - offsetDays * dayMs + 1500000,
    actualMs: 1500000, completed: true, interrupts: 0, reason: null,
  })
  const imp = await json(req(base + '/api/import', 'POST', {
    data: {
      settings: { focusMs: 3000, shortMs: 2000, longMs: 2000, longEvery: 2 },
      tasks: [], sessions: [mkSession(1), mkSession(2)], unplanned: [],
    },
  }))
  ok(imp.status === 200, '导入成功')
  ok(imp.data.runtime.running === false, '导入后一律停在暂停态（不静默续跑）')
  const stt2 = (await json(get(base + '/api/stats?days=7&weeks=12'))).data
  ok(stt2.streak >= 2, '连续天数由导入数据推导 >= 2', String(stt2.streak))
  ok(stt2.total.completed === 2, '总完成数 = 导入的 2 个番茄', String(stt2.total.completed))
  const exp = await get(base + '/api/export')
  let expJson = null
  try { expJson = JSON.parse(exp.body) } catch { /* ignore */ }
  ok(exp.status === 200 && expJson && expJson.app === 'pomodmer', '导出返回可解析 JSON')
  ok(expJson && expJson.sessions.length === 2, '导出内容含 2 条会话', expJson && String(expJson.sessions.length))
  ok((exp.headers['content-disposition'] || '').includes('attachment'), '导出带 attachment 头')
  const badImp = await json(req(base + '/api/import', 'POST', { data: { sessions: 'not-an-array' } }))
  ok(badImp.status === 400, '非法导入 -> 400', String(badImp.status))

  console.log('\n=== 9f. P1：主题 ===')
  const th1 = (await json(req(base + '/api/settings', 'PATCH', { theme: 'dark' }))).data
  ok(th1.settings.theme === 'dark', '主题切到 dark', th1.settings.theme)
  const th2 = (await json(req(base + '/api/settings', 'PATCH', { theme: 'neon' }))).data
  ok(th2.settings.theme === 'light', '非法主题归一化为 light', th2.settings.theme)

  console.log('\n=== 10. 落盘与重启恢复（被杀进程不静默补时）===')
  // 让一个番茄处于 running 状态，然后"硬杀"宿主（模拟断电/强杀），检查落盘数据
  // 注意：上一步刚导入过数据，runtime 已被重置为 idle，所以这里用 start 而不是 resume
  await json(req(base + '/api/timer/start', 'POST'))
  await sleep(600)
  const diskBefore = JSON.parse(readFileSync(storeFile, 'utf8'))
  ok(diskBefore.runtime.running === true, '运行态已实时落盘（running=true）')
  await stopHost()
  ok(existsSync(storeFile), '数据文件存在: ' + storeFile)

  // 重启：上次在跑的番茄应被冻结为暂停态，而不是"补时"到已完成
  const ctx2 = await bootHost({ config: cfgFile })
  const s2 = (await json(get(ctx2.http.url.replace(/\/$/, '') + '/api/state'))).data
  ok(s2.runtime.running === false, '重启后不自动续跑（冻结为暂停）', String(s2.runtime.running))
  const sess2 = (await json(get(ctx2.http.url.replace(/\/$/, '') + '/api/sessions'))).data.sessions
  ok(!sess2.some((x) => x.reason === 'shutdown' && x.completed === true),
    '退出期间到点的番茄不会"静默补时"成已完成', JSON.stringify(sess2.slice(-1)))
  await stopHost()

  console.log('\n=== 11. P2：周报 xlsx（启用可选插件，复用 Python OpenPyXL）===')
  const cfg2 = join(dir, 'cordis.xlsx.json')
  writeFileSync(cfg2, JSON.stringify({
    entries: [
      { id: 'store', name: './src/plugins/store.mjs', config: { file: storeFile } },
      { id: 'timer', name: './src/plugins/timer.mjs' },
      { id: 'http', name: './src/plugins/http.mjs', config: { host: '127.0.0.1', port: 0, open: false } },
      { id: 'table', name: './src/plugins/table.mjs', config: { timeoutMs: 7000 } },
      { id: 'report', name: './src/plugins/report.mjs', config: { outDir: dir.replace(/\\/g, '/') } },
    ],
  }, null, 2))
  const ctx3 = await bootHost({ config: cfg2 })
  const base3 = ctx3.http.url.replace(/\/$/, '')
  ok(!!ctx3.report && !!ctx3.table, 'with-xlsx 清单下 ctx.table / ctx.report 均就绪')
  const rep = await json(req(base3 + '/api/report', 'POST', { days: 7 }))
  ok(rep.status === 200, '周报生成成功', rep.data && rep.data.error)
  ok(rep.data && existsSync(rep.data.file), 'xlsx 落盘：' + (rep.data && rep.data.file))
  ok(rep.data && rep.data.sheets && rep.data.sheets.length === 4,
    '四张表：概览/每日/会话/任务', rep.data && String(rep.data.sheets))
  // 11k 跨时区验收要用这份导出产物；它在下面的 if 块里产生，所以先在这里占位
  let dlPathForTz = null
  // 回读依赖上一步真的产出了文件：失败时不能让 TypeError 把整个 smoke 掀翻，
  // 否则报错停在 "Cannot read properties of undefined"，真正的病因（生成失败的原因）反而被埋掉。
  if (rep.data && existsSync(rep.data.file)) {
    const backDay = await ctx3.table.readSheet(rep.data.file, '每日')
    ok(backDay.max_row === 8, '「每日」= 表头 + 7 天', String(backDay.max_row))
    const backSum = await ctx3.table.readSheet(rep.data.file, '概览')
    ok(backSum.max_row === 10, '「概览」= 表头 + 9 项指标', String(backSum.max_row))

    console.log('\n=== 11b. xlsx 数据形态：真实日期 / 数字格式 / 冻结表头 / 坏单元格不再弄死 worker ===')
    // 日期必须是 Excel 原生 datetime，而不是文本 —— 否则 Excel 里没法排序/筛选/做日期计算。
    const metaDay = await ctx3.table.sheetMeta(rep.data.file, '每日')
    // 内存里是 date，落盘后 openpyxl 重新加载会变成 datetime（Excel 里都是"真日期"）—— 两者都算过
    ok(['date', 'datetime'].includes(metaDay.value_types[0]),
      '「每日」日期列是原生日期类型（不是文本）', metaDay.value_types.join(','))
    ok(metaDay.number_formats[0] === 'yyyy-mm-dd', '「每日」日期列带日期格式', metaDay.number_formats[0])
    ok(metaDay.freeze_panes === 'A2', '「每日」表头已冻结', String(metaDay.freeze_panes))

    const metaSess = await ctx3.table.sheetMeta(rep.data.file, '会话')
    ok(metaSess.freeze_panes === 'A2', '「会话」表头已冻结', String(metaSess.freeze_panes))
    ok(metaSess.number_formats[0] === 'yyyy-mm-dd hh:mm', '「会话」时间列带时间格式', metaSess.number_formats[0])
    // 必须查 value_types：文本日期同样能匹配 ISO 正则，只测字符串形态会假绿
    ok(metaSess.value_types[0] === 'datetime' && metaSess.value_types[1] === 'datetime',
      '「会话」开始/结束是原生 datetime（不是文本）', metaSess.value_types.join(','))

    // 读回：datetime 必须以 ISO 串出现（worker 用 _json_default 兜住），且读完后 worker 还活着 ——
    // 这条是回归测试：改动前 read_sheet 撞上日期会让 json.dumps 抛错并带走整个 worker 进程。
    const sessBack = await ctx3.table.readSheet(rep.data.file, '会话')
    const isoLike = (v) => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(v)
    const firstSess = sessBack.rows.find((r) => isoLike(r[0]))
    ok(!!firstSess, '带日期的 xlsx 能读回（ISO 串），不再崩 worker', JSON.stringify(sessBack.rows.slice(0, 2)))
    const alive = await ctx3.table.ping()
    ok(!!alive && !!alive.openpyxl, '读日期后 worker 仍存活（回归：旧版会整进程退出）', JSON.stringify(alive))

    console.log('\n=== 11c. 联合套件新增能力（并集来自 cordis-table-app 的那一半）===')
    // 三件套已统一到权威源：pomodmer 这边顺带获得合并单元格/批注/填充/边框等能力。
    // 只断言"真的生效"，不做存在性检查 —— 方法在不在，下面的调用会直接说话。
    const extra = join(dir, 'pomodmer-kit-extra.xlsx')
    await ctx3.table.createWorkbook(extra, '样式')
    await ctx3.table.writeRows(extra, '样式', 1, 1, [['旧标题', ''], [1, 2]])
    await ctx3.table.mergeCells(extra, '样式', 1, 1, 1, 2)
    await ctx3.table.setCellText(extra, '样式', 1, 1, '合并标题')
    await ctx3.table.setCellFill(extra, '样式', 2, 1, 'FFF2E2C0')
    await ctx3.table.setComment(extra, '样式', 2, 2, '来自 kit 的批注')
    await ctx3.table.setBorders(extra, '样式', 1, 1, 2, 2)
    await ctx3.table.save(extra)
    const metaExtra = await ctx3.table.sheetMeta(extra, '样式')
    ok(metaExtra.merged.includes('A1:B1'), '合并单元格生效', JSON.stringify(metaExtra.merged))
    ok(metaExtra.comments.includes('B2'), '批注生效', JSON.stringify(metaExtra.comments))
    const backExtra = await ctx3.table.readSheet(extra, '样式')
    ok(backExtra.rows[0][0] === '合并标题', '写回合并区标题生效', JSON.stringify(backExtra.rows[0]))

    console.log('\n=== 11d. 全量 xlsx 导出（GET /api/export?format=xlsx，附件下载）===')
    // 先造一条计划外事件：9e 的导入把它清空了，这里要验证"新记录真能被带进表"
    await json(req(base3 + '/api/unplanned', 'POST', { kind: 'external', note: '冒烟-全量导出' }))
    // 走真实 HTTP：既验证响应头，也把字节落盘后**用 openpyxl 读回来**验证内容
    const dlPath = join(dir, 'download.xlsx')
    dlPathForTz = dlPath
    const dl = await download(base3 + '/api/export?format=xlsx', dlPath)
    ok(dl.status === 200, 'GET /api/export?format=xlsx -> 200', String(dl.status))
    ok(/spreadsheetml\.sheet/.test(dl.headers['content-type'] || ''), 'Content-Type 是 xlsx',
      String(dl.headers['content-type']))
    ok(/attachment; filename="pomodmer-all-.*\.xlsx"/.test(dl.headers['content-disposition'] || ''),
      '带附件文件名', String(dl.headers['content-disposition']))
    ok(dl.bytes > 0 && readFileSync(dlPath).subarray(0, 2).toString() === 'PK', '下载到的是真 xlsx（zip 魔数 PK）',
      String(dl.bytes) + ' bytes')

    const dlMeta = await ctx3.table.sheetMeta(dlPath, '计划外事件')
    ok(dlMeta.visible_sheets.length === 5 && dlMeta.visible_sheets.includes('计划外事件'),
      '全量导出含 5 张可见表（比周报多出「计划外事件」）', JSON.stringify(dlMeta.visible_sheets))
    ok(dlMeta.hidden_sheets.includes('_meta') && dlMeta.hidden_sheets.includes('_epochs'),
      '带隐藏元数据表（_meta 时区偏移 / _epochs 逐行绝对时刻）', JSON.stringify(dlMeta.hidden_sheets))
    ok(dlMeta.freeze_panes === 'A2', '「计划外事件」表头已冻结', String(dlMeta.freeze_panes))
    ok(dlMeta.value_types[0] === 'datetime', '「计划外事件」时间列是原生 datetime', dlMeta.value_types.join(','))
    const dlOverview = await ctx3.table.readSheet(dlPath, '概览')
    ok(dlOverview.rows[1][1] === '全部', '概览标注统计区间=全部（区别于周报的"最近 N 天"）',
      JSON.stringify(dlOverview.rows[1]))
    const dlUnplanned = await ctx3.table.readSheet(dlPath, '计划外事件')
    ok(dlUnplanned.rows.length === 2, '「计划外事件」= 表头 + 1 条记录', JSON.stringify(dlUnplanned.rows))
    ok(dlUnplanned.rows[1][1] === '外部' && String(dlUnplanned.rows[1][2]).includes('全量导出'),
      '事件的类型与备注正确落表', JSON.stringify(dlUnplanned.rows[1]))

    console.log('\n=== 11e. P3：xlsx 回灌（预览 → 落库 → 幂等 → 往返不翻倍）===')
    // 拿上面刚下载的全量导出当模板，像人一样在上面编辑
    const edited = join(dir, 'edited.xlsx')
    copyFileSync(dlPath, edited)
    await ctx3.table.writeRows(edited, '任务', 2, 1, [['冒烟任务A', 4, 0, '否']], { colTypes: ['text', 'number', 'number', 'text'] })
    await ctx3.table.writeRows(edited, '会话', 2, 1,
      [['2026-09-28T10:00:00', '2026-09-28T10:25:00', '专注', 25, '是', 0, '', '冒烟任务A']],
      { colTypes: ['datetime', 'datetime', 'text', 'number', 'text', 'number', 'text', 'text'] })
    await ctx3.table.save(edited)

    const before = await json(get(base3 + '/api/state'))
    const pv = await json(postBinary(base3 + '/api/import/xlsx?mode=preview', edited))
    ok(pv.status === 200 && pv.data.tasks.add >= 1, '预览返回计划（新增任务 >= 1）',
      JSON.stringify(pv.data && { t: pv.data.tasks, s: pv.data.sessions, u: pv.data.unplanned }))
    const afterPv = await json(get(base3 + '/api/state'))
    ok(before.data.tasks.length === afterPv.data.tasks.length, '预览**不改动**数据（只算不写）',
      before.data.tasks.length + ' -> ' + afterPv.data.tasks.length)

    const ap = await json(postBinary(base3 + '/api/import/xlsx?mode=apply', edited))
    ok(ap.status === 200, '落库请求成功', String(ap.status))
    const st2 = await json(get(base3 + '/api/state'))
    const sess2 = await json(get(base3 + '/api/sessions'))
    const 任务A = st2.data.tasks.find((t) => t.title === '冒烟任务A')
    ok(!!任务A && 任务A.estimate === 4, '新任务按表里的预估番茄落库', JSON.stringify(任务A))
    ok(sess2.data.sessions.some((s) => s.taskId === (任务A && 任务A.id)),
      '会话按「任务」列标题关联到该任务（不是留空）')

    // 幂等：同一份表再落一次，必须一条都不新增
    const ap2 = await json(postBinary(base3 + '/api/import/xlsx?mode=apply', edited))
    ok(ap2.data.tasks.add === 0 && ap2.data.sessions.add === 0 && ap2.data.unplanned.add === 0,
      '同一份表重复导入：全部跳过（幂等）', JSON.stringify({ t: ap2.data.tasks, s: ap2.data.sessions, u: ap2.data.unplanned }))

    // 往返不变量：**原样导出的文件再导回，历史不能翻倍**。
    // xlsx 只有秒精度而库里带毫秒，这条专门防"按毫秒精确比对 -> 每次导入把记录翻一倍"。
    const n1 = { t: st2.data.tasks.length, s: sess2.data.sessions.length }
    const roundTrip = await json(postBinary(base3 + '/api/import/xlsx?mode=apply', dlPath))
    const st3 = await json(get(base3 + '/api/state'))
    const sess3 = await json(get(base3 + '/api/sessions'))
    ok(roundTrip.data.tasks.add === 0 && roundTrip.data.sessions.add === 0 && roundTrip.data.unplanned.add === 0,
      '原样回灌：一条都不新增（秒级容差比对）',
      JSON.stringify({ t: roundTrip.data.tasks, s: roundTrip.data.sessions, u: roundTrip.data.unplanned }))
    ok(st3.data.tasks.length === n1.t && sess3.data.sessions.length === n1.s,
      '往返后历史规模不变（没有翻倍）', JSON.stringify(n1) + ' -> ' + JSON.stringify({ t: st3.data.tasks.length, s: sess3.data.sessions.length }))

    // 坏输入要给人话，不是 500
    const notZip = await json(postBinaryRaw(base3 + '/api/import/xlsx', Buffer.from('definitely not a zip')))
    ok(notZip.status === 400 && /xlsx/.test(notZip.data.error || ''), '非 xlsx 文件 -> 400 + 可读原因',
      notZip.status + ' ' + (notZip.data.error || ''))

    console.log('\n=== 11f. 导出面做齐：周报也能直接下载（scope/days）===')
    const wkPath = join(dir, 'weekly-dl.xlsx')
    const wk = await download(base3 + '/api/export?format=xlsx&scope=weekly&days=7', wkPath)
    ok(wk.status === 200 && /filename="pomodmer-weekly-/.test(wk.headers['content-disposition'] || ''),
      'scope=weekly 下载的是周报文件（文件名带 weekly）', String(wk.headers['content-disposition']))
    const wkInfo = JSON.parse(wk.headers['x-pomodmer-info'] || 'null')
    ok(wkInfo && wkInfo.scope === 'weekly' && wkInfo.sheets === 4,
      '响应头带回摘要（scope=weekly / 4 张表）', JSON.stringify(wkInfo))
    const wkMeta = await ctx3.table.sheetMeta(wkPath, '概览')
    ok(wkMeta.visible_sheets.length === 4 && !wkMeta.visible_sheets.includes('计划外事件'),
      '周报仍 4 张可见表（与全量的 5 张区分开）', JSON.stringify(wkMeta.visible_sheets))
    const wkOverview = await ctx3.table.readSheet(wkPath, '概览')
    ok(wkOverview.rows[1][1] === '最近 7 天', '概览统计区间跟随 days=7', JSON.stringify(wkOverview.rows[1]))

    const d1Path = join(dir, 'weekly-1d.xlsx')
    await download(base3 + '/api/export?format=xlsx&scope=weekly&days=1', d1Path)
    const d1 = await ctx3.table.readSheet(d1Path, '每日')
    ok(d1.max_row === 2, 'days=1 -> 「每日」只有表头 + 1 天', String(d1.max_row))

    // 不认识的 scope 必须报错，而不是默默给全量（否则"以为导了周报"很难发现）
    const badScope = await json(req(base3 + '/api/export?format=xlsx&scope=nope', 'GET'))
    ok(badScope.status === 400 && /scope/.test(badScope.data.error || ''), '未知 scope -> 400 + 可读原因',
      badScope.status + ' ' + (badScope.data.error || ''))
    // POST /api/report 保持向后兼容（脚本/定时任务用它拿磁盘路径）
    const legacy = await json(req(base3 + '/api/report', 'POST', { days: 7 }))
    ok(legacy.status === 200 && typeof legacy.data.file === 'string',
      'POST /api/report 仍返回磁盘路径（老用法不破）', legacy.status + ' ' + (legacy.data.file || ''))

    console.log('\n=== 11g. P5：worker 出问题时宿主不陪葬（超时配置 + 崩溃自愈）===')
    // 超时值取 7000 而不是压到 1 秒：这里验的是"配置有没有传到桥上"，不是"超时能不能触发"
    // （超时/宽限的机制由权威源 _smoke_bridge.mjs 用假 worker 确定性地验）。
    // 压到 1 秒的话，机器繁忙时冷启动就可能超过预算 —— 那是测试太苛刻，不是被测代码有问题。
    ok(ctx3.table.bridge.timeoutMs === 7000, '插件 config.timeoutMs 传到桥上',
      String(ctx3.table.bridge.timeoutMs))
    ok(ctx3.table.bridge.coldStartGraceMs > 0, '冷启动宽限生效（新 worker 第一笔调用不算进超时预算）',
      String(ctx3.table.bridge.coldStartGraceMs))
    // b) worker 崩溃后：桥不留死管道引用，下一次调用自动拉起新进程
    const pidBefore = ctx3.table.pid
    ctx3.table.bridge.child.kill('SIGKILL')
    await sleep(400)
    ok(ctx3.table.bridge.child === null, 'worker 崩溃后桥置为"未启动"（不会往死管道里写干等超时）',
      String(ctx3.table.bridge.child))
    const alive2 = await ctx3.table.ping()
    const pidAfter = ctx3.table.pid
    ok(!!alive2 && !!alive2.openpyxl, '崩溃后 ping 自动成功（新 worker 已拉起）', JSON.stringify(alive2))
    ok(pidAfter && pidAfter !== pidBefore, 'pid 确实换了新进程', pidBefore + ' -> ' + pidAfter)
    // c) 恢复后整条导出链路仍然可用（不是"能 ping 但导不出来"）
    const rep2 = await ctx3.report.weekly({ days: 3 })
    ok(existsSync(rep2.file), '崩溃自愈后周报仍能生成', rep2.file)

    console.log('\n=== 11h. SSE 客户端断开后下载路由不能被带崩（回归：ERR_HTTP_HEADERS_SENT）===')
    // 复现路径：导出路由是"先 writeHead 再广播"，而广播遇上已断开的 SSE 客户端就会抛；
    // 异常冒到顶层 catch 时响应头已经发出去了，旧代码在那里抛 ERR_HTTP_HEADERS_SENT，
    // 把一次正常的下载变成一次 500（而且用户完全看不出所以然）。
    const dead = http.get(base3 + '/api/events', () => {})
    dead.on('error', () => {})
    await sleep(300)
    dead.destroy()
    await sleep(200)
    const dl2Path = join(dir, 'after-sse-dead.xlsx')
    const dl2 = await download(base3 + '/api/export?format=xlsx', dl2Path)
    ok(dl2.status === 200 && readFileSync(dl2Path).subarray(0, 2).toString() === 'PK',
      'SSE 客户端断开后仍能正常下载 xlsx（旧代码：500 / headers-sent）', String(dl2.status))
    ok((await json(get(base3 + '/api/state'))).status === 200, '宿主仍正常服务（异常没有扩散）')

    console.log('\n=== 11i. P6：月报（含本月 vs 上月对比表）===')
    const mon = await ctx3.report.month()
    const monMeta = await ctx3.table.sheetMeta(mon.file)
    ok(monMeta.visible_sheets.length === 6 && monMeta.visible_sheets.includes('对比'),
      '月报可见表 = 概览/每日/会话/任务/计划外事件/对比', JSON.stringify(monMeta.visible_sheets))
    ok(monMeta.hidden_sheets.includes('_meta') && monMeta.hidden_sheets.includes('_epochs'),
      '月报同样带隐藏元数据表', JSON.stringify(monMeta.hidden_sheets))
    const cmp = await ctx3.table.readSheet(mon.file, '对比')
    ok(cmp.max_row === 7 && cmp.rows[0][1] === '本月' && cmp.rows[0][2] === '上月',
      '对比表 = 表头 + 6 项指标（本月/上月/变化/变化率）', JSON.stringify(cmp.rows[0]))
    const monScope = String((await ctx3.table.readSheet(mon.file, '概览')).rows[1][1])
    ok(/^\d{4}-\d{2}（\d{4}-\d{2}-\d{2} ~ \d{4}-\d{2}-\d{2}）$/.test(monScope),
      '概览标注了本月的起止日期', monScope)
    const nowD = new Date()
    const pm = new Date(nowD.getFullYear(), nowD.getMonth() - 1, 1)
    const pmKey = `${pm.getFullYear()}-${String(pm.getMonth() + 1).padStart(2, '0')}`
    const pmReport = await ctx3.report.month({ month: pmKey })
    ok(existsSync(pmReport.file) && pmReport.file.includes(pmKey), '可指定月份导出（month=YYYY-MM）',
      pmReport.file.split(/[\\/]/).pop())
    const badMonth = await json(req(base3 + '/api/export?format=xlsx&scope=month&month=2026-13', 'GET'))
    ok(badMonth.status === 400 && /month/.test(badMonth.data.error || ''), 'month=2026-13 -> 400 + 可读原因',
      badMonth.status + ' ' + (badMonth.data.error || ''))

    console.log('\n=== 11j. P6：自定义区间（含首尾两天，非法入参给 400）===')
    const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    const dTo = new Date(nowD.getFullYear(), nowD.getMonth(), nowD.getDate())
    const dFrom = new Date(nowD.getFullYear(), nowD.getMonth(), nowD.getDate() - 6)
    const rngPath = join(dir, 'range-dl.xlsx')
    const rng = await download(`${base3}/api/export?format=xlsx&scope=range&from=${iso(dFrom)}&to=${iso(dTo)}`, rngPath)
    ok(rng.status === 200 && /filename="pomodmer-range-/.test(rng.headers['content-disposition'] || ''),
      '区间导出可下载（文件名带 range）', String(rng.headers['content-disposition']))
    ok((await ctx3.table.readSheet(rngPath, '每日')).max_row === 8, '区间 7 天 -> 「每日」= 表头 + 7 行',
      String((await ctx3.table.readSheet(rngPath, '每日')).max_row))
    const noFrom = await json(req(base3 + '/api/export?format=xlsx&scope=range', 'GET'))
    ok(noFrom.status === 400 && /from/.test(noFrom.data.error || ''), '缺 from -> 400 + 可读原因',
      noFrom.status + ' ' + (noFrom.data.error || ''))
    const reversed = await json(req(base3 + `/api/export?format=xlsx&scope=range&from=${iso(dTo)}&to=${iso(dFrom)}`, 'GET'))
    ok(reversed.status === 400 && /晚于/.test(reversed.data.error || ''), 'from > to -> 400 + 可读原因',
      reversed.status + ' ' + (reversed.data.error || ''))
    const badDay = await json(req(base3 + '/api/export?format=xlsx&scope=range&from=2026-02-30&to=2026-03-01', 'GET'))
    ok(badDay.status === 400 && /合法日期/.test(badDay.data.error || ''), '2026-02-30 这类假日期 -> 400',
      badDay.status + ' ' + (badDay.data.error || ''))
  } else {
    ok(false, '回读四张表（周报未产出，跳过回读并保留上方真实错误）')
  }
  await stopHost()

  console.log('\n=== 11k. P6：跨时区回灌必须逐毫秒相等（导出端 TZ ≠ 导入端 TZ）===')
  // 做法：上面导出的 dlPath（上海时区产出，带 _meta/_epochs）→ 切到 UTC → 灌进一个**空库**。
  // 空库很关键：否则会被"去重跳过"掩盖，看不出时刻到底有没有漂移。
  const tzStore = join(dir, 'store-tz.json')
  const tzCfg = join(dir, 'cordis.tz.json')
  writeFileSync(tzCfg, JSON.stringify({
    entries: [
      { id: 'store', name: './src/plugins/store.mjs', config: { file: tzStore } },
      { id: 'timer', name: './src/plugins/timer.mjs' },
      { id: 'http', name: './src/plugins/http.mjs', config: { host: '127.0.0.1', port: 0, open: false } },
      { id: 'table', name: './src/plugins/table.mjs' },
      { id: 'report', name: './src/plugins/report.mjs', config: { outDir: dir.replace(/\\/g, '/') } },
    ],
  }, null, 2))
  const tzBackup = process.env.TZ
  process.env.TZ = 'UTC'
  const tzHost = await bootHost({ config: tzCfg })
  const tzTookEffect = new Date(Date.parse('2026-06-16T00:00:00')).getUTCHours() === 0
  // 期望值直接取自导出文件的隐藏 _epochs 表（那就是导出时的绝对时刻），逐毫秒比对
  const epochRows = dlPathForTz
    ? ((await tzHost.table.readSheet(dlPathForTz, '_epochs')).rows || []).slice(1)
    : []
  const wantEpochs = epochRows
    .filter((r) => String(r[0]) === '会话')
    .map((r) => Number(r[2]))
    .sort((a, b) => a - b)
  const tzApply = dlPathForTz ? await tzHost.report.importXlsx(dlPathForTz, { mode: 'apply' }) : { sessions: { add: 0, skip: 0 } }
  const gotEpochs = tzHost.store.sessions.map((s) => s.startAt).sort((a, b) => a - b)
  await stopHost()
  if (tzBackup === undefined) delete process.env.TZ
  else process.env.TZ = tzBackup
  console.log('  [info] 导入端 TZ=UTC 生效=%s | 导入结果 %s | 期望 %d 条 / 落库 %d 条',
    tzTookEffect, JSON.stringify(tzApply.sessions), wantEpochs.length, gotEpochs.length)
  ok(tzTookEffect, '运行时切换 TZ 确实生效（否则这条断言没有意义）', String(tzTookEffect))
  ok(wantEpochs.length > 0 && tzApply.sessions.add === wantEpochs.length,
    '空库导入：把导出里的会话全量写入', JSON.stringify(tzApply.sessions))
  ok(JSON.stringify(gotEpochs) === JSON.stringify(wantEpochs),
    '跨时区导入后**逐毫秒**等于导出时的绝对时刻（旧版会整体平移一个时差）',
    JSON.stringify(wantEpochs.slice(0, 3)) + ' vs ' + JSON.stringify(gotEpochs.slice(0, 3)))

  console.log('\n=== 12. P2/P3 资产自检 ===')
  const appjsSrc = readFileSync('web/app.js', 'utf8')
  ok(appjsSrc.includes('startAmbient') && appjsSrc.includes('brown'), '前端含白噪音实现（白噪音/棕噪音，实时合成）')
  ok(appjsSrc.includes('openMini'), '前端含迷你窗实现')
  const htmlSrc = readFileSync('web/index.html', 'utf8')
  ok(htmlSrc.includes('btnMini') && htmlSrc.includes('cfgAmbient') && htmlSrc.includes('btnReport'),
    '页面含迷你窗 / 白噪音 / 周报入口')
  ok(existsSync('pomodmer.bat'), '自愈式启动器 pomodmer.bat 就位')
  // 文档也是资产：完整能力说明被删/改名时说一声，别让它悄悄从仓库里消失
  ok(existsSync('docs/CAPABILITIES.md') && readFileSync('docs/CAPABILITIES.md', 'utf8').includes('/api/import/xlsx'),
    '完整能力说明 docs/CAPABILITIES.md 就位且覆盖回灌接口')
  ok(existsSync('src/core/toast.mjs'), 'Windows 原生通知模块就位（best-effort）')
  ok(existsSync('electron/main.cjs') && existsSync('electron/start.mjs')
    && existsSync('electron/make-icon.mjs') && existsSync('electron/icon.png'),
  'Electron 桌面壳：主进程 + 启动器 + 图标生成脚本 + 图标就位')
  const electronBin = existsSync('node_modules/electron/dist/electron.exe') || existsSync('node_modules/electron/dist/electron')
  console.log('  [info] Electron 运行时：' + (electronBin ? '已安装，可用 npm run electron' : '未安装（可选项，不影响主功能）'))

  console.log('\n=== 13. 表格能力三件套的来源锁（防两个仓库再次静默分叉）===')
  // 纯本地不变量：bridge.mjs / table.mjs / rpc_server.py 必须与 tools/table-kit.lock.json 一致。
  // 手改这三件套却没走同步 → 这里立刻红（用 --lock-only，不要求权威源在场，任何机器都能跑）。
  const kit = spawnSync(process.execPath, ['tools/sync-table-kit.mjs', '--lock-only'], { encoding: 'utf8' })
  ok(kit.status === 0, '三件套与来源锁一致（node tools/sync-table-kit.mjs --lock-only）',
    ((kit.stdout || '') + (kit.stderr || '')).trim().split('\n').slice(-4).join(' | '))
  const lockJson = JSON.parse(readFileSync('tools/table-kit.lock.json', 'utf8'))
  ok(!!lockJson.source && !!lockJson.source.repo && !!lockJson.source.commit,
    '来源锁记录了权威源与提交号（可追溯"这份代码从哪来"）',
    JSON.stringify(lockJson.source))

  console.log('\n=== 14. 表格能力自动启用决策（既有 OpenPyXL 资产不再靠"记得设环境变量"）===')
  // 本机探测结果决定自动清单；断言的是"决策与探测一致"这条不变量，
  // 所以在装了 Python+openpyxl 的机器和没装的机器上都成立。
  const probe = probeTableWorker(null, { timeoutMs: 2500, budgetMs: 4000 })
  console.log('  [info] 本机探测：openpyxl=%s bin=%s anyBin=%s', probe.openpyxl, probe.bin, probe.anyBin)
  const auto = resolveConfigPath({})
  ok(auto.path === (probe.openpyxl ? 'cordis.with-xlsx.json' : 'cordis.json'),
    '自动清单与探测结果一致（能跑表格能力就带上）', auto.path)
  ok(!!auto.reason && auto.reason.length > 0, '决策带可读原因（日志可解释）', auto.reason)
  ok(resolveConfigPath({ config: 'cordis.table.json' }).path === 'cordis.table.json',
    '显式 --config 优先于自动探测')

  const envBackup = { cfg: process.env.POMODMER_CONFIG, off: process.env.POMODMER_NO_XLSX }
  try {
    process.env.POMODMER_CONFIG = 'cordis.json'
    ok(resolveConfigPath({}).path === 'cordis.json', 'POMODMER_CONFIG 优先于自动探测')
    delete process.env.POMODMER_CONFIG
    process.env.POMODMER_NO_XLSX = '1'
    const off = resolveConfigPath({})
    ok(off.path === 'cordis.json', 'POMODMER_NO_XLSX=1 可主动关闭自动启用', off.reason)
  } finally {
    if (envBackup.cfg === undefined) delete process.env.POMODMER_CONFIG
    else process.env.POMODMER_CONFIG = envBackup.cfg
    if (envBackup.off === undefined) delete process.env.POMODMER_NO_XLSX
    else process.env.POMODMER_NO_XLSX = envBackup.off
  }

  console.log('\n=== 结果 ===')
  console.log(failed === 0 ? '  ALL PASS' : '  FAILED: ' + failed + ' 项')
  process.exit(failed === 0 ? 0 : 1)
}

main().catch((e) => {
  console.error('[smoke-pom] FATAL:', e)
  process.exit(1)
})
