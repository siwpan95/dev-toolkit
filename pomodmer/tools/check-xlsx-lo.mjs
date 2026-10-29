#!/usr/bin/env node
// check-xlsx-lo.mjs —— 用**另一个实现**（LibreOffice）验收我们导出的 xlsx
//
// 为什么要有它：整套测试里其他环节都是 openpyxl（写）与 openpyxl（读）——
// 同一个人写、同一个人读，"没问题"这件事证明力有限。这里让 LibreOffice 的 Calc
// 导入过滤器真的打开文件，独立回答四个问题：
//   1) 能不能正常打开（有修复痕迹的文件会在这里暴露）；
//   2) 图表在不在（LO 自己解析 chart XML，而不是听 openpyxl 自述）；
//   3) 隐藏表是否真的隐藏；
//   4) 日期是"真日期"还是文本（LO 给的是序列号就说明是真日期）。
//
// 用法：
//   node tools/check-xlsx-lo.mjs                 # 自造数据 → 生成月报 → 交给 LibreOffice 验
//   node tools/check-xlsx-lo.mjs --file x.xlsx   # 验一个已存在的文件
//   --keep  保留临时目录与 soffice；--no-pdf 不导出 PDF；--pdf <路径> 指定 PDF 输出
//   POMODMER_SOFFICE=<soffice 可执行路径>  显式指定 LibreOffice（找不到就自动跳过，退出码 0）
import { spawn, spawnSync } from 'node:child_process'
import { existsSync, mkdtempSync, rmSync, writeFileSync, readFileSync, copyFileSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, delimiter, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { bootHost, stopHost } from '../src/boot.mjs'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..')

let failed = 0
const ok = (cond, msg, extra = '') => {
  if (cond) console.log('  [ok] ' + msg)
  else { failed++; console.log('  [FAIL] ' + msg + (extra ? ' -> ' + extra : '')) }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const argOf = (name) => {
  const i = process.argv.indexOf(name)
  return i >= 0 ? process.argv[i + 1] : null
}
const KEEP = process.argv.includes('--keep')
const WANT_PDF = !process.argv.includes('--no-pdf')

// ---------- 找 LibreOffice（不硬编码盘符：环境变量 → PATH → 常见目录 → 逐个就绪盘符探测）----------
function driveLetters() {
  if (process.platform !== 'win32') return []
  const out = []
  for (let c = 65; c <= 90; c++) {
    const d = String.fromCharCode(c)
    try { if (existsSync(d + ':/')) out.push(d) } catch { /* ignore */ }
  }
  return out
}

function findSoffice() {
  const names = process.platform === 'win32' ? ['soffice.exe'] : ['soffice']
  const cands = []
  if (process.env.POMODMER_SOFFICE) cands.push(process.env.POMODMER_SOFFICE)
  for (const dir of (process.env.PATH || '').split(delimiter)) {
    if (!dir) continue
    for (const n of names) cands.push(resolve(dir, n))
  }
  if (process.platform === 'win32') {
    for (const d of driveLetters()) {
      for (const root of ['Libre', 'LibreOffice', 'Program Files/LibreOffice', 'Program Files (x86)/LibreOffice']) {
        cands.push(`${d}:/${root}/program/soffice.exe`)
      }
    }
    const pf = process.env.ProgramFiles || 'C:/Program Files'
    const pf86 = process.env['ProgramFiles(x86)'] || 'C:/Program Files (x86)'
    cands.push(resolve(pf, 'LibreOffice/program/soffice.exe'), resolve(pf86, 'LibreOffice/program/soffice.exe'))
  } else {
    cands.push('/usr/bin/soffice', '/usr/local/bin/soffice',
      '/Applications/LibreOffice.app/Contents/MacOS/soffice')
  }
  return cands.find((p) => p && existsSync(p)) || null
}

// LibreOffice 自带的 python（带 uno）；找不到就退回系统 python3
function findLoPython(soffice) {
  const dir = dirname(soffice)
  const cands = process.platform === 'win32'
    ? [resolve(dir, 'python.exe')]
    : [resolve(dir, 'python'), '/usr/bin/python3', '/usr/local/bin/python3']
  for (const p of cands) {
    if (!existsSync(p)) continue
    const r = spawnSync(p, ['-c', 'import uno'], { stdio: 'ignore' })
    if (r.status === 0) return p
  }
  return null
}

function freePort() {
  return 2002 + Math.floor(Math.random() * 500)
}

const soffice = findSoffice()
if (!soffice) {
  console.log('  [info] 没找到 LibreOffice：跳过（可用 POMODMER_SOFFICE=<soffice 路径> 指定，例如 F:\\Libre\\program\\soffice.exe）')
  process.exit(0)
}
const loPython = findLoPython(soffice)
if (!loPython) {
  console.log('  [info] 找到 LibreOffice 但没有带 uno 的 python：跳过（Linux 需装 python3-uno）')
  process.exit(0)
}
console.log(`=== LibreOffice 独立验收 ===`)
console.log(`   soffice  : ${soffice}`)
console.log(`   LO python: ${loPython}`)

const dir = mkdtempSync(join(tmpdir(), 'pom-lo-'))
const profile = join(dir, 'profile')
const resultJson = join(dir, 'lo-result.json')

// ---------- 准备被测文件 ----------
let xlsx = argOf('--file')
if (xlsx) {
  xlsx = resolve(xlsx)
  console.log(`   被测文件 : ${xlsx}（--file 指定）`)
} else {
  const store = join(dir, 'store.json')
  const now = Date.now()
  const sessions = []
  for (let i = 0; i < 14; i++) {
    const startAt = now - (13 - i) * 86400000 + 9 * 3600000
    sessions.push({
      id: 's' + i, type: 'focus', taskId: null, plannedMs: 1500000,
      startAt, endAt: startAt + 1500000, actualMs: 1500000, completed: true, interrupts: 0, reason: null,
    })
  }
  writeFileSync(store, JSON.stringify({ version: 1, settings: {}, tasks: [], sessions, unplanned: [], runtime: { phase: 'idle', running: false } }))
  const cfg = join(dir, 'cordis.json')
  writeFileSync(cfg, JSON.stringify({ entries: [
    { id: 'store', name: './src/plugins/store.mjs', config: { file: store } },
    { id: 'timer', name: './src/plugins/timer.mjs' },
    { id: 'http', name: './src/plugins/http.mjs', config: { host: '127.0.0.1', port: 0, open: false } },
    { id: 'table', name: './src/plugins/table.mjs' },
    { id: 'report', name: './src/plugins/report.mjs', config: { outDir: dir.replace(/\\/g, '/') } },
  ]}, null, 2))
  const ctx = await bootHost({ config: cfg })
  if (!ctx.table || !ctx.report) {
    console.log('  [info] 本机没启用表格能力（没探测到 Python + openpyxl），无法生成被测文件，跳过')
    await stopHost()
    rmSync(dir, { recursive: true, force: true })
    process.exit(0)
  }
  const out = await ctx.report.month()
  await stopHost()
  xlsx = join(dir, 'fixture.xlsx')
  copyFileSync(out.file, xlsx)
  console.log(`   被测文件 : 现场生成月报 -> ${xlsx.split(/[\\/]/).pop()}（${statSync(xlsx).size} 字节）`)
}

const pdf = process.argv.includes('--no-pdf')
  ? null
  : (argOf('--pdf') || join(KEEP ? dir : process.env.TEMP || dir, 'pomodmer-lo-preview.pdf'))

// ---------- 起 headless soffice + UNO socket ----------
const port = freePort()
const inst = spawn(soffice, [
  '--headless', '--norestore', '--invisible', '--nologo', '--nodefault', '--nofirststartwizard',
  `-env:UserInstallation=file:///${profile.replace(/\\/g, '/')}`,
  `--accept=socket,host=127.0.0.1,port=${port};urp;`,
], { stdio: 'ignore' })

const stopLo = async () => {
  try { inst.kill() } catch { /* ignore */ }
  await sleep(500)
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/IM', 'soffice.bin', '/F'], { stdio: 'ignore' })
  }
}

let result = null
try {
  // 等 UNO 端口可用（最多 ~30s，冷启动较慢）
  let up = false
  for (let i = 0; i < 60 && !up; i++) {
    await sleep(500)
    const probe = spawnSync(loPython, ['-c',
      'import sys, uno\n' +
      'from com.sun.star.beans import PropertyValue\n' +
      'try:\n' +
      `    uno.getComponentContext().ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", uno.getComponentContext()).resolve("uno:socket,host=127.0.0.1,port=${port};urp;StarOffice.ComponentContext")\n` +
      '    print("UP")\n' +
      'except Exception:\n' +
      '    print("DOWN")\n',
    ], { encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
    up = /UP/.test(probe.stdout || '')
  }
  ok(up, 'LibreOffice 无头实例与 UNO 通道就绪', `port=${port}`)
  if (!up) throw new Error('LibreOffice 未在预期时间内就绪')

  const args = [join(__dirname, 'lo-check.py'), xlsx, String(port), resultJson]
  if (pdf) args.push('--pdf', pdf)
  const resaved = join(dir, 'lo-resaved.xlsx')
  args.push('--resave', resaved)
  const r = spawnSync(loPython, args, { encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
  if (r.status !== 0 || !existsSync(resultJson)) {
    throw new Error('lo-check.py 失败：' + ((r.stderr || r.stdout || '').trim().slice(0, 400) || 'exit ' + r.status))
  }
  result = JSON.parse(readFileSync(resultJson, 'utf8'))
  result.resaved = existsSync(resaved) ? resaved : null
} catch (e) {
  failed++
  console.log('  [FAIL] LibreOffice 验收过程异常 -> ' + e.message)
} finally {
  await stopLo()
}

if (result) {
  const s = result.sheets
  const byName = new Map(s.map((x) => [x.name, x]))
  console.log('  [info] LO 读到 ' + result.sheet_count + ' 张表：' +
    s.map((x) => `${x.name}${x.visible ? '' : '(隐藏)'}${x.charts ? `[${x.charts}图]` : ''}`).join(' / '))
  console.log('  [info] 打开后 isModified=' + result.modified_after_load + '（LO 会因良性原因置位，仅作参考，不作判据）')
  ok(s.length >= 6, '可见表 + 隐藏元数据表都在', String(s.length))
  ok(byName.has('概览') && byName.has('每日') && byName.has('会话') && byName.has('任务'), '四张业务表都在')
  ok(byName.has('_meta') && byName.get('_meta').visible === false, '_meta 存在且是隐藏表（LO 独立确认）')
  ok(byName.has('_epochs') && byName.get('_epochs').visible === false, '_epochs 存在且是隐藏表')
  const daily = byName.get('每日')
  ok(daily && daily.charts === 2, '「每日」表里有 2 个图表（LO 自己解析 chart XML）',
    daily ? String(daily.charts) : '缺表')
  // 日期是"真日期"还是文本：LO 对真日期给的是数值（Excel 序列号），文本则 b2_type/value 都空
  const sess = byName.get('会话')
  ok(sess && typeof sess.b2_value === 'number' && sess.b2_value > 40000,
    '「会话」开始列是**真日期**（LO 读出序列号，不是文本）',
    sess ? JSON.stringify({ type: sess.b2_type, value: sess.b2_value, text: sess.b2_text }) : '缺表')
  ok(byName.get('概览') && byName.get('概览').a1 === '指标', '「概览」A1 = 指标（中文表头原样读到）',
    byName.get('概览') ? JSON.stringify(byName.get('概览').a1) : '缺表')
  if (pdf && existsSync(pdf)) {
    const size = statSync(pdf).size
    ok(size > 5000, '导出 PDF 成功（图表渲染的旁证，可肉眼查看）', `${pdf} ${size} 字节`)
  } else if (pdf) {
    ok(false, '导出 PDF 成功', pdf + ' 不存在')
  }

  // ---- 跨实现往返：LibreOffice 用自己的 xlsx 过滤器重存 → 再用 openpyxl 读回 ----
  // 这一步比"openpyxl 自己读写自己"强得多：若我们的图表/隐藏表依赖了 openpyxl 的私有写法，
  // LO 重存时就会丢掉，这里立刻能看出来。
  if (result.resaved) {
    const { probeTableWorker } = await import('../src/plugins/table.mjs')
    const pyBin = probeTableWorker(null, { timeoutMs: 2500, budgetMs: 4000 }).bin
    if (!pyBin) {
      console.log('  [info] 没有可用的 Python+openpyxl，跳过重存文件的复核')
    } else {
      const probeCode = [
        'import sys, json, openpyxl',
        'wb = openpyxl.load_workbook(sys.argv[1])',
        'out = {"sheets": wb.sheetnames,',
        '       "charts": {n: len(wb[n]._charts) for n in wb.sheetnames},',
        '       "hidden": [n for n in wb.sheetnames if wb[n].sheet_state != "visible"]}',
        'print(json.dumps(out, ensure_ascii=False))',
      ].join('\n')
      const pr = spawnSync(pyBin, ['-c', probeCode, result.resaved],
        { encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
      let info = null
      try { info = JSON.parse((pr.stdout || '').trim()) } catch { /* 下面按失败处理 */ }
      console.log('  [info] LO 重存后再用 openpyxl 读回：' + JSON.stringify(info))
      ok(info && info.charts && info.charts['每日'] === 2,
        '跨实现往返：LO 重存的 xlsx 里图表仍在（说明图表不是 openpyxl 私有写法）',
        JSON.stringify(info && info.charts))
      ok(info && Array.isArray(info.hidden) && info.hidden.includes('_meta') && info.hidden.includes('_epochs'),
        '跨实现往返：隐藏表仍是隐藏表', JSON.stringify(info && info.hidden))
    }
  } else {
    console.log('  [info] 没有重存文件，跳过跨实现往返复核')
  }
}

if (KEEP) console.log('  [info] --keep：临时目录保留在 ' + dir)
else rmSync(dir, { recursive: true, force: true })

console.log('\n=== 结果 ===')
console.log(failed === 0 ? '  ALL PASS' : '  FAILED: ' + failed + ' 项')
process.exit(failed === 0 ? 0 : 1)
