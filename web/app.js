// app.js —— 番茄钟前端（零框架）
// 铁律：本页**不推进时间**。服务端通过 SSE 下发 endAt（绝对时刻）与 now，
// 前端只在本地按 endAt 插值渲染，刷新/切后台/掉线重连都不会让计时出错。
const $ = (id) => document.getElementById(id)
const CIRC = 2 * Math.PI * 120

const el = {
  time: $('time'), sub: $('roundInfo'), badge: $('phaseBadge'), ring: $('ringFg'),
  toggle: $('btnToggle'), reset: $('btnReset'), skip: $('btnSkip'), void: $('btnVoid'),
  done: $('stDone'), min: $('stMin'), int: $('stInt'),
  focus: $('cfgFocus'), short: $('cfgShort'), long: $('cfgLong'), every: $('cfgEvery'),
  autoBreak: $('cfgAutoBreak'), autoFocus: $('cfgAutoFocus'), sound: $('cfgSound'),
  tick: $('cfgTick'), notify: $('cfgNotify'), save: $('btnSave'), hint: $('saveHint'),
}

let state = null          // 最近一次服务端快照
let settings = null
let offset = 0            // 服务端时钟 - 本地时钟
let audioCtx = null
let audioReady = false
let lastPhase = null

const PHASE_COLOR = { focus: '#e24b4a', short: '#1d9e75', long: '#185fa5', idle: '#b4b2a9' }
const PHASE_TEXT = { focus: '专注', short: '短休息', long: '长休息', idle: '待开始' }

// ---------- 音频：Web Audio 实时合成，零音频资产 ----------
function initAudio() {
  if (audioCtx) return audioCtx
  const Ctx = window.AudioContext || window.webkitAudioContext
  if (!Ctx) return null
  audioCtx = new Ctx()
  return audioCtx
}

function beep(freq, dur = 0.18, gain = 0.16, type = 'sine') {
  const ctx = initAudio()
  if (!ctx) return
  if (ctx.state === 'suspended') ctx.resume()
  const osc = ctx.createOscillator()
  const g = ctx.createGain()
  osc.type = type
  osc.frequency.setValueAtTime(freq, ctx.currentTime)
  g.gain.setValueAtTime(gain, ctx.currentTime)
  g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur)
  osc.connect(g)
  g.connect(ctx.destination)
  osc.start()
  osc.stop(ctx.currentTime + dur)
}

function chime(kind) {
  if (!settings || !settings.sound) return
  if (kind === 'focus') { beep(587.33, 0.22); setTimeout(() => beep(880, 0.3), 220) }
  else { beep(880, 0.22); setTimeout(() => beep(587.33, 0.3), 220) }
}

function tickSound() {
  if (!settings || !settings.tick) return
  beep(1200, 0.03, 0.05, 'square')
}

// ---------- 通知 ----------
function notify(title, body) {
  if (!settings || !settings.notify) return
  if (!('Notification' in window)) return
  if (Notification.permission === 'default') Notification.requestPermission()
  if (Notification.permission === 'granted') {
    try { new Notification(title, { body }) } catch { /* ignore */ }
  }
}

// ---------- 渲染 ----------
function fmt(ms) {
  const total = Math.max(0, Math.ceil(ms / 1000))
  const m = Math.floor(total / 60)
  const s = total % 60
  return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0')
}

function remainingNow() {
  if (!state) return 0
  if (state.running && state.endAt) return Math.max(0, state.endAt - (Date.now() + offset))
  return state.remainingMs || 0
}

function render() {
  if (!state) return
  const remain = remainingNow()
  const planned = state.plannedMs || 1
  el.time.textContent = fmt(remain)
  el.badge.textContent = state.phaseLabel || PHASE_TEXT[state.phase] || state.phase
  el.ring.style.stroke = PHASE_COLOR[state.phase] || PHASE_COLOR.idle
  el.ring.style.strokeDasharray = CIRC
  el.ring.style.strokeDashoffset = CIRC * Math.min(1, Math.max(0, remain / planned))
  el.toggle.textContent = state.running ? '暂停' : (state.phase === 'idle' ? '开始' : '继续')
  const round = (state.round || 0) % (state.longEvery || 4)
  el.sub.textContent = state.phase === 'idle'
    ? '准备开始'
    : (state.phase === 'focus' ? `第 ${round + 1} 个番茄` : `${state.phaseLabel}中`)
  const t = state.today || {}
  el.done.textContent = t.completed || 0
  el.min.textContent = Math.round((t.focusMs || 0) / 60000)
  el.int.textContent = t.interrupts || 0
  document.title = `${fmt(remain)} · ${el.badge.textContent} · Pomodmer`
}

// 本地插值：按 endAt 每 200ms 重绘一次，秒变化时补一声滴答（不依赖服务端 tick 频率）
let lastSec = -1
setInterval(() => {
  if (!state) return
  render()
  if (state.running) {
    const sec = Math.ceil(remainingNow() / 1000)
    if (sec !== lastSec) { lastSec = sec; tickSound() }
  }
}, 200)

// ---------- 服务端通信 ----------
function applyState(s) {
  offset = (s.now || Date.now()) - Date.now()
  state = s
  render()
}

async function post(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  })
  const data = await res.json()
  if (data && data.now) applyState(data)
  return data
}

async function loadState() {
  const res = await fetch('/api/state')
  const data = await res.json()
  settings = data.settings
  applyState(data.runtime)
  fillSettings()
}

function fillSettings() {
  if (!settings) return
  el.focus.value = Math.round(settings.focusMs / 60000)
  el.short.value = Math.round(settings.shortMs / 60000)
  el.long.value = Math.round(settings.longMs / 60000)
  el.every.value = settings.longEvery
  el.autoBreak.checked = !!settings.autoStartBreak
  el.autoFocus.checked = !!settings.autoStartFocus
  el.sound.checked = !!settings.sound
  el.tick.checked = !!settings.tick
  el.notify.checked = !!settings.notify
}

function connect() {
  const es = new EventSource('/api/events')
  es.addEventListener('hello', (e) => { const d = JSON.parse(e.data); offset = d.now - Date.now(); state = d; render() })
  es.addEventListener('tick', (e) => applyState(JSON.parse(e.data)))
  es.addEventListener('phase', (e) => onPhase(JSON.parse(e.data)))
  es.addEventListener('session', () => { /* P1：会话列表 */ })
  es.addEventListener('settings', (e) => { settings = JSON.parse(e.data); fillSettings() })
  es.onerror = () => { /* EventSource 自带重连（retry: 3000） */ }
}

function onPhase(p) {
  if (!p || !p.type) return
  if (p.type === 'pause' || p.type === 'resume' || p.type === 'reset' || p.type === 'void') {
    if (settings && settings.sound && p.type !== 'reset') beep(p.type === 'pause' ? 520 : 760, 0.08, 0.1)
    return
  }
  const from = p.phase
  if (lastPhase === from && p.type === 'end') return
  lastPhase = from
  chime(from === 'focus' ? 'focus' : 'break')
  const nextText = PHASE_TEXT[p.next] || ''
  if (from === 'focus') notify('番茄完成', `休息一下，接下来是${nextText}`)
  else notify(`${PHASE_TEXT[from] || '休息'}结束`, nextText ? `开始${nextText}` : '继续')
}

// ---------- 交互 ----------
function ensureAudio() {
  if (!audioReady) { initAudio(); audioReady = true }
}

el.toggle.onclick = async () => { ensureAudio(); await post('/api/timer/toggle') }
el.reset.onclick = async () => { await post('/api/timer/reset') }
el.skip.onclick = async () => { await post('/api/timer/skip') }
el.void.onclick = async () => { await post('/api/timer/void', { reason: 'void' }) }

el.save.onclick = async () => {
  const res = await fetch('/api/settings', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      focusMs: Number(el.focus.value) * 60000,
      shortMs: Number(el.short.value) * 60000,
      longMs: Number(el.long.value) * 60000,
      longEvery: Number(el.every.value),
      autoStartBreak: el.autoBreak.checked,
      autoStartFocus: el.autoFocus.checked,
      sound: el.sound.checked,
      tick: el.tick.checked,
      notify: el.notify.checked,
    }),
  })
  const data = await res.json()
  settings = data.settings
  applyState(data.runtime)
  el.hint.textContent = '已保存'
  setTimeout(() => { el.hint.textContent = '' }, 2000)
}

document.addEventListener('keydown', (e) => {
  if (e.code !== 'Space') return
  const tag = (document.activeElement && document.activeElement.tagName) || ''
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'BUTTON') return
  e.preventDefault()
  ensureAudio()
  post('/api/timer/toggle')
})

// 回到前台立刻校正（后台标签页会被浏览器节流，回来必须重算）
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) loadState()
})

loadState().then(connect)
