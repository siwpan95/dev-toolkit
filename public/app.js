const stage = document.getElementById('stage')
const script = document.getElementById('script')
const topicsEl = document.getElementById('topics')
const sourcesEl = document.getElementById('sources')
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

// 词源状态：键 = source key（如 "literature"），值 = true/false
let sourceState = {}
// 由 /api/sources 取到的来源统计缓存
let sourceStats = null

function applyFont() {
  script.style.fontSize = fontEl.value + 'px'
}

function applyMirror() {
  document.body.classList.toggle('mirror', mirrorEl.checked)
}

/** 渲染「词源」选择条，并保留当前选中状态。 */
function renderSources(stats) {
  sourceStats = stats
  // 首次加载时默认全部开启
  if (Object.keys(sourceState).length === 0) {
    for (const s of stats.sources) sourceState[s] = true
  }
  sourcesEl.innerHTML = ''
  for (const key of stats.sources) {
    const on = !!sourceState[key]
    const label = (stats.labels && stats.labels[key]) || key
    // 总条目数（三档之和）
    const total = Object.values(stats.stats).reduce(
      (acc, v) => acc + (v.bySource[key] || 0), 0)

    const chip = document.createElement('label')
    chip.className = 'source-chip'
    chip.dataset.on = String(on)
    chip.title = `${label} · 共 ${total} 条`
    chip.innerHTML = `
      <input type="checkbox" ${on ? 'checked' : ''} />
      <span class="label">${label}</span>
      <span class="count">${total}</span>
    `
    const cb = chip.querySelector('input')
    cb.addEventListener('change', () => {
      sourceState[key] = cb.checked
      chip.dataset.on = String(cb.checked)
      drawTopics()
    })
    sourcesEl.appendChild(chip)
  }
}

async function loadSources() {
  try {
    const res = await fetch('/api/sources')
    if (!res.ok) throw new Error('HTTP ' + res.status)
    const data = await res.json()
    renderSources(data)
  } catch (e) {
    sourcesEl.innerHTML = '<span class="chip">词源加载失败</span>'
  }
}

function activeSources() {
  return Object.keys(sourceState).filter((k) => sourceState[k])
}

async function drawTopics() {
  try {
    const params = new URLSearchParams()
    const sel = activeSources()
    // 全部开启时不传 sources（让后端走全集）；
    // 部分开启时显式传 selected 列表，避免误把后端默认全集塞进来。
    if (sel.length > 0 && sel.length < Object.keys(sourceState).length) {
      params.set('sources', sel.join(','))
    }
    const url = '/api/topics/random' + (params.toString() ? '?' + params : '')
    const res = await fetch(url)
    const data = await res.json()
    const t = data.topics || []
    topicsEl.innerHTML = ''
    if (t.every((x) => !x || !x.word || x.word === '—')) {
      topicsEl.innerHTML = '<span class="chip">当前词源无题</span>'
      return
    }
    for (const w of t) {
      const span = document.createElement('span')
      span.className = 'chip'
      const word = (w && w.word) || '—'
      const src = (w && w.source) || ''
      if (src) {
        span.dataset.source = src
        const srcLabel = (sourceStats && sourceStats.labels && sourceStats.labels[src]) || src
        span.innerHTML = `<span class="word">${word}</span><span class="src-tag">${srcLabel}</span>`
      } else {
        span.textContent = word || '—'
      }
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
loadSources()
drawTopics()