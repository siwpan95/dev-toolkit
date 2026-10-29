import { Context } from 'cordis'
import { pathToFileURL } from 'node:url'
import { TopicsService } from './topics.js'
import { serverPlugin, shutdownServer } from './plugin-server.js'
import { readConfig, ROOT } from './config.js'

// 启动 cordis 后端：注册全部插件后再统一 await（cordis 要求先注册后 await）
export async function startApp() {
  const cfg = readConfig()
  const ctx = new Context()

  const fTopics = ctx.plugin(TopicsService, cfg)
  const fServer = ctx.plugin(serverPlugin, cfg)
  await fTopics
  await fServer

  const shutdown = () => {
    shutdownServer()
    process.exit(0)
  }
  process.on('SIGINT', shutdown)
  process.on('SIGTERM', shutdown)

  return { ctx, port: cfg.port, root: ROOT }
}

// 直接运行（网页版备选）：node src/index.js
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  startApp()
    .then(({ port }) => {
      console.log(`远子学姐的三题故事 · 提词器 (Web) 已启动: http://localhost:${port}`)
    })
    .catch((e) => {
      console.error(e)
      process.exit(1)
    })
}
