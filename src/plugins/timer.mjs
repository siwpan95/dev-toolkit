// TimerService —— 番茄钟状态机 + 权威计时，挂到 ctx.timer
//
// 计时权威的三条硬规则（调研结论落地）：
//   1) 进度不是"累加 tick 次数"，而是每次现算 remaining = endAt - now（endAt 为绝对时刻）
//   2) 用递归 setTimeout 且对齐到整秒边界（nextTarget 固定），不用 setInterval —— 不累积漂移
//   3) 系统休眠/进程被挂起导致的 gap 超阈值：不静默补时，标记 interrupted（番茄工作法：中断即作废）
//
// 时间口径：Date.now()（墙钟）负责"几点开始/结束"，落盘与 UI 都用它；
//           perf_hooks.performance.now()（单调钟）只用于校验调度精度，不参与业务判定。
import { Service } from 'cordis'
import { randomUUID } from 'node:crypto'
import { performance } from 'node:perf_hooks'

const PHASE_LABEL = { idle: '待开始', focus: '专注', short: '短休息', long: '长休息' }
const DEFAULT_SUSPEND_GAP_MS = 10_000

export class TimerService extends Service {
  static provide = 'timer'
  static inject = ['store']

  constructor(ctx, config) {
    super(ctx, 'timer')
    this.config = config || {}
    this.store = ctx.store
    this.suspendGapMs = Number(this.config.suspendGapMs) || DEFAULT_SUSPEND_GAP_MS
    this._timerId = null
    this._lastTickAt = 0
    this._tickSeq = 0
  }

  [Service.init]() {
    if (!this.store) throw new Error('TimerService 依赖 ctx.store（cordis.json 中 store 必须在 timer 之前）')
    this._recover()
    this._lastTickAt = Date.now()
    this._schedule()
    this.ctx.logger.info('timer: 就绪 phase=%s running=%s round=%d',
      this.store.runtime.phase, this.store.runtime.running, this.store.runtime.round)
    return () => {
      this._clear()
    }
  }

  // ---------- 对外状态 ----------
  duration(phase) {
    const s = this.store.settings
    if (phase === 'short') return s.shortMs
    if (phase === 'long') return s.longMs
    return s.focusMs
  }

  remainingMs() {
    const rt = this.store.runtime
    if (rt.running) return Math.max(0, rt.endAt - Date.now())
    return rt.remainingMs || 0
  }

  state() {
    const rt = this.store.runtime
    const phase = rt.phase
    const planned = phase === 'idle' ? this.duration('focus') : (rt.plannedMs || this.duration(phase))
    const remaining = phase === 'idle' ? (rt.remainingMs || this.duration('focus')) : this.remainingMs()
    return {
      seq: this._tickSeq,
      now: Date.now(),
      phase,
      phaseLabel: PHASE_LABEL[phase] || phase,
      running: !!rt.running,
      remainingMs: remaining,
      plannedMs: planned,
      endAt: rt.running ? rt.endAt : 0,
      round: rt.round,
      longEvery: this.store.settings.longEvery,
      currentTaskId: rt.currentTaskId,
      interrupts: rt.interrupts || 0,
      today: this.today(),
    }
  }

  // ---------- 控制 ----------
  start(taskId) {
    const rt = this.store.runtime
    if (rt.running) return this.state()
    if (rt.phase === 'idle') return this._begin('focus', taskId === undefined ? rt.currentTaskId : taskId)
    return this.resume()
  }

  pause() {
    const rt = this.store.runtime
    if (!rt.running) return this.state()
    const now = Date.now()
    this.store.update((d) => {
      d.runtime.running = false
      d.runtime.remainingMs = Math.max(0, d.runtime.endAt - now)
      d.runtime.endAt = 0
      d.runtime.interrupts = (d.runtime.interrupts || 0) + 1
    })
    this._emit('pomodoro/phase', { type: 'pause', phase: this.store.runtime.phase })
    return this.state()
  }

  resume() {
    const rt = this.store.runtime
    if (rt.running || rt.phase === 'idle') return this.state()
    const now = Date.now()
    this.store.update((d) => {
      d.runtime.running = true
      d.runtime.endAt = now + (d.runtime.remainingMs || this.duration(d.runtime.phase))
      d.runtime.remainingMs = d.runtime.endAt - now
    })
    this._schedule()
    this._emit('pomodoro/phase', { type: 'resume', phase: this.store.runtime.phase })
    return this.state()
  }

  toggle(taskId) {
    return this.store.runtime.running ? this.pause() : this.start(taskId)
  }

  // 重置：当前阶段回到起点，不记录 session、不影响 round
  reset() {
    const rt = this.store.runtime
    const phase = rt.phase === 'idle' ? 'focus' : rt.phase
    const dur = this.duration(phase)
    this.store.update((d) => {
      d.runtime.phase = phase
      d.runtime.running = false
      d.runtime.remainingMs = dur
      d.runtime.plannedMs = dur
      d.runtime.endAt = 0
      d.runtime.startedAt = 0
      d.runtime.interrupts = 0
    })
    this._schedule()
    this._emit('pomodoro/phase', { type: 'reset', phase })
    return this.state()
  }

  // 跳过：结束当前阶段但不计入完成（番茄工作法：番茄不可分割，提前结束不算）
  skip() {
    const rt = this.store.runtime
    if (rt.phase === 'idle') return this.state()
    this._finish(false, 'skipped')
    return this.state()
  }

  // 作废：番茄工作法的"中断即作废"——当前番茄归零，回到专注起点
  voidCurrent(reason = 'void') {
    const rt = this.store.runtime
    if (rt.phase === 'idle') return this.state()
    const phase = rt.phase
    this._record({ type: phase, completed: false, reason, endAt: Date.now() })
    const dur = this.duration(phase === 'focus' ? 'focus' : phase)
    this.store.update((d) => {
      d.runtime.running = false
      d.runtime.remainingMs = dur
      d.runtime.plannedMs = dur
      d.runtime.endAt = 0
      d.runtime.startedAt = 0
    })
    this._schedule()
    this._emit('pomodoro/phase', { type: 'void', phase })
    return this.state()
  }

  setSettings(patch = {}) {
    const allow = ['focusMs', 'shortMs', 'longMs', 'longEvery', 'autoStartBreak', 'autoStartFocus', 'sound', 'tick', 'notify']
    this.store.update((d) => {
      for (const k of Object.keys(patch)) {
        if (!allow.includes(k)) continue
        const v = patch[k]
        if (k.endsWith('Ms')) {
          const n = Number(v)
          if (!Number.isFinite(n) || n < 1000) continue      // 至少 1 秒，防误设
          d.settings[k] = Math.round(n)
        } else if (k === 'longEvery') {
          const n = Number(v)
          if (!Number.isFinite(n) || n < 1) continue
          d.settings[k] = Math.round(n)
        } else {
          d.settings[k] = !!v
        }
      }
      // 未在运行的阶段，剩余时间跟随新设置
      const rt = d.runtime
      if (!rt.running) {
        if (rt.phase === 'idle') rt.remainingMs = d.settings.focusMs
        else if (rt.phase === 'focus' && !rt.startedAt) rt.remainingMs = d.settings.focusMs
        else if (rt.phase !== 'focus') rt.remainingMs = this.duration(rt.phase)
      }
    })
    this._emit('pomodoro/settings', this.store.settings)
    return this.state()
  }

  // ---------- 任务（P0 提供接口，UI 在 P1 铺开）----------
  addTask(title, estimate = 1) {
    const task = { id: randomUUID(), title: String(title || '').trim() || '未命名任务', estimate: Math.max(1, Number(estimate) || 1), spent: 0, done: false, createdAt: Date.now() }
    this.store.update((d) => { d.tasks.push(task) })
    return task
  }

  updateTask(id, patch = {}) {
    let found = null
    this.store.update((d) => {
      const t = d.tasks.find((x) => x.id === id)
      if (!t) return
      if (patch.title !== undefined) t.title = String(patch.title)
      if (patch.estimate !== undefined) t.estimate = Math.max(1, Number(patch.estimate) || 1)
      if (patch.done !== undefined) t.done = !!patch.done
      found = t
    })
    return found
  }

  deleteTask(id) {
    let ok = false
    this.store.update((d) => {
      const i = d.tasks.findIndex((x) => x.id === id)
      if (i >= 0) { d.tasks.splice(i, 1); ok = true }
      if (d.runtime.currentTaskId === id) d.runtime.currentTaskId = null
    })
    return ok
  }

  setCurrentTask(id) {
    this.store.update((d) => { d.runtime.currentTaskId = id || null })
    return this.state()
  }

  // ---------- 统计 ----------
  today() {
    const now = new Date()
    const dayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
    const list = this.store.sessions.filter((s) => (s.startAt || 0) >= dayStart)
    const focus = list.filter((s) => s.type === 'focus')
    return {
      date: new Date(dayStart).toISOString().slice(0, 10),
      completed: focus.filter((s) => s.completed).length,
      abandoned: focus.filter((s) => !s.completed).length,
      focusMs: focus.reduce((a, s) => a + (s.actualMs || 0), 0),
      interrupts: list.reduce((a, s) => a + (s.interrupts || 0), 0),
    }
  }

  // ---------- 内部：阶段推进 ----------
  _begin(phase, taskId) {
    const now = Date.now()
    const dur = this.duration(phase)
    this.store.update((d) => {
      const rt = d.runtime
      rt.phase = phase
      rt.running = true
      rt.startedAt = now
      rt.plannedMs = dur
      rt.endAt = now + dur
      rt.remainingMs = dur
      rt.interrupts = 0
      if (taskId !== undefined) rt.currentTaskId = taskId
    })
    this._lastTickAt = now
    this._schedule()
    this._emit('pomodoro/phase', { type: 'begin', phase })
    return this.state()
  }

  _finish(completed, reason) {
    const rt = this.store.runtime
    const now = Date.now()
    const endAt = completed ? (rt.endAt || now) : now
    this._record({ type: rt.phase, completed, reason, endAt })
    this._advance(completed)
  }

  _record({ type, completed, reason, endAt }) {
    const rt = this.store.runtime
    const startAt = rt.startedAt || endAt
    const session = {
      id: randomUUID(),
      type,
      taskId: rt.currentTaskId,
      plannedMs: rt.plannedMs || this.duration(type),
      startAt,
      endAt,
      actualMs: Math.max(0, endAt - startAt),
      completed: !!completed,
      interrupts: rt.interrupts || 0,
      reason: reason || null,
    }
    this.store.update((d) => {
      d.sessions.push(session)
      if (completed && type === 'focus') {
        d.runtime.round = (d.runtime.round || 0) + 1
        const t = d.tasks.find((x) => x.id === rt.currentTaskId)
        if (t) t.spent = (t.spent || 0) + 1
      }
    })
    this._emit('pomodoro/session', session)
    return session
  }

  // 决定下一阶段并按 autoStart 决定是立刻开始还是待启动
  _advance(lastCompleted) {
    const rt = this.store.runtime
    const s = this.store.settings
    const from = rt.phase
    let next = 'focus'
    if (from === 'focus') {
      const round = rt.round || 0
      next = (round > 0 && round % s.longEvery === 0) ? 'long' : 'short'
    }
    const auto = next === 'focus' ? s.autoStartFocus : s.autoStartBreak
    if (auto) {
      this._emit('pomodoro/phase', { type: 'end', phase: from, next, completed: lastCompleted })
      return this._begin(next, rt.currentTaskId)
    }
    const dur = this.duration(next)
    this.store.update((d) => {
      d.runtime.phase = next
      d.runtime.running = false
      d.runtime.plannedMs = dur
      d.runtime.remainingMs = dur
      d.runtime.endAt = 0
      d.runtime.startedAt = 0
      if (next !== 'focus') d.runtime.currentTaskId = rt.currentTaskId
    })
    this._schedule()
    this._emit('pomodoro/phase', { type: 'end', phase: from, next, completed: lastCompleted })
  }

  // ---------- 内部：调度 ----------
  _clear() {
    if (this._timerId) {
      clearTimeout(this._timerId)
      this._timerId = null
    }
  }

  // 对齐到下一个整秒边界：remaining=1500 -> 500ms 后 tick（到达 1000ms 整）
  _nextDelay() {
    const remaining = this.remainingMs()
    if (remaining <= 0) return 0
    let d = remaining % 1000
    if (d === 0) d = 1000
    return Math.min(d, remaining)
  }

  _schedule() {
    this._clear()
    if (!this.store.runtime.running) return
    this._timerId = setTimeout(() => this._tick(), this._nextDelay())
  }

  _tick() {
    const t0 = performance.now()
    const rt = this.store.runtime
    const now = Date.now()
    const gap = now - this._lastTickAt
    this._lastTickAt = now

    if (rt.running) {
      if (gap > this.suspendGapMs) {
        // 进程/系统被挂起过（休眠、长阻塞）：不静默补时，按番茄工作法作废当前番茄
        this.ctx.logger.warn('timer: 检测到 %ds 空档，判定为休眠/挂起，当前番茄作废', Math.round(gap / 1000))
        this._finish(false, 'suspend')
      } else if (now >= rt.endAt) {
        this._finish(true, null)
      }
    }

    this._tickSeq++
    this._emit('pomodoro/tick', this.state())
    if (process.env.POMODMER_TRACE) {
      this.ctx.logger.debug('timer: tick cost=%.2fms', performance.now() - t0)
    }
    this._schedule()
  }

  // 启动恢复：上次退出时若仍在运行，冻结为暂停态；已过 endAt 的记为中断，绝不静默补时
  _recover() {
    const rt = this.store.runtime
    if (!rt.running) return
    const now = Date.now()
    if (now >= rt.endAt) {
      const startAt = rt.startedAt || rt.endAt
      this._record({ type: rt.phase, completed: false, reason: 'shutdown', endAt: rt.endAt || now })
      this.ctx.logger.warn('timer: 上次运行中退出，该阶段已过终点（%s -> %s），记为中断不计完成',
        new Date(startAt).toLocaleString(), new Date(rt.endAt || now).toLocaleString())
      this._advance(false)
      this.store.update((d) => { d.runtime.running = false })
    } else {
      this.store.update((d) => {
        d.runtime.running = false
        d.runtime.remainingMs = d.runtime.endAt - now
        d.runtime.endAt = 0
      })
      this.ctx.logger.info('timer: 上次运行中退出，已冻结为暂停态（剩余 %s）',
        (this.store.runtime.remainingMs / 1000).toFixed(1) + 's')
    }
  }

  _emit(name, payload) {
    try {
      this.ctx.emit(name, payload)
    } catch (e) {
      this.ctx.logger.warn('timer: 事件 %s 分发失败 %s', name, e.message)
    }
  }
}

export default TimerService
