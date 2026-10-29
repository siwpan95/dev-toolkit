// toast.mjs —— Windows 原生气泡通知（P2，best-effort）
// 为什么是 best-effort：纯 Node 没有系统通知 API，只能借 PowerShell 起一个临时 NotifyIcon
// 弹气泡。**失败不影响主功能**（浏览器 Notification 仍是主通道，Electron 壳有真正的原生通知）。
// 安全：标题/正文通过**环境变量**传递，不拼进命令行，杜绝引号注入。
import { spawn } from 'node:child_process'

const SCRIPT = [
  'Add-Type -AssemblyName System.Windows.Forms;',
  '$n = New-Object System.Windows.Forms.NotifyIcon;',
  '$n.Icon = [System.Drawing.SystemIcons]::Information;',
  '$n.BalloonTipTitle = $env:POMODMER_TOAST_TITLE;',
  '$n.BalloonTipText = $env:POMODMER_TOAST_TEXT;',
  '$n.Visible = $true;',
  '$n.ShowBalloonTip(5000);',
  'Start-Sleep -Seconds 6;',
  '$n.Dispose();',
].join(' ')

export function toast(title, text) {
  if (process.platform !== 'win32') return false
  try {
    const child = spawn('powershell', ['-NoProfile', '-NonInteractive', '-Command', SCRIPT], {
      env: {
        ...process.env,
        POMODMER_TOAST_TITLE: String(title || 'Pomodmer').slice(0, 100),
        POMODMER_TOAST_TEXT: String(text || '').slice(0, 200),
      },
      stdio: 'ignore',
      detached: true,
      windowsHide: true,
    })
    child.unref()
    child.on('error', () => { /* 静默失败，不打扰用户 */ })
    return true
  } catch {
    return false
  }
}

export default toast
