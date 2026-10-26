#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""subtitle（字幕工具）无头自检。

只导入 core（纯逻辑 + ffmpeg 参数拼接），不导入 main（Tkinter GUI）。

验证点：
  1. SRT 解析：多条目、CRLF 归一化、点号时间码统一为逗号、缺序号自动补号、
     无时间码的坏块被跳过而不抛异常；
  2. 数据往返：parse -> serialize -> parse，条目数、时间码、文本逐字段一致；
  3. 序列化规范：索引递增、块间空行、以单个换行结尾；
  4. ffmpeg 参数拼接：提取用 -map 0:s:0，烧录用 subtitles 滤镜且 Windows
     路径（反斜杠 / 冒号 / 空格）按滤镜语法转义；
  5. 缺 ffmpeg / 视频不存在时返回 (False, 提示) 而不是崩溃。
"""
import os
import sys
import time
import traceback


def _setup_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

SAMPLE_SRT = (
    "1\r\n"
    "00:00:01,000 --> 00:00:04,000\r\n"
    "第一行\r\n"
    "第二行\r\n"
    "\r\n"
    "2\r\n"
    "00:00:05.500 --> 00:00:07,000\r\n"
    "second block\r\n"
    "\r\n"
    "no timecode here\r\n"
    "\r\n"
    "00:00:08,000 --> 00:00:09,250\r\n"
    "第三段（缺序号）\r\n"
)


def run_checks():
    from core import (
        build_burn_args,
        build_extract_args,
        ffmpeg_path,
        parse_srt,
        serialize_srt,
        translate_hook,
    )

    checks = []

    # --- 1. 解析 -------------------------------------------------------------
    blocks = parse_srt(SAMPLE_SRT)
    if len(blocks) != 3:
        raise AssertionError(f"应解析出 3 条（坏块被跳过），实际 {len(blocks)}: {blocks}")
    if [b["index"] for b in blocks] != [1, 2, 3]:
        raise AssertionError(f"缺序号未按顺序补号: {[b['index'] for b in blocks]}")
    if blocks[0]["start"] != "00:00:01,000" or blocks[0]["end"] != "00:00:04,000":
        raise AssertionError(f"时间码保留错误: {blocks[0]}")
    if blocks[0]["text"] != "第一行\n第二行":
        raise AssertionError(f"多行文本错误: {blocks[0]['text']!r}")
    if blocks[1]["start"] != "00:00:05,500":
        raise AssertionError(f"点号时间码未统一为逗号: {blocks[1]['start']!r}")
    if blocks[2]["text"] != "第三段（缺序号）":
        raise AssertionError(f"缺序号块文本错误: {blocks[2]['text']!r}")

    # 空输入 / None 的行为
    if parse_srt("") != []:
        raise AssertionError("空文本应解析为空列表")
    try:
        parse_srt(None)  # type: ignore[arg-type]
    except TypeError:
        pass
    else:
        raise AssertionError("parse_srt(None) 应抛 TypeError")
    checks.append("SRT 解析：多条目/多行文本/缺序号补号/坏块跳过/空输入")

    # --- 2. 序列化 + 往返 ----------------------------------------------------
    text = serialize_srt(blocks)
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise AssertionError(f"序列化应恰以一个换行结尾: {text[-4:]!r}")
    if "\r" in text:
        raise AssertionError("序列化输出不应包含 CR")
    if "\n\n\n" in text:
        raise AssertionError("序列化块间空行过多")

    reparsed = parse_srt(text)
    if len(reparsed) != len(blocks):
        raise AssertionError(f"往返条目数不一致: {len(reparsed)} vs {len(blocks)}")
    for before, after in zip(blocks, reparsed):
        for key in ("index", "start", "end", "text"):
            if before[key] != after[key]:
                raise AssertionError(f"往返字段不一致 {key}: {before[key]!r} -> {after[key]!r}")
    if serialize_srt(reparsed) != text:
        raise AssertionError("二次序列化结果不稳定（非幂等）")
    checks.append(f"SRT 往返：{len(blocks)} 条 parse -> serialize -> parse 逐字段一致且幂等")

    # --- 3. 翻译占位 ---------------------------------------------------------
    src = ["你好", "world"]
    out = translate_hook(src)
    if out != src or out is src:
        raise AssertionError("translate_hook 应返回等长的新列表")
    checks.append("翻译占位：原样返回且不与入参共用列表")

    # --- 4. ffmpeg 参数拼接（纯逻辑，不需要 ffmpeg） -------------------------
    extract = build_extract_args("in.mp4", "out.srt")
    if extract != ["-i", "in.mp4", "-map", "0:s:0", "-y", "out.srt"]:
        raise AssertionError(f"提取参数错误: {extract}")

    win_srt = r"C:\tmp\my subtitles\字幕's.srt"
    burn = build_burn_args("in.mp4", win_srt, "out.mp4")
    if burn[:3] != ["-i", "in.mp4", "-vf"] or burn[-2:] != ["-y", "out.mp4"] or len(burn) != 6:
        raise AssertionError(f"烧录参数结构错误: {burn}")
    expected_vf = "subtitles='C\\:/tmp/my subtitles/字幕\\'s.srt'"
    if burn[3] != expected_vf:
        raise AssertionError(f"烧录滤镜转义错误: {burn[3]!r} != {expected_vf!r}")
    checks.append(f"ffmpeg 参数拼接：提取 -map 0:s:0，烧录滤镜 {burn[3]}")

    # --- 5. 缺少 ffmpeg / 输入不存在时安全失败 ------------------------------
    probe = ffmpeg_path()
    if probe is not None and not os.path.isfile(probe):
        raise AssertionError(f"ffmpeg_path 返回了不存在的路径: {probe}")
    ok, msg = __import__("core").extract_subtitles("no_such_video.mp4", "out.srt")
    if ok is not False or not msg:
        raise AssertionError(f"输入缺失时应安全失败: ({ok}, {msg!r})")
    checks.append(f"异常路径：ffmpeg={'已安装' if probe else '未安装'}，缺视频时返回 (False, 提示) 不崩溃")

    return checks


def main() -> int:
    _setup_stdout()
    started = time.time()
    try:
        checks = run_checks()
    except Exception as exc:
        print(f"selfcheck FAIL: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1

    print(f"selfcheck ok: subtitle 无头核心逻辑（{'; '.join(checks)}）"
          f" [{time.time() - started:.2f}s]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
