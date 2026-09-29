// electron/start.mjs —— Electron 启动器（npm run electron 走这里）
// 为什么需要它：某些环境（本机实测）全局带着 ELECTRON_RUN_AS_NODE=1，
// 此时 electron.exe 会退化成"纯 Node"运行 —— require('electron') 拿到的是二进制路径字符串，
// 症状是 `app.whenReady()` 报 undefined。这个变量在 Electron 启动前就被读取，main.cjs 里改已经来不及，
// 所以必须在**启动前**把它从子进程环境里删掉。
import { spawn } from 'node:child_process'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { existsSync } from 'node:fs'

const require = createRequire(import.meta.url)
const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..')

let bin
try {
  bin = require('electron')   // node_modules/electron/index.js 导出的就是二进制路径
} catch (e) {
  console.error('[start] 未找到 electron：请先 npm install（会下载约 100MB 二进制）')
  process.exit(1)
}
if (typeof bin !== 'string' || !existsSync(bin)) {
  console.error('[start] electron 二进制缺失：' + bin + '\n请先执行 npm install（国内建议配 ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/）')
  process.exit(1)
}

const env = { ...process.env }
delete env.ELECTRON_RUN_AS_NODE     // 关键：否则 Electron 退化成 Node

console.log('[start] electron=' + bin)
const child = spawn(bin, [resolve(__dirname, 'main.cjs')], { cwd: ROOT, env, stdio: 'inherit' })
child.on('exit', (code) => process.exit(code === null ? 1 : code))
process.on('SIGINT', () => child.kill())
process.on('SIGTERM', () => child.kill())
