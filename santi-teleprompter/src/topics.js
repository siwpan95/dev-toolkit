import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Service } from 'cordis'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
export const ROOT = path.resolve(__dirname, '..')
export const POOLS_DIR = path.join(ROOT, 'pools')

// 三档词池：A=1~2字，B=3~4字，C=5字及以上
export const POOL_KEYS = ['title_A', 'title_B', 'title_C']

export const POOL_LABELS = {
  title_A: '短题（1–2 字）',
  title_B: '中题（3–4 字）',
  title_C: '长题（5 字以上）',
}

// 词源标识 -> 展示名
export const SOURCE_LABELS = {
  literature: '文学少女',
  general: '通用词表',
  meme: '梗百科',
}

// 中文原始 source 名 -> 英文标识（词库文件里写的是中文，便于人工审阅）
const SOURCE_KEY = {
  文学少女: 'literature',
  通用词表: 'general',
  梗百科: 'meme',
}

/**
 * 归一化一条词条。
 * 兼容三种历史/手写格式：
 *   1. "云"                                  （纯字符串，归为文学少女）
 *   2. { word: "云" }
 *   3. { word: "云", source: "梗百科", tags: [...] }
 */
function normalizeEntry(raw) {
  let word, source, tags
  if (typeof raw === 'string') {
    word = raw
  } else if (raw && typeof raw === 'object') {
    word = raw.word
    source = raw.source
    tags = raw.tags
  }
  if (!word || typeof word !== 'string') return null
  word = word.trim()
  if (!word) return null
  return {
    word,
    source: SOURCE_KEY[source] || source || 'literature',
    tags: Array.isArray(tags) ? tags : [],
  }
}

/** 按字/词长度分档（汉字个数），用于校验词条落在预期档位。 */
export function tierOf(word) {
  const n = (word.match(/[\u4e00-\u9fff]/g) || []).length
  if (n <= 2) return 'title_A'
  if (n <= 4) return 'title_B'
  return 'title_C'
}

export function loadPools() {
  const pools = {}
  for (const key of POOL_KEYS) {
    const file = path.join(POOLS_DIR, key, 'words.json')
    try {
      const data = JSON.parse(fs.readFileSync(file, 'utf8'))
      const list = Array.isArray(data) ? data : []
      pools[key] = list.map(normalizeEntry).filter(Boolean)
    } catch {
      pools[key] = []
    }
  }
  return pools
}

export class TopicsService extends Service {
  constructor(ctx, cfg) {
    super(ctx, 'topics')
    this.pools = loadPools()
  }

  /** 全部词源标识（按固定顺序）。 */
  sources() {
    const seen = new Set()
    for (const key of POOL_KEYS) {
      for (const e of this.pools[key]) seen.add(e.source)
    }
    const order = ['literature', 'general', 'meme']
    return [...seen].sort(
      (a, b) => (order.indexOf(a) + 1 || 99) - (order.indexOf(b) + 1 || 99)
    )
  }

  /** 每个档位 × 每个来源的词条数，用于前端展示与筛选。 */
  stats() {
    const out = {}
    for (const key of POOL_KEYS) {
      const bySrc = {}
      for (const e of this.pools[key]) {
        bySrc[e.source] = (bySrc[e.source] || 0) + 1
      }
      out[key] = { total: this.pools[key].length, bySource: bySrc }
    }
    return out
  }

  /**
   * 从 A/B/C 三档各随机抽 1 个词，组成三题。
   * @param {string[]} [sources] 只从这些词源里抽；空/未传 = 全部来源
   */
  randomThree(sources) {
    const allow = Array.isArray(sources) && sources.length ? new Set(sources) : null
    const pick = (arr) => {
      const cand = allow ? arr.filter((e) => allow.has(e.source)) : arr
      if (!cand.length) return null
      return cand[Math.floor(Math.random() * cand.length)]
    }
    const res = POOL_KEYS.map((k) => pick(this.pools[k]))
    return res.map((e) => e || { word: '—', source: null, tags: [] })
  }

  /** 各档总数（兼容旧接口）。 */
  poolsInfo() {
    return Object.fromEntries(
      POOL_KEYS.map((k) => [k, this.pools[k].length])
    )
  }
}
