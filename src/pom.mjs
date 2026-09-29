// pom.mjs —— 番茄钟应用入口：启动 Cordis 宿主（store/timer/http 三个插件），打印并打开本地地址。
// 用法：
//   node src/pom.mjs [--port 5173] [--host 127.0.0.1] [--no-open] [--config cordis.json]
// 环境变量：POMODMER_PORT / POMODMER_HOST / POMODMER_OPEN=0 / POMODMER_CONFIG
import { bootHost, stopHost } from './boot.mjs'
import { parseArgs } from 'node:util'
import { spawn } from 'node:child_process'

const { values: args } = parseArgs({
  options: {
    port: { type: 'string', short: 'p' },
    host: { type: 'string', short: 'H' },
    open: { type: 'boolean', default: true },
    config: { type: 'string', short: 'c' },
  },
})

// 端口/地址：CLI > 环境变量 > cordis.json 默认值（由 http 插件自己兜底）
if (args.port) process.env.POMODMER_PORT = args.port
if (args.host) process.env.POMODMER_HOST = args.host
if (args.open === false) process.env.POMODMER_OPEN = '0'

function openBrowser(url) {
  if (process.env.POMODMER_OPEN === '0') return
  try {
    if (process.platform === 'win32') {
      spawn('cmd', ['/c', 'start', '', url], { stdio: 'ignore', detached: true }).unref()
    } else if (process.platform === 'darwin') {
      spawn('open', [url], { stdio: 'ignore', detached: true }).unref()
    } else {
      spawn('xdg-open', [url], { stdio: 'ignore', detached: true }).unref()
    }
  } catch {
    /* 打不开就算了，地址已打印 */
  }
}

let ctx = null
async function main() {
  ctx = await bootHost({ config: args.config })
  const http = ctx.http
  if (!http || !http.url) {
    throw new Error('http 服务未就绪（插件未加载或端口被占用）')
  }
  console.log('\n  Pomodmer 番茄钟已启动')
  console.log('  ' + http.url)
  console.log('  数据文件: ' + ctx.store.file)
  console.log('  按 Ctrl+C 停止\n')
  openBrowser(http.url)
}

// 优雅退出：先关宿主（flush 数据 + 关 HTTP），再退出
async function shutdown(signal) {
  console.log('\n[pom] 收到 ' + signal + '，正在停止...')
  try { await stopHost() } catch { /* ignore */ }
  process.exit(0)
}
process.on('SIGINT', () => shutdown('SIGINT'))
process.on('SIGTERM', () => shutdown('SIGTERM'))

main().catch((e) => {
  console.error('[pom] FATAL:', e)
  process.exit(1)
})
