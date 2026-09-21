import { app, BrowserWindow } from 'electron'
import { startApp } from './index.js'

async function createWindow() {
  const { port } = await startApp()

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
