// demo.mjs —— 端到端演示：用 Cordis 内核 + OpenPyXL 生成一张表格
// 数据源：E:\desk\_extract\cordis-main\packages（即"文件夹中的源码"）
// 产物：output/cordis-packages.xlsx（Packages 表 + Hello 表演示表）
import { bootHost, stopHost } from './boot.mjs'
import { readdirSync, readFileSync, existsSync, mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const SRC = 'E:/desk/_extract/cordis-main/packages'
const OUT = resolve(__dirname, '../output/cordis-packages.xlsx')

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

  const pkgRows = await scanPackages(SRC)
  console.log('[demo] 扫描到 Cordis 包：', pkgRows.length, '个')

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
