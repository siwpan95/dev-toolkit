// probe.mjs — 工具链探测。
//
// 决定「哪种语言在本机真的能跑」。这是诚实性的关键：
//   探测通过 → 组件 enabled，真正执行、参与共识
//   探测失败 → 组件 disabled，并在清单里写明缺什么（reason）
//
// 与参考项目 chess-cordis 一致：cpp/go/rust 当初也是因为本机没工具链而 disabled，
// 找到工具链后只改数据、不改代码就点亮。这里把这一步自动化了。

import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);

// Windows 下 PATH 里的可执行文件可能带 .exe/.cmd/.bat 后缀。
const PATHEXT = (process.env.PATHEXT || '.EXE;.CMD;.BAT;.COM').split(';')
  .map((e) => e.toLowerCase())
  .filter(Boolean);

// 这台机器上不在 PATH 里、但确实存在的解释器候选位置（逐条实测过）。
const EXTRA_DIRS = [
  'C:\\Windows\\System32\\WindowsPowerShell\\v1.0',
  'C:\\Program Files\\Git\\bin',
  'C:\\Program Files\\Git\\usr\\bin',
  'C:\\Program Files\\PowerShell\\7',
  'C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319',
];

export function resolveExec(name) {
  if (!name) return null;
  if (path.isAbsolute(name) && fs.existsSync(name)) return name;

  const dirs = [...(process.env.PATH || '').split(path.delimiter).filter(Boolean), ...EXTRA_DIRS];
  for (const dir of dirs) {
    const direct = path.join(dir, name);
    if (fs.existsSync(direct) && fs.statSync(direct).isFile()) return direct;
    // 带后缀再试一遍（Windows）
    if (!path.extname(name)) {
      for (const ext of PATHEXT) {
        const cand = direct + ext;
        if (fs.existsSync(cand) && fs.statSync(cand).isFile()) return cand;
      }
    }
  }
  return null;
}

export function hasNpmPackage(pkg, cwd = process.cwd()) {
  try {
    require.resolve(pkg, { paths: [cwd] });
    return true;
  } catch {
    return false;
  }
}

function nodeFeature(name) {
  switch (name) {
    case 'node:vm':
      return true; // Node 自带
    case 'node:sqlite': {
      try {
        require('node:sqlite');
        return true;
      } catch {
        return false;
      }
    }
    default:
      return false;
  }
}

/**
 * 探测一个 requires 键。
 * 支持的形式：
 *   node                        → 宿主 Node 可执行文件
 *   node:vm / node:sqlite       → Node 内建能力
 *   npm:<pkg>                   → 可选 npm 依赖是否装入
 *   never:<原因>                → 显式放弃自动探测（存在同名系统程序等误判风险）
 *   <其它>                      → PATH / 已知目录下的可执行程序
 * @returns {{ok:boolean, resolved:string|null, reason:string}}
 */
export function probeRequires(key, cwd = process.cwd()) {
  if (!key) return { ok: false, resolved: null, reason: 'requires 未声明' };

  if (key.startsWith('never:')) {
    return { ok: false, resolved: null, reason: key.slice(6) };
  }
  if (key === 'node') {
    return { ok: true, resolved: process.execPath, reason: '' };
  }
  if (key.startsWith('node:')) {
    const ok = nodeFeature(key);
    return { ok, resolved: ok ? key : null, reason: ok ? '' : `Node ${process.version} 不支持 ${key}` };
  }
  if (key === 'npm:none') {    return { ok: false, resolved: null, reason: '尚无可用适配器（esolang 未实现 VM）' };
  }
  if (key.startsWith('npm:')) {
    const pkg = key.slice(4);
    const ok = hasNpmPackage(pkg, cwd);
    return { ok, resolved: ok ? pkg : null, reason: ok ? '' : `可选依赖未安装：npm i ${pkg}` };
  }

  const resolved = resolveExec(key);
  return resolved
    ? { ok: true, resolved, reason: '' }
    : { ok: false, resolved: null, reason: `本机未找到工具链 ${key}` };
}

// 一次性命令行探测（给 `npm run probe` 用）
export function probeAllLangDb(LANG_DB) {
  const report = {};
  for (const [slug, spec] of Object.entries(LANG_DB)) {
    report[slug] = probeRequires(spec.requires);
  }
  return report;
}
