// _smoke_pom.mjs —— 番茄钟端到端冒烟（走真实 HTTP，不 mock）
// 覆盖：启动 -> 状态 -> 设置 -> 开始/暂停冻结/继续 -> 到点自动流转 -> 跳过/作废 -> 任务 CRUD
//       -> 会话落库 -> 静态资源与穿越防护 -> SSE -> 重启恢复（进程被杀不静默补时）
// 数据落 os.tmpdir()，端口由系统分配（port: 0），不污染真实 data/store.json、不抢端口。
import { bootHost, stopHost } from './boot.mjs'
import { mkdtempSync, readFileSync, writeFileSync, existsSync } from 'node:fs'
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
      hostname: u.hostname, port: u.port, path: u.pathname, method,
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

  console.log('\n=== 10. 落盘与重启恢复（被杀进程不静默补时）===')
  // 让一个番茄处于 running 状态，然后"硬杀"宿主（模拟断电/强杀），检查落盘数据
  await json(req(base + '/api/timer/resume', 'POST'))
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

  console.log('\n=== 结果 ===')
  console.log(failed === 0 ? '  ALL PASS' : '  FAILED: ' + failed + ' 项')
  process.exit(failed === 0 ? 0 : 1)
}

main().catch((e) => {
  console.error('[smoke-pom] FATAL:', e)
  process.exit(1)
})
