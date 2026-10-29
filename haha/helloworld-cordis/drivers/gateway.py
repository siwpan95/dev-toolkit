#!/usr/bin/env python3
# drivers/gateway.py — 常驻 JSON-stdio worker（harness 胶水，不属于 helloworld 源文件）
#
# 协议（每行一个 JSON 对象，与参考项目 chess-cordis 的子进程协议同构）：
#   握手  worker -> host : {"ready": true}
#   请求  host   -> worker: {"id": "1", "cmd": "hello", "file": "<绝对路径>"}
#   响应  worker -> host : {"id": "1", "ok": true,  "out": "Hello, World!\n"}
#                          {"id": "1", "ok": false, "error": "..."}
#
# 关键设计：对 .py 源文件采用「在本进程内 exec + 截获 stdout」而不是再 fork 一层。
# 这样 Python 的冷启动成本只在握手时付一次，后续每次调用只剩字节码开销。
# 非 Python 文件退化到 subprocess.run —— 仍然可用，但不再享受预热收益。

import io
import json
import os
import subprocess
import sys
import contextlib


def run_python_inplace(path):
    """在本 worker 进程里执行一段 Python 源码，截获它想打印的东西。"""
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            exec(compile(source, path, "exec"), {"__name__": "__main__", "__file__": path})
    except SystemExit:
        pass
    return buf.getvalue()


def run_subprocess(argv):
    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    out = proc.stdout.decode("utf-8", "replace")
    if proc.returncode != 0:
        raise RuntimeError("exit %d: %s" % (proc.returncode, proc.stderr.decode("utf-8", "replace").strip()[:200]))
    return out


def handle(msg):
    cmd = msg.get("cmd")
    if cmd == "hello":
        path = msg["file"]
        if path.endswith(".py"):
            return run_python_inplace(path)
        # 非 Python：给 argv 就用 argv，否则退化成直接执行该文件
        argv = msg.get("argv") or [path]
        return run_subprocess(argv)
    if cmd == "run":
        return run_subprocess(msg["argv"])
    if cmd == "ping":
        return "pong"
    raise ValueError("unknown command: %s" % cmd)


def main():
    out = sys.stdout
    out.write(json.dumps({"ready": True}) + "\n")
    out.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception as e:  # 坏帧不能拖死 worker
            out.write(json.dumps({"id": None, "ok": False, "error": "bad frame: %s" % e}) + "\n")
            out.flush()
            continue
        try:
            res = handle(msg)
            out.write(json.dumps({"id": msg.get("id"), "ok": True, "out": res}) + "\n")
        except Exception as e:
            out.write(json.dumps({"id": msg.get("id"), "ok": False, "error": str(e)}) + "\n")
        out.flush()


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
