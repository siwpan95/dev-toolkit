// loader.mjs — 把 config/cordis.yml 喂给真正的 @cordisjs/plugin-loader。
//
// cordis.yml 是唯一的组合真相（SPATIAL composability = 数据而非代码）：
//   新增一种语言  → 追加一条 YAML，宿主/加载器/校验器一行代码都不改
//   运行时摘掉一种 → ctx.loader.resolve(id).update({disabled:true})，
//                    Cordis 回收它的 Fiber，顺便执行它的可逆效应（杀子进程）
//
// 与参考项目 chess-cordis 一致的两个硬性经验：
//   ① EntryGroup.update() 收的是数组，不是按 id 建对象的 map（传对象会报 map is not a function）
//   ② 每个条目的 name 是相对 ctx.baseUrl 解析的模块路径

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as yaml from 'js-yaml';
import { helloRegistry } from './registry.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const PORT_BY_CARRIER = {
  embedded: './src/ports/embedded.mjs',
  subprocess: './src/ports/subprocess.mjs',
  gateway: './src/ports/gateway.mjs',
};

/** 一条清单记录 → 一个真实 loader 条目 { id, name, config, disabled }。 */
function toEntry(id, cfg) {
  const carrier = cfg.carrier ?? 'subprocess';
  const name = PORT_BY_CARRIER[carrier];
  if (!name) throw new Error(`未知载体: ${carrier}（组件 ${id}）`);
  return {
    id,
    name,
    config: { ...cfg, id },
    disabled: cfg.enabled === false,
  };
}

export function manifestToEntries(manifestPath) {
  const doc = yaml.load(fs.readFileSync(manifestPath, 'utf8'));
  const plugins = (doc && doc.plugins) || {};
  return Object.entries(plugins).map(([id, cfg]) => toEntry(id, cfg || {}));
}

/**
 * 应用清单：把每个 enabled 的语言组件安装成一个一等 Cordis 组件。
 * 调用前必须先 await ctx.plugin(loader) 装上真实加载器。
 */
export async function applyManifest(ctx, manifestPath = path.join(__dirname, '../config/cordis.yml')) {
  const entries = manifestToEntries(manifestPath);
  await ctx.loader.root.update(entries);

  // 把热插拔 API 绑到共享单例上（故意不做成 per-fiber Service，
  // 原因见 registry.mjs 顶部注释）。
  helloRegistry.bindLoader({
    mountAll: async () => {
      for (const e of entries) {
        if (!e.disabled) await ctx.loader.resolve(e.id).update({ disabled: false });
      }
    },
    mount: async (id) => ctx.loader.resolve(id).update({ disabled: false }),
    unmount: async (id) => ctx.loader.resolve(id).update({ disabled: true }),
    list: () => helloRegistry.list(),
    isMounted: (id) => helloRegistry.has(id),
    entries,
  });

  return entries;
}
