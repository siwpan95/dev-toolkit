import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { SOURCE_LABELS, POOL_LABELS } from './topics.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PUBLIC_DIR = path.join(path.resolve(__dirname, '..'), 'public')

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
}

let currentServer = null

export function shutdownServer() {
  if (currentServer) {
    currentServer.close()
    currentServer = null
  }
}

export function serverPlugin(ctx, cfg) {
  const port = cfg.port || 8787

  const server = http.createServer((req, res) => {
    const url = new URL(req.url, `http://localhost:${port}`)

    // —— API ——
    if (url.pathname === '/api/topics/random') {
      // ?sources=literature,meme  只从指定词源抽取；省略 = 全部
      const raw = url.searchParams.get('sources')
      const sources = raw
        ? raw.split(',').map((s) => s.trim()).filter(Boolean)
        : []
      const topics = ctx.topics.randomThree(sources)
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' })
      res.end(JSON.stringify({ topics }))
      return
    }
    if (url.pathname === '/api/pools') {
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' })
      res.end(JSON.stringify({ pools: ctx.topics.poolsInfo() }))
      return
    }
    if (url.pathname === '/api/sources') {
      const stats = ctx.topics.stats()
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' })
      res.end(JSON.stringify({
        sources: ctx.topics.sources(),
        labels: SOURCE_LABELS,
        poolLabels: POOL_LABELS,
        stats,
      }))
      return
    }
    if (url.pathname === '/api/config') {
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' })
      res.end(JSON.stringify({ prompter: cfg.prompter || {} }))
      return
    }

    // —— 静态资源 ——
    const rel = url.pathname === '/' ? '/index.html' : url.pathname
    const filePath = path.normalize(path.join(PUBLIC_DIR, rel))
    if (!filePath.startsWith(PUBLIC_DIR)) {
      res.writeHead(403)
      res.end('forbidden')
      return
    }
    fs.readFile(filePath, (err, data) => {
      if (err) {
        res.writeHead(404)
        res.end('not found')
        return
      }
      const ext = path.extname(filePath)
      res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' })
      res.end(data)
    })
  })

  return new Promise((resolve) => {
    server.listen(port, () => {
      currentServer = server
      ctx.logger.info(`提词器服务已启动: http://localhost:${port}`)
      ctx.emit('server-ready', port)
      resolve()
    })
  })
}

serverPlugin.inject = ['topics']
