// 跨语言耗时表。
//
// 三种载体在这里会显出各自的代价：
//   embedded   运行时就在主进程里，只有计算成本，没有 IPC
//   subprocess 每次调用都要付一次 fork + 解释器冷启动
//   gateway    冷启动只在握手时付一次，之后每次调用只剩计算 + 一遍 JSON-stdio 往返
//
// 两个刻意设置的对照组（和参考项目 chess-cordis 用 js↔ts 隔离 IPC 是同一手法）：
//   javascript vs javascript-fork —— 同一份 .js，只差「进程内」还是「fork node」
//   python     vs python-warm     —— 同一份 .py，只差「冷 fork」还是「长驻 worker」
//
// Run: node src/timing.js [--iterations=N]

import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Context } from 'cordis';
import loader from '@cordisjs/plugin-loader';
import { helloRegistry } from './registry.mjs';
import { applyManifest } from './loader.mjs';
import { normalizeOutput, GOLDEN } from './ports/common.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const argOf = (flag, dflt) => {
  const hit = process.argv.find((a) => a.startsWith(`--${flag}=`));
  return hit ? Number(hit.split('=')[1]) : dflt;
};
const ITER = Math.max(1, argOf('iterations', 5));

const ctx = new Context();
ctx.baseUrl = new URL('../', import.meta.url);
helloRegistry.bindContext(ctx);

async function timeOnce(id) {
  const c = helloRegistry.get(id);
  const t0 = Date.now();
  const out = await c.greet();
  return { ms: Date.now() - t0, ok: normalizeOutput(out) === GOLDEN };
}

async function main() {
  await ctx.plugin(loader);
  await applyManifest(ctx, path.join(__dirname, '../config/cordis.yml'));

  const rows = [];
  for (const id of helloRegistry.list()) {
    const c = helloRegistry.get(id);
    try {
      await timeOnce(id); // warmup
      const samples = [];
      for (let i = 0; i < ITER; i++) {
        const r = await timeOnce(id);
        if (!r.ok) throw new Error('输出与黄金值不符');
        samples.push(r.ms);
      }
      samples.sort((a, b) => a - b);
      rows.push({
        id,
        language: c.language,
        carrier: c.carrier,
        min: samples[0],
        med: samples[Math.floor(samples.length / 2)],
        avg: +(samples.reduce((a, b) => a + b, 0) / samples.length).toFixed(1),
        max: samples[samples.length - 1],
      });
    } catch (e) {
      rows.push({ id, language: c.language, carrier: c.carrier, error: String(e.message ?? e) });
    }
  }

  rows.sort((a, b) => (a.error ? 1 : b.error ? -1 : a.avg - b.avg));

  console.log(`=== 跨语言单次 greet() 耗时（${ITER} 次采样，已预热）===`);
  console.log('');
  console.log('  rank  id              语言           载体          min    中位    平均    最大');
  console.log('  ' + '-'.repeat(78));
  rows.forEach((r, i) => {
    if (r.error) {
      console.log(`  ${String(i + 1).padStart(4)}  ${r.id.padEnd(14)} ${r.language.padEnd(14)} ${r.carrier.padEnd(12)} ERR ${r.error}`);
      return;
    }
    console.log(
      `  ${String(i + 1).padStart(4)}  ${r.id.padEnd(14)} ${r.language.padEnd(14)} ${r.carrier.padEnd(12)} ${String(r.min + 'ms').padStart(7)}${String(r.med + 'ms').padStart(7)}${String(r.avg + 'ms').padStart(8)}${String(r.max + 'ms').padStart(7)}`,
    );
  });

  // ---- 两组受控对照：把 IPC / 冷启动的成本单独挖出来 ----
  const pair = (a, b, title) => {
    const ra = rows.find((r) => r.id === a);
    const rb = rows.find((r) => r.id === b);
    if (!ra || !rb || ra.error || rb.error) return;
    console.log('');
    console.log(`  ${title}`);
    console.log(`    ${a.padEnd(15)} 平均 ${ra.avg}ms`);
    console.log(`    ${b.padEnd(15)} 平均 ${rb.avg}ms`);
    const [fast, slow] = ra.avg <= rb.avg ? [ra, rb] : [rb, ra];
    const ratio = (slow.avg / Math.max(fast.avg, 0.01)).toFixed(0);
    console.log(`    → ${slow.id} 比 ${fast.id} 慢 ${ratio}×（同一份源文件，仅载体不同）`);
  };
  pair('javascript', 'javascript-fork', '[对照 A] javascript(embedded) vs javascript-fork(subprocess) —— 纯 fork 开销');
  pair('python', 'python-warm', '[对照 B] python(subprocess 冷启动) vs python-warm(gateway 预热) —— 解释器冷启动开销');

  await ctx.fiber.dispose();
  process.exit(rows.some((r) => r.error) ? 1 : 0);
}

main().catch((e) => {
  console.error('timing crashed:', e);
  process.exit(2);
});
