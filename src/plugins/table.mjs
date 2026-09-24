// TableService —— Cordis 服务，挂到 ctx.table
// 它是"构造器插件"：被 Cordis 实例化后通过 Service 基类提供 ctx.table；
// 内部 spawn 一个 Python OpenPyXL worker（JsonRpcBridge），所有表格操作经 JSON-RPC 转发。
import { Service } from 'cordis'
import { JsonRpcBridge } from '../core/bridge.mjs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const SCRIPT = resolve(__dirname, '../../python/rpc_server.py')

export function resolvePythonBin(config) {
  if (config && config.pythonBin) return config.pythonBin
  if (process.env.PYTHON_BIN) return process.env.PYTHON_BIN
  // 本机已装 OpenPyXL 3.1.5 的解释器；找不到再退化到 PATH 里的 python
  const candidates = ['E:/Python314/python.exe', 'C:/Python314/python.exe', 'python3', 'python']
  return candidates[0]
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
      ctx.logger.debug('python worker exited (code ' + code + ')')
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
