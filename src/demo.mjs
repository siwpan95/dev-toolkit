// demo.mjs —— 端到端演示：用 Cordis 内核 + OpenPyXL 生成一张表格
// 数据源（可选）：环境变量 CORDIS_PKG_SRC 或 --src 指向的目录（含若干子目录，每个有 package.json）
//   不设 / 找不到时，回退到内置样例数据，保证任何机器上都能跑通演示。
// 产物：output/cordis-packages.xlsx（Packages 表 + Hello 表演示表）
import { bootHost, stopHost } from './boot.mjs'
import { readdirSync, readFileSync, existsSync, mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { parseArgs } from 'node:util'

const __dirname = dirname(fileURLToPath(import.meta.url))
const OUT = resolve(__dirname, '../output/cordis-packages.xlsx')

const { values: args } = parseArgs({
  options: {
    src: { type: 'string', short: 's' },
  },
})

// 内置样例（无外部源码目录时回退，保证演示可复现、与机器无关）
const SAMPLE_PACKAGES = [
  ['cordis', '4.0.0-rc.10', 'A modern framework for building extensible applications'],
  ['@cordisjs/plugin-loader', '1.0.0-rc.7', 'Declarative plugin host for Cordis'],
  ['@cordisjs/plugin-logger-console', '1.0.0', 'Console exporter for Cordis logger'],
  ['openpyxl', '3.1.5', 'A Python library to read/write Excel 2010 xlsx/xlsm files'],
]

async function scanPackages(dir) {
  const rows = []
  const names = readdirSync(dir, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name)
  for (const name of names) {
    const pj = resolve(dir, name, 'package.json')
    if (existsSync(pj)) {
      const p = JSON.parse(readFileSync(pj, 'utf8'))
      rows.push([p.name || name, p.version || '', p.description || ''])
    }
  }
  rows.sort((a, b) => String(a[0]).localeCompare(String(b[0])))
  return rows
}

function printTable(title, rows, limit = 12) {
  console.log('\n=== ' + title + ' ===')
  const show = rows.slice(0, limit)
  for (const r of show) {
    console.log('  ' + (Array.isArray(r) ? r.map((c) => (c === null || c === undefined ? '' : String(c))).join(' | ') : String(r)))
  }
  if (rows.length > limit) console.log('  ... 共 ' + rows.length + ' 行')
}

async function main() {
  const ctx = await bootHost()
  const table = ctx.table

  const info = await table.ping()
  console.log('[demo] python/openpyxl =>', info.python, '/', info.openpyxl)

  mkdirSync(dirname(OUT), { recursive: true })

  // 数据源可配置：--src 或环境变量 CORDIS_PKG_SRC；缺失则回退内置样例
  const SRC = args.src || process.env.CORDIS_PKG_SRC
  let pkgRows
  if (SRC && existsSync(SRC)) {
    pkgRows = await scanPackages(SRC)
    console.log('[demo] 扫描目录 ' + SRC + ' -> Cordis 包：', pkgRows.length, '个')
  } else {
    pkgRows = SAMPLE_PACKAGES
    console.log('[demo] 未指定/找不到外部源码目录（CORDIS_PKG_SRC），使用内置样例：', pkgRows.length, '条')
  }

  // ---- 表 1：Cordis 包清单 ----
  await table.createWorkbook(OUT, 'Packages')
  const header = ['Package', 'Version', 'Description']
  await table.writeRows(OUT, 'Packages', 1, 1, [header])
  await table.writeRows(OUT, 'Packages', 2, 1, pkgRows)
  await table.styleHeader(OUT, 'Packages', 1, 3, { fill: 'FF4472C4' })
  await table.setColumnWidth(OUT, 'Packages', 1, 34)
  await table.setColumnWidth(OUT, 'Packages', 2, 14)
  await table.setColumnWidth(OUT, 'Packages', 3, 64)

  // ---- 表 2：演示小表 ----
  await table.addSheet(OUT, 'Hello')
  await table.writeRows(OUT, 'Hello', 1, 1, [
    ['#', 'Greeting', 'Lang'],
    [1, '你好，表格世界', 'zh-CN'],
    [2, 'Hello, Table World', 'en'],
    [3, 'Cordis + OpenPyXL', 'app'],
  ])
  await table.styleHeader(OUT, 'Hello', 1, 3, { fill: 'FF548235' })

  await table.save(OUT)

  // ---- 读回校验（不只看文件存在，还要核对内容）----
  const back = await table.readSheet(OUT, 'Packages')
  console.log('[demo] 读回 Packages：', back.max_row, '行 x', back.max_col, '列')
  console.log('[demo] 首数据行原始 JSON：', JSON.stringify(back.rows[1]))
  printTable('Packages（读回前 12 行）', back.rows)

  const hello = await table.readSheet(OUT, 'Hello')
  printTable('Hello（读回）', hello.rows)

  console.log('\n[demo] 文件已生成：', OUT)
  const pyPid = ctx.table ? ctx.table.pid : null
  await stopHost()
  console.log('[demo] 宿主已关停，python worker (pid=' + pyPid + ') 已回收。')
  process.exit(0)
}

main().catch((e) => {
  console.error('[demo] FATAL:', e)
  process.exit(1)
})
