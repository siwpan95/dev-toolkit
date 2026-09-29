// ReportService —— 周报导出（P2），挂到 ctx.report
// 复用既有资产：ctx.table（Cordis -> JSON-RPC stdio -> Python OpenPyXL），宿主自己不碰 Excel。
// table 是**可选依赖**：不 inject，调用时才 ctx.get('table')，缺失给出可执行的修复提示。
// 启用方式：POMODMER_CONFIG=cordis.with-xlsx.json（需要 Python + openpyxl）。
import { Service } from 'cordis'
import { resolve, dirname } from 'node:path'
import { mkdirSync } from 'node:fs'

const NO_TABLE_MSG = 'xlsx 导出需要 table 插件：请用 POMODMER_CONFIG=cordis.with-xlsx.json 启动（需要 Python + openpyxl）'

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

  // 生成周报 xlsx：概览 / 每日 / 会话 / 任务 四张表
  async weekly({ days = 7 } = {}) {
    const table = this._table()
    const timer = this.ctx.timer
    const store = this.ctx.store
    const stats = timer.stats({ days })

    const since = Date.now() - days * 86400000
    const sessions = store.sessions.filter((s) => (s.startAt || 0) >= since)
    const iso = new Date().toISOString().slice(0, 10)
    const file = resolve(process.cwd(), this.outDir, 'pomodmer-weekly-' + iso + '.xlsx')
    mkdirSync(dirname(file), { recursive: true })

    const mins = (ms) => Math.round((ms || 0) / 60000)
    const when = (ts) => (ts ? new Date(ts).toLocaleString('zh-CN', { hour12: false }) : '')

    // ---- 表 1：概览 ----
    await table.createWorkbook(file, '概览')
    await table.writeRows(file, '概览', 1, 1, [['指标', '值']])
    await table.writeRows(file, '概览', 2, 1, [
      ['统计区间', `最近 ${days} 天`],
      ['完成番茄', stats.total.completed],
      ['专注总时长(分钟)', mins(stats.total.focusMs)],
      ['连续天数', stats.streak],
      ['今日完成', stats.today.completed],
      ['今日专注(分钟)', mins(stats.today.focusMs)],
      ['今日中断', stats.today.interrupts],
      ['计划外事件', store.unplanned.length],
      ['生成时间', when(Date.now())],
    ])
    await table.styleHeader(file, '概览', 1, 2, { fill: 'FFE24B4A' })
    await table.setColumnWidth(file, '概览', 1, 20)
    await table.setColumnWidth(file, '概览', 2, 30)

    // ---- 表 2：每日 ----
    await table.addSheet(file, '每日')
    await table.writeRows(file, '每日', 1, 1, [['日期', '完成番茄', '作废', '专注(分钟)']])
    const dayRows = stats.recent.map((d) => [d.date, d.completed, d.abandoned, mins(d.focusMs)])
    await table.writeRows(file, '每日', 2, 1, dayRows)
    await table.styleHeader(file, '每日', 1, 4, { fill: 'FF4472C4' })
    await table.setColumnWidth(file, '每日', 1, 14)
    await table.setColumnWidth(file, '每日', 2, 12)
    await table.setColumnWidth(file, '每日', 3, 10)
    await table.setColumnWidth(file, '每日', 4, 14)

    // ---- 表 3：会话明细 ----
    await table.addSheet(file, '会话')
    await table.writeRows(file, '会话', 1, 1, [['开始', '结束', '类型', '时长(分钟)', '完成', '中断', '原因', '任务']])
    const titleOf = (id) => {
      const t = store.tasks.find((x) => x.id === id)
      return t ? t.title : ''
    }
    const TYPE = { focus: '专注', short: '短休息', long: '长休息' }
    const sessRows = sessions.map((s) => [
      when(s.startAt), when(s.endAt), TYPE[s.type] || s.type,
      mins(s.actualMs), s.completed ? '是' : '否', s.interrupts || 0, s.reason || '', titleOf(s.taskId),
    ])
    await table.writeRows(file, '会话', 2, 1, sessRows)
    await table.styleHeader(file, '会话', 1, 8, { fill: 'FF548235' })
    for (let c = 1; c <= 8; c++) await table.setColumnWidth(file, '会话', c, c <= 2 ? 20 : 12)

    // ---- 表 4：任务 ----
    await table.addSheet(file, '任务')
    await table.writeRows(file, '任务', 1, 1, [['任务', '预估番茄', '实际番茄', '已完成']])
    const taskRows = stats.byTask.map((t) => [t.title, t.estimate || 1, t.spent || 0, t.done ? '是' : '否'])
    await table.writeRows(file, '任务', 2, 1, taskRows.length ? taskRows : [['（无任务）', 0, 0, '']])
    await table.styleHeader(file, '任务', 1, 4, { fill: 'FFBA7517' })
    await table.setColumnWidth(file, '任务', 1, 34)
    for (let c = 2; c <= 4; c++) await table.setColumnWidth(file, '任务', c, 12)

    await table.save(file)

    return {
      file,
      days,
      sheets: ['概览', '每日', '会话', '任务'],
      sessions: sessions.length,
      summary: {
        completed: stats.total.completed,
        focusMinutes: mins(stats.total.focusMs),
        streak: stats.streak,
      },
    }
  }
}

export default ReportService
