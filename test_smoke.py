"""字幕工具冒烟测试（无显示器 / 无需 ffmpeg 也可运行）。

测试内容：
  1. 导入 core 模块（不应报错，且不实例化 Tk）。
  2. parse_srt / serialize_srt 往返一致性：
     造一段 SRT 文本 → parse → serialize → 再 parse，比对条目数与文本。
  3. ffmpeg 相关仅测参数拼接（build_extract_args / build_burn_args），
     不实际执行 ffmpeg。
  4. translate_hook 默认原样返回且长度对齐。

ffmpeg 缺失时仅测纯逻辑，并在结果中注明。

运行：
  python test_smoke.py
"""

from __future__ import annotations

import sys

import core

SAMPLE_SRT = """\
1
00:00:01,000 --> 00:00:04,000
你好，世界。
这是第一行字幕。

2
00:00:05,500 --> 00:00:08,200
第二行字幕内容。
跨行文本第一行
跨行文本第二行。

3
00:01:00,000 --> 00:01:03,000
第三条。
"""


def test_parse_serialize_roundtrip() -> None:
    """parse→serialize→parse 往返一致性。"""
    blocks1 = core.parse_srt(SAMPLE_SRT)
    assert len(blocks1) == 3, f"解析条目数应为 3，实际 {len(blocks1)}"

    # 序列化后再解析，文本应完全一致
    serialized = core.serialize_srt(blocks1)
    blocks2 = core.parse_srt(serialized)

    assert len(blocks2) == len(blocks1), "往返后条目数不一致"
    for a, b in zip(blocks1, blocks2):
        assert a["text"] == b["text"], f"文本不一致：{a['text']!r} != {b['text']!r}"
        assert a["start"] == b["start"], "时间码 start 不一致"
        assert a["end"] == b["end"], "时间码 end 不一致"

    # 跨行文本应被保留
    assert "跨行文本第二行" in blocks2[1]["text"], "跨行文本丢失"
    print(f"[OK] parse/serialize 往返一致：{len(blocks1)} 条，文本无丢失")


def test_build_extract_args() -> None:
    """提取字幕的参数拼接符合预期。"""
    args = core.build_extract_args("movie.mp4", "out.srt")
    assert args == ["-i", "movie.mp4", "-map", "0:s:0", "-y", "out.srt"], args
    print(f"[OK] build_extract_args: {args}")


def test_build_burn_args() -> None:
    """烧录字幕的参数拼接：包含 subtitles 滤镜且路径被转义。"""
    args = core.build_burn_args("movie.mp4", "sub/test.srt", "burned.mp4")
    assert args[0] == "-i" and args[1] == "movie.mp4"
    vf = args[args.index("-vf") + 1]
    assert vf.startswith("subtitles='"), f"subtitles 滤镜缺失: {vf}"
    # Windows 风格路径转义检查（反斜杠→斜杠，冒号→\:）
    escaped = core._escape_subtitles_path(r"C:\subs\test.srt")
    assert "/" in escaped and "\\:" in escaped, f"路径转义异常: {escaped}"
    print(f"[OK] build_burn_args: vf={vf}  转义示例={escaped}")


def test_translate_hook() -> None:
    """translate_hook 默认原样返回，且长度对齐。"""
    texts = ["a", "b", "c"]
    out = core.translate_hook(texts)
    assert out == texts and len(out) == len(texts)
    print(f"[OK] translate_hook 原样返回：{out}")


def main() -> int:
    print("=== 字幕工具冒烟测试 ===")
    exe = core.ffmpeg_path()
    if exe is None:
        print("[注] 未检测到 ffmpeg（shutil.which 返回 None）：仅测试纯逻辑与参数拼接，不执行 ffmpeg。")
    else:
        print(f"[注] 检测到 ffmpeg：{exe}（本测试仍不实际调用 ffmpeg）。")

    test_parse_serialize_roundtrip()
    test_build_extract_args()
    test_build_burn_args()
    test_translate_hook()

    print("=== 全部通过 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
