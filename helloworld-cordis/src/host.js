// Cordis host：把 helloworld 的语言舰队收编进同一套时空可组合架构。
//
// 流程与其它 Cordis 应用别无二致：
//   1. new Context()，把 baseUrl 锚到项目根（loader 用它解析相对模块路径）
//   2. await ctx.plugin(loader)                    ← 真正的 @cordisjs/plugin-loader
//   3. await applyManifest(ctx, config/cordis.yml) ← 声明式挂载全部语言组件
//   4. 挂 HelloHarness service，跑跨语言共识校验
//
// 这里没有一行代码知道"某种语言怎么跑"—— 那件事完全由 config/cordis.yml 决定。
// 加第 N 种语言 = 追加一条 YAML；这在参考项目 chess-cordis 里已经验证过。

import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Context } from 'cordis';
import loader from '@cordisjs/plugin-loader';
import { helloRegistry } from './registry.mjs';
import { harnessPlugin } from './harness.mjs';
import { applyManifest } from './loader.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 允许用另一份清单跑子集：CORDIS_MANIFEST=../config/cordis.subset.yml
const manifestPath = process.env.CORDIS_MANIFEST
  ? path.resolve(__dirname, process.env.CORDIS_MANIFEST)
  : path.join(__dirname, '../config/cordis.yml');

const ctx = new Context();
ctx.baseUrl = new URL('../', import.meta.url);
helloRegistry.bindContext(ctx);

async function main() {
  await ctx.plugin(loader);

  const entries = await applyManifest(ctx, manifestPath);
  const enabled = entries.filter((e) => !e.disabled).length;
  console.log(`[host] 清单已装载：声明 ${entries.length} 项，启用 ${enabled} 项`);

  await ctx.plugin(harnessPlugin);
  const report = await ctx.helloHarness.run();
  console.log(ctx.helloHarness.formatReport());
  console.log('');
  console.log(ctx.helloHarness.formatUnmounted());

  const failed = !report.agreesGolden || report.diverged.length > 0 || report.failed.length > 0;

  await ctx.fiber.dispose();
  process.exit(failed ? 1 : 0);
}

main().catch((err) => {
  console.error('host crashed:', err);
  process.exit(2);
});
