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
  constructor(pythonBin, scriptPath, opts = {}) {
    this.pythonBin = pythonBin
    this.scriptPath = scriptPath
    // 单次调用超时（毫秒）：worker 卡死时，宿主不能跟着无限等待 —— 见 call() 的注释。
    // 默认 15s：正常导出（几千行）在 1s 级，15s 足够宽松，同时把"永久挂起"变成"一次可重试的失败"。
    const t = Number(opts.timeoutMs)
    this.timeoutMs = Number.isFinite(t) && t > 0 ? t : 15000
    // 冷启动宽限：新 worker 的**第一笔**调用要付解释器启动 + openpyxl 导入的账
    // （实测 ~300ms，机器繁忙/杀毒扫描时可能到秒级）。这笔账属于"进程还没起来"，
    // 不该算进"调用预算" —— 否则把超时调小的用户会在冷启动上误杀正常调用。
    const g = Number(opts.coldStartGraceMs)
    this.coldStartGraceMs = Number.isFinite(g) && g >= 0 ? g : 10000
    this._cold = false
    this.child = null
    this.pending = new Map()
    this.nextId = 1
    this.onExit = null
    this.onRestart = null
    this.restarts = 0
    this._stopped = false
  }

  // 同步创建子进程并返回 "已 spawn" 的 Promise（拿到 pid 即 resolve）
  start() {
    if (this.child) return Promise.resolve(this.child.pid)
    const [bin, ...preArgs] = pythonCommandParts(this.pythonBin)
    const child = spawn(bin, [...preArgs, '-u', this.scriptPath], {
      stdio: ['pipe', 'pipe', 'pipe'],
      // 编码纪律：本桥一律以 UTF-8 写管道（child.stdin.write(str) 就是 UTF-8），
      // 而 Windows 中文环境里 Python 默认按区域编码 gbk/cp936 解 stdio ——
      // 中文会被解成乱码，甚至退化成本不该存在的孤立代理字符，
      // 一路潜伏到 openpyxl 落盘才炸（lxml: surrogates not allowed）。
      // worker 脚本内也有一道 reconfigure 兜底，两道都要：
      // 脚本兜底管"谁来启动都对"，env 兜底管"将来新加的 py 脚本也自动对"。
      env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' },
    })
    this.child = child
    this._cold = true // 新进程：下一笔调用享受冷启动宽限

    child.on('error', (err) => {
      // 启动失败（如 python 不存在）：reject 所有 pending
      this._settleAll(err)
    })

    child.stderr.on('data', (d) => {
      process.stderr.write('[py] ' + d.toString())
    })

    const rl = readline.createInterface({ input: child.stdout })
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

    child.on('exit', (code) => {
      // 只处理"当前这个子进程"的退出：重启时旧进程的 exit 会晚到，
      // 不加判断的话会把新进程刚建立的 pending 一起 reject 掉。
      if (this.child === child) {
        // 关键：把引用清空，让下一次 call() 直接拉起新 worker。
        // 否则 this.child 还是个死进程对象，后续调用会往死管道里写，
        // 既收不到响应、也不会触发"重启"，只能干等到超时 —— 白等 15 秒。
        this.child = null
        this._settleAll(new Error('python worker exited (code ' + code + ')'))
      }
      if (this.onExit) this.onExit(code)
    })

    if (child.pid) return Promise.resolve(child.pid)
    return new Promise((resolve) => child.on('spawn', () => resolve(child.pid)))
  }

  /**
   * 发一次调用。三条纪律（都是"worker 出问题时宿主不能陪葬"）：
   *   1) 每次调用都有超时：worker 卡住（死循环、被系统挂起、openpyxl 卡在 IO）时，
   *      没有超时的话这个 Promise 永远不 settle —— HTTP 请求永久挂起，UI 停在"正在生成…"，
   *      而且**之后所有**表格调用一起排队等死，只能重启整个宿主。
   *   2) 超时/写入失败即**重启 worker**：把"整个进程永久残废"降级成"一次可重试的失败"。
   *   3) 写入失败（子进程已死、管道已关）同步抛出的异常也要转成 reject：
   *      调用方（HTTP 层）只会 catch Promise，同步抛出会变成 500 而不是可读错误。
   * 不自动重试：重试有副作用（半份工作簿、重复写入），交给调用方决定要不要再来一次。
   */
  call(method, params) {
    if (this._stopped) return Promise.reject(new Error('bridge 已关闭'))
    if (!this.child) this.start()
    const id = this.nextId++
    // 冷启动宽限只给"新进程的第一笔调用"：那笔账是解释器启动，不是 worker 不干活
    const grace = this._cold ? this.coldStartGraceMs : 0
    this._cold = false
    const budget = this.timeoutMs + grace
    const p = new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id)
        reject(new Error(`python worker 超时（${budget}ms 未响应 ${method}）：已重启 worker，请重试`))
        this._restart('调用超时: ' + method)
      }, budget)
      this.pending.set(id, { resolve, reject, timer, method })
    })
    try {
      this.child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n')
    } catch (e) {
      const entry = this.pending.get(id)
      if (entry) {
        clearTimeout(entry.timer)
        this.pending.delete(id)
      }
      this._restart('写入失败: ' + e.message)
      return Promise.reject(new Error('python worker 写入失败（已重启）：' + e.message))
    }
    return p
  }

  // 全部 pending 一起 reject，并清掉各自的超时定时器（不清的话定时器还会再触发一次重启）
  _settleAll(err) {
    for (const [, entry] of this.pending) {
      clearTimeout(entry.timer)
      entry.reject(err)
    }
    this.pending.clear()
  }

  // 杀掉卡死/已死的 worker 并立刻拉起一个新的。
  // 注意先把 this.child 置空再 kill：旧进程的 exit 回调稍后才到，不能让它影响新进程。
  _restart(reason) {
    if (this._stopped) return null
    const old = this.child
    this.child = null
    this._settleAll(new Error('python worker 已重启（' + reason + '）'))
    try {
      if (old && !old.killed) old.kill('SIGKILL')
    } catch {
      /* ignore */
    }
    this.restarts++
    const ready = this.start()
    if (this.onRestart) {
      try {
        this.onRestart(reason, this.restarts, ready)
      } catch {
        /* 回调不该影响协议 */
      }
    }
    return ready
  }

  // 优雅关停：发 exit 通知 + 关闭 stdin（EOF 触发 python 自行退出），800ms 兜底 SIGKILL
  // 幂等：已被调用过（或 stdin 已关闭）则直接返回，避免 write-after-end 崩溃。
  async stop() {
    if (!this.child || this._stopped) return
    this._stopped = true
    const child = this.child
    this._settleAll(new Error('bridge 已关闭'))
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
