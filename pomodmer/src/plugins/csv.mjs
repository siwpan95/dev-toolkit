// CsvService —— CSV / TSV 出口，挂到 ctx.csv（**纯 JS，不需要 Python**）
//
// 为什么单独一个服务：xlsx 出口依赖 Python + openpyxl（可选能力），而"把数据导出来"这件事
// 不该被它绑住 —— 没装 Python 的机器也得能把会话导给 Excel / pandas / grep 用。
// 行数据来自 src/core/view.mjs（与 xlsx **同一份来源**），所以"CSV 与同名 xlsx 表一致"
// 是结构上成立的，而不是靠两边人工对齐。
//
// 约定：
//   - 行尾 CRLF、按 RFC 4180 加引号（字段含分隔符/引号/换行时用双引号包裹，内部引号翻倍）；
//   - 默认**带 UTF-8 BOM**（Excel 双击打开 CSV 才不会把中文显示成乱码）；
//     给 pandas/grep 用时传 bom=false 或 URL 上加 &bom=0；
//   - 时间列沿用与 xlsx 相同的 ISO 串（readSheet 读回来也是这个形态，便于逐格比对）。
import { Service } from 'cordis'
import { buildView, badInput } from '../core/view.mjs'

// 表名 → ASCII 文件名/响应头用的 slug：响应头里不能塞非 ASCII（Node 会直接报 ERR_INVALID_CHAR）
export const SHEET_SLUG = {
  概览: 'overview',
  每日: 'daily',
  会话: 'sessions',
  任务: 'tasks',
  计划外事件: 'unplanned',
  对比: 'compare',
}

export function csvCell(v, delimiter) {
  if (v === null || v === undefined) return ''
  const s = typeof v === 'string' ? v : String(v)
  const needsQuote = s.includes(delimiter) || s.includes('"') || s.includes('\n') || s.includes('\r')
  return needsQuote ? '"' + s.replace(/"/g, '""') + '"' : s
}

export function serializeRows(rows, delimiter = ',') {
  return rows.map((r) => r.map((c) => csvCell(c, delimiter)).join(delimiter)).join('\r\n') + '\r\n'
}

export class CsvService extends Service {
  // 注意这里的分号：类字段后面跟一个以 [ 开头的成员（[Service.init]）时，
  // 少了分号会被 ASI 拼成 `['store','timer'][Service.init]()` —— 直接 SyntaxError。
  static provide = 'csv';
  static inject = ['store', 'timer'];

  [Service.init]() {
    return () => {}
  }

  view(opts = {}) {
    return buildView({
      store: this.ctx.store,
      timerStats: (d) => this.ctx.timer.stats({ days: d }),
      ...opts,
    })
  }

  // 生成一段 CSV/TSV 文本（单张表 —— 多表请分多次请求，别自己糊一个 zip）
  render({ sheet = '会话', scope = 'all', days, month, from, to, delimiter = ',', bom } = {}) {
    const view = this.view({ scope, days, month, from, to })
    const rows = view.data[sheet]
    if (!rows) {
      throw badInput(`没有这张表：${String(sheet)}（这份导出可选：${view.sheets.join(' / ')}）`)
    }
    const withBom = bom === undefined ? delimiter === ',' : !!bom
    return {
      text: (withBom ? '\uFEFF' : '') + serializeRows(rows, delimiter),
      sheet,
      slug: SHEET_SLUG[sheet] || 'sheet',
      scope,
      label: view.label,
      fileTag: view.fileTag,
      rows: Math.max(0, rows.length - 1),
      sheets: view.sheets,
    }
  }
}

export default CsvService
