"""字幕工具核心逻辑（纯逻辑 + ffmpeg 封装）。

设计原则（铁律）：自包含，不 import 其他工具目录，无中心化共享核。
GUI 不直接实例化 Tk()，所有纯逻辑函数在本模块，便于无显示器环境测试。

依赖：Pillow / numpy 已预装，但本工具核心不依赖它们；
      ffmpeg 为系统二进制，运行时需系统已安装（测试时若缺失则仅测纯逻辑）。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess


# ---------------------------------------------------------------------------
# ffmpeg 路径解析
# ---------------------------------------------------------------------------
def ffmpeg_path() -> str | None:
    """返回系统 ffmpeg 可执行文件路径，未找到则返回 None。

    Returns:
        str | None: ffmpeg 的绝对路径，或 None（未安装/不在 PATH）。
    """
    return shutil.which("ffmpeg")


# ---------------------------------------------------------------------------
# 纯逻辑：SRT 解析 / 序列化
# ---------------------------------------------------------------------------
def parse_srt(text: str) -> list[dict]:
    """解析 SRT 字幕文本为结构化条目列表。

    每个条目为字典：{"index": int, "start": str, "end": str, "text": str}。
    start/end 保留原始时间码字符串（如 "00:00:01,000"），避免时区/精度损耗。

    对不符合规范的块尽量健壮处理：
      - 忽略多余空行与首尾空白；
      - 缺少时间码行的块将被跳过并给出告警（不抛异常）。

    Args:
        text (str): 完整 .srt 文本内容。

    Returns:
        list[dict]: 解析后的字幕条目列表（按出现顺序）。
    """
    if text is None:
        raise TypeError("text 不能为 None")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 以一个或多个空行作为块分隔符
    raw_blocks = re.split(r"\n\s*\n", text.strip())
    blocks: list[dict] = []
    timecode_re = re.compile(
        r"^\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*"
        r"(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})"
    )

    for raw in raw_blocks:
        lines = raw.split("\n")
        if not lines or all(not ln.strip() for ln in lines):
            continue

        # 尝试定位时间码行
        tc_idx = -1
        for i, ln in enumerate(lines):
            if timecode_re.match(ln):
                tc_idx = i
                break

        if tc_idx == -1:
            # 没有时间码行的块直接跳过（健壮处理）
            continue

        m = timecode_re.match(lines[tc_idx])
        assert m is not None  # 上面已匹配
        start = m.group(1).replace(".", ",")
        end = m.group(2).replace(".", ",")

        # 时间码行之前若有余行（通常是 index 序号），尝试解析
        index = None
        for pre in lines[:tc_idx]:
            pre = pre.strip()
            if pre.isdigit():
                index = int(pre)
                break

        body = "\n".join(ln for ln in lines[tc_idx + 1:] if ln.strip() != "")
        blocks.append({"index": index, "start": start, "end": end, "text": body})

    # 若未解析出任何 index，按出现顺序补填
    for i, blk in enumerate(blocks, start=1):
        if blk["index"] is None:
            blk["index"] = i

    return blocks


def serialize_srt(blocks: list[dict]) -> str:
    """将结构化字幕条目列表序列化为标准 SRT 文本。

    输出格式：
        1
        00:00:01,000 --> 00:00:04,000
        第一行
        第二行

        2
        ...

    Args:
        blocks (list[dict]): parse_srt 返回的条目列表（或等结构）。
            每条需含 "index"/"start"/"end"/"text" 键。

    Returns:
        str: 规范化的 .srt 文本内容（以单个换行结尾）。

    Raises:
        TypeError: blocks 不是列表。
        ValueError: 条目缺少必要字段。
    """
    if not isinstance(blocks, list):
        raise TypeError("blocks 必须是 list")

    parts: list[str] = []
    for i, blk in enumerate(blocks):
        try:
            index = blk["index"]
            start = blk["start"]
            end = blk["end"]
            content = blk.get("text", "")
        except (KeyError, TypeError) as exc:
            raise ValueError(f"第 {i} 条字幕缺少必要字段: {exc}") from exc

        if index is None:
            index = i + 1
        # 统一时间码分隔符为逗号（SRT 标准）
        start = str(start).replace(".", ",")
        end = str(end).replace(".", ",")

        block_text = str(content).replace("\r\n", "\n").replace("\r", "\n").rstrip()
        parts.append(f"{index}\n{start} --> {end}\n{block_text}")

    return "\n\n".join(parts) + ("\n" if parts else "")


# ---------------------------------------------------------------------------
# 翻译占位（可接翻译 API）
# ---------------------------------------------------------------------------
def translate_hook(texts: list[str]) -> list[str]:
    """翻译占位函数：默认原样返回。

    此处预留接入翻译 API 的位置。实现外部翻译时，可将本函数替换为：
      1. 调用在线翻译接口（如 DeepL / 百度 / 自建 LLM 网关）；
      2. 注意批量发送以降低请求数、处理速率限制与异常；
      3. 返回长度须与输入 texts 一致，保持条目对齐。

    当前为占位实现，不强制联网，便于离线运行与测试。

    Args:
        texts (list[str]): 待翻译文本列表（每条对应一个字幕块文本）。

    Returns:
        list[str]: 翻译后文本列表（默认原样返回）。
    """
    if not isinstance(texts, list):
        raise TypeError("texts 必须是 list[str]")
    return list(texts)


# ---------------------------------------------------------------------------
# ffmpeg 参数拼接（纯逻辑，可测，无需 ffmpeg 存在）
# ---------------------------------------------------------------------------
def _escape_subtitles_path(path: str) -> str:
    """转义字幕滤镜路径中的特殊字符（冒号/反斜杠/单引号）。

    ffmpeg subtitles 滤镜把路径当作表达式，Windows 路径含反斜杠与冒号，
    需按滤镜语法转义，否则解析失败。

    Args:
        path (str): 字幕文件路径。

    Returns:
        str: 转义后的路径字符串。
    """
    return path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def build_extract_args(video: str, out_srt: str) -> list[str]:
    """拼接“从视频提取字幕流”的 ffmpeg 参数列表（不含 ffmpeg 本身路径）。

    命令语义：-map 0:s:0 选取第一条字幕流导出为 .srt。
    本函数只做参数拼接，便于纯逻辑测试，不实际执行。

    Args:
        video (str): 输入视频路径。
        out_srt (str): 输出字幕文件路径。

    Returns:
        list[str]: ffmpeg 参数列表，例如
            ['-i', video, '-map', '0:s:0', '-y', out_srt]
    """
    return ["-i", video, "-map", "0:s:0", "-y", out_srt]


def build_burn_args(video: str, srt: str, out_video: str) -> list[str]:
    """拼接“烧录字幕到视频”的 ffmpeg 参数列表（不含 ffmpeg 本身路径）。

    使用 subtitles 滤镜硬编码字幕。路径经 _escape_subtitles_path 转义。

    Args:
        video (str): 输入视频路径。
        srt (str): 字幕文件路径。
        out_video (str): 输出视频路径。

    Returns:
        list[str]: ffmpeg 参数列表。
    """
    vf = f"subtitles='{_escape_subtitles_path(srt)}'"
    return ["-i", video, "-vf", vf, "-y", out_video]


# ---------------------------------------------------------------------------
# ffmpeg 实际执行封装（运行时需 ffmpeg）
# ---------------------------------------------------------------------------
def extract_subtitles(video: str, out_srt: str) -> tuple[bool, str]:
    """从视频提取字幕流到 .srt。

    运行时需要系统安装 ffmpeg。若未找到 ffmpeg 或视频无字幕流，
    返回 (False, 友好提示)；成功返回 (True, 信息)。

    Args:
        video (str): 输入视频路径。
        out_srt (str): 输出字幕文件路径。

    Returns:
        tuple[bool, str]: (是否成功, 信息/友好提示)。
    """
    exe = ffmpeg_path()
    if exe is None:
        return False, "未找到 ffmpeg，请先系统安装 ffmpeg 并加入 PATH。"

    if not os.path.isfile(video):
        return False, f"输入视频不存在：{video}"

    args = [exe, *build_extract_args(video, out_srt)]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, check=False)
    except OSError as exc:
        return False, f"执行 ffmpeg 失败：{exc}"

    if proc.returncode != 0:
        stderr = (proc.stderr or "").lower()
        if "stream map" in stderr or "no such stream" in stderr:
            return False, "该视频似乎没有字幕流（0:s:0 不存在），无法提取。"
        return False, f"提取失败（ffmpeg 返回码 {proc.returncode}）：\n{proc.stderr}"

    if not os.path.isfile(out_srt):
        return False, "ffmpeg 执行成功但未生成字幕文件，可能视频无字幕流。"

    return True, f"已提取字幕到：{out_srt}"


def burn_subtitles(video: str, srt: str, out_video: str) -> tuple[bool, str]:
    """将 .srt 字幕硬编码（烧录）进视频。

    运行时需要系统安装 ffmpeg。成功返回 (True, 信息)。

    Args:
        video (str): 输入视频路径。
        srt (str): 字幕文件路径。
        out_video (str): 输出视频路径。

    Returns:
        tuple[bool, str]: (是否成功, 信息/友好提示)。
    """
    exe = ffmpeg_path()
    if exe is None:
        return False, "未找到 ffmpeg，请先系统安装 ffmpeg 并加入 PATH。"

    if not os.path.isfile(video):
        return False, f"输入视频不存在：{video}"
    if not os.path.isfile(srt):
        return False, f"字幕文件不存在：{srt}"

    args = [exe, *build_burn_args(video, srt, out_video)]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, check=False)
    except OSError as exc:
        return False, f"执行 ffmpeg 失败：{exc}"

    if proc.returncode != 0:
        return False, f"烧录失败（ffmpeg 返回码 {proc.returncode}）：\n{proc.stderr}"

    if not os.path.isfile(out_video):
        return False, "ffmpeg 执行成功但未生成输出视频。"

    return True, f"已烧录字幕到：{out_video}"
