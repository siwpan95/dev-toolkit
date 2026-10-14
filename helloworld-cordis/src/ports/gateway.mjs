// gateway.mjs — 长驻 JSON-stdio 网关载体。
//
// 与 subprocess 载体跑的是同一批源文件，区别只在「解释器什么时候付冷启动的钱」：
//   subprocess：每次 greet() fork 一个新解释器（冷）
//   gateway：启动时握手一次，之后所有请求都在这个常驻进程里换反应（预热）
//
// worker 本身就是 harness 胶水：drivers/gateway.py，
// 绝对不染 helloworld/ 下的任何源文件。
//
// 卸载时 ctx.effect 会执行回滚：先反注册组件，再 SIGKILL 掉子进程 ——
// 与参考 chess-cordis 里子进程引擎的处理一模一样。

import { spawn } from 'node:child_process';
import { registerGateway } from './common.mjs';

export default function gatewayPort(ctx, config = {}) {
  const id = config.id;
  if (!id) throw new Error('gateway 端口需要 config.id');

  const cmd = config.cmd;
  const args = config.args ?? [];
  const timeout = config.timeout ?? 20000;

  const proc = spawn(cmd, args, { cwd: config.cwd, stdio: ['pipe', 'pipe', 'pipe'] });
  let buffer = '';
  let ready = false;
  const pending = new Map();
  let seq = 0;

  proc.stdout.setEncoding('utf8');
  proc.stdout.on('data', (chunk) => {
    buffer += chunk;
    let idx;
    while ((idx = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 1);
      if (!line) continue;
      let msg;
      try { msg = JSON.parse(line); } catch { continue; }
      if (msg.ready) { ready = true; continue; }
      const cb = pending.get(msg.id);
      if (cb) { pending.delete(msg.id); cb(msg); }
    }
  });
  proc.stderr.on('data', () => { /* worker 的诊断输出不干扰协议 */ });

  function rpc(payload) {
    return new Promise((resolve, reject) => {
      const rid = String(++seq);
      const timer = setTimeout(() => {
        pending.delete(rid);
        reject(new Error(`gateway timeout: ${payload.cmd} ${payload.file ?? ''}`));
      }, timeout);
      pending.set(rid, (msg) => { clearTimeout(timer); resolve(msg); });
      proc.stdin.write(JSON.stringify({ ...payload, id: rid }) + '\n');
    });
  }

  const api = {
    language: config.language,
    family: config.family,
    pid: proc.pid,
    alive: () => !proc.killed && proc.exitCode === null,
    async greet() {
      const r = await rpc({ cmd: 'hello', file: config.file });
      if (!r.ok) throw new Error(r.error || 'gateway 执行失败');
      return r.out;
    },
  };

  registerGateway(ctx, { id, language: config.language, family: config.family, file: config.file }, api);
  // 可逆效应：卸载 = 杀掉常驻 worker，不留孤儿进程。
  ctx.effect(() => {
    return () => { try { proc.kill('SIGKILL'); } catch { /* 已退出 */ } };
  }, `kill-${id}`);

  return api;
}
