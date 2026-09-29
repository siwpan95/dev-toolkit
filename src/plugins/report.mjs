// ReportService —— xlsx 双向能力，挂到 ctx.report
// 导出（同一套构建逻辑，同一层 ctx.table，宿主自己不碰 Excel）：
//   weekly({ days })  周报：最近 N 天（概览 / 每日 / 会话 / 任务）
//   full()            全量导出：从第一条会话到今天（再加一张「计划外事件」）
// 导入（P3，反向用 readSheet）：
//   importXlsx(file, { mode })  把我们导出的表改完再灌回来 —— 去重追加，永不删已有记录
// 分工：JSON 导出（/api/export）用来**回灌备份**；xlsx 两条链路给人看、二次分析、再导回。
// table 是**可选依赖**：不 inject，调用时才 ctx.get('table')，缺失给出可执行的修复提示。
// 启用方式：启动时探测到 Python + openpyxl 就自动带上（boot.mjs 的 resolveConfigPath），
// 也可用 POMODMER_CONFIG=cordis.with-xlsx.json 强制启用 / POMODMER_NO_XLSX=1 主动关闭。
import { Service } from 'cordis'
import { resolve, dirname } from 'node:path'
import { mkdirSync } from 'node:fs'
import { randomUUID } from 'node:crypto'

const NO_TABLE_MSG = 'xlsx 导出需要 table 插件：当前清单没挂表格能力（未探测到 Python + openpyxl，或用 POMODMER_NO_XLSX=1 主动关闭）。装好 Python + openpyxl 后重启即自动启用，也可 POMODMER_CONFIG=cordis.with-xlsx.json 强制启用'

const TYPE = { focus: '专注', short: '短休息', long: '长休息' }
const KIND = { internal: '内部', external: '外部' }
const DATETIME_FMT = 'yyyy-mm-dd hh:mm'
const DATE_FMT = 'yyyy-mm-dd'
const MAX_DAYS = 3650 // 十年：防脏数据（比如一条 1970 年的时间戳）把每日表撑爆

// 空表占位行：给人看的（"这张表这次没内容"），但**导入时必须认出来并跳过** ——
// 否则"空表 -> 导出 -> 导回"会凭空造出一个叫「（无任务）」的任务（冒烟抓到过）。
// 写与读共用同一组常量，别让两边各写一份字面量。
const EMPTY_TASKS = '（无任务）'
const EMPTY_UNPLANNED = '（无记录）'

// 本地时间的 ISO 串（不带时区），交给 worker 变成 Excel 原生 datetime。
// 不能用 toISOString()：那是 UTC，导出的表在 Excel 里会整体差几个时区。
function localIso(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
const mins = (ms) => Math.round((ms || 0) / 60000)
const today = () => localIso(Date.now()).slice(0, 10)
const dayKey = (ts) => {
  const d = new Date(ts)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

// 入参错误（HTTP 层据此回 400，而不是把用户输入问题当服务端故障回 500）
const badInput = (msg) => Object.assign(new Error(msg), { code: 'BAD_INPUT' })

// "墙上时间"（带时间但**没有时区标记**）—— 我们导出的就是这个形态
const NAIVE_LOCAL = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?(\.\d+)?$/

// 把 xlsx 里的时间还原成**绝对时刻**，三级优先：
//   1) 逐行 epoch（导出时写在隐藏表里）+ 该行与"换算后的墙上时间"一致 → 行未被编辑，直接用 epoch
//      （保留毫秒；跨时区、跨夏令时都精确）；
//   2) 行被编辑过 → 用 _meta 的 tzOffsetMinutes 把墙上时间换算回绝对时刻（秒级精度）；
//   3) 没有元数据（用户自制的表）→ 按本机时区解析，等同旧行为。
// 注意第 1 步的一致性判断必须拿**换算后**的值去比：早先拿"本机解析值"去比，
// 在 UTC 机器上它天然差 8 小时，于是 epoch 通道永远被判为"不一致"而退回秒级换算 —— 毫秒就这么丢了。
function fixInstant(raw, naiveMs, rowEpoch, metaTz) {
  const s = String(raw == null ? '' : raw).trim()
  let converted = null
  if (metaTz !== null && metaTz !== undefined && NAIVE_LOCAL.test(s)) {
    const asUtc = Date.parse(s.replace(' ', 'T') + 'Z')
    if (Number.isFinite(asUtc)) converted = asUtc - metaTz * 60000
  }
  if (rowEpoch !== null && rowEpoch !== undefined) {
    const ref = converted === null ? naiveMs : converted
    if (Math.abs(ref - rowEpoch) <= 3000) return rowEpoch
  }
  if (converted !== null) return converted
  return naiveMs
}

// ---------- 回灌导入（P3）：Excel 里的中文/文本 → 库里的规范值 ----------
// 认表头名、不认列序：用户在 Excel 里挪列、插列、调顺序都不该让导入失败。
const TYPE_IN = {
  专注: 'focus', 短休息: 'short', 长休息: 'long',
  focus: 'focus', short: 'short', long: 'long',
}
const KIND_IN = { 内部: 'internal', 外部: 'external', internal: 'internal', external: 'external' }
const truthy = (v) => v === true || v === 1 || v === '是' || v === 'true' || v === '1' || v === 'TRUE'
const numOf = (v) => {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}
const textOf = (v) => (v === null || v === undefined ? '' : String(v)).trim()

// 时间解析：只认两种能确定的东西 —— ISO/本地时间字符串（我们导出的就是这种），
// 以及毫秒时间戳数字。**不猜 Excel 日期序列号**：猜错就是几十年，宁可跳过并告警。
function parseTime(v) {
  if (v === null || v === undefined || v === '') return null
  if (typeof v === 'number') return v > 1e11 ? Math.round(v) : null
  const t = Date.parse(String(v))
  return Number.isFinite(t) ? t : null
}

export class ReportService extends Service {
  static provide = 'report'
  static inject = ['store', 'timer']

  constructor(ctx, config) {
    super(ctx, 'report')
    this.config = config || {}
    this.outDir = this.config.outDir || 'output'
  }

  [Service.init]() {
    this.ctx.logger.info('report: 就绪（xlsx 表=%s）', !!this.ctx.get('table'))
    return () => {}
  }

  _table() {
    const t = this.ctx.get('table')
    if (!t) throw new Error(NO_TABLE_MSG)
    return t
  }

  available() {
    return !!this.ctx.get('table')
  }

  // 全量导出的时间跨度：从最早一条会话算到今天。
  // 注意别用"会话条数"或固定天数糊弄 —— 跨度决定「每日」表有多少行、统计窗口有多长。
  spanDays() {
    let earliest = Date.now()
    for (const s of this.ctx.store.sessions || []) {
      const t = s.startAt || 0
      if (t && t < earliest) earliest = t
    }
    const days = Math.ceil((Date.now() - earliest) / 86400000) + 1
    return Math.min(Math.max(days, 1), MAX_DAYS)
  }

  // 周报：最近 N 天
  weekly({ days = 7 } = {}) {
    const d = Math.min(Math.max(Math.trunc(Number(days)) || 7, 1), MAX_DAYS)
    return this._export({ days: d, scope: `最近 ${d} 天`, name: 'pomodmer-weekly-' + today() + '.xlsx' })
  }

  // 全量导出：所有会话 + 计划外事件（"我要在 Excel 里自己分析"的场景）
  full() {
    const days = this.spanDays()
    return this._export({
      days,
      scope: '全部',
      name: 'pomodmer-all-' + today() + '.xlsx',
      all: true,
      includeUnplanned: true,
    })
  }

  // 月报：整月 + 「本月 vs 上月」对比表（month 形如 '2026-08'，缺省为当前月）
  month({ month } = {}) {
    const now = new Date()
    const target = month ? this._parseMonth(month) : { y: now.getFullYear(), m: now.getMonth() }
    const win = this._monthWindow(target.y, target.m)
    const prev = this._monthWindow(
      target.m === 0 ? target.y - 1 : target.y,
      target.m === 0 ? 11 : target.m - 1,
    )
    return this._export({
      scope: win.label,
      name: `pomodmer-month-${win.tag}.xlsx`,
      window: win,
      includeUnplanned: true,
      compareWith: prev,
    })
  }

  // 自定义区间（含首尾两天，均为本地日期 YYYY-MM-DD）
  range({ from, to } = {}) {
    const win = this._rangeWindow(from, to)
    return this._export({
      scope: win.label,
      name: `pomodmer-range-${win.fromKey}_${win.toKey}.xlsx`,
      window: win,
      includeUnplanned: true,
    })
  }

  _parseMonth(s) {
    const m = /^(\d{4})-(\d{1,2})$/.exec(String(s || '').trim())
    if (!m) throw badInput(`month 需要 YYYY-MM 格式，收到：${s}`)
    const y = Number(m[1])
    const mm = Number(m[2])
    if (mm < 1 || mm > 12) throw badInput(`month 的月份必须在 1-12，收到：${s}`)
    return { y, m: mm - 1 }
  }

  // [当月 1 日 00:00, 月末 23:59:59.999]；若是**当前月**则截到此刻
  // （把还没发生的日子算进"活跃天数/平均每天"会得出误导性的低值）
  _monthWindow(y, m) {
    const from = new Date(y, m, 1, 0, 0, 0, 0)
    const monthEnd = new Date(y, m + 1, 0, 23, 59, 59, 999)
    const now = Date.now()
    const to = Math.min(monthEnd.getTime(), now)
    const toDate = new Date(Math.max(to, from.getTime()))
    const tag = `${y}-${String(m + 1).padStart(2, '0')}`
    return {
      from: from.getTime(),
      to: toDate.getTime(),
      fromKey: dayKey(from),
      toKey: dayKey(toDate),
      dayCount: Math.round((new Date(toDate.getFullYear(), toDate.getMonth(), toDate.getDate()) - from) / 86400000) + 1,
      tag,
      label: `${tag}（${dayKey(from)} ~ ${dayKey(toDate)}）`,
    }
  }

  _rangeWindow(from, to) {
    const parse = (s, field) => {
      const m = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(String(s || '').trim())
      if (!m) throw badInput(`${field} 需要 YYYY-MM-DD 格式，收到：${s}`)
      const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 0, 0, 0, 0)
      if (Number.isNaN(d.getTime()) || d.getMonth() !== Number(m[2]) - 1 || d.getDate() !== Number(m[3])) {
        throw badInput(`${field} 不是合法日期：${s}`)
      }
      return d
    }
    const d1 = parse(from, 'from')
    const d2 = parse(to || from, 'to')
    if (d2.getTime() < d1.getTime()) throw badInput(`区间起点晚于终点：${from} > ${to}`)
    const dayCount = Math.round((d2 - d1) / 86400000) + 1
    if (dayCount > MAX_DAYS) throw badInput(`区间跨度过大：${dayCount} 天 > ${MAX_DAYS} 天上限`)
    const end = new Date(d2.getFullYear(), d2.getMonth(), d2.getDate(), 23, 59, 59, 999)
    return {
      from: d1.getTime(),
      to: end.getTime(),
      fromKey: dayKey(d1),
      toKey: dayKey(d2),
      dayCount,
      label: `${dayKey(d1)} ~ ${dayKey(d2)}（${dayCount} 天）`,
    }
  }

  // 任意区间的聚合。为什么不复用 timer.stats()：那个口径永远是"截至今天最近 N 天"，
  // 而月度/自定义区间是显式的 [from, to]（可以是过去的任意一段），两者的"每日"与"总数"都不同。
  // 日切桶按**本地日**（与 UI、与存档一致），且用日期构造逐天推进 —— 加 86400000 跨 DST 会错位。
  _aggregate(sessions, from, to) {
    const inWin = sessions.filter((s) => {
      const t = s.startAt || 0
      return t >= from && t <= to
    })
    const byDay = new Map()
    const start = new Date(from)
    start.setHours(0, 0, 0, 0)
    const end = new Date(to)
    end.setHours(0, 0, 0, 0)
    for (let d = new Date(start); d.getTime() <= end.getTime(); d = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1)) {
      byDay.set(dayKey(d), { date: dayKey(d), completed: 0, abandoned: 0, focusMs: 0 })
    }

    const taskById = new Map(this.ctx.store.tasks.map((t) => [t.id, t]))
    const byTaskMap = new Map()
    const total = { completed: 0, abandoned: 0, focusMs: 0 }
    for (const s of inWin) {
      const day = byDay.get(dayKey(s.startAt))
      if (s.type !== 'focus') continue // 休息不计入"番茄完成数/专注时长"
      if (s.completed) {
        total.completed++
        total.focusMs += s.actualMs || 0
        if (day) { day.completed++; day.focusMs += s.actualMs || 0 }
        if (s.taskId) {
          const t = taskById.get(s.taskId)
          const title = t ? t.title : '（已删除的任务）'
          const rec = byTaskMap.get(title) || { title, estimate: t ? t.estimate : 0, spent: 0, done: t ? !!t.done : false }
          rec.spent++
          byTaskMap.set(title, rec)
        }
      } else {
        total.abandoned++
        if (day) day.abandoned++
      }
    }

    const days = [...byDay.values()]
    const unplanned = (this.ctx.store.unplanned || [])
      .filter((u) => (u.at || 0) >= from && (u.at || 0) <= to)
      .sort((a, b) => (b.at || 0) - (a.at || 0))
    return {
      sessions: inWin,
      days,
      total,
      activeDays: days.filter((d) => d.completed > 0 || d.abandoned > 0).length,
      byTask: [...byTaskMap.values()].sort((a, b) => b.spent - a.spent),
      unplanned,
    }
  }

  async _export({ days = 7, scope, name, all = false, includeUnplanned = false, window = null, compareWith = null }) {
    const table = this._table()
    const store = this.ctx.store
    const file = resolve(process.cwd(), this.outDir, name)
    mkdirSync(dirname(file), { recursive: true })

    // 两条口径（"最近 N 天/全部" 与 "显式区间"）只在**数据视图**上不同，建表逻辑完全共用：
    // 概览固定 9 行、其余各表的列与格式也一致，避免两套建表代码各自漂移。
    let sessions
    let dayRows
    let byTask
    let unplanned
    let overview
    let stats = null
    let agg = null
    if (window) {
      agg = this._aggregate(store.sessions || [], window.from, window.to)
      sessions = agg.sessions
      dayRows = agg.days.map((d) => [d.date, d.completed, d.abandoned, mins(d.focusMs)])
      byTask = agg.byTask
      unplanned = agg.unplanned
      overview = [
        ['统计区间', window.label],
        ['完成番茄', agg.total.completed],
        ['专注总时长(分钟)', mins(agg.total.focusMs)],
        ['活跃天数', agg.activeDays],
        ['作废番茄', agg.total.abandoned],
        ['计划外事件', unplanned.length],
        ['平均每天(分钟)', Math.round(mins(agg.total.focusMs) / Math.max(1, window.dayCount))],
        ['会话条数', agg.sessions.length],
        ['生成时间', localIso(Date.now())],
      ]
      days = window.dayCount
    } else {
      stats = this.ctx.timer.stats({ days })
      sessions = all
        ? (store.sessions || []).slice()
        : (store.sessions || []).filter((s) => (s.startAt || 0) >= Date.now() - days * 86400000)
      dayRows = stats.recent.map((d) => [d.date, d.completed, d.abandoned, mins(d.focusMs)])
      byTask = stats.byTask
      unplanned = (store.unplanned || []).slice().sort((a, b) => (b.at || 0) - (a.at || 0))
      overview = [
        ['统计区间', scope],
        ['完成番茄', stats.total.completed],
        ['专注总时长(分钟)', mins(stats.total.focusMs)],
        ['连续天数', stats.streak],
        ['今日完成', stats.today.completed],
        ['今日专注(分钟)', mins(stats.today.focusMs)],
        ['今日中断', stats.today.interrupts],
        ['计划外事件', (store.unplanned || []).length],
        ['生成时间', localIso(Date.now())],
      ]
    }

    const titleOf = (id) => {
      const t = store.tasks.find((x) => x.id === id)
      return t ? t.title : ''
    }
    const sheets = []

    // ---- 表 1：概览 ----
    sheets.push('概览')
    await table.createWorkbook(file, '概览')
    await table.writeRows(file, '概览', 1, 1, [['指标', '值']])
    // 第 2 列混了文本/数字/日期：类型声明只对"能解析的字符串"生效，其余原样写入
    await table.writeRows(file, '概览', 2, 1, overview, { colTypes: ['text', 'datetime'] })
    await table.setNumberFormat(file, '概览', [{ range: 'B10', format: DATETIME_FMT }])
    await table.styleHeader(file, '概览', 1, 2, { fill: 'FFE24B4A' })
    await table.setColumnWidth(file, '概览', 1, 20)
    await table.setColumnWidth(file, '概览', 2, 30)

    // ---- 表 2：每日 ----
    sheets.push('每日')
    await table.addSheet(file, '每日')
    await table.writeRows(file, '每日', 1, 1, [['日期', '完成番茄', '作废', '专注(分钟)']])
    await table.writeRows(file, '每日', 2, 1, dayRows, { colTypes: ['date', 'number', 'number', 'number'] })
    if (dayRows.length) {
      await table.setNumberFormat(file, '每日', [{ range: `A2:A${dayRows.length + 1}`, format: DATE_FMT }])
    }
    await table.styleHeader(file, '每日', 1, 4, { fill: 'FF4472C4' })
    await table.setColumnWidth(file, '每日', 1, 14)
    await table.setColumnWidth(file, '每日', 2, 12)
    await table.setColumnWidth(file, '每日', 3, 10)
    await table.setColumnWidth(file, '每日', 4, 14)

    // ---- 表 3：会话明细 ----
    sheets.push('会话')
    await table.addSheet(file, '会话')
    await table.writeRows(file, '会话', 1, 1, [['开始', '结束', '类型', '时长(分钟)', '完成', '中断', '原因', '任务']])
    const sessRows = sessions.map((s) => [
      localIso(s.startAt), localIso(s.endAt), TYPE[s.type] || s.type,
      mins(s.actualMs), s.completed ? '是' : '否', s.interrupts || 0, s.reason || '', titleOf(s.taskId),
    ])
    await table.writeRows(file, '会话', 2, 1, sessRows, {
      colTypes: ['datetime', 'datetime', 'text', 'number', 'text', 'number', 'text', 'text'],
    })
    if (sessRows.length) {
      await table.setNumberFormat(file, '会话', [
        { range: `A2:B${sessRows.length + 1}`, format: DATETIME_FMT },
        { range: `D2:D${sessRows.length + 1}`, format: '0' },
      ])
    }
    await table.styleHeader(file, '会话', 1, 8, { fill: 'FF548235' })
    for (let c = 1; c <= 8; c++) await table.setColumnWidth(file, '会话', c, c <= 2 ? 20 : 12)

    // ---- 表 4：任务 ----
    sheets.push('任务')
    await table.addSheet(file, '任务')
    await table.writeRows(file, '任务', 1, 1, [['任务', '预估番茄', '实际番茄', '已完成']])
    const taskRows = byTask.map((t) => [t.title, t.estimate || 1, t.spent || 0, t.done ? '是' : '否'])
    await table.writeRows(file, '任务', 2, 1, taskRows.length ? taskRows : [[EMPTY_TASKS, 0, 0, '']],
      { colTypes: ['text', 'number', 'number', 'text'] })
    await table.styleHeader(file, '任务', 1, 4, { fill: 'FFBA7517' })
    await table.setColumnWidth(file, '任务', 1, 34)
    for (let c = 2; c <= 4; c++) await table.setColumnWidth(file, '任务', c, 12)

    // ---- 表 5（全量/月度/区间）：计划外事件 ----
    // 这些记录原先只有 JSON 导出带得走，人在 Excel 里看不到；现在凡是"全量口径"的导出都带上。
    if (includeUnplanned) {
      sheets.push('计划外事件')
      await table.addSheet(file, '计划外事件')
      await table.writeRows(file, '计划外事件', 1, 1, [['时间', '类型', '备注', '阶段', '任务']])
      const rows = unplanned.map((u) => [
        localIso(u.at), KIND[u.kind] || u.kind || '', u.note || '',
        TYPE[u.phase] || u.phase || '', titleOf(u.taskId),
      ])
      await table.writeRows(file, '计划外事件', 2, 1, rows || [['', '', EMPTY_UNPLANNED, '', '']], {
        colTypes: ['datetime', 'text', 'text', 'text', 'text'],
      })
      if (rows.length) {
        await table.setNumberFormat(file, '计划外事件', [{ range: `A2:A${rows.length + 1}`, format: DATETIME_FMT }])
      }
      await table.styleHeader(file, '计划外事件', 1, 5, { fill: 'FF7030A0' })
      await table.setColumnWidth(file, '计划外事件', 1, 20)
      await table.setColumnWidth(file, '计划外事件', 2, 10)
      await table.setColumnWidth(file, '计划外事件', 3, 40)
      await table.setColumnWidth(file, '计划外事件', 4, 10)
      await table.setColumnWidth(file, '计划外事件', 5, 22)
    }

    // ---- 表 6（仅月报）：本月 vs 上月对比 ----
    if (compareWith) {
      const prev = this._aggregate(store.sessions || [], compareWith.from, compareWith.to)
      const rows = [
        ['完成番茄', agg.total.completed, prev.total.completed],
        ['专注总时长(分钟)', mins(agg.total.focusMs), mins(prev.total.focusMs)],
        ['活跃天数', agg.activeDays, prev.activeDays],
        ['作废番茄', agg.total.abandoned, prev.total.abandoned],
        ['计划外事件', unplanned.length, prev.unplanned.length],
        ['会话条数', agg.sessions.length, prev.sessions.length],
      ].map(([label, cur, before]) => {
        const delta = cur - before
        const pct = before === 0 ? (cur === 0 ? '—' : '+∞') : (delta >= 0 ? '+' : '') + Math.round((delta / before) * 100) + '%'
        return [label, cur, before, (delta >= 0 ? '+' : '') + delta, pct]
      })
      sheets.push('对比')
      await table.addSheet(file, '对比')
      await table.writeRows(file, '对比', 1, 1, [['指标', '本月', '上月', '变化', '变化率']])
      await table.writeRows(file, '对比', 2, 1, rows, {
        colTypes: ['text', 'number', 'number', 'number', 'text'],
      })
      await table.styleHeader(file, '对比', 1, 5, { fill: 'FFC00000' })
      await table.setColumnWidth(file, '对比', 1, 22)
      for (let c = 2; c <= 5; c++) await table.setColumnWidth(file, '对比', c, 12)
    }

    // ---- 隐藏表：给"回灌"用的机器元数据 ----
    // 为什么必须有：xlsx 单元格里存的是**本地墙上时间**（不带时区偏移），换台机器导入会整体平移
    // （实测：上海导出 → UTC 机器导入 = +480 分钟，正好等于时差）。这里记两样东西：
    //   _meta   ：导出端时区偏移（分钟，东为正）等上下文；
    //   _epochs ：逐行的绝对时刻（毫秒）—— 未被编辑的行直接用它还原，跨时区、跨夏令时都精确。
    await table.addSheet(file, '_meta', { hidden: true })
    await table.writeRows(file, '_meta', 1, 1, [['key', 'value']])
    await table.writeRows(file, '_meta', 2, 1, [
      ['app', 'pomodmer'],
      ['scope', window ? window.label : scope],
      ['exportedAt', localIso(Date.now())],
      ['tzOffsetMinutes', -new Date().getTimezoneOffset()],
      ['sessions', sessions.length],
      ['unplanned', includeUnplanned ? unplanned.length : 0],
    ], { colTypes: ['text', 'text'] })

    const epochRows = sessions.map((s, i) => ['会话', i + 2, s.startAt || 0, s.endAt || 0])
    if (includeUnplanned) unplanned.forEach((u, i) => epochRows.push(['计划外事件', i + 2, u.at || 0, '']))
    await table.addSheet(file, '_epochs', { hidden: true })
    await table.writeRows(file, '_epochs', 1, 1, [['表', '行', 'startMs', 'endMs']])
    if (epochRows.length) {
      await table.writeRows(file, '_epochs', 2, 1, epochRows, { colTypes: ['text', 'number', 'number', 'number'] })
    }

    // 每张表都冻结表头：几十上百行会话明细往下翻时，没有表头等于看天书
    for (const s of sheets) await table.freezePanes(file, s, 'A2')

    await table.save(file)

    const summary = {
      completed: window ? agg.total.completed : stats.total.completed,
      focusMinutes: mins(window ? agg.total.focusMs : stats.total.focusMs),
    }
    if (stats) summary.streak = stats.streak
    if (agg) summary.activeDays = agg.activeDays

    return {
      file,
      days,
      scope,
      sheets,
      sessions: sessions.length,
      unplanned: includeUnplanned ? unplanned.length : undefined,
      tzOffsetMinutes: -new Date().getTimezoneOffset(),
      summary,
    }
  }

  // ================= P3：从 xlsx 回灌（去重追加，永不删已有记录）=================
  // 设计取舍：
  //   1) 认表头名不认列序 —— 表是给人改的，改列序不该导致导入失败或错位；
  //   2) 只新增 + 有限更新（任务的预估/完成状态），**不删任何东西**；
  //   3) 先给预演（新增/更新/跳过各多少、哪些行被跳过及原因），确认后再落库；
  //   4) 幂等：同一份表连导两次，第二次全部跳过（靠自然键去重，不靠"记得别点两次"）。
  async importXlsx(file, { mode = 'preview' } = {}) {
    const parsed = await this._parseXlsx(file)
    const plan = this._plan(parsed)
    if (mode !== 'apply') return this._summarize(plan, 'preview')
    return this._commit(plan, 'apply')
  }

  // 读回三张表 → 规范成库内结构（解析不了的行走 warnings，不静默丢）
  async _parseXlsx(file) {
    const table = this._table()
    const warnings = []
    // 不带表名调用 sheetMeta：不会"顺手创建"工作表，还能拿到全部表名
    const meta = await table.sheetMeta(file)
    const names = meta.sheets || []
    const out = { tasks: [], sessions: [], unplanned: [], warnings, sheets: names }

    const read = async (name) => {
      if (!names.includes(name)) return null
      const back = await table.readSheet(file, name)
      return back.rows || []
    }
    const headerOf = (rows) => {
      const head = (rows[0] || []).map(textOf)
      const idx = {}
      head.forEach((h, i) => { if (h && idx[h] === undefined) idx[h] = i })
      return idx
    }
    const cell = (row, idx, name) => (idx[name] === undefined ? null : row[idx[name]])

    // 隐藏元数据（我们自己导出的文件才有；用户自制的表没有 → 退回旧行为，不报错）
    let metaTz = null
    if (names.includes('_meta')) {
      const metaRows = (await table.readSheet(file, '_meta')).rows || []
      for (const r of metaRows.slice(1)) {
        if (textOf(r[0]) === 'tzOffsetMinutes') {
          const n = numOf(r[1])
          if (n !== null) metaTz = n
        }
      }
    }
    const epochMap = new Map()
    if (names.includes('_epochs')) {
      const epochRows = (await table.readSheet(file, '_epochs')).rows || []
      for (const r of epochRows.slice(1)) {
        const s = numOf(r[2])
        const e = numOf(r[3])
        epochMap.set(textOf(r[0]) + ':' + numOf(r[1]), { start: s, end: e })
      }
    }
    if (metaTz !== null || epochMap.size) {
      this.ctx.logger.info('report: 回灌读到元数据（tzOffset=%s 分钟，逐行 epoch=%d 条）',
        metaTz === null ? '无' : metaTz, epochMap.size)
    }

    // ---- 任务 ----
    const taskRows = await read('任务')
    if (taskRows) {
      const idx = headerOf(taskRows)
      if (idx['任务'] === undefined) {
        warnings.push('「任务」表没有「任务」列，已跳过该表')
      } else {
        for (let i = 1; i < taskRows.length; i++) {
          const title = textOf(cell(taskRows[i], idx, '任务'))
          if (!title || title === EMPTY_TASKS) continue // 空表占位行不是任务
          out.tasks.push({
            title,
            estimate: numOf(cell(taskRows[i], idx, '预估番茄')),
            spent: numOf(cell(taskRows[i], idx, '实际番茄')),
            done: idx['已完成'] === undefined ? null : truthy(cell(taskRows[i], idx, '已完成')),
            row: i + 1,
          })
        }
      }
    }

    // ---- 会话 ----
    const sessRows = await read('会话')
    if (sessRows) {
      const idx = headerOf(sessRows)
      if (idx['开始'] === undefined || idx['类型'] === undefined) {
        warnings.push('「会话」表缺少「开始」或「类型」列，已跳过该表')
      } else {
        for (let i = 1; i < sessRows.length; i++) {
          const row = sessRows[i]
          const ep = epochMap.get('会话:' + (i + 1))
          const rawStart = cell(row, idx, '开始')
          const naiveStart = parseTime(rawStart)
          const startAt = naiveStart === null ? null : fixInstant(rawStart, naiveStart, ep ? ep.start : null, metaTz)
          const type = TYPE_IN[textOf(cell(row, idx, '类型'))]
          if (!startAt || !type) {
            warnings.push(`「会话」第 ${i + 1} 行缺少可解析的开始时间或类型（类型=${textOf(cell(row, idx, '类型')) || '空'}），已跳过`)
            continue
          }
          const rawEnd = cell(row, idx, '结束')
          const naiveEnd = parseTime(rawEnd)
          const endAt = naiveEnd === null ? null : fixInstant(rawEnd, naiveEnd, ep ? ep.end : null, metaTz)
          const minutes = numOf(cell(row, idx, '时长(分钟)'))
          out.sessions.push({
            startAt,
            endAt: endAt || startAt,
            type,
            actualMs: minutes === null ? 0 : Math.max(0, Math.round(minutes * 60000)),
            completed: truthy(cell(row, idx, '完成')),
            interrupts: numOf(cell(row, idx, '中断')) || 0,
            reason: textOf(cell(row, idx, '原因')) || null,
            taskTitle: textOf(cell(row, idx, '任务')),
            row: i + 1,
          })
        }
      }
    }

    // ---- 计划外事件 ----
    const unpRows = await read('计划外事件')
    if (unpRows) {
      const idx = headerOf(unpRows)
      if (idx['时间'] === undefined) {
        warnings.push('「计划外事件」表没有「时间」列，已跳过该表')
      } else {
        for (let i = 1; i < unpRows.length; i++) {
          const row = unpRows[i]
          const ep = epochMap.get('计划外事件:' + (i + 1))
          const rawAt = cell(row, idx, '时间')
          const naiveAt = parseTime(rawAt)
          const at = naiveAt === null ? null : fixInstant(rawAt, naiveAt, ep ? ep.start : null, metaTz)
          const note = textOf(cell(row, idx, '备注'))
          if (!at) {
            // 空表占位行：静默跳过，别拿它去刷告警
            if (note && note !== EMPTY_UNPLANNED) {
              warnings.push(`「计划外事件」第 ${i + 1} 行时间无法解析（${textOf(cell(row, idx, '时间'))}），已跳过`)
            }
            continue
          }
          out.unplanned.push({
            at,
            kind: KIND_IN[textOf(cell(row, idx, '类型'))] || 'internal',
            note,
            phase: TYPE_IN[textOf(cell(row, idx, '阶段'))] || null,
            taskTitle: textOf(cell(row, idx, '任务')),
            row: i + 1,
          })
        }
      }
    }

    if (!taskRows && !sessRows && !unpRows) {
      throw new Error('文件里没有可识别的表（需要「任务」/「会话」/「计划外事件」至少一张；可用本应用的 xlsx 导出作为模板）')
    }
    return out
  }

  // 预演：算出"会新增/会更新/会跳过"各多少（纯读，不落库）
  _plan(parsed) {
    const store = this.ctx.store
    const taskByTitle = new Map(store.tasks.map((t) => [t.title.trim(), t]))
    // 同一份表里同一个标题出现多行时**只认第一次**：否则两行取值不同就会互相打架，
    // 每导一次把预估改一次（振荡），而"重复导入结果一致"是回灌功能最基本的承诺。
    const inFile = new Map()
    const tasks = { add: [], update: [], skip: 0 }
    for (const t of parsed.tasks) {
      const first = inFile.get(t.title)
      if (first) {
        tasks.skip++
        if (first.estimate !== t.estimate || (first.done !== null && t.done !== null && first.done !== t.done)) {
          parsed.warnings.push(`「任务」表里「${t.title}」出现多次且取值不一致（第 ${first.row} 行 vs 第 ${t.row} 行），按首次出现的值处理`)
        }
        continue
      }
      inFile.set(t.title, t)
      const hit = taskByTitle.get(t.title)
      if (!hit) {
        tasks.add.push(t)
        continue
      }
      const patch = {}
      if (t.estimate !== null && t.estimate !== hit.estimate) patch.estimate = Math.max(1, t.estimate)
      if (t.done !== null && !!hit.done !== !!t.done) patch.done = !!t.done
      if (Object.keys(patch).length) tasks.update.push({ id: hit.id, title: hit.title, patch })
      else tasks.skip++
    }

    // 时间比对必须带秒级容差：xlsx 里的时间只有秒精度（手打的更是如此），而库里的记录带毫秒。
    // 按毫秒精确比对的话，"导出后原样导回"会把每一条记录都当成新记录再插一遍 —— 历史翻倍。
    // 容差取 ±2 秒：番茄钟一条记录动辄几分钟，同类型两条记录差 2 秒内现实中不可能出现。
    const TOL = 2
    const nearKey = (at, tag) => Math.floor(at / 1000) + '|' + tag
    const hasNear = (set, at, tag) => {
      const base = Math.floor(at / 1000)
      for (let d = -TOL; d <= TOL; d++) if (set.has(base + d + '|' + tag)) return true
      return false
    }

    const seenSess = new Set(store.sessions.map((s) => nearKey(s.startAt, s.type)))
    const sessions = { add: [], skip: 0 }
    for (const s of parsed.sessions) {
      if (hasNear(seenSess, s.startAt, s.type)) sessions.skip++
      else { sessions.add.push(s); seenSess.add(nearKey(s.startAt, s.type)) }
    }

    const seenUnp = new Set(store.unplanned.map((u) => nearKey(u.at, u.note)))
    const unplanned = { add: [], skip: 0 }
    for (const u of parsed.unplanned) {
      if (hasNear(seenUnp, u.at, u.note)) unplanned.skip++
      else { unplanned.add.push(u); seenUnp.add(nearKey(u.at, u.note)) }
    }

    return { tasks, sessions, unplanned, warnings: parsed.warnings, sheets: parsed.sheets }
  }

  // 落库：只 push / 有限 update，绝不 splice —— 回灌是"补录"，不是"重置"
  _commit(plan, mode) {
    const store = this.ctx.store
    const summary = this._summarize(plan, mode) // 先算好数字再改数据，报告与动作同源

    store.update((d) => {
      const now = Date.now()
      for (const t of plan.tasks.add) {
        d.tasks.push({
          id: randomUUID(),
          title: t.title,
          estimate: Math.max(1, t.estimate ?? 1),
          spent: Math.max(0, t.spent ?? 0),
          done: !!t.done,
          createdAt: now,
        })
      }
      for (const u of plan.tasks.update) {
        const t = d.tasks.find((x) => x.id === u.id)
        if (t) Object.assign(t, u.patch)
      }
      const titleToId = new Map(d.tasks.map((t) => [t.title.trim(), t.id]))
      for (const s of plan.sessions.add) {
        d.sessions.push({
          id: randomUUID(),
          type: s.type,
          taskId: s.taskTitle ? (titleToId.get(s.taskTitle) || null) : null,
          // 计划时长在 xlsx 里没有这一列（导出也没写）：用实际时长兜底，
          // 免得留下一堆 plannedMs=0 的记录把将来的"实际/计划"对比算成除零。
          plannedMs: s.actualMs,
          startAt: s.startAt,
          endAt: s.endAt,
          actualMs: s.actualMs,
          completed: s.completed,
          interrupts: s.interrupts,
          reason: s.reason,
        })
      }
      for (const u of plan.unplanned.add) {
        d.unplanned.push({
          id: randomUUID(),
          kind: u.kind,
          note: u.note,
          at: u.at,
          phase: u.phase,
          taskId: u.taskTitle ? (titleToId.get(u.taskTitle) || null) : null,
        })
      }
    })

    this.ctx.logger.info('report: xlsx 回灌完成 tasks +%d/~%d sessions +%d unplanned +%d',
      summary.tasks.add, summary.tasks.update, summary.sessions.add, summary.unplanned.add)
    return summary
  }

  _summarize(plan, mode) {
    return {
      mode,
      sheets: plan.sheets,
      tasks: { add: plan.tasks.add.length, update: plan.tasks.update.length, skip: plan.tasks.skip },
      sessions: { add: plan.sessions.add.length, skip: plan.sessions.skip },
      unplanned: { add: plan.unplanned.add.length, skip: plan.unplanned.skip },
      warnings: plan.warnings,
      sample: {
        tasks: plan.tasks.add.slice(0, 3).map((t) => t.title),
        sessions: plan.sessions.add.slice(0, 3).map((s) => `${TYPE[s.type] || s.type} @ ${localIso(s.startAt)}`),
        unplanned: plan.unplanned.add.slice(0, 3).map((u) => `${KIND[u.kind] || u.kind}：${u.note}`),
      },
    }
  }
}

export default ReportService
