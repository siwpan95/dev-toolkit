// make-icon.mjs —— 生成托盘图标（32x32 PNG，零依赖手写 PNG 编码）
// 为什么要自己生成：托盘需要一个真实 PNG 文件，但仓库不该塞来历不明的二进制；
// 用脚本生成 => 可复现、可审计、体积极小（< 400B）。
import zlib from 'node:zlib'
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const OUT = resolve(__dirname, 'icon.png')
const W = 32
const H = 32

function crc32(buf) {
  let c
  const table = []
  for (let n = 0; n < 256; n++) {
    c = n
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    table[n] = c >>> 0
  }
  let crc = 0xffffffff
  for (const b of buf) crc = table[(crc ^ b) & 0xff] ^ (crc >>> 8)
  return (crc ^ 0xffffffff) >>> 0
}

function chunk(type, data) {
  const len = Buffer.alloc(4)
  len.writeUInt32BE(data.length)
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(body))
  return Buffer.concat([len, body, crc])
}

// 画一个番茄：红色圆身 + 绿色小蒂
const raw = Buffer.alloc((W * 4 + 1) * H)
const cx = 15.5, cy = 18, r = 11
for (let y = 0; y < H; y++) {
  const rowStart = y * (W * 4 + 1)
  raw[rowStart] = 0 // filter: none
  for (let x = 0; x < W; x++) {
    const i = rowStart + 1 + x * 4
    const dx = x - cx
    const dy = y - cy
    const inCircle = dx * dx + dy * dy <= r * r
    const stem = (y < 10 && Math.abs(x - 16) <= (y < 8 ? 1 : 2) && y >= 5)
    if (stem) {
      raw[i] = 0x63; raw[i + 1] = 0x99; raw[i + 2] = 0x22; raw[i + 3] = 255
    } else if (inCircle) {
      // 左上打一点高光，避免纯色块显得呆板
      const hl = (dx + 4) * (dx + 4) + (dy + 5) * (dy + 5) < 16
      raw[i] = hl ? 0xf2 : 0xe2
      raw[i + 1] = hl ? 0x8a : 0x4b
      raw[i + 2] = hl ? 0x88 : 0x4a
      raw[i + 3] = 255
    } else {
      raw[i] = 0; raw[i + 1] = 0; raw[i + 2] = 0; raw[i + 3] = 0
    }
  }
}

const ihdr = Buffer.alloc(13)
ihdr.writeUInt32BE(W, 0)
ihdr.writeUInt32BE(H, 4)
ihdr[8] = 8    // bit depth
ihdr[9] = 6    // color type RGBA
ihdr[10] = 0
ihdr[11] = 0
ihdr[12] = 0

const png = Buffer.concat([
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  chunk('IHDR', ihdr),
  chunk('IDAT', zlib.deflateSync(raw, { level: 9 })),
  chunk('IEND', Buffer.alloc(0)),
])

mkdirSync(dirname(OUT), { recursive: true })
writeFileSync(OUT, png)
console.log('[make-icon] 已生成', OUT, png.length, 'bytes')
