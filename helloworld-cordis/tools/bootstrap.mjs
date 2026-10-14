// bootstrap.mjs — 扫描 helloworld/ → 生成 config/languages.yml 与 config/cordis.yml。
//
// 这一步存在的意义：把「76 个源文件」翻译成「76 条可组合的声明」，让宿主一行代码都不用改。
// 每次 helloworld/ 里新增文件，重跑 `node tools/bootstrap.mjs` 即可自动纳入组合。
//
// 架构边界：本脚本只读 helloworld/，从不写它。

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import * as yaml from 'js-yaml';

import { LANG_DB, slugOf } from './lang-db.mjs';
import { probeRequires } from '../src/probe.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');
const HELLOWORLD = path.resolve(PROJECT_ROOT, '../helloworld');
const CONFIG_DIR = path.join(PROJECT_ROOT, 'config');

const abs = (p) => p.replace(/\\/g, '/');

/** requires 键 → embedded 载体所需的 runtime 名 */
const RUNTIME_OF = {
  'node:vm': 'node:vm',
  'node:sqlite': 'node:sqlite',
  'npm:fengari': 'fengari',
  'npm:@ruby/3.2-wasm-wasi': '@ruby/3.2-wasm-wasi',
};

/**
 * 把命令模板首位的裸可执行名（'python' / 'perl' / 'vbc'）换成探测到的绝对路径。
 * 清单保持人类可读，运行时不依赖 PATH —— Windows 上这一条很关键。
 */
function resolveArgv(argv, spec, probe) {
  if (!Array.isArray(argv) || !argv.length) return argv;
  let absExe = null;
  if (spec.requires === 'node') absExe = process.execPath;
  else if (probe.ok && typeof probe.resolved === 'string' && probe.resolved.includes(path.sep)) absExe = probe.resolved;
  if (!absExe) return argv;
  const head = String(argv[0]);
  if (head !== spec.requires && head !== 'node') return argv;
  return [abs(absExe), ...argv.slice(1)];
}

function main() {
  fs.mkdirSync(CONFIG_DIR, { recursive: true });

  const files = fs.readdirSync(HELLOWORLD).filter((f) => !f.startsWith('.')).sort();

  // ---- 1. 扫描 + 查表 + 探测 ----
  const langs = [];
  const unknown = [];
  for (const f of files) {
    const slug = slugOf(f);
    if (!slug) { unknown.push(f); continue; }
    const spec = LANG_DB[slug];
    if (!spec) { unknown.push(`${f}（语言 slug=${slug} 未在知识库里）`); continue; }
    const probe = probeRequires(spec.requires, PROJECT_ROOT);
    langs.push({
      id: slug,
      language: spec.lang,
      family: spec.family,
      ext: path.extname(f),
      file: abs(path.join(HELLOWORLD, f)),
      spec,
      probe,
      runnable: probe.ok && (spec.carrier !== 'subprocess' || Array.isArray(spec.run)),
    });
  }

  // ---- 2. 写 config/languages.yml（静态知识 + 本机探测结论）----
  const langDoc = {
    meta: {
      source: abs(HELLOWORLD),
      generatedAt: new Date().toISOString(),
      node: process.version,
      platform: process.platform,
      totalFiles: files.length,
      recognized: langs.length,
      runnableHere: langs.filter((l) => l.runnable).length,
    },
    languages: Object.fromEntries(
      langs.map((l) => [l.id, {
        language: l.language,
        family: l.family,
        carrier: l.spec.carrier,
        requires: l.spec.requires,
        run: l.spec.run ?? null,
        build: l.spec.build ?? null,
        note: l.spec.note ?? null,
        probe: { ok: l.probe.ok, resolved: l.probe.resolved, reason: l.probe.reason },
      }]),
    ),
  };
  fs.writeFileSync(path.join(CONFIG_DIR, 'languages.yml'), yaml.dump(langDoc, { lineWidth: 200, sortKeys: false }), 'utf8');

  // ---- 3. 写 config/cordis.yml（Cordis 组合清单）----
  const plugins = {};

  for (const l of langs) {
    const carrier = l.spec.carrier;
    const available = l.runnable;
    const base = {
      carrier,
      enabled: available,
      language: l.language,
      family: l.family,
      file: l.file,
      root: abs(PROJECT_ROOT),
      timeout: 30000,
    };
    if (!available) {
      base.reason = l.probe.reason || '缺少可执行的运行方式';
      plugins[l.id] = base;
      continue;
    }
    if (carrier === 'embedded') {
      plugins[l.id] = { ...base, runtime: RUNTIME_OF[l.spec.requires] ?? l.spec.requires };
    } else if (carrier === 'subprocess') {
      plugins[l.id] = {
        ...base,
        run: resolveArgv(l.spec.run, l.spec, l.probe),
        ...(l.spec.build ? { build: resolveArgv(l.spec.build, l.spec, l.probe) } : {}),
      };
    } else {
      plugins[l.id] = { ...base };
    }
  }

  // ---- 4. 变体组件：同一源文件换载体，用来量化 IPC / 冷启动开销 ----
  //      （参考项目 chess-cordis 用 js↔ts 做同一件事，这里复用相同手法）
  const py = langs.find((l) => l.id === 'python');
  if (py?.probe.ok) {
    plugins['python-warm'] = {
      carrier: 'gateway',
      enabled: true,
      language: 'Python',
      family: 'script',
      variantOf: 'python',
      purpose: '常驻 JSON-stdio worker 版 Python，用于测出「跳过冷启动」省下多少',
      file: py.file,
      root: abs(PROJECT_ROOT),
      cmd: abs(py.probe.resolved),
      args: [abs(path.join(PROJECT_ROOT, 'drivers/gateway.py'))],
      timeout: 30000,
    };
  }
  const js = langs.find((l) => l.id === 'javascript');
  if (js) {
    plugins['javascript-fork'] = {
      carrier: 'subprocess',
      enabled: true,
      language: 'JavaScript',
      family: 'script',
      variantOf: 'javascript',
      purpose: '同一份 .js 改成 fork node 执行，用来测出进程创建的开销',
      file: js.file,
      root: abs(PROJECT_ROOT),
      run: ['{node}', '{file}'],
      timeout: 30000,
    };
  }

  const manifest = {
    meta: {
      generatedAt: new Date().toISOString(),
      note: '本文件是唯一的组合真相。新增语言 = 追加一条 plugins.<id>，宿主/加载器/校验器无需改动。',
      carriers: {
        embedded: '运行时加载进 Cordis 主进程，零 IPC',
        subprocess: '每次调用 fork/exec 一次外部解释器（冷启动）',
        gateway: '常驻 JSON-stdio worker，握一次手后只付调用开销（预热）',
      },
    },
    plugins,
  };
  fs.writeFileSync(path.join(CONFIG_DIR, 'cordis.yml'), yaml.dump(manifest, { lineWidth: 200, sortKeys: false }), 'utf8');

  // ---- 5. 控制台摘要 ----
  const enabled = Object.values(plugins).filter((p) => p.enabled).length;
  console.log(`扫描 ${files.length} 个源文件 → 识别 ${langs.length} 种语言`);
  if (unknown.length) console.log(`未识别 ${unknown.length} 项:\n  ${unknown.join('\n  ')}`);
  console.log(`清单已就绪：${enabled} 个组件可挂载，${Object.keys(plugins).length - enabled} 个因缺工具链 disabled`);
  console.log('  ENABLED :', Object.keys(plugins).filter((k) => plugins[k].enabled).join(', '));
  console.log('  config/languages.yml, config/cordis.yml 已写入');
}

main();
