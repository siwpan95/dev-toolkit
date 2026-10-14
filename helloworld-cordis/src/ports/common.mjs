// common.mjs — 各载体共享的助手：输出归一化、模板替换、组件注册（附带可逆效应）。

import { helloRegistry } from '../registry.mjs';
import { probeRequires } from '../probe.mjs';

/**
 * 语言无关的黄金值。perft 之于国际象棋、Hello, World! 之于本项目的地位是对等的：
 * 一个只由语言语义决定、与实现语言本身无关的常量。任何组件的偏差都是真缺陷。
 */
export const GOLDEN = 'Hello, World!';

/**
 * 归一化：取首行非空内容并去掉首尾空白。
 * 各语言的行尾习惯不同（\n / \r\n / 无换行），但不影响语义同一性。
 */
export function normalizeOutput(raw) {
  if (raw === null || raw === undefined) return null;
  const s = String(raw);
  for (const line of s.split(/\r?\n/)) {
    const t = line.trim();
    if (t) return t;
  }
  return '';
}

export function matchesGolden(raw) {
  return normalizeOutput(raw) === GOLDEN;
}

// 命令模板占位符替换。
//  {file}   helloworld 源文件绝对路径
//  {out}    编译产物路径（build/ 下）
//  {outdir} 编译输出目录
//  {node}   宿主 Node 可执行文件
export function fillTemplate(argv, vars) {
  return argv.map((a) =>
    String(a).replace(/\{(\w+)\}/g, (_, k) => (vars[k] !== undefined ? vars[k] : `{${k}}`)),
  );
}

// 注册组件 + 登记撤销动作：卸载时先反注册，再执行载体自己的清理（如杀子进程）。
// 这正是论文里"可逆效应"的具体形态。
function registerWith(ctx, { id, language, family, carrier, file, api, dispose }) {
  const full = { id, language, family, carrier, file, ...api };
  helloRegistry.register(id, full);
  ctx.effect(() => {
    return () => {
      helloRegistry.unregister(id);
      try { dispose?.(); } catch { /* 清理失败不应影响其它组件卸载 */ }
    };
  }, `component-${id}`);
  return full;
}

export function registerEmbedded(ctx, meta, api, dispose) {
  return registerWith(ctx, { ...meta, carrier: 'embedded', api, dispose });
}
export function registerSubprocess(ctx, meta, api, dispose) {
  return registerWith(ctx, { ...meta, carrier: 'subprocess', api, dispose });
}
export function registerGateway(ctx, meta, api, dispose) {
  return registerWith(ctx, { ...meta, carrier: 'gateway', api, dispose });
}

// 二次保险：把 requires 探测失败拦在挂载之前（loader 侧已按清单 disabled，
// 这里防止有人绕过清单直接手工调用端口模块）。
export function assertAvailable(cfg) {
  if (!cfg.requires) return { ok: true, resolved: null, reason: '' };
  const p = probeRequires(cfg.requires);
  if (!p.ok) throw new Error(`组件 ${cfg.id} 缺少依赖：${p.reason}`);
  return p;
}
