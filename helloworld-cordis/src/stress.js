// 时间维（temporal composability）热插拔压力测试。
//
// 验证的是 Cordis 的核心承诺：运行时摘掉任意一个组件，
//   ① 它被干净地注销；② 它的 OS 子进程真的死了（不是泄漏）；
//   ③ 其余组件照常服务；④ 装回去还能继续通过校验。
// 全程不重启宿主进程。
//
// 三种载体各挑一个代表：python（子进程）、javascript（进程内）、python-warm（长驻网关）。
// Run: node src/stress.js   (退出码 0 = 全部通过)

import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Context } from 'cordis';
import loader from '@cordisjs/plugin-loader';
import { helloRegistry } from './registry.mjs';
import { applyManifest } from './loader.mjs';
import { GOLDEN, normalizeOutput } from './ports/common.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const ctx = new Context();
ctx.baseUrl = new URL('../', import.meta.url);
helloRegistry.bindContext(ctx);

const checks = [];
function record(name, pass, detail = '') {
  checks.push({ name, pass });
  console.log(`${pass ? '[PASS]' : '[FAIL]'} ${name}${detail ? '  — ' + detail : ''}`);
}

/** 让当前所有已挂载组件各跑一次，逐个对着黄金值判定。 */
async function allMatchGolden() {
  const results = await helloRegistry.runGreet();
  const bad = results.filter((r) => !r.ok || normalizeOutput(r.out) !== GOLDEN);
  return {
    pass: results.length > 0 && bad.length === 0,
    info: bad.map((r) => `${r.id}=${r.ok ? JSON.stringify(r.out) : 'ERR:' + r.error}`).join(' | '),
    n: results.length,
  };
}

/** 挑一个存在于清单里的组件 id。 */
function pick(...candidates) {
  for (const id of candidates) {
    if (helloRegistry.has(id)) return id;
  }
  return null;
}

async function hotSwapCycle(label, id) {
  const before = helloRegistry.get(id);
  const pid = before?.pid;

  await ctx.loader.resolve(id).update({ disabled: true });
  const gone = !helloRegistry.has(id);
  let dead = true;
  if (before?.alive) {
    // 给 OS 一点回收时间，再确认子进程真的不在了
    await new Promise((r) => setTimeout(r, 400));
    dead = !before.alive();
  }
  record(`hot-swap ${label}: 已从注册表注销`, gone, `id=${id}`);
  if (pid) record(`hot-swap ${label}: 子进程已被回收`, dead, `pid=${pid}`);

  const during = await allMatchGolden();
  record(`hot-swap ${label}: 摘除期间其余组件照常服务`, during.pass, `${during.n} 个组件${during.info ? ' | ' + during.info : ''}`);

  await ctx.loader.resolve(id).update({ disabled: false });
  const after = await allMatchGolden();
  record(
    `hot-swap ${label}: 重新挂载并通过校验`,
    helloRegistry.has(id) && after.pass,
    `${after.n} 个组件${after.info ? ' | ' + after.info : ''}`,
  );
}

async function main() {
  await ctx.plugin(loader);
  const entries = await applyManifest(ctx, path.join(__dirname, '../config/cordis.yml'));

  const ids = helloRegistry.list().sort();
  record('baseline: 组件按清单挂载', ids.length > 0, ids.join(','));
  const base = await allMatchGolden();
  record('baseline: 全部组件输出黄金值', base.pass, `${base.n} 个组件${base.info ? ' | ' + base.info : ''}`);

  // subprocess 载体（每次 fork 解释器）
  await hotSwapCycle('subprocess', pick('python', 'typescript', 'bash'));
  // embedded 载体（进程内 VM，无子进程）
  await hotSwapCycle('embedded', pick('javascript', 'lua', 'sql'));
  // gateway 载体（常驻 worker，卸载必须连 worker 一起杀掉）
  await hotSwapCycle('gateway', pick('python-warm', 'javascript-fork'));

  const allPass = checks.every((c) => c.pass);
  console.log('---');
  console.log(
    allPass
      ? 'STRESS TEST: ALL PHASES PASS (temporal composability verified)'
      : 'STRESS TEST: FAILURES DETECTED',
  );
  await ctx.fiber.dispose();
  process.exit(allPass ? 0 : 1);
}

main().catch((err) => {
  console.error('stress test crashed:', err);
  process.exit(2);
});
