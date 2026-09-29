// TableService —— Cordis 服务，挂到 ctx.table
// 它是"构造器插件"：被 Cordis 实例化后通过 Service 基类提供 ctx.table；
// 内部 spawn 一个 Python OpenPyXL worker（JsonRpcBridge），所有表格操作经 JSON-RPC 转发。
import { Service } from 'cordis'
import { JsonRpcBridge } from '../core/bridge.mjs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve, sep } from 'node:path'
import { existsSync } from 'node:fs'
import { execSync } from 'node:child_process'

const __dirname = dirname(fileURLToPath(import.meta.url))
const SCRIPT = resolve(__dirname, '../../python/rpc_server.py')

// 自发现 Python 解释器（全程不硬编码任何本机盘符）：
//   1) cordis.json 里 table 条目的 config.pythonBin（显式优先）
//   2) 环境变量 PYTHON_BIN
//   3) 扫描 PATH + 常见安装目录，挑第一个能 `import openpyxl` 的
//   4) 兜底回退到 PATH 里的 python3 / python（让其自行报缺依赖，错误信息更明确）
// 换机 / 换系统 / 装到任意盘都能直接用，无需改代码。
// 这套探测有两个消费者，都走 probeTableWorker：
//   - TableService 构造时解析 worker 解释器（resolvePythonBin）；
//   - boot.mjs 启动时判断"本机到底能不能用表格能力"，据此决定插件清单（见 resolveConfigPath）。
const WINDOWS_COMMON = [
  'C:/Python314/python.exe',
  'C:/Python313/python.exe',
  'C:/Python312/python.exe',
  'C:/Python311/python.exe',
  'D:/Python314/python.exe',
  'D:/Python313/python.exe',
]
const POSIX_COMMON = [
  '/usr/bin/python3',
  '/usr/local/bin/python3',
  '/opt/homebrew/bin/python3',
  '/usr/bin/python',
]

function pathCandidates() {
  const out = []
  const pathEnv = process.env.PATH || ''
  const sepCh = process.platform === 'win32' ? ';' : ':'
  const names = process.platform === 'win32'
    ? ['python.exe', 'python3.exe', 'pythonw.exe']
    : ['python3', 'python']
  for (const dir of pathEnv.split(sepCh)) {
    if (!dir) continue
    for (const n of names) {
      const p = resolve(dir, n)
      try { if (existsSync(p)) out.push(p) } catch { /* ignore */ }
    }
  }
  return out
}

function commonCandidates() {
  if (process.platform === 'win32') {
    const localApp = process.env.LOCALAPPDATA || ''
    const extra = []
    if (localApp) {
      // Microsoft Store / 官方安装器常见落点
      extra.push(resolve(localApp, 'Programs/Python/Python314/python.exe'))
      extra.push(resolve(localApp, 'Programs/Python/Python313/python.exe'))
      extra.push(resolve(localApp, 'Programs/Python/Python312/python.exe'))
    }
    return [...WINDOWS_COMMON, ...extra]
  }
  return POSIX_COMMON
}

function canImportOpenpyxl(bin, timeoutMs = 8000) {
  try {
    execSync('"' + bin + '" -c "import openpyxl"', { stdio: 'ignore', timeout: timeoutMs })
    return true
  } catch {
    return false
  }
}

// 候选解释器（去重后保持优先级）：显式指定 > PYTHON_BIN > PATH 扫描 > 常见安装目录 > 裸命令名
function candidateList(config) {
  const raw = []
  if (config && config.pythonBin) raw.push(config.pythonBin)
  if (process.env.PYTHON_BIN) raw.push(process.env.PYTHON_BIN)
  raw.push(...pathCandidates(), ...commonCandidates(), 'python3', 'python')
  const seen = new Set()
  return raw.filter((c) => {
    if (!c || seen.has(c)) return false
    seen.add(c)
    return true
  })
}

// 探测结果 memo：一个进程内环境不会变，而每次探测都要 spawn 解释器（本机约 0.3s）。
// 没有 memo 的话，"启动时决定清单"和 TableService 构造会各探一遍，纯属白等。
let probeMemo = { key: null, result: null }

/**
 * 探测本机表格能力：返回 { bin, openpyxl, anyBin }
 *   - bin     能 `import openpyxl` 的解释器；null 表示没有
 *   - anyBin  第一个"看起来存在"的解释器；用来区分"根本没装 Python"与"装了但缺 openpyxl"
 *              （这两种情况给用户的提示完全不同，不能混为一谈）
 *
 * 显式指定（config.pythonBin / PYTHON_BIN）视为权威：只探它、不做跨解释器回退。
 * 否则用户明明指定了某个解释器，却被悄悄换成另一个，排查起来极其费解。
 *
 * opts.timeoutMs 单个候选的探测上限；opts.budgetMs 整轮探测总预算（0=不限）。
 * 启动时的自动探测用较小预算：个别候选（如 Microsoft Store 的 python 占位程序）卡住时，
 * 不能让"锦上添花"的能力探测把应用启动拖成好几秒 —— 探不到就安静退回纯番茄钟清单。
 */
export function probeTableWorker(config, opts = {}) {
  const explicit = (config && config.pythonBin) || process.env.PYTHON_BIN || null
  const key = explicit || '(auto)'
  if (probeMemo.key === key && probeMemo.result && !opts.fresh) return probeMemo.result

  const timeoutMs = opts.timeoutMs || 8000
  const budgetMs = opts.budgetMs || 0
  let result

  if (explicit) {
    result = { bin: explicit, openpyxl: canImportOpenpyxl(explicit, timeoutMs), anyBin: explicit }
  } else {
    const startedAt = Date.now()
    let anyBin = null
    let bin = null
    for (const c of candidateList(config)) {
      if (budgetMs && Date.now() - startedAt > budgetMs) break
      const bare = !c.includes(sep)
      // 裸命令名（python3/python）交给操作系统按 PATH 解析，绝对路径才做存在性检查
      if (!bare && !existsSync(c)) continue
      // anyBin 只认"确认存在"的绝对路径：否则在根本没装 Python 的机器上，
      // 列表尾部的裸名 python3 会让提示误报成"装了 Python 但缺 openpyxl"，指错方向。
      if (!anyBin && !bare) anyBin = c
      if (canImportOpenpyxl(c, timeoutMs)) {
        bin = c
        break
      }
    }
    result = { bin, openpyxl: !!bin, anyBin }
  }

  probeMemo = { key, result }
  return result
}

// TableService 用的解释器解析（语义与改动前一致）：
// 优先能 `import openpyxl` 的；一个都没有时回退到首个"看起来存在"的解释器或 'python3'，
// 让"缺依赖"由 Python 自己报出来（错误信息更明确），而不是在这里变成一句"找不到 Python"。
export function resolvePythonBin(config) {
  const p = probeTableWorker(config)
  return p.openpyxl ? p.bin : p.anyBin || 'python3'
}

export class TableService extends Service {
  static provide = 'table'

  constructor(ctx, config) {
    super(ctx, 'table')
    this.config = config || {}
    const pythonBin = resolvePythonBin(this.config)
    this.bridge = new JsonRpcBridge(pythonBin, SCRIPT)
    this.pid = null
  }

  // Service.init：返回清理函数（fiber dispose 时执行 -> 杀掉 python worker）
  [Service.init]() {
    const bridge = this.bridge
    const ready = bridge.start()
    ready.then((pid) => {
      this.pid = pid
    })
    bridge.onExit = (code) => {
      this.ctx?.logger?.debug?.('python worker exited (code ' + code + ')')
    }
    return () => {
      bridge.stop()
    }
  }

  // ---- RPC 代理方法（与 python/rpc_server.py 的 method 一一对应）----
  ping() {
    return this.bridge.call('ping', {})
  }
  createWorkbook(path, sheet) {
    return this.bridge.call('create_workbook', { path, sheet })
  }
  addSheet(path, name) {
    return this.bridge.call('add_sheet', { path, name })
  }
  writeRows(path, sheet, startRow, startCol, rows) {
    return this.bridge.call('write_rows', { path, sheet, start_row: startRow, start_col: startCol, rows })
  }
  writeCell(path, sheet, row, col, value) {
    return this.bridge.call('write_cell', { path, sheet, row, col, value })
  }
  styleHeader(path, sheet, row, ncols, opts = {}) {
    return this.bridge.call('style_header', { path, sheet, row, ncols, ...opts })
  }
  setColumnWidth(path, sheet, col, width) {
    return this.bridge.call('set_column_width', { path, sheet, col, width })
  }
  readSheet(path, sheet) {
    return this.bridge.call('read_sheet', { path, sheet })
  }
  save(path) {
    return this.bridge.call('save', { path })
  }
  close(path) {
    return this.bridge.call('close', { path })
  }
}

export default TableService
