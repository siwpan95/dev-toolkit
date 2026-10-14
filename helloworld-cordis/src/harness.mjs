// harness.mjs — HelloHarness：跨语言一致性校验器（一个 Cordis Service）。
//
// 类比参考项目：那里用 perft 黄金节点数证明「10 个语言的走子生成器等价」；
// 这里用 Hello, World! 这个语言无关常量证明「N 个语言的运行时与源文件都通了」。
// 二者性质相同 —— 期望值只由语义决定，和实现语言无关，所以任何偏差都是真缺陷。

import { Service } from 'cordis';
import { helloRegistry } from './registry.mjs';
import { GOLDEN, normalizeOutput } from './ports/common.mjs';

export { GOLDEN };

export class HelloHarness extends Service {
  constructor(ctx) {
    super(ctx, 'helloHarness');
    this.lastReport = null;
  }

  /**
   * 驱动全部已挂载组件跑一次 Hello, World!，并与黄金值 + 跨语言众数双向比对。
   * @returns {Promise<{results:Array, consensus:string|null, diverged:string[], failed:string[], agreesGolden:boolean, unknown:string[]}>}
   */
  async run() {
    const results = await helloRegistry.runGreet();
    const supported = results.filter((r) => !r.unsupported);

    const { consensus, diverged } = helloRegistry.analyzeConsensus(supported, normalizeOutput);
    const failed = results.filter((r) => !r.ok && !r.unsupported).map((r) => r.id);
    const agreesGolden = consensus === GOLDEN;
    const unknown = results.filter((r) => r.unsupported).map((r) => r.id);

    const summary = {
      results,
      supportedCount: supported.length,
      consensus,
      diverged,
      failed,
      unknown,
      agreesGolden,
    };

    if (!agreesGolden || diverged.length || failed.length) {
      this.ctx.emit('hello/divergence', summary);
    }
    this.lastReport = summary;
    return summary;
  }

  /** 控制台可读汇总。 */
  formatReport() {
    const rep = this.lastReport;
    if (!rep) return '(尚未运行校验)';
    const lines = [];
    lines.push('=== Cordis HelloHarness: 跨语言 Hello, World! 共识校验 ===');
    lines.push(`黄金值 = ${JSON.stringify(GOLDEN)}   已挂载组件 = ${rep.supportedCount}`);
    lines.push('');
    lines.push('  id            语言           载体          耗时    输出');
    lines.push('  ' + '-'.repeat(74));
    for (const r of rep.results) {
      const shown = r.unsupported
        ? '(未实现 greet)'
        : (r.ok ? JSON.stringify(normalizeOutput(r.out)) : 'ERR ' + (r.error || ''));
      // 非 ASCII 输出一律转义，控制台宽度才不会乱
      const safe = shown.replace(/[^\x20-\x7e]/g, (c) => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0'));
      lines.push(
        `  ${r.id.padEnd(14)} ${String(r.language ?? '').padEnd(14)} ${String(r.carrier ?? '').padEnd(12)} ${String(r.ms + 'ms').padStart(7)}  ${safe.slice(0, 60)}`,
      );
    }
    lines.push('');
    lines.push(`共识值      : ${JSON.stringify(rep.consensus)}`);
    lines.push(`与黄金值一致 : ${rep.agreesGolden ? 'YES' : 'NO'}`);
    if (rep.diverged.length) lines.push(`偏离共识     : ${rep.diverged.join(', ')}`);
    if (rep.failed.length) lines.push(`执行失败     : ${rep.failed.join(', ')}`);
    lines.push(
      rep.agreesGolden && rep.diverged.length === 0 && rep.failed.length === 0
        ? 'OVERALL: ALL LANGUAGES AGREE ON GOLDEN'
        : 'OVERALL: DIVERGENCE DETECTED',
    );
    return lines.join('\n');
  }

  /** 清单里被声明但未挂载的组件（通常是缺工具链）—— 诚实起见必须显式列出。 */
  formatUnmounted() {
    const entries = helloRegistry.loaderApi?.entries ?? [];
    const off = entries.filter((e) => e.disabled);
    if (!off.length) return '（无）';
    const lines = off.map(
      (e) => `  -  ${e.id.padEnd(14)} ${String(e.config.language ?? '').padEnd(14)} 原因: ${e.config.reason || '清单里 enabled: false'}`,
    );
    return `清单声明但未挂载 ${off.length} 项：\n${lines.join('\n')}`;
  }
}

export const harnessPlugin = {
  name: 'hello-harness',
  apply(ctx) {
    new HelloHarness(ctx);
  },
};
