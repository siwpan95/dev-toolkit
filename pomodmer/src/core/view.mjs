// view.mjs —— "数据 → 表格行"的纯函数层（不碰文件、不碰 ctx、不需要 Python）
//
// 为什么单独抽出来：xlsx 导出走 Python（ctx.table），CSV/TSV 导出是纯 JS，两条链路必须
// **同一份行数据**，否则"CSV 与同名 xlsx 表一致"就只能靠人工对齐，早晚漂移。
// 这里只做纯转换：给 store/timer 数据与一个区间口径，产出各张表的行 + 该用的单元格类型。
//
// 口径说明：周报/全量沿用 timer.stats() 的"截至今天最近 N 天"；月度/自定义区间是显式 [from,to]
// （可能是过去任意一段），两者"每日桶"与"总数"都不同，所以区间口径自己按**本地日**切桶。
export const MAX_DAYS = 3650 // 十年：防脏数据（比如一条 1970 年的时间戳）把每日表撑爆

export const TYPE_TEXT = { focus: '专注', short: '短休息', long: '长休息' }
export const KIND_TEXT = { internal: '内部', external: '外部' }
export const DATETIME_FMT = 'yyyy-mm-dd hh:mm'
export const DATE_FMT = 'yyyy-mm-dd'

// 空表占位行：给人看的（"这张表这次没内容"），导入时必须认出来并跳过
export const EMPTY_TASKS = '（无任务）'
export const EMPTY_UNPLANNED = '（无记录）'

export const mins = (ms) => Math.round((ms || 0) / 60000)

// 本地时间的 ISO 串（不带时区）：写成 Excel 原生 datetime 时用。
// 不能用 toISOString()：那是 UTC，导出的表在 Excel 里会整体差几个时区。
export function localIso(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

export const today = () => localIso(Date.now()).slice(0, 10)

export function dayKey(ts) {
  const d = new Date(ts)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

// 入参错误（HTTP 层据此回 400，而不是把用户输入问题当服务端故障回 500）
export const badInput = (msg) => Object.assign(new Error(msg), { code: 'BAD_INPUT' })

export function parseMonth(s) {
  const m = /^(\d{4})-(\d{1,2})$/.exec(String(s || '').trim())
  if (!m) throw badInput(`month 需要 YYYY-MM 格式，收到：${s}`)
  const y = Number(m[1])
  const mm = Number(m[2])
  if (mm < 1 || mm > 12) throw badInput(`month 的月份必须在 1-12，收到：${s}`)
  return { y, m: mm - 1 }
}

// [当月 1 日 00:00, 月末 23:59:59.999]；若是**当前月**则截到此刻
// （把还没发生的日子算进"活跃天数/平均每天"会得出误导性的低值）
export function monthWindow(y, m) {
  const from = new Date(y, m, 1, 0, 0, 0, 0)
  const monthEnd = new Date(y, m + 1, 0, 23, 59, 59, 999)
  const toDate = new Date(Math.max(Math.min(monthEnd.getTime(), Date.now()), from.getTime()))
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

export function rangeWindow(from, to) {
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

// 全量跨度：从最早一条会话到今天
export function spanDays(sessions) {
  let earliest = Date.now()
  for (const s of sessions || []) {
    const t = s.startAt || 0
    if (t && t < earliest) earliest = t
  }
  return Math.min(Math.max(Math.ceil((Date.now() - earliest) / 86400000) + 1, 1), MAX_DAYS)
}

// 任意区间聚合（按本地日切桶；用日期构造逐天推进 —— 加 86400000 跨 DST 会错位）
export function aggregate({ sessions, tasks, unplanned, from, to }) {
  const inWin = (sessions || []).filter((s) => {
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

  const taskById = new Map((tasks || []).map((t) => [t.id, t]))
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
  const unp = (unplanned || [])
    .filter((u) => (u.at || 0) >= from && (u.at || 0) <= to)
    .sort((a, b) => (b.at || 0) - (a.at || 0))
  return {
    sessions: inWin,
    days,
    total,
    activeDays: days.filter((d) => d.completed > 0 || d.abandoned > 0).length,
    byTask: [...byTaskMap.values()].sort((a, b) => b.spent - a.spent),
    unplanned: unp,
  }
}

// 每张表的单元格类型（xlsx 写入时把 ISO 串还原成 Excel 原生类型；CSV 只按它判断怎么转义）
export const SHEET_TYPES = {
  概览: ['text', 'datetime'],
  每日: ['date', 'number', 'number', 'number'],
  会话: ['datetime', 'datetime', 'text', 'number', 'text', 'number', 'text', 'text'],
  任务: ['text', 'number', 'number', 'text'],
  计划外事件: ['datetime', 'text', 'text', 'text', 'text'],
  对比: ['text', 'number', 'number', 'number', 'text'],
}

/**
 * 统一视图：给定口径（all / weekly / month / range），产出各张表的行。
 * @param store  提供 sessions / tasks / unplanned
 * @param timerStats  (days) => stats（"截至今天最近 N 天"口径由 TimerService 提供，这里注入以保持纯函数）
 * 返回 { scope, label, days, fileTag, sheets, data, sessions, unplanned, summary, compareWith }
 *   data: { 表名: 行数组（含表头） }
 */
export function buildView({ store, timerStats, scope = 'all', days = 7, month, from, to }) {
  const sessions = store.sessions || []
  const tasks = store.tasks || []
  const allUnplanned = store.unplanned || []
  const titleOf = (id) => {
    const t = tasks.find((x) => x.id === id)
    return t ? t.title : ''
  }

  const wantUnplanned = scope === 'all' || scope === 'month' || scope === 'range'
  const data = {}

  if (scope === 'month' || scope === 'range') {
    let win
    let compareWith = null
    let fileTag
    if (scope === 'month') {
      const nowD = new Date()
      const target = month ? parseMonth(month) : { y: nowD.getFullYear(), m: nowD.getMonth() }
      win = monthWindow(target.y, target.m)
      compareWith = monthWindow(target.m === 0 ? target.y - 1 : target.y, target.m === 0 ? 11 : target.m - 1)
      fileTag = `month-${win.tag}`
    } else {
      win = rangeWindow(from, to)
      fileTag = `range-${win.fromKey}_${win.toKey}`
    }

    const agg = aggregate({ sessions, tasks, unplanned: allUnplanned, from: win.from, to: win.to })
    const overview = [
      ['统计区间', win.label],
      ['完成番茄', agg.total.completed],
      ['专注总时长(分钟)', mins(agg.total.focusMs)],
      ['活跃天数', agg.activeDays],
      ['作废番茄', agg.total.abandoned],
      ['计划外事件', agg.unplanned.length],
      ['平均每天(分钟)', Math.round(mins(agg.total.focusMs) / Math.max(1, win.dayCount))],
      ['会话条数', agg.sessions.length],
      ['生成时间', localIso(Date.now())],
    ]
    const sheets = ['概览', '每日', '会话', '任务']
    data['概览'] = [['指标', '值'], ...overview]
    data['每日'] = [['日期', '完成番茄', '作废', '专注(分钟)'], ...agg.days.map((d) => [d.date, d.completed, d.abandoned, mins(d.focusMs)])]
    data['会话'] = [['开始', '结束', '类型', '时长(分钟)', '完成', '中断', '原因', '任务'],
      ...agg.sessions.map((s) => sessionRow(s, titleOf))]
    data['任务'] = [['任务', '预估番茄', '实际番茄', '已完成'],
      ...(agg.byTask.length ? agg.byTask.map(taskRow) : [[EMPTY_TASKS, 0, 0, '']])]
    if (wantUnplanned) {
      sheets.push('计划外事件')
      data['计划外事件'] = [['时间', '类型', '备注', '阶段', '任务'],
        ...(agg.unplanned.length ? agg.unplanned.map((u) => unplannedRow(u, titleOf)) : [['', '', EMPTY_UNPLANNED, '', '']])]
    }
    let compareRows = null
    if (compareWith) {
      const prev = aggregate({ sessions, tasks, unplanned: allUnplanned, from: compareWith.from, to: compareWith.to })
      compareRows = buildCompare(agg, prev, compareWith)
      sheets.push('对比')
      data['对比'] = [['指标', '本月', '上月', '变化', '变化率'], ...compareRows]
    }
    return {
      scope,
      label: win.label,
      days: win.dayCount,
      fileTag,
      sheets,
      data,
      sessions: agg.sessions,
      unplanned: agg.unplanned,
      summary: { completed: agg.total.completed, focusMinutes: mins(agg.total.focusMs), activeDays: agg.activeDays },
      compareWith,
    }
  }

  // ---- days 口径：weekly / all ----
  const stats = timerStats(scope === 'all' ? spanDays(sessions) : days)
  const inWindow = scope === 'all'
    ? sessions.slice()
    : sessions.filter((s) => (s.startAt || 0) >= Date.now() - days * 86400000)
  const unplanned = allUnplanned.slice().sort((a, b) => (b.at || 0) - (a.at || 0))
  const label = scope === 'all' ? '全部' : `最近 ${days} 天`
  const sheets = ['概览', '每日', '会话', '任务']
  data['概览'] = [['指标', '值'], ...[
    ['统计区间', label],
    ['完成番茄', stats.total.completed],
    ['专注总时长(分钟)', mins(stats.total.focusMs)],
    ['连续天数', stats.streak],
    ['今日完成', stats.today.completed],
    ['今日专注(分钟)', mins(stats.today.focusMs)],
    ['今日中断', stats.today.interrupts],
    ['计划外事件', allUnplanned.length],
    ['生成时间', localIso(Date.now())],
  ]]
  data['每日'] = [['日期', '完成番茄', '作废', '专注(分钟)'],
    ...stats.recent.map((d) => [d.date, d.completed, d.abandoned, mins(d.focusMs)])]
  data['会话'] = [['开始', '结束', '类型', '时长(分钟)', '完成', '中断', '原因', '任务'],
    ...inWindow.map((s) => sessionRow(s, titleOf))]
  data['任务'] = [['任务', '预估番茄', '实际番茄', '已完成'],
    ...(stats.byTask.length ? stats.byTask.map(taskRow) : [[EMPTY_TASKS, 0, 0, '']])]
  if (wantUnplanned) {
    sheets.push('计划外事件')
    data['计划外事件'] = [['时间', '类型', '备注', '阶段', '任务'],
      ...(unplanned.length ? unplanned.map((u) => unplannedRow(u, titleOf)) : [['', '', EMPTY_UNPLANNED, '', '']])]
  }
  return {
    scope,
    label,
    days: scope === 'all' ? spanDays(sessions) : days,
    fileTag: scope === 'all' ? 'all' : 'weekly',
    sheets,
    data,
    sessions: inWindow,
    unplanned,
    summary: { completed: stats.total.completed, focusMinutes: mins(stats.total.focusMs), streak: stats.streak },
    compareWith: null,
  }
}

function sessionRow(s, titleOf) {
  return [
    localIso(s.startAt), localIso(s.endAt), TYPE_TEXT[s.type] || s.type,
    mins(s.actualMs), s.completed ? '是' : '否', s.interrupts || 0, s.reason || '', titleOf(s.taskId),
  ]
}
function taskRow(t) {
  return [t.title, t.estimate || 1, t.spent || 0, t.done ? '是' : '否']
}
function unplannedRow(u, titleOf) {
  return [localIso(u.at), KIND_TEXT[u.kind] || u.kind || '', u.note || '', TYPE_TEXT[u.phase] || u.phase || '', titleOf(u.taskId)]
}
function buildCompare(cur, prev, prevWin) {
  return [
    ['完成番茄', cur.total.completed, prev.total.completed],
    ['专注总时长(分钟)', mins(cur.total.focusMs), mins(prev.total.focusMs)],
    ['活跃天数', cur.activeDays, prev.activeDays],
    ['作废番茄', cur.total.abandoned, prev.total.abandoned],
    ['计划外事件', cur.unplanned.length, prev.unplanned.length],
    ['会话条数', cur.sessions.length, prev.sessions.length],
  ].map(([label, c, p]) => {
    const delta = c - p
    const pct = p === 0 ? (c === 0 ? '—' : '+∞') : (delta >= 0 ? '+' : '') + Math.round((delta / p) * 100) + '%'
    return [label, c, p, (delta >= 0 ? '+' : '') + delta, pct]
  })
}
