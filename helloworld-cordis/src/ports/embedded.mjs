// embedded.mjs — 进程内载体：语言运行时被加载进 Cordis 主进程，零 IPC。
//
// 这是三种载体里最快的一种，因为它连 fork 都不做。代价是运行时必须以库的形式存在：
//   node:vm    Node 自身就是 JavaScript 的运行时 → 直接用 vm 沙箱执行源文件
//   node:sqlite SQLite 引擎随 Node 内建 → SQL 文件在内存库里真跑一遍并取回结果集
//   fengari    纯 JS 实现的 Lua 5.3 VM（npm 可选依赖）
//
// 每个 runtime 的实现都必须满足同一条契约：输入源文件绝对路径 + 源码文本，
// 输出「该程序打印到 stdout 的东西」。

import fs from 'node:fs';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import { helloRegistry } from '../registry.mjs';
import { registerEmbedded } from './common.mjs';

const require = createRequire(import.meta.url);

function runInVm(source) {
  // Node 即宿主运行时：把 console.log 换成收集器，在一个干净上下文里执行。
  const lines = [];
  const sandbox = {
    console: {
      log: (...args) => lines.push(args.map((a) => (typeof a === 'string' ? a : JSON.stringify(a))).join(' ')),
      error: (...args) => lines.push(args.join(' ')),
      warn: (...args) => lines.push(args.join(' ')),
    },
    process,
    globalThis: undefined,
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInNewContext(source, sandbox, { filename: 'helloworld.js', timeout: 5000 });
  return lines.join('\n');
}

function runSqlite(source) {
  const { DatabaseSync } = require('node:sqlite');
  const db = new DatabaseSync(':memory:');
  const out = [];
  for (const raw of source.split(';')) {
    const stmtText = raw.trim();
    if (!stmtText) continue;
    const stmt = db.prepare(stmtText);
    try {
      const rows = stmt.all();
      if (rows.length) {
        // 取出结果集首行的第一个列值 —— SELECT 'Hello, World!' 的结果就在这里。
        for (const row of rows) out.push(String(Object.values(row)[0]));
      }
    } catch {
      // 非 SELECT 语句：执行即可，不计入输出。
      stmt.run();
    }
  }
  db.close();
  return out.join('\n');
}

function luaToJs(s) {
  if (s === null || s === undefined) return '';
  // fengari 的 lua_tostring 返回 UTF-8 字节数组
  return Buffer.from(s).toString('utf8');
}

function runFengari(source) {
  const fengari = require('fengari');
  const { lua, lauxlib, lualib, to_luastring } = fengari;
  const L = lauxlib.luaL_newstate();
  lualib.luaL_openlibs(L);

  const lines = [];
  // 用 JS 闭包替换掉 Lua 的 print，就地截获输出（无需碰 stdin/stdout）。
  lua.lua_pushcfunction(L, (Ls) => {
    const parts = [];
    const top = lua.lua_gettop(Ls);
    for (let i = 1; i <= top; i++) {
      parts.push(luaToJs(lua.lua_tostring(Ls, i)));
    }
    lines.push(parts.join('\t'));
    return 0;
  });
  lua.lua_setglobal(L, to_luastring('print'));

  const status = lauxlib.luaL_dostring(L, to_luastring(source));
  if (status !== lua.LUA_OK) {
    let msg = luaToJs(lua.lua_tostring(L, -1));
    lua.lua_close(L);
    throw new Error(`Lua 运行失败: ${msg}`);
  }
  lua.lua_close(L);
  return lines.join('\n');
}

async function runRubyWasm(source) {
  let mod;
  try {
    mod = await import('@ruby/3.2-wasm-wasi/dist/node');
  } catch {
    throw new Error('未安装 Ruby WASM 运行时：npm i @ruby/3.2-wasm-wasi');
  }
  const { DefaultRubyVM } = mod.default ?? mod;
  const response = await fetch('file://' + require.resolve('@ruby/3.2-wasm-wasi/dist/ruby+stdlib.wasm'));
  const module = await WebAssembly.compileStreaming(response);
  const { vm } = await DefaultRubyVM(module);
  const lines = [];
  const orig = console.log;
  console.log = (...a) => lines.push(a.join(' '));
  try {
    vm.eval(source);
  } finally {
    console.log = orig;
  }
  return lines.join('\n');
}

/** runtime key → { run(source, info) } */
export const RUNTIMES = {
  'node:vm': { run: runInVm },
  'node:sqlite': { run: runSqlite },
  fengari: { run: runFengari },
  '@ruby/3.2-wasm-wasi': { run: runRubyWasm },
};

export default function embeddedPort(ctx, config = {}) {
  const id = config.id;
  if (!id) throw new Error('embedded 端口需要 config.id');
  const file = config.file;
  const runtime = config.runtime;
  if (!RUNTIMES[runtime]) throw new Error(`未知的进程内运行时: ${runtime}`);

  const source = fs.readFileSync(file, 'utf8');
  const impl = RUNTIMES[runtime];

  const api = {
    language: config.language,
    family: config.family,
    runtime,
    alive: () => true, // 进程内组件无所谓"存活"；始终可用
    greet() {
      // 同步实现也有必需：串行化 sandbox 副作用，便于重复调用得到稳定结果。
      return impl.run(source, { file });
    },
  };
  return registerEmbedded(ctx, { id, language: config.language, family: config.family, file }, api);
}
