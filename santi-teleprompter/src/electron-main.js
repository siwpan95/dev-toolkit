import { app, BrowserWindow } from 'electron'
import { startApp } from './index.js'

// 先启动 cordis 后端（HTTP 服务，无需显示器即可运行），再根据是否就绪创建窗口。
const started = startApp()

async function createWindow() {
  const { port } = await started

  const win = new BrowserWindow({
    fullscreen: true,
    backgroundColor: '#000000',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  win.loadURL(`http://localhost:${port}`)
  win.on('closed', () => {})
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})
