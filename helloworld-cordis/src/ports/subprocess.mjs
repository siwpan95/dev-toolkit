// subprocess.mjs — 一次性子进程载体：每次 greet() 都 fork/exec 一次外部解释器。
//
// 优点：任何有命令行调用方式的语言都能接进来，与宿主零耦合。
// 代价：解释器冷启动要为每个调用付一遍 —— timing.js 会把这笔钱摊开给你看。
//
// 可选的 build 步骤（编译型语言）：挂载时按 build 模板编译一次，之后只跑产物。
// 这正是参考项目 "drivers/<lang>/ 里做 harness 适配"，引擎目录保持干净的做法。

import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { registerSubprocess, fillTemplate } from './common.mjs';

// 为什么盯着 'exit' 而不是 'close'：
//   'close' 要等 stdio 管道全部关闭，而某些 Windows 编译器（实测 vbc.exe）会派生
//   后台进程继承管道句柄 —— 产物早就写好了、编译器也早退了，'close' 却永远不来，
//   表现为"挂载卡死"。这里以 'exit'（进程本体退出）为准，再留 40ms 排空管道。
function once(cmd, args, { cwd, timeout = 20000 } = {}) {
  return new Promise((resolve, reject) => {
    const proc = spawn(cmd, args, { cwd, stdio: ['ignore', 'pipe', 'pipe'] });
    let out = '';
    let err = '';
    let settled = false;

    const finish = (fn) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      setTimeout(() => fn(), 40); // 排空缓冲
    };

    const timer = setTimeout(() => {
      proc.kill('SIGKILL');
      finish(() => reject(new Error(`timeout: ${cmd} ${args.join(' ')}`)));
    }, timeout);

    proc.stdout.setEncoding('utf8');
    proc.stderr.setEncoding('utf8');
    proc.stdout.on('data', (c) => { out += c; });
    proc.stderr.on('data', (c) => { err += c; });
    proc.on('error', (e) => { finish(() => reject(e)); });
    proc.on('exit', (code) => {
      finish(() => (code === 0
        ? resolve(out)
        : reject(new Error(`exit ${code}${err ? ': ' + err.trim().split(/\r?\n/)[0] : ''}`))));
    });
    proc.on('close', () => finish(() => resolve(out)));
  });
}

// 编译型语言的构建。这里有个 Windows 专属的坑：vbc.exe 编译完就把产物写好了，
// 可它自己不退出（'exit' 永远不来），只会把管道一直占着。于是改成：
//   「产物一出现就算完工，立刻把编译器收掉」——同时也兜底 process exit 与超时。
// 产物存在且比源文件新时直接跳过编译（幂等，重复运行不再白等）。
async function ensureBuilt(bc, bargs, { cwd, artifact, sources, timeout = 60000 }) {
  if (artifact && fs.existsSync(artifact)) {
    const srcTimes = (sources ?? []).map((s) => fs.statSync(s).mtimeMs);
    if (srcTimes.every((t) => t <= fs.statSync(artifact).mtimeMs)) return; // 已是最新
  }
  fs.mkdirSync(path.dirname(artifact), { recursive: true });

  const trace = process.env.TRACE_BUILD ? console.error : () => {};
  let spawnError = null;
  let procExited = false;
  let err = '';

  const proc = spawn(bc, bargs, { cwd, stdio: ['ignore', 'pipe', 'pipe'], detached: true });
  proc.stderr.setEncoding('utf8');
  proc.stderr.on('data', (c) => { err += c; });
  proc.on('exit', (code) => { procExited = true; trace(`[build] exit ${code}`); });
  proc.on('error', (e) => { procExited = true; spawnError = e; });
  trace(`[build] spawn ${bc} ${bargs.join(' ')}\n[build] cwd=${cwd} artifact=${artifact}`);

  // 等产物「稳定」：连续 3 次采样大小不变且非空，才算编译真正落地。
  // 只看一次存在是不够的 —— 实测 vbc 会先把产物写出来再收尾，抢在下一次写之前
  // 判定成功，就会遇到"刚才还在、转眼没了"。
  async function awaitArtifact(ms) {
    const deadline = Date.now() + ms;
    let last = -1;
    let stable = 0;
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 150));
      if (!artifact || !fs.existsSync(artifact)) { stable = 0; continue; }
      const size = fs.statSync(artifact).size;
      if (size > 0 && size === last) {
        if (++stable >= 3) return true;
      } else {
        stable = 0;
      }
      last = size;
    }
    return false;
  }

  const ok = await awaitArtifact(timeout);
  if (!ok) {
    try { proc.kill('SIGKILL'); } catch { /* 已经退了 */ }
    throw new Error(
      `build 超时/失败：${bc} ${bargs.join(' ')}` +
      `${err ? ' | ' + err.trim().split(/\r?\n/)[0] : ''}` +
      `${spawnError ? ' | ' + spawnError : ''}`,
    );
  }

  // 产物稳住了，编译器本身可能还赖着不走（vbc 实测如此），收掉它。
  try { proc.kill('SIGKILL'); } catch { /* 已经退了 */ }
  await new Promise((r) => setTimeout(r, 200));

  if (!fs.existsSync(artifact)) {
    throw new Error(`构建产物在收尾时消失：${artifact}${err ? ': ' + err.trim().split(/\r?\n/)[0] : ''}`);
  }
}

export default function subprocessPort(ctx, config = {}) {
  const id = config.id;
  if (!id) throw new Error('subprocess 端口需要 config.id');

  const file = config.file;
  // 默认把工作目录设到源文件所在目录：实测 vbc.exe 拿绝对路径输入时会静默失败，
  // 换成「相对文件名 + cwd」才成立。对解释器无副作用（它们拿的是绝对路径）。
  const srcDir = path.dirname(file);
  const cwd = config.cwd || srcDir;
  const buildDir = path.resolve(config.root, 'build', id);
  const artifactName = process.platform === 'win32' ? `${id}.exe` : id;
  const vars = {
    file,
    relfile: path.basename(file),
    relout: artifactName,
    node: process.execPath,
    out: path.join(buildDir, artifactName),
    outdir: buildDir,
    outjar: path.join(buildDir, `${id}.jar`),
  };

  // build 是异步的：编译型语言必须在 greet() 可用前把产物准备好。
  // Cordis 的插件工厂允许返回一个 Promise —— 这里就用这个语义。
  const buildPromise = (async () => {
    if (!config.build) return;
    const [bc, ...bargs] = fillTemplate(config.build, vars);
    await ensureBuilt(bc, bargs, {
      cwd,
      artifact: vars.out,
      sources: [file],
      timeout: config.buildTimeout ?? 45000,
    });
  })();

  const [cmd, ...args] = fillTemplate(config.run, vars);

  const api = {
    language: config.language,
    family: config.family,
    argv: [cmd, ...args],
    async greet() {
      await buildPromise; // 首次调用前确保编译完成
      return once(cmd, args, { cwd, timeout: config.timeout ?? 20000 });
    },
  };

  return registerSubprocess(ctx, { id, language: config.language, family: config.family, file }, api);
}
