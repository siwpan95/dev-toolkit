#!/usr/bin/env node
// sync-table-kit.mjs —— 把"表格能力三件套"从权威源同步进本项目（带来源锁，防静默漂移）
//
// 为什么需要它：这套能力（bridge.mjs + table.mjs + rpc_server.py）原本在两个仓库里各存一份，
// 结果同一个"日期单元格杀死 worker"的缺陷被两边各自踩了一遍、各修一遍；UTF-8 那个坑也是。
// 复制粘贴治不了这个病，能治的是"单一权威源 + 可验证的来源锁"。
//
// 用法：
//   node tools/sync-table-kit.mjs --check     只体检（不改文件）：锁↔本地、锁↔源 是否一致
//   node tools/sync-table-kit.mjs --lock-only 只体检"锁↔本地"（不依赖权威源在场，适合挂进 smoke/CI）
//   node tools/sync-table-kit.mjs            同步（本地若有未登记的改动会拒绝，除非 --force）
//   node tools/sync-table-kit.mjs --force    强推（丢弃本地对这三件套的改动）
//   --src <dir> / 环境变量 POMODMER_KIT_SRC   指定权威源目录（默认取 tools/table-kit.json 的 defaultDir）
//
// 退出码：0 = 一致 / 同步成功；1 = 有漂移或出错（便于挂进 CI 或 smoke）。
import { readFileSync, writeFileSync, existsSync, mkdirSync, copyFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { dirname, resolve, relative, isAbsolute } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..')
const MANIFEST = resolve(__dirname, 'table-kit.json')
const LOCK = resolve(__dirname, 'table-kit.lock.json')

const argv = process.argv.slice(2)
const has = (flag) => argv.includes(flag)
const valueOf = (flag) => {
  const i = argv.indexOf(flag)
  return i >= 0 ? argv[i + 1] : null
}
const CHECK = has('--check') || has('--lock-only')
const LOCK_ONLY = has('--lock-only')
const FORCE = has('--force')

// 哈希前统一行尾：来源锁要盯的是"内容有没有被改"，不是"这台机器按哪种行尾检出"。
// core.autocrlf=true 的机器把同一提交检出成 CRLF，另一台检出成 LF ——
// 若直接按原始字节哈希，新克隆一上来就体检失败，那是误报，比不检查更糟（会让人学会无视它）。
// 语义变更（多一行、少一行、改一字）照样会被逮住，行尾策略差异则被吸收掉。
const normalizeEol = (buf) => Buffer.from(buf.toString('utf8').replace(/\r\n/g, '\n'), 'utf8')
const sha256 = (buf) => 'sha256:' + createHash('sha256').update(normalizeEol(buf)).digest('hex')
const readIfExists = (p) => (existsSync(p) ? readFileSync(p) : null)

const manifest = JSON.parse(readFileSync(MANIFEST, 'utf8'))
const lockPath = (rel) => resolve(ROOT, rel)
const srcDir = (() => {
  const given = valueOf('--src') || process.env.POMODMER_KIT_SRC || manifest.source.defaultDir
  // 相对路径按仓库根解析（manifest 里的 "../cordis-table-app" 是相对项目根写的意思）
  return isAbsolute(given) ? given : resolve(ROOT, given)
})()

const lock = readIfExists(LOCK) ? JSON.parse(readFileSync(LOCK, 'utf8')) : null
const problems = []
const notes = []

// ---- 体检 1：锁 ↔ 本地文件（这一条不依赖权威源，永远能跑，因此可以进 smoke）----
for (const f of manifest.files) {
  const local = readIfExists(lockPath(f.to))
  if (!local) {
    problems.push(`缺少文件: ${f.to}（锁里有登记，本地却没有）`)
    continue
  }
  const expected = lock && lock.files ? lock.files[f.to] : null
  if (!expected) {
    problems.push(`未登记: ${f.to}（锁里没有它的哈希 —— 说明没走过同步，或锁被改坏）`)
    continue
  }
  const actual = sha256(local)
  if (actual !== expected) {
    problems.push(`本地已漂移: ${f.to}\n      锁记录 ${expected}\n      实际   ${actual}`)
  }
}

// ---- 体检 2：锁 ↔ 权威源（源不在本机时跳过，不算失败）----
const srcCommit = (() => {
  try {
    return execFileSync('git', ['-C', srcDir, 'rev-parse', 'HEAD'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim()
  } catch {
    return null
  }
})()

if (!existsSync(srcDir) || LOCK_ONLY) {
  notes.push(
    LOCK_ONLY
      ? '按 --lock-only 只做"锁 ↔ 本地"体检（不比对权威源）'
      : `权威源目录不存在，跳过源比对：${srcDir}（用 --src 或 POMODMER_KIT_SRC 指定）`,
  )
} else {
  for (const f of manifest.files) {
    const src = readIfExists(resolve(srcDir, f.from))
    if (!src) {
      problems.push(`权威源缺少: ${f.from}`)
      continue
    }
    const local = readIfExists(lockPath(f.to))
    if (CHECK && local && sha256(src) !== sha256(local)) {
      problems.push(`与权威源不一致: ${f.to}（源已更新，本仓库还没同步）`)
    }
  }
  if (srcCommit && lock && lock.source && lock.source.commit && lock.source.commit !== srcCommit && CHECK) {
    notes.push(`权威源 HEAD 已前进：锁记录 ${lock.source.commit.slice(0, 7)}，当前 ${srcCommit.slice(0, 7)}`)
  }
}

if (CHECK) {
  for (const n of notes) console.log('  [info] ' + n)
  if (problems.length) {
    console.log('\n  [FAIL] 表格能力三件套体检未通过（' + problems.length + ' 项）:')
    for (const p of problems) console.log('    - ' + p)
    console.log('\n  修法：node tools/sync-table-kit.mjs（同步后锁会更新）')
    process.exit(1)
  }
  console.log('  [ok] 表格能力三件套与来源锁一致')
  process.exit(0)
}

// ---- 同步：本地漂移默认拒绝，避免把别人手改的东西悄悄覆盖掉 ----
const localDrift = problems.filter((p) => p.startsWith('本地已漂移'))
if (localDrift.length && !FORCE) {
  console.log('  [FAIL] 本地对三件套有未登记的改动，拒绝覆盖：')
  for (const p of localDrift) console.log('    - ' + p)
  console.log('\n  这些改动要么该提到权威源（cordis-table-app）去，要么用 --force 明确丢弃。')
  process.exit(1)
}

if (!existsSync(srcDir)) {
  console.log('  [FAIL] 找不到权威源目录：' + srcDir)
  console.log('  用 --src <dir> 或环境变量 POMODMER_KIT_SRC 指定 cordis-table-app 的位置。')
  process.exit(1)
}

const files = {}
for (const f of manifest.files) {
  const src = resolve(srcDir, f.from)
  const dst = lockPath(f.to)
  const srcBuf = readFileSync(src)
  const before = readIfExists(dst)
  mkdirSync(dirname(dst), { recursive: true })
  copyFileSync(src, dst)
  files[f.to] = sha256(srcBuf)
  const same = before && sha256(before) === files[f.to]
  console.log(`  ${same ? '=' : '↓'} ${f.to}${same ? '（无变化）' : '（已更新）'}`)
}

const nextLock = {
  name: manifest.name,
  syncedAt: new Date().toISOString(),
  source: {
    repo: manifest.source.repo,
    dir: relative(ROOT, srcDir).replace(/\\/g, '/'),
    commit: srcCommit,
  },
  files,
}
writeFileSync(LOCK, JSON.stringify(nextLock, null, 2) + '\n')
console.log('\n  [ok] 已同步 ' + manifest.files.length + ' 个文件；来源锁已更新 -> tools/table-kit.lock.json')
console.log('       权威源: ' + srcDir + (srcCommit ? ' @ ' + srcCommit.slice(0, 7) : '（非 git 目录）'))
for (const n of notes) console.log('  [info] ' + n)
