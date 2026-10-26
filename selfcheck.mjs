// pomodmer 无头自检（不启动 HTTP 服务、不开浏览器、不起 Electron）
//
// 直接用 Cordis 把 store（JSON 原子落盘）+ timer（番茄钟状态机）挂到一个裸 Context 上，
// 数据目录指向 os.tmpdir()，不碰项目里的 data/store.json。验证四件事：
//
//   1. 设置：默认值、合法 patch 生效、非法值（<1s / 未知键 / 坏枚举）被拒；
//   2. 任务 CRUD：新增（含空标题/非法估算的收敛）、改名/估算、完成标记、删除；
//   3. 状态机推进：开始→暂停冻结→继续→到点自动流转（round +1、会话落库、任务 spent 累加）
//      →跳过不计完成；
//   4. 持久化往返：落盘 JSON 可被新实例读回（设置/任务/会话/轮次一致）。
//
// 用法：node selfcheck.mjs
// 退出码：0 成功 / 1 失败。

import { mkdtempSync, readFileSync, readdirSync, rmSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { Context } from 'cordis'

import StoreService from './src/plugins/store.mjs'
import TimerService from './src/plugins/timer.mjs'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function fail(msg) {
  console.error('FAIL: ' + msg)
  process.exit(1)
}

function expect(cond, msg) {
  if (!cond) fail(msg)
}

function setup(dataDir) {
  const ctx = new Context()
  return (async () => {
    const storeFiber = await ctx.plugin(StoreService, { file: join(dataDir, 'store.json') })
    const timerFiber = await ctx.plugin(TimerService, {})
    return { ctx, storeFiber, timerFiber }
  })()
}

/* ===================== 1. 设置 ===================== */

function checkSettings(timer) {
  const defaults = timer.store.settings
  expect(timer.duration('focus') === 25 * 60 * 1000, '默认专注时长不是 25 分钟：' + timer.duration('focus'))
  expect(defaults.longEvery === 4, '默认 longEvery 不是 4：' + defaults.longEvery)
  expect(defaults.autoStartBreak === true && defaults.autoStartFocus === false, '默认自动开始策略不对')

  timer.setSettings({
    focusMs: 1000, shortMs: 60000, longMs: 60000, longEvery: 2,
    autoStartBreak: true, autoStartFocus: false, theme: 'dark',
    notify: 'yes', nope: 123,
  })
  const s = timer.store.settings
  expect(s.focusMs === 1000 && s.shortMs === 60000 && s.longMs === 60000, '合法设置未生效：' + JSON.stringify(s))
  expect(s.longEvery === 2, 'longEvery 未生效')
  expect(s.theme === 'dark', 'theme=dark 未生效')
  expect(s.notify === true, 'boolean 型设置未被强制转 bool')
  expect(!('nope' in s), '未知设置键被写入了数据')

  timer.setSettings({ focusMs: 500, theme: 'midnight', longEvery: 0, sound: false })
  const s2 = timer.store.settings
  expect(s2.focusMs === 1000, '<1s 的 focusMs 应被拒：' + s2.focusMs)
  expect(s2.theme === 'light', '未知 theme 应回落 light：' + s2.theme)
  expect(s2.longEvery === 2, 'longEvery=0 应被拒：' + s2.longEvery)
  expect(s2.sound === false, 'sound=false 未生效')

  return Object.keys(s).length
}

/* ===================== 2. 任务 CRUD ===================== */

function checkTaskCrud(timer) {
  const task = timer.addTask('写自检', 3)
  expect(task.title === '写自检' && task.estimate === 3 && task.spent === 0 && task.done === false,
    '新增任务字段不对：' + JSON.stringify(task))
  expect(timer.store.tasks.length === 1, '任务未入库')

  const upd = timer.updateTask(task.id, { title: '写自检 v2', estimate: 5, done: true })
  expect(upd && upd.title === '写自检 v2' && upd.estimate === 5 && upd.done === true,
    '更新任务未生效：' + JSON.stringify(upd))
  expect(timer.updateTask('no-such-id', { title: 'x' }) === null, '更新不存在的任务应返回 null')

  const clamped = timer.addTask('   ', 0)
  expect(clamped.title === '未命名任务', '空标题未回落占位名：' + clamped.title)
  expect(clamped.estimate === 1, '估算 0 未夹到 1：' + clamped.estimate)

  expect(timer.deleteTask(clamped.id) === true, '删除任务应返回 true')
  expect(timer.deleteTask(clamped.id) === false, '重复删除应返回 false')
  expect(timer.store.tasks.length === 1, '删除后任务数不对：' + timer.store.tasks.length)

  timer.setCurrentTask(task.id)
  expect(timer.state().currentTaskId === task.id, 'setCurrentTask 未生效')
  return task.id
}

/* ===================== 3. 状态机推进 ===================== */

async function checkStateMachine(timer, taskId) {
  const started = timer.start(taskId)
  expect(started.running === true && started.phase === 'focus', 'start 后未进入运行中的专注：' + JSON.stringify(started))
  expect(started.plannedMs === 1000, 'plannedMs 不等于设置的 1000ms：' + started.plannedMs)
  expect(started.currentTaskId === taskId, 'start 未绑定当前任务')
  expect(Math.abs(started.endAt - Date.now() - 1000) < 200, 'endAt 不是绝对结束时刻')

  const paused = timer.pause()
  expect(paused.running === false, 'pause 后仍在运行')
  expect(paused.remainingMs > 0 && paused.remainingMs <= 1000, '暂停剩余时间越界：' + paused.remainingMs)
  expect(paused.interrupts === 1, '暂停未计一次中断：' + paused.interrupts)
  const frozen = paused.remainingMs
  await sleep(120)
  expect(timer.state().remainingMs === frozen, '暂停期间剩余时间仍在流逝（应冻结）')
  expect(timer.remainingMs() === frozen, 'remainingMs() 暂停时未返回冻结值')

  const resumed = timer.resume()
  expect(resumed.running === true, 'resume 后未恢复运行')
  expect(Math.abs(resumed.endAt - Date.now() - frozen) < 200, 'resume 未按冻结剩余时间重算 endAt')

  // 到点自动流转：等状态机自己走（最多 6s，正常约 1s）
  const deadline = Date.now() + 6000
  while (Date.now() < deadline && timer.store.runtime.phase !== 'short') await sleep(25)
  const after = timer.state()
  expect(after.phase === 'short', '专注结束后未进入短休息：' + after.phase)
  expect(after.running === true, '短休息未按 autoStartBreak 自动开始')
  expect(timer.store.runtime.round === 1, '完成一个番茄后 round 未 +1：' + timer.store.runtime.round)

  const sessions = timer.store.sessions
  expect(sessions.length === 1, '应只落库 1 条会话：' + sessions.length)
  expect(sessions[0].type === 'focus' && sessions[0].completed === true, '专注会话记录不对：' + JSON.stringify(sessions[0]))
  expect(sessions[0].plannedMs === 1000, '会话 plannedMs 不对：' + sessions[0].plannedMs)
  const task = timer.store.tasks.find((t) => t.id === taskId)
  expect(task && task.spent === 1, '完成任务后 spent 未累加：' + task?.spent)

  // 跳过休息：记录为未完成，且因 autoStartFocus=false 停在待启动的专注
  const skipped = timer.skip()
  expect(skipped.phase === 'focus' && skipped.running === false, 'skip 后未停在待启动的专注：' + JSON.stringify(skipped))
  expect(timer.store.sessions.length === 2, 'skip 未落库会话：' + timer.store.sessions.length)
  const last = timer.store.sessions.at(-1)
  expect(last.type === 'short' && last.completed === false && last.reason === 'skipped',
    'skip 会话记录不对：' + JSON.stringify(last))
  expect(timer.store.runtime.round === 1, 'skip 不应改变 round：' + timer.store.runtime.round)

  // voidCurrent：中断即作废，回到专注起点
  timer.start(taskId)
  const voided = timer.voidCurrent('selfcheck')
  expect(voided.running === false && voided.phase === 'focus', 'voidCurrent 未回到待启动专注')
  expect(voided.remainingMs === 1000, 'voidCurrent 未把剩余时间归位：' + voided.remainingMs)
  expect(timer.store.sessions.at(-1).reason === 'selfcheck', 'voidCurrent 未记录原因')

  return { sessions: timer.store.sessions.length, round: timer.store.runtime.round }}

/* ===================== 4. 持久化往返 ===================== */

async function checkPersistence(dataDir, timer, expectedTaskId) {
  const file = join(dataDir, 'store.json')
  expect(existsSync(file), '落盘文件不存在：' + file)
  const onDisk = JSON.parse(readFileSync(file, 'utf8'))
  expect(onDisk.settings.focusMs === 1000, '落盘 settings.focusMs 不对：' + onDisk.settings.focusMs)
  expect(onDisk.tasks.length === 1 && onDisk.tasks[0].title === '写自检 v2', '落盘任务不对')
  expect(onDisk.sessions.length === 3, '落盘会话数不对：' + onDisk.sessions.length)
  expect(onDisk.runtime.round === 1, '落盘 round 不对：' + onDisk.runtime.round)
  expect(!readdirSync(dataDir).some((n) => n.endsWith('.tmp')), '残留了原子写临时文件')

  const before = timer.store.tasks.length
  const second = await setup(dataDir)
  try {
    const s2 = second.ctx.store
    expect(s2.settings.focusMs === 1000, '重载后设置丢失：' + s2.settings.focusMs)
    expect(s2.tasks.length === before, '重载后任务数不对：' + s2.tasks.length)
    expect(s2.tasks[0].id === expectedTaskId && s2.tasks[0].spent === 1, '重载后任务内容不对')
    expect(s2.sessions.length === 3, '重载后会话数不对：' + s2.sessions.length)
    expect(s2.sessions[0].completed === true, '重载后会话内容不对')
    expect(second.ctx.timer.state().phase === 'focus', '重载后状态机未按落盘的 pending 专注恢复：' + second.ctx.timer.state().phase)
    return s2.sessions.length
  } finally {
    await second.timerFiber.dispose()
    await second.storeFiber.dispose()
  }
  return 3
}

/* ===================== main ===================== */

async function main() {
  const dataDir = mkdtempSync(join(tmpdir(), 'pomodmer-selfcheck-'))
  const { ctx, storeFiber, timerFiber } = await setup(dataDir)
  try {
    const settingKeys = checkSettings(ctx.timer)
    const taskId = checkTaskCrud(ctx.timer)
    const sm = await checkStateMachine(ctx.timer, taskId)
    const reloaded = await checkPersistence(dataDir, ctx.timer, taskId)
    console.log(
      'selfcheck ok: 设置 %d 项（<1s/未知键/坏枚举被拒） / 任务 CRUD（含空标题与非法估算收敛） / '
      + '状态机 开始→暂停冻结→继续→到点流转（round=%d，skip+void 不计完成，共 %d 条会话） / '
      + '落盘 JSON 重载往返 %d 条会话',
      settingKeys, sm.round, sm.sessions, reloaded,
    )
  } finally {
    try { await timerFiber.dispose() } catch { /* ignore */ }
    try { await storeFiber.dispose() } catch { /* ignore */ }
    rmSync(dataDir, { recursive: true, force: true })
  }
  process.exit(0)
}

main().catch((e) => fail(e && e.stack ? e.stack : String(e)))
