// app.js —— 番茄钟前端（零框架）
// 铁律：本页**不推进时间**。服务端通过 SSE 下发 endAt（绝对时刻）与 now，
// 前端只在本地按 endAt 插值渲染，刷新/切后台/掉线重连都不会让计时出错。
const $ = (id) => document.getElementById(id)
const CIRC = 2 * Math.PI * 120

const el = {
  time: $('time'), sub: $('roundInfo'), badge: $('phaseBadge'), ring: $('ringFg'),
  toggle: $('btnToggle'), reset: $('btnReset'), skip: $('btnSkip'), void: $('btnVoid'),
  done: $('stDone'), min: $('stMin'), int: $('stInt'), streak: $('stStreak'),
  curTask: $('curTask'), theme: $('btnTheme'),
  focus: $('cfgFocus'), short: $('cfgShort'), long: $('cfgLong'), every: $('cfgEvery'),
  autoBreak: $('cfgAutoBreak'), autoFocus: $('cfgAutoFocus'), sound: $('cfgSound'),
  tick: $('cfgTick'), notify: $('cfgNotify'), save: $('btnSave'), hint: $('saveHint'),
  taskTitle: $('taskTitle'), taskEst: $('taskEst'), addTask: $('btnAddTask'),
  taskList: $('taskList'), taskEmpty: $('taskEmpty'), taskBars: $('taskBars'),
  bars: $('bars'), heat: $('heat'),
  intNote: $('intNote'), intIn: $('btnIntIn'), intOut: $('btnIntOut'),
  unplannedList: $('unplannedList'), unplannedEmpty: $('unplannedEmpty'),
  exportBtn: $('btnExport'), exportXlsxBtn: $('btnExportXlsx'), importBtn: $('btnImport'), fileImport: $('fileImport'), ioHint: $('ioHint'),
  importXlsxBtn: $('btnImportXlsx'), fileImportXlsx: $('fileImportXlsx'), applyXlsxBtn: $('btnApplyXlsx'),
  monthBtn: $('btnMonth'), rangeBtn: $('btnRange'), rangeFrom: $('rangeFrom'), rangeTo: $('rangeTo'),
  ambient: $('cfgAmbient'), toastChk: $('cfgToast'), mini: $('btnMini'),
  reportBtn: $('btnReport'), reportHint: $('reportHint'), reportNote: $('reportNote'),
}

let state = null          // 最近一次服务端快照（runtime）
let settings = null
let tasks = []
let stats = null
let unplanned = []
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

// ---------- P2：白噪音（Web Audio 实时生成，零音频资产）----------
let noise = null

function stopAmbient() {
  if (!noise) return
  try { noise.src.stop() } catch { /* ignore */ }
  try { noise.src.disconnect() } catch { /* ignore */ }
  noise = null
}

function startAmbient(kind) {
  stopAmbient()
  if (!kind || kind === 'off') return
  const ctx = initAudio()
  if (!ctx) return
  if (ctx.state === 'suspended') ctx.resume()
  const len = Math.floor(ctx.sampleRate * 2)
  const buf = ctx.createBuffer(1, len, ctx.sampleRate)
  const data = buf.getChannelData(0)
  let last = 0
  for (let i = 0; i < len; i++) {
    const w = Math.random() * 2 - 1
    if (kind === 'brown') { last = (last + 0.02 * w) / 1.02; data[i] = Math.max(-1, Math.min(1, last * 3.5)) }
    else data[i] = w * 0.5
  }
  const src = ctx.createBufferSource()
  src.buffer = buf
  src.loop = true
  const g = ctx.createGain()
  g.gain.value = 0.05
  src.connect(g)
  g.connect(ctx.destination)
  src.start()
  noise = { src, g }
}

// 只在「专注阶段且正在计时」时播放，休息/暂停自动停
function syncAmbient() {
  const kind = settings && settings.ambient
  const want = kind && kind !== 'off' && state && state.running && state.phase === 'focus'
  if (want && (!noise || noise.kind !== kind)) { startAmbient(kind); if (noise) noise.kind = kind }
  else if (!want && noise) stopAmbient()
}

// ---------- P2：迷你窗（独立小窗，只显示倒计时）----------
let miniWin = null

function openMini() {
  if (miniWin && !miniWin.closed) { miniWin.focus(); return }
  miniWin = window.open('', 'pomodmer-mini', 'width=320,height=190,menubar=no,toolbar=no,location=no,status=no')
  if (!miniWin) { el.reportHint.textContent = '浏览器拦截了弹出窗口，请允许本站弹出窗口'; return }
  miniWin.document.write(
    '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>Pomodmer 迷你窗</title>' +
    '<style>body{margin:0;height:100vh;display:flex;flex-direction:column;align-items:center;' +
    'justify-content:center;background:#f6f6f4;color:#2c2c2a;font-family:system-ui,"Microsoft YaHei",sans-serif}' +
    '#t{font-size:44px;font-variant-numeric:tabular-nums}#p{color:#6b6a65;font-size:12px}' +
    '.row{margin-top:10px;display:flex;gap:8px}' +
    'button{padding:6px 14px;border:1px solid #e3e2dd;border-radius:10px;background:#fff;cursor:pointer;font-size:13px}' +
    '.pri{background:#e24b4a;border-color:#e24b4a;color:#fff}</style></head><body>' +
    '<div id="t">--:--</div><div id="p">连接中…</div>' +
    '<div class="row"><button class="pri" id="tg">开始</button><button id="sk">跳过</button></div>' +
    '<script>const $=function(i){return document.getElementById(i)};' +
    'function fmt(ms){var n=Math.max(0,Math.ceil(ms/1000));return String(Math.floor(n/60)).padStart(2,"0")+":"+String(n%60).padStart(2,"0")}' +
    'async function loop(){try{var r=await fetch("/api/state");var d=await r.json();var s=d.runtime;' +
    'var rm=s.running&&s.endAt?Math.max(0,s.endAt-Date.now()):(s.remainingMs||0);' +
    '$("t").textContent=fmt(rm);$("p").textContent=s.phaseLabel;document.title=fmt(rm)+" · "+s.phaseLabel;' +
    '$("tg").textContent=s.running?"暂停":"继续"}catch(e){$("p").textContent="连接中断，重试中…"}' +
    'setTimeout(loop,500)}' +
    '$("tg").onclick=function(){fetch("/api/timer/toggle",{method:"POST"})};' +
    '$("sk").onclick=function(){fetch("/api/timer/skip",{method:"POST"})};' +
    'loop()<\/script></body></html>'
  )
  miniWin.document.close()
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

// ---------- 计时渲染 ----------
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
  el.streak.textContent = stats ? stats.streak : 0
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

// ---------- 任务清单 ----------
function currentTask() {
  return tasks.find((t) => t.id === (state && state.currentTaskId)) || null
}

function renderTasks() {
  const cur = currentTask()
  el.curTask.textContent = cur ? `${cur.title}（${cur.spent || 0}/${cur.estimate || 1}）` : '未选择'
  el.taskEmpty.style.display = tasks.length ? 'none' : ''
  el.taskList.innerHTML = ''
  for (const t of tasks) {
    const li = document.createElement('li')
    li.className = 'task-item' + (t.id === (state && state.currentTaskId) ? ' active' : '') + (t.done ? ' done' : '')
    const name = document.createElement('span')
    name.className = 't-title'
    name.textContent = t.title
    const cnt = document.createElement('span')
    cnt.className = 't-count'
    cnt.textContent = `${t.spent || 0}/${t.estimate || 1}`
    const pick = document.createElement('button')
    pick.className = 'btn tiny'
    pick.textContent = t.id === (state && state.currentTaskId) ? '当前' : '选择'
    pick.onclick = () => patch('/api/tasks/current', { taskId: t.id }).then(refreshAll)
    const done = document.createElement('button')
    done.className = 'btn tiny'
    done.textContent = t.done ? '重开' : '完成'
    done.onclick = () => patch('/api/tasks/' + t.id, { done: !t.done }).then(refreshAll)
    const del = document.createElement('button')
    del.className = 'btn tiny danger'
    del.textContent = '删'
    del.onclick = () => del_(t.id)
    li.append(name, cnt, pick, done, del)
    el.taskList.appendChild(li)
  }
}

async function del_(id) {
  await fetch('/api/tasks/' + id, { method: 'DELETE' })
  refreshAll()
}

async function addTask() {
  const title = el.taskTitle.value.trim()
  if (!title) return
  await fetch('/api/tasks', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, estimate: Number(el.taskEst.value) || 1 }),
  })
  el.taskTitle.value = ''
  refreshAll()
}

// ---------- 图表（纯 SVG 手绘，不引图表库）----------
function renderCharts() {
  if (!stats) return
  const max = Math.max(1, ...stats.recent.map((d) => d.completed))
  const bw = 320 / stats.recent.length
  let bars = ''
  stats.recent.forEach((d, i) => {
    const h = Math.max(2, (d.completed / max) * 62)
    const x = i * bw + bw * 0.22
    const w = bw * 0.56
    bars += `<rect x="${x.toFixed(1)}" y="${(70 - h).toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" rx="3" fill="#e24b4a" opacity="${d.completed ? 0.9 : 0.25}"></rect>`
    bars += `<text x="${(i * bw + bw / 2).toFixed(1)}" y="84" font-size="9" text-anchor="middle" fill="var(--muted)">${d.date.slice(5)}</text>`
    if (d.completed) bars += `<text x="${(i * bw + bw / 2).toFixed(1)}" y="${(70 - h - 3).toFixed(1)}" font-size="9" text-anchor="middle" fill="var(--muted)">${d.completed}</text>`
  })
  el.bars.innerHTML = bars

  const cell = 12
  const gap = 2
  const cols = Math.ceil(stats.heat.length / 7)
  let heat = ''
  stats.heat.forEach((d, i) => {
    const col = Math.floor(i / 7)
    const row = i % 7
    const lv = Math.min(4, d.level)
    const fill = ['var(--heat0)', 'var(--heat1)', 'var(--heat2)', 'var(--heat3)', 'var(--heat4)'][lv]
    heat += `<rect x="${col * (cell + gap)}" y="${row * (cell + gap)}" width="${cell}" height="${cell}" rx="2" fill="${fill}"><title>${d.date}: ${d.level} 个番茄</title></rect>`
  })
  el.heat.setAttribute('viewBox', `0 0 ${cols * (cell + gap)} ${7 * (cell + gap)}`)
  el.heat.innerHTML = heat

  el.taskBars.innerHTML = stats.byTask.length
    ? stats.byTask.map((t) => {
      const pct = Math.min(100, Math.round(((t.spent || 0) / Math.max(1, t.estimate)) * 100))
      return `<li><span class="bl-name">${escapeHtml(t.title)}</span>` +
        `<span class="bl-bar"><i style="width:${pct}%"></i></span>` +
        `<span class="bl-num">${t.spent || 0}/${t.estimate || 1}</span></li>`
    }).join('')
    : '<li class="empty">还没有任务</li>'
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
}

function renderUnplanned() {
  el.unplannedEmpty.style.display = unplanned.length ? 'none' : ''
  el.unplannedList.innerHTML = unplanned.map((u) => {
    const when = new Date(u.at).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    return `<li><span class="tag ${u.kind}">${u.kind === 'external' ? '外部' : '内部'}</span>` +
      `<span class="ev-note">${escapeHtml(u.note || '（无备注）')}</span>` +
      `<span class="ev-time">${when}</span>` +
      `<button class="btn tiny" data-del="${u.id}">删</button></li>`
  }).join('')
  for (const b of el.unplannedList.querySelectorAll('button[data-del]')) {
    b.onclick = async () => {
      await fetch('/api/unplanned/' + b.dataset.del, { method: 'DELETE' })
      loadUnplanned()
    }
  }
}

// ---------- 主题 ----------
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme === 'dark' ? 'dark' : 'light'
  el.theme.textContent = theme === 'dark' ? '亮色' : '暗色'
}

// ---------- 服务端通信 ----------
function applyState(s) {
  offset = (s.now || Date.now()) - Date.now()
  state = s
  render()
  renderTasks()
  syncAmbient()
}

async function getJson(path) {
  const r = await fetch(path)
  return r.json()
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

async function patch(path, body) {
  const res = await fetch(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  })
  const data = await res.json()
  if (data && data.now) applyState(data)
  return data
}

async function loadState() {
  const data = await getJson('/api/state')
  settings = data.settings
  tasks = data.tasks || []
  applyState(data.runtime)
  applyTheme(settings.theme)
  fillSettings()
}

async function loadStats() {
  stats = await getJson('/api/stats?days=7&weeks=12')
  renderCharts()
  render()
}

async function loadUnplanned() {
  const d = await getJson('/api/unplanned')
  unplanned = d.unplanned || []
  renderUnplanned()
}

function refreshAll() {
  return Promise.all([loadState(), loadStats(), loadUnplanned(), loadReportAvailability()])
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
  el.toastChk.checked = !!settings.nativeToast
  el.ambient.value = settings.ambient || 'off'
}

function connect() {
  const es = new EventSource('/api/events')
  es.addEventListener('hello', (e) => { const d = JSON.parse(e.data); offset = d.now - Date.now(); state = d; render() })
  es.addEventListener('tick', (e) => applyState(JSON.parse(e.data)))
  es.addEventListener('phase', (e) => onPhase(JSON.parse(e.data)))
  es.addEventListener('session', () => { loadStats() })
  es.addEventListener('settings', (e) => { settings = JSON.parse(e.data); fillSettings(); applyTheme(settings.theme) })
  es.addEventListener('interrupt', () => { loadUnplanned(); loadStats() })
  es.addEventListener('imported', () => { refreshAll() })
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
el.skip.onclick = async () => { await post('/api/timer/skip'); loadStats() }
el.void.onclick = async () => { await post('/api/timer/void', { reason: 'void' }); loadStats() }

el.addTask.onclick = addTask
el.taskTitle.onkeydown = (e) => { if (e.key === 'Enter') addTask() }

el.intIn.onclick = () => recordInterrupt('internal')
el.intOut.onclick = () => recordInterrupt('external')
el.intNote.onkeydown = (e) => { if (e.key === 'Enter') recordInterrupt('internal') }

async function recordInterrupt(kind) {
  await post('/api/unplanned', { kind, note: el.intNote.value.trim() })
  el.intNote.value = ''
  loadUnplanned()
  loadStats()
}

el.theme.onclick = async () => {
  const next = (settings && settings.theme) === 'dark' ? 'light' : 'dark'
  const d = await patch('/api/settings', { theme: next })
  settings = d.settings
  applyTheme(settings.theme)
}

el.save.onclick = async () => {
  const d = await patch('/api/settings', {
    focusMs: Number(el.focus.value) * 60000,
    shortMs: Number(el.short.value) * 60000,
    longMs: Number(el.long.value) * 60000,
    longEvery: Number(el.every.value),
    autoStartBreak: el.autoBreak.checked,
    autoStartFocus: el.autoFocus.checked,
    sound: el.sound.checked,
    tick: el.tick.checked,
    notify: el.notify.checked,
    nativeToast: el.toastChk.checked,
    ambient: el.ambient.value,
  })
  settings = d.settings
  applyState(d.runtime)
  el.hint.textContent = '已保存'
  setTimeout(() => { el.hint.textContent = '' }, 2000)
}

el.mini.onclick = () => { ensureAudio(); openMini() }

// 两个 xlsx 按钮共用这一条下载逻辑：拿 blob → 触发下载 → 顺带把服务端摘要带回来回显。
// 抽出来是因为"直接改 window.location"没法读响应头、也没法在失败时给人话错误。
async function downloadXlsx(url) {
  const res = await fetch(url)
  if (!res.ok) {
    const out = await res.json().catch(() => ({}))
    throw new Error(out.error || ('HTTP ' + res.status))
  }
  const blob = await res.blob()
  const m = (res.headers.get('content-disposition') || '').match(/filename="([^"]+)"/)
  const filename = m ? m[1] : 'pomodmer.xlsx'
  const href = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(href)
  let info = null
  try { info = JSON.parse(res.headers.get('x-pomodmer-info') || 'null') } catch { /* 摘要可选 */ }
  return { filename, size: blob.size, info }
}

el.reportBtn.onclick = async () => {
  el.reportBtn.disabled = true
  el.reportHint.className = 'hint'
  el.reportHint.textContent = '正在生成周报…'
  try {
    // 与「导出数据 xlsx」走同一条下载路径：生成的文件同样落在 output/，但直接交付给浏览器
    const { filename, size, info } = await downloadXlsx('/api/export?format=xlsx&scope=weekly&days=7')
    const extra = info ? `（${info.completed} 个番茄 / ${info.sessions} 条会话 / ${info.sheets} 张表）` : ''
    el.reportHint.textContent = `已下载 ${filename}${extra} · ${Math.round(size / 1024)} KB`
  } catch (e) {
    el.reportHint.className = 'hint err'
    el.reportHint.textContent = '失败：' + e.message
  } finally {
    el.reportBtn.disabled = false
  }
}

async function loadReportAvailability() {
  try {
    const d = await getJson('/api/report')
    if (!d.available) {
      el.reportBtn.disabled = true
      // 直接用服务端给的 hint：能力没启用有三种原因（没装 Python / 装了缺 openpyxl / 被主动关闭），
      // 只有服务端知道是哪一种，前端不要自己编。
      el.reportNote.textContent = (d.hint || '未启用 xlsx 报表能力。') + '（重启后自动生效）'
    } else {
      el.reportBtn.disabled = false
      el.reportNote.textContent = ''
    }
  } catch { /* ignore */ }
}

el.exportBtn.onclick = () => { window.location.href = '/api/export' }

// 全量 xlsx：直接交给浏览器下载（服务端以附件流回，不经前端内存）。
// 先把按钮点成"生成中…"——服务端要拉起 Python worker 写盘，几十条会话也要几百毫秒，
// 没有任何反馈的话用户会以为按钮没反应而反复点。
el.exportXlsxBtn.onclick = async () => {
  el.exportXlsxBtn.disabled = true
  el.ioHint.className = 'hint'
  el.ioHint.textContent = '正在生成 xlsx…'
  try {
    const { filename, size, info } = await downloadXlsx('/api/export?format=xlsx')
    const extra = info ? `（${info.sessions} 条会话 / ${info.sheets} 张表）` : ''
    el.ioHint.textContent = `已导出 ${filename}${extra} · ${Math.round(size / 1024)} KB`
  } catch (e) {
    el.ioHint.className = 'hint err'
    el.ioHint.textContent = '导出失败：' + e.message
  } finally {
    el.exportXlsxBtn.disabled = false
  }
}

el.importBtn.onclick = () => el.fileImport.click()
el.fileImport.onchange = async () => {
  const file = el.fileImport.files && el.fileImport.files[0]
  if (!file) return
  try {
    const text = await file.text()
    const data = JSON.parse(text)
    const res = await fetch('/api/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data }),
    })
    const out = await res.json()
    el.ioHint.textContent = res.ok ? '导入成功' : ('导入失败: ' + (out.error || res.status))
    el.ioHint.className = res.ok ? 'hint' : 'hint err'
    refreshAll()
  } catch (e) {
    el.ioHint.textContent = '导入失败: ' + e.message
    el.ioHint.className = 'hint err'
  }
  el.fileImport.value = ''
}

// 月报与自定义区间：与上面两个 xlsx 按钮共用同一条下载器
async function exportXlsxTo(btn, url, label) {
  btn.disabled = true
  el.ioHint.className = 'hint'
  el.ioHint.textContent = `正在生成${label}…`
  try {
    const { filename, size, info } = await downloadXlsx(url)
    const extra = info ? `（${info.completed} 个番茄 / ${info.sessions} 条会话 / ${info.sheets} 张表）` : ''
    el.ioHint.textContent = `已导出 ${filename}${extra} · ${Math.round(size / 1024)} KB`
  } catch (e) {
    el.ioHint.className = 'hint err'
    el.ioHint.textContent = `${label}导出失败：` + e.message
  } finally {
    btn.disabled = false
  }
}

el.monthBtn.onclick = () => exportXlsxTo(el.monthBtn, '/api/export?format=xlsx&scope=month', '月报')

// 区间默认填最近 7 天，省得每次都手填；用户改了就按用户的来
el.rangeBtn.onclick = () => {
  const from = el.rangeFrom.value
  const to = el.rangeTo.value
  if (!from || !to) {
    const today = new Date()
    const p = (n) => String(n).padStart(2, '0')
    const iso = (d) => `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
    const back = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 6)
    el.rangeFrom.value = el.rangeFrom.value || iso(back)
    el.rangeTo.value = el.rangeTo.value || iso(today)
    el.ioHint.className = 'hint'
    el.ioHint.textContent = `已填好最近 7 天（${el.rangeFrom.value} ~ ${el.rangeTo.value}），再点一次即导出`
    return
  }
  exportXlsxTo(el.rangeBtn, `/api/export?format=xlsx&scope=range&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`, '区间')
}

// ---- P3：xlsx 回灌（先预览，再确认；预览不写库）----
let pendingXlsx = null

function describeXlsx(d) {
  const parts = [
    `任务 +${d.tasks.add}/~${d.tasks.update}/跳过${d.tasks.skip}`,
    `会话 +${d.sessions.add}/跳过${d.sessions.skip}`,
    `事件 +${d.unplanned.add}/跳过${d.unplanned.skip}`,
  ]
  const warn = d.warnings && d.warnings.length ? `；告警 ${d.warnings.length} 条：${d.warnings[0]}` : ''
  return parts.join('；') + warn
}

el.importXlsxBtn.onclick = () => el.fileImportXlsx.click()

el.fileImportXlsx.onchange = async () => {
  const file = el.fileImportXlsx.files && el.fileImportXlsx.files[0]
  if (!file) return
  el.applyXlsxBtn.hidden = true
  pendingXlsx = null
  el.ioHint.className = 'hint'
  el.ioHint.textContent = '正在预览（不会改动数据）…'
  try {
    const res = await fetch('/api/import/xlsx?mode=preview', { method: 'POST', body: file })
    const d = await res.json()
    if (!res.ok) {
      el.ioHint.className = 'hint err'
      el.ioHint.textContent = '预览失败：' + (d.error || res.status)
      return
    }
    pendingXlsx = file
    el.ioHint.textContent = '预览：' + describeXlsx(d)
    el.applyXlsxBtn.hidden = false
  } catch (e) {
    el.ioHint.className = 'hint err'
    el.ioHint.textContent = '预览失败：' + e.message
  }
}

el.applyXlsxBtn.onclick = async () => {
  if (!pendingXlsx) return
  el.applyXlsxBtn.disabled = true
  el.ioHint.className = 'hint'
  el.ioHint.textContent = '正在导入…'
  try {
    const res = await fetch('/api/import/xlsx?mode=apply', { method: 'POST', body: pendingXlsx })
    const d = await res.json()
    if (!res.ok) {
      el.ioHint.className = 'hint err'
      el.ioHint.textContent = '导入失败：' + (d.error || res.status)
      return
    }
    el.ioHint.textContent = '导入完成：' + describeXlsx(d)
    pendingXlsx = null
    el.applyXlsxBtn.hidden = true
    el.fileImportXlsx.value = ''
    refreshAll()
  } catch (e) {
    el.ioHint.className = 'hint err'
    el.ioHint.textContent = '导入失败：' + e.message
  } finally {
    el.applyXlsxBtn.disabled = false
  }
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
  if (!document.hidden) refreshAll()
})

refreshAll().then(connect)
