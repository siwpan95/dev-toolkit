// HelloRegistry — 跨插件共享的唯一组合点（NOT a Cordis Service）。
//
// 为什么用模块单例而不是 Cordis Service：Service 按 Fiber 解析实例，loader 把每个
// 语言组件挂在各自 Fiber 下，做成 Service 会让 harness 在根 ctx 拿到 F 份互不相干的
// 注册表（参考项目 chess-cordis §3.1 踩过这个坑，这里直接沿用修正后的结论）。
//
// 单例只负责「身份」，temporal 语义仍交给 Cordis：每个组件挂载时用 ctx.effect 登记
// 回滚动作（反注册 / 杀子进程），卸载时 Cordis 自动执行。

export class HelloRegistry {
  constructor() {
    /** @type {Map<string, object>} id -> component api */
    this.components = new Map();
    this.ctx = null;
    this.loaderApi = null;
  }

  bindContext(ctx) { this.ctx = ctx; }
  bindLoader(api) { this.loaderApi = api; }

  register(id, api) { this.components.set(id, api); }
  unregister(id) { this.components.delete(id); }
  has(id) { return this.components.has(id); }
  get(id) { return this.components.get(id); }
  list() { return [...this.components.keys()]; }

  snapshot() {
    return [...this.components.entries()].map(([id, c]) => ({
      id, language: c.language, family: c.family, carrier: c.carrier,
    }));
  }

  /**
   * 驱动所有已挂载组件跑一次 greet()，收集 {id, language, family, carrier, out, ok, error, ms}。
   *
   * 注意这里的 await：embedded 载体有的是同步返回（fengari / node:sqlite），
   * subprocess / gateway 载体返回 Promise。`await` 一个非 Promise 是 no-op，
   * 因此同一段代码同时服三种载体 —— 参考项目在这里漏过 await，导致子进程引擎
   * 全体静默 ERR，本实现一开始就把口子堵上。
   */
  async runGreet() {
    const results = [];
    for (const [id, c] of this.components) {
      const rec = {
        id, language: c.language, family: c.family, carrier: c.carrier,
        out: null, ok: false, unsupported: false, error: null, ms: 0,
      };
      if (typeof c.greet !== 'function') {
        rec.unsupported = true;
        results.push(rec);
        continue;
      }
      const t0 = Date.now();
      try {
        rec.out = await c.greet();
        rec.ok = rec.out !== null && rec.out !== undefined;
      } catch (err) {
        rec.error = String(err?.message ?? err);
      }
      rec.ms = Date.now() - t0;
      results.push(rec);
    }
    return results;
  }

  /** 取众数作为共识值，并统计偏离者（简陋错误诊断用）。 */
  analyzeConsensus(results, normalize) {
    const counts = new Map();
    for (const r of results) {
      if (!r.ok) continue;
      const key = normalize(r.out);
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    let consensus = null;
    let best = -1;
    for (const [key, n] of counts) {
      if (n > best) { best = n; consensus = key; }
    }
    const diverged = results
      .filter((r) => r.ok && consensus !== null && normalize(r.out) !== consensus)
      .map((r) => r.id);
    return { consensus, count: best, diverged };
  }
}

export const helloRegistry = new HelloRegistry();
