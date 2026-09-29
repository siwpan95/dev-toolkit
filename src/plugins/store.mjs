// StoreService —— 番茄钟的持久化层，挂到 ctx.store
// 设计要点：
//   1) 单文件 JSON（默认 data/store.json），**原子写**：写 .tmp 再 rename，避免 Ctrl+C 杀进程写坏数据
//   2) 启动时合并默认值（旧档缺字段也能开），不抛错
//   3) [Service.init] 返回清理函数：fiber dispose 时兜底 flush（沿用 TableService 的范式）
//   4) 只有这一个写入口，TimerService / HttpService 都不直接碰 fs
import { Service } from 'cordis'
import { readFileSync, writeFileSync, renameSync, mkdirSync, existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'

export function defaultData() {
  return {
    version: 1,
    settings: {
      focusMs: 25 * 60 * 1000,
      shortMs: 5 * 60 * 1000,
      longMs: 15 * 60 * 1000,
      longEvery: 4,             // 每 N 个番茄后进入长休息（番茄工作法标准 = 4）
      autoStartBreak: true,     // 番茄结束后自动开始休息
      autoStartFocus: false,    // 休息结束后自动开始下一个番茄
      sound: true,              // 提示音
      tick: false,              // 每秒滴答声
      notify: true,             // 桌面通知
    },
    tasks: [],                  // { id, title, estimate, spent, done, createdAt }
    sessions: [],               // { id, type, taskId, plannedMs, startAt, endAt, actualMs, completed, interrupts, reason }
    runtime: {
      phase: 'idle',            // idle | focus | short | long
      running: false,
      endAt: 0,                 // 运行中的绝对结束时刻（epoch ms）——计时权威
      remainingMs: 0,           // 暂停时冻结的剩余毫秒
      startedAt: 0,             // 当前阶段开始时刻
      plannedMs: 0,             // 当前阶段计划总时长
      round: 0,                 // 本轮已完成的番茄数（用于判断何时长休）
      currentTaskId: null,
      interrupts: 0,            // 当前阶段的中断次数
    },
  }
}

export class StoreService extends Service {
  static provide = 'store'

  constructor(ctx, config) {
    super(ctx, 'store')
    this.config = config || {}
    this.file = resolve(process.cwd(), this.config.file || 'data/store.json')
    this.data = defaultData()
    this._dirty = false
  }

  [Service.init]() {
    this.load()
    return () => {
      // 关停兜底：把仍在运行的阶段冻结成"未完成"，下次启动不会凭空补时
      this.flush()
    }
  }

  // ---- 读写 ----
  load() {
    if (!existsSync(this.file)) {
      this.ctx.logger.info('store: 无数据文件，使用默认配置 -> %s', this.file)
      return this.data
    }
    try {
      const raw = JSON.parse(readFileSync(this.file, 'utf8'))
      this.data = this._merge(defaultData(), raw)
      this.ctx.logger.info('store: 已加载 %s（sessions=%d, tasks=%d）',
        this.file, this.data.sessions.length, this.data.tasks.length)
    } catch (e) {
      // 坏档不丢：备份后回退默认值，保证应用能开
      const bak = this.file + '.broken-' + Date.now()
      try { renameSync(this.file, bak) } catch { /* ignore */ }
      this.ctx.logger.warn('store: 数据文件损坏，已备份到 %s，回退默认配置（%s）', bak, e.message)
      this.data = defaultData()
    }
    return this.data
  }

  flush() {
    try {
      mkdirSync(dirname(this.file), { recursive: true })
      const tmp = this.file + '.tmp'
      writeFileSync(tmp, JSON.stringify(this.data, null, 2), 'utf8')
      renameSync(tmp, this.file)
      this._dirty = false
      return true
    } catch (e) {
      this.ctx.logger.warn('store: 落盘失败 %s', e.message)
      return false
    }
  }

  // 唯一写入口：改数据在 fn 里做，改完立刻落盘（数据量小，简单可靠）
  update(fn) {
    const r = fn(this.data)
    this.flush()
    return r
  }

  // ---- 便捷访问 ----
  get settings() { return this.data.settings }
  get runtime() { return this.data.runtime }
  get tasks() { return this.data.tasks }
  get sessions() { return this.data.sessions }

  // 合并：深合并普通对象，数组以新值为准（旧档缺字段用默认补齐）
  _merge(base, patch) {
    if (patch === null || patch === undefined) return base
    if (Array.isArray(base) || Array.isArray(patch)) return Array.isArray(patch) ? patch : base
    if (typeof base !== 'object' || typeof patch !== 'object') return patch
    const out = { ...base }
    for (const k of Object.keys(patch)) {
      out[k] = k in base ? this._merge(base[k], patch[k]) : patch[k]
    }
    return out
  }
}

export default StoreService
