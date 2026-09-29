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
    await table.writeRows(file, '任务', 2, 1, taskRows.length ? taskRows : [[EMPTY_TASKS, 0, 0, '']],
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
          const startAt = parseTime(cell(row, idx, '开始'))
          const type = TYPE_IN[textOf(cell(row, idx, '类型'))]
          if (!startAt || !type) {
            warnings.push(`「会话」第 ${i + 1} 行缺少可解析的开始时间或类型（类型=${textOf(cell(row, idx, '类型')) || '空'}），已跳过`)
            continue
          }
          const endAt = parseTime(cell(row, idx, '结束'))
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
          const at = parseTime(cell(row, idx, '时间'))
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
