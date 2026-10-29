#!/usr/bin/env node
// bench-export.mjs —— 导出链路的大数据基线与时区自检
//
// 用法：
//   node tools/bench-export.mjs [--sessions 3000] [--days 180] [--repeat 1]
//   TZ=UTC node tools/bench-export.mjs --sessions 500      # 换时区跑同一份数据
//
// 做三件事：
//   1) 造 N 条**绝对时刻已知**的会话（不经 HTTP，直接写 store.json，避免把"造数据"的耗时算进去）
//   2) 跑一次全量导出，报耗时 / RSS 增量 / 文件大小 / 「每日」表行数
//   3) 同 TZ 下把导出的文件"原样回灌"（preview）：应当 **0 新增**（派生自 P3 的往返不变量）
//
// 为什么要有它：P5 要求"几千条会话的导出耗时与内存有实测数字"，而不是拍脑袋说"应该很快"；
// 时区则要能换着跑 —— 日期列是 Excel 原生日期，按本机时区渲染，必须能证明"换时区跑结果自洽"。
import { mkdtempSync, writeFileSync, rmSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { bootHost, stopHost } from '../src/boot.mjs'

const arg = (name, dflt) => {
  const i = process.argv.indexOf('--' + name)
  return i >= 0 ? Number(process.argv[i + 1]) : dflt
}
const N = arg('sessions', 3000)
const DAYS = arg('days', 180)
const REPEAT = Math.max(1, arg('repeat', 1))

const dir = mkdtempSync(join(tmpdir(), 'pom-bench-'))
const storeFile = join(dir, 'store.json')
const now = Date.now()
const sessions = []
for (let i = 0; i < N; i++) {
  // 分散在最近 DAYS 天里，且尽量落在不同小时 —— 让「每日」表与日期渲染都真的有活干
  const startAt = now - (i % (DAYS * 24)) * 3600000 - (i % 60) * 60000 - (i % 1000)
  sessions.push({
    id: 's' + i,
    type: i % 5 === 4 ? 'short' : 'focus',
    taskId: null,
    plannedMs: 1500000,
    startAt,
    endAt: startAt + 1500000,
    actualMs: 1500000,
    completed: true,
    interrupts: 0,
    reason: null,
  })
}
writeFileSync(storeFile, JSON.stringify({
  version: 1, settings: {}, tasks: [], sessions, unplanned: [],
  runtime: { phase: 'idle', running: false },
}))

const cfg = join(dir, 'cordis.xlsx.json')
writeFileSync(cfg, JSON.stringify({
  entries: [
    { id: 'store', name: './src/plugins/store.mjs', config: { file: storeFile } },
    { id: 'timer', name: './src/plugins/timer.mjs' },
    { id: 'http', name: './src/plugins/http.mjs', config: { host: '127.0.0.1', port: 0, open: false } },
    { id: 'table', name: './src/plugins/table.mjs' },
    { id: 'report', name: './src/plugins/report.mjs', config: { outDir: dir.replace(/\\/g, '/') } },
  ],
}, null, 2))

const tz = process.env.TZ || '(系统默认)'
console.log(`=== 导出基线：${N} 条会话 / 跨度 ${DAYS} 天 / TZ=${tz} ===`)

const ctx = await bootHost({ config: cfg })
if (!ctx.table || !ctx.report) {
  console.log('  [skip] 本机没启用表格能力（没探测到 Python + openpyxl），基线无法测')
  await stopHost()
  rmSync(dir, { recursive: true, force: true })
  process.exit(0)
}

const rss0 = process.memoryUsage().rss
let out = null
let last = 0
for (let i = 0; i < REPEAT; i++) {
  const t0 = performance.now()
  out = await ctx.report.full()
  last = performance.now() - t0
  const rssNow = process.memoryUsage().rss
  const size = statSync(out.file).size
  const back = await ctx.table.readSheet(out.file, '会话')
  console.log(`  #${i + 1} 导出耗时 ${last.toFixed(0)}ms | 工作簿 ${(size / 1024).toFixed(0)}KB | 会话行数 ${back.max_row} | 「每日」行数 ${(await ctx.table.readSheet(out.file, '每日')).max_row} | 宿主 RSS ${(rssNow / 1048576).toFixed(0)}MB（导出前 ${(rss0 / 1048576).toFixed(0)}MB）`)
}

// 时间渲染自检：第一行「开始」应等于该会话在**本时区**的墙上时间
const firstRow = (await ctx.table.readSheet(out.file, '会话')).rows[1]
const sampleStart = sessions.reduce((a, s) => Math.min(a, s.startAt), Infinity)
const d = new Date(sampleStart)
const p = (n) => String(n).padStart(2, '0')
const expect = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
const hit = (await ctx.table.readSheet(out.file, '会话')).rows.slice(1).find((r) => r[0] === expect)
console.log(`  最早会话 ${sampleStart} 在本时区应渲染为 ${expect} -> ${hit ? '表里命中 ✔' : '未命中 ✘'}`)

// 同 TZ 原样回灌：秒级容差去重，必须一条都不新增
const rt = await ctx.report.importXlsx(out.file, { mode: 'preview' })
console.log(`  同 TZ 原样回灌预览：会话 新增 ${rt.sessions.add} / 跳过 ${rt.sessions.skip} -> ${rt.sessions.add === 0 ? '往返一致 ✔' : '不一致 ✘（跨时区导入会这样）'}`)

await stopHost()
rmSync(dir, { recursive: true, force: true })
