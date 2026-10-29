// electron/main.cjs —— Pomodmer 桌面壳（P3，可选）
//
// 用 CommonJS 的原因：package.json 是 "type": "module"，而 Electron 主进程对
// `import { app } from 'electron'` 的命名导出支持不完整（实测 44.4.5 报
// "does not provide an export named 'BrowserWindow'"），.cjs 是明确无歧义的写法。
//
// 设计：Electron **不改架构，只换外壳**。
//   · Cordis 宿主（src/pom.mjs）照旧跑在 Node 里，这里用 child_process 拉起它；
//   · BrowserWindow 只是加载 http://127.0.0.1:<port>/ —— 和浏览器里看到的是同一份 web/；
//   · 桌面专属能力（托盘、置顶、全局快捷键、原生通知）只在这一层补，主功能不依赖它。
//
// 失败可降级：装不了 electron 时直接用 npm run pom 走浏览器模式，功能完全一致。
const { app, BrowserWindow, Tray, Menu, Notification, globalShortcut, nativeImage } = require('electron')
const { spawn } = require('node:child_process')
const { resolve } = require('node:path')
const http = require('node:http')

const ROOT = resolve(__dirname, '..')
const PORT = process.env.POMODMER_PORT || '5173'
const BASE = 'http://127.0.0.1:' + PORT

let win = null
let tray = null
let host = null
let lastPhase = null
let pollTimer = null

function log(...a) { console.log('[electron]', ...a) }

// ---------- 拉起 Cordis 宿主 ----------
function startHost() {
  host = spawn(process.execPath, [resolve(ROOT, 'src/pom.mjs')], {
    cwd: ROOT,
    env: Object.assign({}, process.env, { POMODMER_OPEN: '0', POMODMER_PORT: PORT }),
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  host.stdout.on('data', (d) => process.stdout.write('[host] ' + d.toString()))
  host.stderr.on('data', (d) => process.stderr.write('[host] ' + d.toString()))
  host.on('exit', (code) => log('宿主进程退出 code=' + code))
  log('宿主已拉起 pid=' + host.pid + ' port=' + PORT)
}

function apiState() {
  return new Promise((ok, no) => {
    const req = http.get(BASE + '/api/state', (res) => {
      let body = ''
      res.on('data', (c) => { body += c })
      res.on('end', () => { try { ok(JSON.parse(body)) } catch (e) { no(e) } })
    })
    req.on('error', no)
    req.setTimeout(2000, () => { req.destroy(); no(new Error('timeout')) })
  })
}

function waitForHost(timeoutMs = 25000) {
  const t0 = Date.now()
  return new Promise((ok, no) => {
    const tick = async () => {
      try {
        const s = await apiState()
        if (s && s.runtime) return ok(s)
      } catch (e) { /* 还没起来，继续等 */ }
      if (Date.now() - t0 > timeoutMs) return no(new Error('宿主启动超时'))
      setTimeout(tick, 300)
    }
    tick()
  })
}

function post(path) {
  return new Promise((ok, no) => {
    const req = http.request({ hostname: '127.0.0.1', port: Number(PORT), path: path, method: 'POST' }, (res) => {
      let body = ''
      res.on('data', (c) => { body += c })
      res.on('end', () => ok(body))
    })
    req.on('error', no)
    req.end()
  })
}

// ---------- 窗口 ----------
function createWindow() {
  win = new BrowserWindow({
    width: 520,
    height: 940,
    minWidth: 380,
    minHeight: 560,
    title: 'Pomodmer',
    autoHideMenuBar: true,
    backgroundColor: '#f6f6f4',
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  })
  win.loadURL(BASE + '/')
  // 关闭 = 退到托盘，不退出应用（番茄继续跑）
  win.on('close', (e) => {
    if (!app.isQuiting) {
      e.preventDefault()
      win.hide()
      if (tray) tray.displayBalloon({ title: 'Pomodmer', content: '已最小化到托盘，计时继续' })
    }
  })
  win.on('closed', () => { win = null })
}

// ---------- 托盘 ----------
function createTray() {
  let image = nativeImage.createFromPath(resolve(__dirname, 'icon.png'))
  if (image.isEmpty()) image = nativeImage.createFromDataURL('data:image/png;base64,iVBORw0KGgo=')
  tray = new Tray(image)
  tray.setToolTip('Pomodmer 番茄钟')
  const menu = Menu.buildFromTemplate([
    {
      label: '显示 / 隐藏',
      click: () => { if (!win) createWindow(); else if (win.isVisible()) win.hide(); else win.show() },
    },
    { label: '窗口置顶', type: 'checkbox', checked: false, click: (m) => { if (win) win.setAlwaysOnTop(m.checked) } },
    { type: 'separator' },
    { label: '开始 / 暂停', click: () => post('/api/timer/toggle').catch(() => {}) },
    { label: '跳过当前阶段', click: () => post('/api/timer/skip').catch(() => {}) },
    { type: 'separator' },
    { label: '退出', click: () => { app.isQuiting = true; app.quit() } },
  ])
  tray.setContextMenu(menu)
  tray.on('click', () => { if (!win) createWindow(); else if (win.isVisible()) win.hide(); else win.show() })
}

// ---------- 原生通知：阶段切换时提醒（窗口隐藏时也有效）----------
function startPhaseWatcher() {
  pollTimer = setInterval(async () => {
    try {
      const s = await apiState()
      const phase = s.runtime.phase
      if (lastPhase && phase !== lastPhase && Notification.isSupported()) {
        const label = { focus: '专注', short: '短休息', long: '长休息', idle: '待开始' }[phase] || phase
        new Notification({ title: 'Pomodmer', body: '进入' + label }).show()
      }
      lastPhase = phase
    } catch (e) { /* 宿主短暂不可达，忽略 */ }
  }, 1000)
}

// ---------- 生命周期 ----------
app.whenReady().then(async () => {
  startHost()
  try {
    await waitForHost()
  } catch (e) {
    log('FATAL: ' + e.message)
    app.quit()
    return
  }
  createWindow()
  createTray()
  startPhaseWatcher()
  globalShortcut.register('Control+Alt+Space', () => { post('/api/timer/toggle').catch(() => {}) })
  log('就绪：' + BASE + '（Ctrl+Alt+Space 开始/暂停，关闭窗口退到托盘）')
})

app.on('before-quit', () => {
  app.isQuiting = true
  if (pollTimer) clearInterval(pollTimer)
  globalShortcut.unregisterAll()
  if (host && !host.killed) {
    log('停止宿主 pid=' + host.pid)
    host.kill()
  }
})

app.on('window-all-closed', () => { /* 保持在托盘运行 */ })
