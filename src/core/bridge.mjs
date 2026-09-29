// JsonRpcBridge —— Cordis 宿主与 Python OpenPyXL worker 之间的 JSON-RPC stdio 桥
// 协议：每行一个 JSON-RPC 2.0 对象；响应按 id 匹配 pending；stdout 仅承载协议。
import { spawn } from 'node:child_process'
import { sep } from 'node:path'
import readline from 'node:readline'

/**
 * 把 pythonBin 拆成 [可执行文件, ...前置参数]。
 *
 * 解释器不一定是单个路径：Windows 官方启动器就是 `py -3` 这种"命令 + 参数"的形态。
 * 直接把它塞给 spawn 会拼成一个不存在的程序名，塞进 cmd 时加引号同理 ——
 * 结果是这一条候选永远不会生效（自发现里"看起来支持、其实从不命中"的坑）。
 *
 * 判定规则：含路径分隔符 = 字面路径（可能带空格，绝不拆）；否则按空白拆词。
 */
export function pythonCommandParts(pythonBin) {
  const s = String(pythonBin || '').trim()
  if (!s) return ['']
  if (s.includes('/') || s.includes('\\')) return [s]
  const parts = s.split(/\s+/).filter(Boolean)
  return parts.length ? parts : [s]
}

export class JsonRpcBridge {
  constructor(pythonBin, scriptPath) {
    this.pythonBin = pythonBin
    this.scriptPath = scriptPath
    this.child = null
    this.pending = new Map()
    this.nextId = 1
    this.onExit = null
  }

  // 同步创建子进程并返回 "已 spawn" 的 Promise（拿到 pid 即 resolve）
  start() {
    if (this.child) return Promise.resolve(this.child.pid)
    const [bin, ...preArgs] = pythonCommandParts(this.pythonBin)
    this.child = spawn(bin, [...preArgs, '-u', this.scriptPath], {
      stdio: ['pipe', 'pipe', 'pipe'],
      // 编码纪律：本桥一律以 UTF-8 写管道（child.stdin.write(str) 就是 UTF-8），
      // 而 Windows 中文环境里 Python 默认按区域编码 gbk/cp936 解 stdio ——
      // 中文会被解成乱码，甚至退化成本不该存在的孤立代理字符，
      // 一路潜伏到 openpyxl 落盘才炸（lxml: surrogates not allowed）。
      // worker 脚本内也有一道 reconfigure 兜底，两道都要：
      // 脚本兜底管"谁来启动都对"，env 兜底管"将来新加的 py 脚本也自动对"。
      env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' },
    })

    this.child.on('error', (err) => {
      // 启动失败（如 python 不存在）：reject 所有 pending
      for (const [, { reject }] of this.pending) reject(err)
      this.pending.clear()
    })

    this.child.stderr.on('data', (d) => {
      process.stderr.write('[py] ' + d.toString())
    })

    const rl = readline.createInterface({ input: this.child.stdout })
    rl.on('line', (line) => {
      line = line.trim()
      if (!line) return
      let msg
      try {
        msg = JSON.parse(line)
      } catch {
        return
      }
      if (msg.id != null && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id)
        this.pending.delete(msg.id)
        if (msg.error) {
          reject(new Error(msg.error.message + '\n' + (msg.error.data || '')))
        } else {
          resolve(msg.result)
        }
      }
    })

    this.child.on('exit', (code) => {
      for (const [, { reject }] of this.pending) reject(new Error('python worker exited (code ' + code + ')'))
      this.pending.clear()
      if (this.onExit) this.onExit(code)
    })

    if (this.child.pid) return Promise.resolve(this.child.pid)
    return new Promise((resolve) => this.child.on('spawn', () => resolve(this.child.pid)))
  }

  call(method, params) {
    if (!this.child) this.start()
    const id = this.nextId++
    const p = new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
    })
    this.child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n')
    return p
  }

  // 优雅关停：发 exit 通知 + 关闭 stdin（EOF 触发 python 自行退出），800ms 兜底 SIGKILL
  // 幂等：已被调用过（或 stdin 已关闭）则直接返回，避免 write-after-end 崩溃。
  async stop() {
    if (!this.child || this._stopped) return
    this._stopped = true
    const child = this.child
    try {
      if (child.stdin && !child.stdin.destroyed && child.stdin.writable) {
        child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'exit' }) + '\n')
        child.stdin.end()
      }
    } catch {
      /* ignore */
    }
    setTimeout(() => {
      try {
        if (!child.killed) child.kill('SIGKILL')
      } catch {
        /* ignore */
      }
    }, 800)
    await new Promise((r) => setTimeout(r, 900))
  }
}
