// ReportService —— xlsx 导出，挂到 ctx.report
// 两种产物共用同一套构建逻辑（同一层 ctx.table，宿主自己不碰 Excel）：
//   weekly({ days })  周报：最近 N 天（四张表：概览 / 每日 / 会话 / 任务）
//   full()            全量导出：从第一条会话到今天（再加一张「计划外事件」）
// 分工：JSON 导出（/api/export）用来**回灌备份**，xlsx 导出来给**人看和二次分析**。
// table 是**可选依赖**：不 inject，调用时才 ctx.get('table')，缺失给出可执行的修复提示。
// 启用方式：启动时探测到 Python + openpyxl 就自动带上（boot.mjs 的 resolveConfigPath），
// 也可用 POMODMER_CONFIG=cordis.with-xlsx.json 强制启用 / POMODMER_NO_XLSX=1 主动关闭。
import { Service } from 'cordis'
import { resolve, dirname } from 'node:path'
import { mkdirSync } from 'node:fs'

const NO_TABLE_MSG = 'xlsx 导出需要 table 插件：当前清单没挂表格能力（未探测到 Python + openpyxl，或用 POMODMER_NO_XLSX=1 主动关闭）。装好 Python + openpyxl 后重启即自动启用，也可 POMODMER_CONFIG=cordis.with-xlsx.json 强制启用'

const TYPE = { focus: '专注', short: '短休息', long: '长休息' }
const KIND = { internal: '内部', external: '外部' }
const DATETIME_FMT = 'yyyy-mm-dd hh:mm'
const DATE_FMT = 'yyyy-mm-dd'
const MAX_DAYS = 3650 // 十年：防脏数据（比如一条 1970 年的时间戳）把每日表撑爆

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

  async _export({ days, scope, name, all = false, includeUnplanned = false }) {
    const table = this._table()
    const store = this.ctx.store
    const stats = this.ctx.timer.stats({ days })

    const sessions = all
      ? (store.sessions || []).slice()
      : (store.sessions || []).filter((s) => (s.startAt || 0) >= Date.now() - days * 86400000)
    const file = resolve(process.cwd(), this.outDir, name)
    mkdirSync(dirname(file), { recursive: true })

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
    await table.writeRows(file, '概览', 2, 1, [
      ['统计区间', scope],
      ['完成番茄', stats.total.completed],
      ['专注总时长(分钟)', mins(stats.total.focusMs)],
      ['连续天数', stats.streak],
      ['今日完成', stats.today.completed],
      ['今日专注(分钟)', mins(stats.today.focusMs)],
      ['今日中断', stats.today.interrupts],
      ['计划外事件', (store.unplanned || []).length],
      ['生成时间', localIso(Date.now())],
    ], { colTypes: ['text', 'datetime'] })
    await table.setNumberFormat(file, '概览', [{ range: 'B10', format: DATETIME_FMT }])
    await table.styleHeader(file, '概览', 1, 2, { fill: 'FFE24B4A' })
    await table.setColumnWidth(file, '概览', 1, 20)
    await table.setColumnWidth(file, '概览', 2, 30)

    // ---- 表 2：每日 ----
    sheets.push('每日')
    await table.addSheet(file, '每日')
    await table.writeRows(file, '每日', 1, 1, [['日期', '完成番茄', '作废', '专注(分钟)']])
    const dayRows = stats.recent.map((d) => [d.date, d.completed, d.abandoned, mins(d.focusMs)])
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
    const taskRows = stats.byTask.map((t) => [t.title, t.estimate || 1, t.spent || 0, t.done ? '是' : '否'])
    await table.writeRows(file, '任务', 2, 1, taskRows.length ? taskRows : [['（无任务）', 0, 0, '']],
      { colTypes: ['text', 'number', 'number', 'text'] })
    await table.styleHeader(file, '任务', 1, 4, { fill: 'FFBA7517' })
    await table.setColumnWidth(file, '任务', 1, 34)
    for (let c = 2; c <= 4; c++) await table.setColumnWidth(file, '任务', c, 12)

    // ---- 表 5（仅全量导出）：计划外事件 ----
    // 这些记录原先只有 JSON 导出带得走，人在 Excel 里看不到；全量导出把它们补上。
    const unplanned = (store.unplanned || []).slice().sort((a, b) => (b.at || 0) - (a.at || 0))
    if (includeUnplanned) {
      sheets.push('计划外事件')
      await table.addSheet(file, '计划外事件')
      await table.writeRows(file, '计划外事件', 1, 1, [['时间', '类型', '备注', '阶段', '任务']])
      const rows = unplanned.map((u) => [
        localIso(u.at), KIND[u.kind] || u.kind || '', u.note || '',
        TYPE[u.phase] || u.phase || '', titleOf(u.taskId),
      ])
      await table.writeRows(file, '计划外事件', 2, 1, rows || [['', '', '（无记录）', '', '']], {
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

    // 每张表都冻结表头：几十上百行会话明细往下翻时，没有表头等于看天书
    for (const s of sheets) await table.freezePanes(file, s, 'A2')

    await table.save(file)

    return {
      file,
      days,
      scope,
      sheets,
      sessions: sessions.length,
      unplanned: includeUnplanned ? unplanned.length : undefined,
      summary: {
        completed: stats.total.completed,
        focusMinutes: mins(stats.total.focusMs),
        streak: stats.streak,
      },
    }
  }
}

export default ReportService
