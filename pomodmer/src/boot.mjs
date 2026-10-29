// boot.mjs —— Cordis 宿主启动/关停（入口/CLI/测试三方共用，防启动路径漂移）
// 架构：new Context() -> 接 console 日志导出器 -> 装 Loader（声明式插件宿主）
//       -> 读 cordis.json 的 entries，逐条 loader.create 加载插件（含 table 服务）
import { Context } from 'cordis'
import Loader from '@cordisjs/plugin-loader'
import ConsoleExporter from '@cordisjs/plugin-logger-console'
import { pathToFileURL } from 'node:url'
import { readFileSync } from 'node:fs'
import { TableService, probeTableWorker } from './plugins/table.mjs'

const PLAIN_CONFIG = 'cordis.json'
const XLSX_CONFIG = 'cordis.with-xlsx.json'

/**
 * 选插件清单：显式入参 > POMODMER_CONFIG > 自动探测 > 纯番茄钟清单。
 *
 * 自动探测的意义：表格能力（ctx.table / ctx.report，Python + OpenPyXL）是从
 * cordis-table-app 继承下来的既有资产，降级成可选插件后一直被"要记得设环境变量"挡住，
 * 于是等于休眠。这里改成"本机能跑就自动带上"：装了 Python + openpyxl 的机器上
 * `npm run pom` 直接就有 xlsx 报表能力，没装的机器一行配置都不用改，安静退回纯番茄钟。
 *
 * 探测带预算（见 probeTableWorker）：个别候选解释器（Microsoft Store 的占位程序）卡住时，
 * 不能让启动被拖成好几秒。自动探测失败 / 超时都只是"这次不带表格能力"，不是错误。
 * 想强制关掉自动启用（例如不想让 Python 被拉起）：POMODMER_NO_XLSX=1。
 */
let ctx = null
let tableBridgeRef = null

export function getCtx() {
  return ctx
}

export function resolveConfigPath(options = {}) {
  if (options.config) return { path: options.config, reason: '显式指定 --config' }
  if (process.env.POMODMER_CONFIG) return { path: process.env.POMODMER_CONFIG, reason: '环境变量 POMODMER_CONFIG' }
  if (process.env.POMODMER_NO_XLSX === '1') return { path: PLAIN_CONFIG, reason: 'POMODMER_NO_XLSX=1（主动关闭表格能力）' }

  const probe = probeTableWorker(null, { timeoutMs: 2500, budgetMs: 4000 })
  if (probe.openpyxl) {
    return { path: XLSX_CONFIG, reason: '自动探测到 Python + openpyxl（' + probe.bin + '）：启用表格/报表能力' }
  }
  if (probe.anyBin) {
    return {
      path: PLAIN_CONFIG,
      reason: '探测到 Python（' + probe.anyBin + '）但缺 openpyxl：装好后重启即自动启用（pip install openpyxl）',
    }
  }
  return { path: PLAIN_CONFIG, reason: '未探测到 Python：不启用表格能力（装 Python + openpyxl 后重启即自动启用）' }
}

export async function bootHost(options = {}) {
  ctx = new Context()

  // 1) 日志导出器（否则 loader 失败路径全走 logger.error 而静默）
  await ctx.plugin(ConsoleExporter)

  // 2) Cordis 插件宿主（声明式入口），baseUrl 决定条目相对路径解析基点 = 项目根
  await ctx.plugin(Loader, { baseUrl: pathToFileURL(process.cwd() + '/').href })
  const loader = ctx.loader

  // 3) 读插件清单，逐条创建入口（table / report 是否在内由 resolveConfigPath 决定）
  const choice = resolveConfigPath(options)
  const cfgPath = choice.path
  ctx.logger.info('plugin manifest: %s（%s）', cfgPath, choice.reason)
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
