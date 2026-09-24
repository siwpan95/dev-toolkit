// cli.mjs —— 通用表格生成小工具（Cordis 内核 + OpenPyXL）
// 用法：
//   node src/cli.mjs --json input.json --out result.xlsx --sheet Data [--header]
// input.json 支持两种形态：
//   1) 数组的数组（二维表）：[[h1,h2],[v1,v2],...]
//   2) 对象的数组（自动以 key 为表头）：[{a:1,b:2}, ...]
// 数组的数组加 --header 时，第一行视为表头并加样式；对象数组默认带表头。
import { bootHost, stopHost } from './boot.mjs'
import { readFileSync, mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { parseArgs } from 'node:util'

const { values } = parseArgs({
  options: {
    json: { type: 'string', short: 'i' },
    out: { type: 'string', short: 'o', default: 'output/out.xlsx' },
    sheet: { type: 'string', short: 's', default: 'Sheet1' },
    header: { type: 'boolean', short: 'h', default: false },
  },
})

async function main() {
  if (!values.json) {
    console.error('用法: node src/cli.mjs --json input.json --out result.xlsx --sheet Data [--header]')
    process.exit(2)
  }
  const raw = JSON.parse(readFileSync(values.json, 'utf8'))
  const out = resolve(values.out)
  mkdirSync(dirname(out), { recursive: true })

  let header = null
  let rows = []
  if (Array.isArray(raw) && raw.length && typeof raw[0] === 'object' && !Array.isArray(raw[0])) {
    header = Object.keys(raw[0])
    rows = raw.map((o) => header.map((k) => o[k]))
  } else if (Array.isArray(raw)) {
    rows = raw.map((r) => (Array.isArray(r) ? r : [r]))
    if (values.header && rows.length) {
      header = rows.shift()
    }
  } else {
    console.error('不支持的 JSON 形态')
    process.exit(2)
  }

  const ctx = await bootHost()
  const table = ctx.table
  await table.createWorkbook(out, values.sheet)
  let r = 1
  if (header) {
    await table.writeRows(out, values.sheet, r, 1, [header])
    await table.styleHeader(out, values.sheet, r, header.length)
    r++
  }
  await table.writeRows(out, values.sheet, r, 1, rows)
  await table.save(out)
  const back = await table.readSheet(out, values.sheet)
  console.log('[cli] 已生成:', out, '（', back.max_row, '行 x', back.max_col, '列 ）')
  await stopHost()
  process.exit(0)
}

main().catch((e) => {
  console.error('[cli] FATAL:', e)
  process.exit(1)
})
