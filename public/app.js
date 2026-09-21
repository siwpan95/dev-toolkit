const stage = document.getElementById('stage')
const script = document.getElementById('script')
const topicsEl = document.getElementById('topics')
const btnDraw = document.getElementById('btn-draw')
const btnPlay = document.getElementById('btn-play')
const btnReset = document.getElementById('btn-reset')
const btnFull = document.getElementById('btn-full')
const speedEl = document.getElementById('speed')
const fontEl = document.getElementById('font')
const mirrorEl = document.getElementById('mirror')
const progressBar = document.getElementById('progress-bar')

let playing = false
let lastTs = 0
let rafId = null

function applyFont() {
  script.style.fontSize = fontEl.value + 'px'
}

function applyMirror() {
  document.body.classList.toggle('mirror', mirrorEl.checked)
}

async function drawTopics() {
  try {
    const res = await fetch('/api/topics/random')
    const data = await res.json()
    const t = data.topics || []
    topicsEl.innerHTML = ''
    for (const w of t) {
      const span = document.createElement('span')
      span.className = 'chip'
      span.textContent = w || '—'
      topicsEl.appendChild(span)
    }
  } catch {
    topicsEl.innerHTML = '<span class="chip">出题失败</span>'
  }
}

function scrollStep(ts) {
  if (!playing) return
  if (!lastTs) lastTs = ts
  const dt = (ts - lastTs) / 1000
  lastTs = ts
  const speed = Number(speedEl.value)
  stage.scrollTop += speed * dt
  const max = stage.scrollHeight - stage.clientHeight
  const pct = max > 0 ? (stage.scrollTop / max) * 100 : 0
  progressBar.style.width = pct + '%'
  if (stage.scrollTop >= max - 0.5) {
    pause()
    return
  }
  rafId = requestAnimationFrame(scrollStep)
}

function play() {
  if (!script.innerText.trim()) {
    drawTopics()
    return
  }
  playing = true
  lastTs = 0
  script.setAttribute('contenteditable', 'false')
  btnPlay.textContent = '⏸ 暂停'
  rafId = requestAnimationFrame(scrollStep)
}

function pause() {
  playing = false
  if (rafId) cancelAnimationFrame(rafId)
  script.setAttribute('contenteditable', 'true')
  btnPlay.textContent = '▶ 开始'
}

function toggle() {
  playing ? pause() : play()
}

function reset() {
  pause()
  stage.scrollTop = 0
  progressBar.style.width = '0%'
}

btnDraw.onclick = drawTopics
btnPlay.onclick = toggle
btnReset.onclick = reset
btnFull.onclick = () => {
  if (!document.fullscreenElement) document.documentElement.requestFullscreen()
  else document.exitFullscreen()
}
fontEl.oninput = applyFont
mirrorEl.onchange = applyMirror

document.addEventListener('keydown', (e) => {
  // 编辑模式下不拦截按键，保证正常输入
  if (script.getAttribute('contenteditable') === 'true') return
  if (e.code === 'Space') {
    e.preventDefault()
    toggle()
  } else if (e.key === 'ArrowUp') {
    speedEl.value = Math.min(200, Number(speedEl.value) + 5)
  } else if (e.key === 'ArrowDown') {
    speedEl.value = Math.max(10, Number(speedEl.value) - 5)
  } else if (e.key === 'm' || e.key === 'M') {
    mirrorEl.checked = !mirrorEl.checked
    applyMirror()
  } else if (e.key === 'n' || e.key === 'N') {
    drawTopics()
  }
})

applyFont()
applyMirror()
drawTopics()
