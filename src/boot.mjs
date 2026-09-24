// boot.mjs —— Cordis 宿主启动/关停（入口/CLI/测试三方共用，防启动路径漂移）
// 架构：new Context() -> 接 console 日志导出器 -> 装 Loader（声明式插件宿主）
//       -> 读 cordis.json 的 entries，逐条 loader.create 加载插件（含 table 服务）
import { Context } from 'cordis'
import Loader from '@cordisjs/plugin-loader'
import ConsoleExporter from '@cordisjs/plugin-logger-console'
import { pathToFileURL } from 'node:url'
import { readFileSync } from 'node:fs'
import { TableService } from './plugins/table.mjs'

let ctx = null
let tableBridgeRef = null

export function getCtx() {
  return ctx
}

export async function bootHost(options = {}) {
  ctx = new Context()

  // 1) 日志导出器（否则 loader 失败路径全走 logger.error 而静默）
  await ctx.plugin(ConsoleExporter)

  // 2) Cordis 插件宿主（声明式入口），baseUrl 决定条目相对路径解析基点 = 项目根
  await ctx.plugin(Loader, { baseUrl: pathToFileURL(process.cwd() + '/').href })
  const loader = ctx.loader

  // 3) 读 cordis.json，逐条创建入口（table 服务即其中之一）
  const cfgPath = options.config || 'cordis.json'
  const entries = JSON.parse(readFileSync(cfgPath, 'utf8')).entries || []
  for (const entry of entries) {
    await loader.create({ ...entry })
  }
  await loader.await()

  // 4) 缓存 table 桥引用，供 stopHost 兜底强杀 python worker
  tableBridgeRef = ctx.table ? ctx.table.bridge : null

  ctx.logger.info('host booted, entries=%d, ctx.table=%s', entries.length, !!ctx.table)
  return ctx
}

// 正确关停（Cordis 无 ctx.stop；根 fiber dispose=restart）：
// 逆序 dispose 顶层入口 fiber -> 触发各服务清理函数（杀 python），最后兜底强杀。
export async function stopHost() {
  if (!ctx) return
  const loader = ctx.loader
  ctx.logger.info('stopping host...')
  for (const entry of [...loader.root.tree.entries()]) {
    if (entry.fiber) {
      try {
        await entry.fiber.dispose()
      } catch (e) {
        ctx.logger.warn('dispose entry %s failed: %s', entry.options.id, e.message)
      }
    }
  }
  // 兜底：确保 python worker 已退出
  if (tableBridgeRef) {
    await tableBridgeRef.stop().catch(() => {})
  }
  ctx = null
  tableBridgeRef = null
}
