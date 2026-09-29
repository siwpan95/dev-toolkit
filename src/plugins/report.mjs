// ReportService —— xlsx 双向能力，挂到 ctx.report（需要 Python + openpyxl）
// 导出：
//   weekly({days})  周报（最近 N 天）
//   full()          全量（所有会话 + 计划外事件）
//   month({month})  月报（整月 + 本月 vs 上月对比）
//   range({from,to}) 自定义区间
// 导入：
//   importXlsx(file, {mode})  把我们导出的表改完再灌回来 —— 去重追加，永不删已有记录
// 行数据从 src/core/view.mjs 来（纯函数），CSV/TSV 出口（src/plugins/csv.mjs）用同一份来源，
// 所以"CSV 与同名 xlsx 表数据一致"是结构上成立的，而不是靠人工对齐。
// table 是**可选依赖**：不 inject，调用时才 ctx.get('table')，缺失给出可执行的修复提示。
// 启用方式：启动时探测到 Python + openpyxl 就自动带上（boot.mjs 的 resolveConfigPath），
// 也可用 POMODMER_CONFIG=cordis.with-xlsx.json 强制启用 / POMODMER_NO_XLSX=1 主动关闭。
import { Service } from 'cordis'
import { resolve, dirname } from 'node:path'
import { mkdirSync } from 'node:fs'
import { randomUUID } from 'node:crypto'
import {
  buildView, localIso, DATETIME_FMT, DATE_FMT,
} from '../core/view.mjs'

const NO_TABLE_MSG = 'xlsx 导出需要 table 插件：当前清单没挂表格能力（未探测到 Python + openpyxl，或用 POMODMER_NO_XLSX=1 主动关闭）。装好 Python + openpyxl 后重启即自动启用，也可 POMODMER_CONFIG=cordis.with-xlsx.json 强制启用'

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

  // 统一视图（纯函数层）：口径 → 各表行数据
  view({ scope = 'all', days = 7, month, from, to } = {}) {
    return buildView({
      store: this.ctx.store,
      timerStats: (d) => this.ctx.timer.stats({ days: d }),
      scope,
      days,
      month,
      from,
      to,
    })
  }

  weekly({ days = 7 } = {}) {
    const d = Math.min(Math.max(Math.trunc(Number(days)) || 7, 1), 3650)
    const v = this.view({ scope: 'weekly', days: d })
    return this._export(v, { name: 'pomodmer-weekly-' + localIso(Date.now()).slice(0, 10) + '.xlsx' })
  }

  full() {
    const v = this.view({ scope: 'all' })
    return this._export(v, { name: 'pomodmer-all-' + localIso(Date.now()).slice(0, 10) + '.xlsx' })
  }

  month({ month } = {}) {
    const v = this.view({ scope: 'month', month })
    return this._export(v, { name: `pomodmer-${v.fileTag}.xlsx` })
  }

  range({ from, to } = {}) {
    const v = this.view({ scope: 'range', from, to })
    return this._export(v, { name: `pomodmer-${v.fileTag}.xlsx` })
  }

  // 把视图写成一个 xlsx：各表行数据来自 view.mjs，这里只负责"写 + 样式 + 元数据"
  async _export(view, { name }) {
    const table = this._table()
    const file = resolve(process.cwd(), this.outDir, name)
    mkdirSync(dirname(file), { recursive: true })

    const TYPES = { 概览: ['text', 'datetime'], 每日: ['date', 'number', 'number', 'number'], 会话: ['datetime', 'datetime', 'text', 'number', 'text', 'number', 'text', 'text'], 任务: ['text', 'number', 'number', 'text'], 计划外事件: ['datetime', 'text', 'text', 'text', 'text'], 对比: ['text', 'number', 'number', 'number', 'text'] }
    const FILLS = { 概览: 'FFE24B4A', 每日: 'FF4472C4', 会话: 'FF548235', 任务: 'FFBA7517', 计划外事件: 'FF7030A0', 对比: 'FFC00000' }
    const WIDTHS = {
      概览: [20, 30],
      每日: [14, 12, 10, 14],
      会话: [20, 20, 12, 12, 12, 12, 12, 12],
      任务: [34, 12, 12, 12],
      计划外事件: [20, 10, 40, 10, 22],
      对比: [22, 12, 12, 12, 12],
    }

    let first = true
    for (const sheet of view.sheets) {
      const rows = view.data[sheet] || []
      if (first) {
        await table.createWorkbook(file, sheet)
        first = false
      } else {
        await table.addSheet(file, sheet)
      }
      await table.writeRows(file, sheet, 1, 1, rows, { colTypes: TYPES[sheet] })
      const ncols = (rows[0] || []).length
      await table.styleHeader(file, sheet, 1, ncols, { fill: FILLS[sheet] })
      const widths = WIDTHS[sheet] || []
      for (let c = 1; c <= ncols; c++) {
        await table.setColumnWidth(file, sheet, c, widths[c - 1] || 12)
      }
      // 数字格式：概览的"生成时间"是 B10；日期/时间列按表逐列设
      if (sheet === '概览') {
        await table.setNumberFormat(file, sheet, [{ range: 'B10', format: DATETIME_FMT }])
      } else if (sheet === '每日' && rows.length > 1) {
        await table.setNumberFormat(file, sheet, [{ range: `A2:A${rows.length}`, format: DATE_FMT }])
      } else if (sheet === '会话' && rows.length > 1) {
        await table.setNumberFormat(file, sheet, [
          { range: `A2:B${rows.length}`, format: DATETIME_FMT },
          { range: `D2:D${rows.length}`, format: '0' },
        ])
      } else if (sheet === '计划外事件' && rows.length > 1 && rows[1][0]) {
        await table.setNumberFormat(file, sheet, [{ range: `A2:A${rows.length}`, format: DATETIME_FMT }])
      }
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
      ['scope', view.scope],
      ['label', view.label],
      ['exportedAt', localIso(Date.now())],
      ['tzOffsetMinutes', -new Date().getTimezoneOffset()],
      ['sessions', view.sessions.length],
      ['unplanned', view.sheets.includes('计划外事件') ? view.unplanned.length : 0],
    ], { colTypes: ['text', 'text'] })

    const epochRows = view.sessions.map((s, i) => ['会话', i + 2, s.startAt || 0, s.endAt || 0])
    if (view.sheets.includes('计划外事件')) {
      view.unplanned.forEach((u, i) => epochRows.push(['计划外事件', i + 2, u.at || 0, '']))
    }
    await table.addSheet(file, '_epochs', { hidden: true })
    await table.writeRows(file, '_epochs', 1, 1, [['表', '行', 'startMs', 'endMs']])
    if (epochRows.length) {
      await table.writeRows(file, '_epochs', 2, 1, epochRows, { colTypes: ['text', 'number', 'number', 'number'] })
    }

    // 每张可见表都冻结表头：几十上百行会话明细往下翻时，没有表头等于看天书
    for (const s of view.sheets) await table.freezePanes(file, s, 'A2')

    await table.save(file)

    return {
      file,
      days: view.days,
      scope: view.scope,
      label: view.label,
      sheets: view.sheets,
      sessions: view.sessions.length,
      unplanned: view.sheets.includes('计划外事件') ? view.unplanned.length : undefined,
      tzOffsetMinutes: -new Date().getTimezoneOffset(),
      summary: view.summary,
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
        epochMap.set(textOf(r[0]) + ':' + numOf(r[1]), { start: numOf(r[2]), end: numOf(r[3]) })
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
          if (!title || title === '（无任务）') continue // 空表占位行不是任务
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
            if (note && note !== '（无记录）') {
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
    const TYPE = { focus: '专注', short: '短休息', long: '长休息' }
    const KIND = { internal: '内部', external: '外部' }
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
