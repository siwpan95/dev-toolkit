import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Service } from 'cordis'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
export const ROOT = path.resolve(__dirname, '..')
export const POOLS_DIR = path.join(ROOT, 'pools')

// 三档词池：A=1~2字，B=3~4字，C=5字及以上
export const POOL_KEYS = ['title_A', 'title_B', 'title_C']

export function loadPools() {
  const pools = {}
  for (const key of POOL_KEYS) {
    const file = path.join(POOLS_DIR, key, 'words.json')
    try {
      const data = JSON.parse(fs.readFileSync(file, 'utf8'))
      pools[key] = Array.isArray(data) ? data : []
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

  // 从 A/B/C 三档各随机抽 1 个词，组成三题
  randomThree() {
    const pick = (arr) =>
      arr && arr.length ? arr[Math.floor(Math.random() * arr.length)] : '—'
    return [pick(this.pools.title_A), pick(this.pools.title_B), pick(this.pools.title_C)]
  }

  poolsInfo() {
    return Object.fromEntries(
      Object.entries(this.pools).map(([k, v]) => [k, v.length])
    )
  }
}
