// HttpService —— 本地接入层，挂到 ctx.http
// 只用 node:http（零新增 npm 依赖）：静态托管 web/ + REST 控制 + SSE 推送。
// 安全：默认只监听 127.0.0.1；静态目录做路径穿越防护；不代理任意路径。
import { Service } from 'cordis'
import { createServer } from 'node:http'
import { readFile, stat, writeFile, unlink } from 'node:fs/promises'
import { resolve, extname, join, sep, basename } from 'node:path'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import { dirname } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const WEB_ROOT = resolve(__dirname, '../../web')

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.png': 'image/png',
}

const MAX_BODY = 1 << 20

export class HttpService extends Service {
  static provide = 'http'
  static inject = ['store', 'timer']

  constructor(ctx, config) {
    super(ctx, 'http')
    this.config = config || {}
    // 优先级：环境变量（CLI 透传）> cordis.json 配置 > 内置默认
    this.host = process.env.POMODMER_HOST || this.config.host || '127.0.0.1'
    // 注意：端口 0（系统分配空闲端口）必须保留，不能用 || 吞掉
    const envPort = process.env.POMODMER_PORT
    this.port = envPort ? Number(envPort) : (this.config.port === 0 ? 0 : Number(this.config.port) || 5173)
    this.open = process.env.POMODMER_OPEN === '0' ? false : this.config.open !== false
    this.server = null
    this.clients = new Set()
  }

  [Service.init]() {
    this.server = createServer((req, res) => this._handle(req, res))
    // 每秒 tick -> SSE 广播（前端只渲染，不自己推进时间）
    this._offTick = null
    const onTick = (state) => this._broadcast('tick', state)
    const onPhase = (p) => this._broadcast('phase', p)
    const onSession = (s) => this._broadcast('session', s)
    const onSettings = (s) => this._broadcast('settings', s)
    const onInterrupt = (i) => this._broadcast('interrupt', i)
    this.ctx.on('pomodoro/tick', onTick)
    this.ctx.on('pomodoro/phase', onPhase)
    this.ctx.on('pomodoro/session', onSession)
    this.ctx.on('pomodoro/settings', onSettings)
    this.ctx.on('pomodoro/interrupt', onInterrupt)

    return new Promise((resolveReady, rejectReady) => {
      this.server.on('error', (e) => {
        this.ctx.logger.warn('http: 服务错误 %s', e.message)
        rejectReady(e)
      })
      this.server.listen(this.port, this.host, () => {
        const addr = this.server.address()
        this.port = addr.port
        this.url = 'http://' + this.host + ':' + this.port + '/'
        this.ctx.logger.info('http: 番茄钟已启动 -> %s', this.url)
        resolveReady()
      })
    }).then(() => () => {
      // 关停：先断 SSE 连接，再关服务器
      for (const res of this.clients) {
        try { res.end() } catch { /* ignore */ }
      }
      this.clients.clear()
      if (this.server) this.server.close()
      this.ctx.logger.info('http: 服务已关闭')
    })
  }

  // ---------- 路由 ----------
  async _handle(req, res) {
    const url = new URL(req.url, 'http://' + (req.headers.host || 'localhost'))
    const path = url.pathname

    try {
      if (path === '/api/events') return this._sse(req, res)
      if (path.startsWith('/api/')) return await this._api(req, res, path, url)
      return await this._static(res, path)
    } catch (e) {
      this.ctx.logger.warn('http: %s %s 失败 %s', req.method, path, e.message)
      return this._json(res, 500, { error: e.message })
    }
  }

  // xlsx 能力缺席时的解释：三种原因（没装 Python / 装了缺 openpyxl / 被主动关闭）里
  // 只有服务端知道是哪一种，所以文案在这里统一产出一份，别让各路由和前端各编一套。
  _xlsxHint() {
    return process.env.POMODMER_NO_XLSX === '1'
      ? 'xlsx 报表能力已被 POMODMER_NO_XLSX=1 主动关闭（去掉该变量重启即恢复）'
      : '未启用 xlsx 报表插件：装好 Python + openpyxl 后重启即自动启用（也可 POMODMER_CONFIG=cordis.with-xlsx.json 强制启用）'
  }

  async _api(req, res, path, url) {
    const timer = this.ctx.timer
    const store = this.ctx.store
    const json = (code, body) => this._json(res, code, body)
    if (path === '/api/state' && req.method === 'GET') {
      return json(200, {
        settings: store.settings,
        tasks: store.tasks,
        runtime: timer.state(),
      })
    }

    if (path === '/api/settings' && req.method === 'PATCH') {
      const body = await this._body(req)
      return json(200, { settings: store.settings, runtime: timer.setSettings(body || {}) })
    }

    if (path.startsWith('/api/timer/') && req.method === 'POST') {
      const action = path.slice('/api/timer/'.length)
      const body = req.headers['content-length'] ? await this._body(req) : {}
      switch (action) {
        case 'start': return json(200, timer.start((body && body.taskId) || undefined))
        case 'pause': return json(200, timer.pause())
        case 'resume': return json(200, timer.resume())
        case 'toggle': return json(200, timer.toggle((body && body.taskId) || undefined))
        case 'reset': return json(200, timer.reset())
        case 'skip': return json(200, timer.skip())
        case 'void': return json(200, timer.voidCurrent((body && body.reason) || 'void'))
        default: return json(404, { error: '未知动作: ' + action })
      }
    }

    if (path === '/api/tasks') {
      if (req.method === 'GET') return json(200, { tasks: store.tasks })
      if (req.method === 'POST') {
        const body = await this._body(req)
        return json(200, { task: timer.addTask(body && body.title, body && body.estimate) })
      }
    }

    // 注意：/api/tasks/current 必须先于 /api/tasks/:id 匹配，否则会被当成 id='current' 的任务
    if (path === '/api/tasks/current' && req.method === 'PATCH') {
      const body = await this._body(req)
      return json(200, timer.setCurrentTask(body && body.taskId))
    }

    if (path.startsWith('/api/tasks/')) {
      const id = decodeURIComponent(path.slice('/api/tasks/'.length))
      if (req.method === 'PATCH') {
        const body = await this._body(req)
        const t = timer.updateTask(id, body || {})
        return t ? json(200, { task: t }) : json(404, { error: '任务不存在' })
      }
      if (req.method === 'DELETE') {
        return timer.deleteTask(id) ? json(200, { ok: true }) : json(404, { error: '任务不存在' })
      }
    }

    if (path === '/api/sessions' && req.method === 'GET') {
      const limit = Math.min(Number(url.searchParams.get('limit')) || 100, 1000)
      return json(200, { sessions: store.sessions.slice(-limit) })
    }

    // ---- P1：统计 / 中断 / 导入导出 ----
    if (path === '/api/stats' && req.method === 'GET') {
      const days = Math.min(Math.max(Number(url.searchParams.get('days')) || 7, 1), 60)
      const heatWeeks = Math.min(Math.max(Number(url.searchParams.get('weeks')) || 12, 1), 52)
      return json(200, timer.stats({ days, heatWeeks }))
    }

    if (path === '/api/unplanned') {
      if (req.method === 'GET') return json(200, { unplanned: timer.listUnplanned(50) })
      if (req.method === 'POST') {
        const body = await this._body(req)
        return json(200, { item: timer.recordInterrupt(body && body.kind, body && body.note) })
      }
    }

    if (path.startsWith('/api/unplanned/') && req.method === 'DELETE') {
      const id = decodeURIComponent(path.slice('/api/unplanned/'.length))
      return timer.deleteUnplanned(id) ? json(200, { ok: true }) : json(404, { error: '记录不存在' })
    }

    if (path === '/api/export' && req.method === 'GET') {
      // format=xlsx：全量 xlsx（给人看/分析）；默认 JSON（用来回灌备份，可再导入）
      if (url.searchParams.get('format') === 'xlsx') {
        const report = this.ctx.get('report')
        if (!report) return json(501, { error: this._xlsxHint() })
        try {
          const out = await report.full()
          const buf = await readFile(out.file)
          res.writeHead(200, {
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'Content-Disposition': 'attachment; filename="' + basename(out.file) + '"',
            'Content-Length': buf.length,
            'Cache-Control': 'no-store',
          })
          this._broadcast('report', { file: out.file, scope: out.scope })
          return res.end(buf)
        } catch (e) {
          return json(500, { error: 'xlsx 全量导出失败: ' + e.message })
        }
      }
      const body = JSON.stringify({ app: 'pomodmer', exportedAt: Date.now(), ...store.snapshot() }, null, 2)
      const name = 'pomodmer-' + new Date().toISOString().slice(0, 10) + '.json'
      res.writeHead(200, {
        'Content-Type': 'application/json; charset=utf-8',
        'Content-Disposition': 'attachment; filename="' + name + '"',
        'Content-Length': Buffer.byteLength(body),
      })
      return res.end(body)
    }

    if (path === '/api/import' && req.method === 'POST') {
      const body = await this._body(req)
      try {
        store.replace(body && body.data ? body.data : body)
        const state = timer.reload()
        this._broadcast('imported', { settings: store.settings })
        return json(200, { ok: true, runtime: state, settings: store.settings })
      } catch (e) {
        return json(400, { error: '导入失败: ' + e.message })
      }
    }

    // ---- P3：从 xlsx 回灌（去重追加，不删任何已有记录）----
    // mode=preview（默认）只算不写；mode=apply 才落库。前端先预览再确认，
    // 就是为了别让"手滑点一下"直接改动几个月的历史记录。
    if (path === '/api/import/xlsx' && req.method === 'POST') {
      const report = this.ctx.get('report')
      if (!report) return json(501, { error: this._xlsxHint() })
      const mode = url.searchParams.get('mode') === 'apply' ? 'apply' : 'preview'
      const buf = await this._rawBody(req)
      if (!buf.length) return json(400, { error: '请求体为空：请上传 .xlsx 文件' })
      if (buf.length > 20 * 1024 * 1024) return json(413, { error: '文件过大（>20MB）：这不是本应用导出的表格吧' })
      if (buf.subarray(0, 2).toString() !== 'PK') {
        return json(400, { error: '不是 xlsx 文件（zip 魔数不匹配）：请上传本应用导出或另存的 .xlsx' })
      }
      // worker 只认路径：把上传字节落到临时文件再交给 ctx.table 读，读完就删
      const tmp = join(tmpdir(), 'pomodmer-import-' + Date.now() + '-' + Math.random().toString(36).slice(2) + '.xlsx')
      try {
        await writeFile(tmp, buf)
        const summary = await report.importXlsx(tmp, { mode })
        if (mode === 'apply') this._broadcast('imported', { settings: store.settings, via: 'xlsx' })
        return json(200, summary)
      } catch (e) {
        return json(400, { error: 'xlsx 解析失败: ' + e.message })
      } finally {
        unlink(tmp).catch(() => {})
      }
    }

    // ---- P2：周报/全量导出（可选能力，依赖 ctx.table -> Python OpenPyXL）----
    // 能力是否在场由启动时的清单决定（boot.mjs resolveConfigPath 自动探测），
    // 所以提示要能解释"为什么没有"，而不是只丢一个环境变量名。
    if (path === '/api/report') {
      const report = this.ctx.get('report')
      const hint = this._xlsxHint()
      if (req.method === 'GET') {
        return json(200, { available: !!report, hint: report ? null : hint })
      }
      if (req.method === 'POST') {
        if (!report) return json(501, { error: hint })
        const body = await this._body(req)
        const days = Math.min(Math.max(Number(body && body.days) || 7, 1), 60)
        try {
          const out = await report.weekly({ days })
          this._broadcast('report', { file: out.file })
          return json(200, out)
        } catch (e) {
          return json(500, { error: '周报生成失败: ' + e.message })
        }
      }
    }

    return json(404, { error: '未找到: ' + path })
  }

  // ---------- SSE ----------
  _sse(req, res) {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    })
    res.write('retry: 3000\n\n')
    this._send(res, 'hello', this.ctx.timer.state())
    this.clients.add(res)
    req.on('close', () => {
      this.clients.delete(res)
    })
  }

  _send(res, event, data) {
    try {
      res.write('event: ' + event + '\n')
      res.write('data: ' + JSON.stringify(data) + '\n\n')
    } catch {
      this.clients.delete(res)
    }
  }

  _broadcast(event, data) {
    for (const res of this.clients) this._send(res, event, data)
  }

  // ---------- 静态资源 ----------
  async _static(res, path) {
    let rel = path === '/' ? 'index.html' : decodeURIComponent(path).replace(/^\/+/, '')
    const full = resolve(WEB_ROOT, rel)
    // 路径穿越防护：解析后必须仍在 web/ 内
    if (full !== WEB_ROOT && !full.startsWith(WEB_ROOT + sep)) {
      return this._json(res, 403, { error: '禁止访问' })
    }
    try {
      const st = await stat(full)
      if (st.isDirectory()) return this._static(res, join(path, 'index.html'))
      const buf = await readFile(full)
      res.writeHead(200, {
        'Content-Type': MIME[extname(full).toLowerCase()] || 'application/octet-stream',
        'Cache-Control': 'no-cache',
      })
      res.end(buf)
    } catch {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' })
      res.end('404 Not Found: ' + path)
    }
  }

  // ---------- 工具 ----------
  _body(req) {
    return new Promise((ok, no) => {
      let size = 0
      const chunks = []
      req.on('data', (c) => {
        size += c.length
        if (size > MAX_BODY) { no(new Error('请求体过大')); req.destroy(); return }
        chunks.push(c)
      })
      req.on('end', () => {
        const raw = Buffer.concat(chunks).toString('utf8').trim()
        if (!raw) return ok({})
        try { ok(JSON.parse(raw)) } catch { no(new Error('请求体不是合法 JSON')) }
      })
      req.on('error', no)
    })
  }

  // 原始字节体（xlsx 上传用）：不能像 _body 那样 toString('utf8')，
  // 二进制被 UTF-8 解码就毁了 —— 而且 zip 里任意字节都可能不是合法 UTF-8。
  _rawBody(req) {
    return new Promise((ok, no) => {
      let size = 0
      const chunks = []
      req.on('data', (c) => {
        size += c.length
        if (size > MAX_BODY) { no(new Error('请求体过大')); req.destroy(); return }
        chunks.push(c)
      })
      req.on('end', () => ok(Buffer.concat(chunks)))
      req.on('error', no)
    })
  }

  _json(res, code, body) {
    const s = JSON.stringify(body)
    res.writeHead(code, {
      'Content-Type': 'application/json; charset=utf-8',
      'Content-Length': Buffer.byteLength(s),
      'Cache-Control': 'no-store',
    })
    res.end(s)
  }
}

export default HttpService
