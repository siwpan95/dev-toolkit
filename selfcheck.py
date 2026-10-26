#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""print（中文拼音输入法）无头自检。

只导入纯逻辑模块（pinyin_syllables / pinyin_dict / pinyin_parser / user_dict），
不导入会创建候选窗口与全局键盘钩子的 ime_core / ime_ui / keyboard_handler / main。

验证点：
  1. 拼音归一化与音节分割：strip_tone、normalize_pinyin、segment_pinyin_greedy
     （含分隔符 ' 指定边界、贪心长音节优先）；
  2. 候选生成：多音节组词（nihao -> 你好 等）、单字查询、候选排序类型标签；
  3. 用户词典状态推进与数据往返：record 累加计数 -> get_user_candidates 排序
     -> save/load 经临时 JSON 往返后数据一致（临时文件写入系统临时目录，
     不改动项目内的 user_dict.json）。
"""
import os
import sys
import tempfile
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


def run_checks():
    import config
    from pinyin_dict import get_pinyin_dict, normalize_pinyin, strip_tone
    from pinyin_parser import CandidateGenerator, segment_pinyin, segment_pinyin_greedy
    from user_dict import UserDict

    checks = []

    # --- 1. 拼音归一化 / 音节分割 -------------------------------------------
    d = get_pinyin_dict()
    if normalize_pinyin("nǐ hǎo") != "nihao":
        raise AssertionError("normalize_pinyin 去声调/空格失败")
    if strip_tone("lǜ") != "lv" or strip_tone("ɡuó") != "guo":
        raise AssertionError("strip_tone 特殊字符归一化失败")

    if segment_pinyin_greedy("nihao") != ["ni", "hao"]:
        raise AssertionError(f"segment_pinyin_greedy('nihao') = {segment_pinyin_greedy('nihao')}")
    if segment_pinyin_greedy("xianshi") != ["xian", "shi"]:
        raise AssertionError(f"贪心长音节匹配失败: {segment_pinyin_greedy('xianshi')}")
    with_apostrophe = segment_pinyin_greedy("nv'er")
    if with_apostrophe != ["nv", "er"]:
        raise AssertionError(f"分隔符分割失败: {with_apostrophe}")
    alts = segment_pinyin("nihao")
    if not alts or ["ni", "hao"] not in alts:
        raise AssertionError(f"segment_pinyin 未给出 ['ni','hao']: {alts[:3]}")
    if len(alts) > 20:
        raise AssertionError(f"分割方案超过上限 20: {len(alts)}")
    checks.append(f"音节分割：nihao->['ni','hao']、xianshi->['xian','shi']、"
                  f"nv'er 按分隔符拆分、回溯方案 {len(alts)} 个")

    # --- 2. 候选词生成（真字典） --------------------------------------------
    gen = CandidateGenerator()
    gen.ensure_dict_loaded()
    if not (d.is_char_loaded and d.is_word_loaded):
        raise AssertionError("单字/词语字典未加载")

    two = gen.generate(["ni", "hao"])
    words = [w for w, _t in two]
    if "你好" not in words:
        raise AssertionError(f"多音节候选缺少「你好」: {words[:8]}")
    if not any(t == "词" for w, t in two if w == "你好"):
        raise AssertionError("「你好」未标记为词典词")

    single = gen.generate(["wo"])
    if not single:
        raise AssertionError("单音节 wo 无候选")
    if any(t not in {"字", "词", "成语", "组词"} for _w, t in single):
        raise AssertionError("候选类型标签越界")
    if not any(t == "字" for _w, t in single):
        raise AssertionError("单音节候选未包含单字")
    if len(two) > 50:
        raise AssertionError(f"候选未按上限裁剪: {len(two)}")
    checks.append(f"候选生成：['ni','hao'] -> 首位「{words[0]}」，单音节 wo -> {len(single)} 条单字候选")

    # --- 3. 用户词典：状态推进 + JSON 往返 ----------------------------------
    original_path = config.USER_DICT_PATH
    tmpdir = tempfile.mkdtemp(prefix="print_selfcheck_")
    try:
        config.USER_DICT_PATH = os.path.join(tmpdir, "user_dict.json")

        ud = UserDict()
        ud.load()
        if ud.word_count != 0:
            raise AssertionError("新建用户词典应为空")

        ud.record("你好", "nihao")
        ud.record("你好", "nihao")
        ud.record("昵好", "nihao")
        if ud.word_count != 2:
            raise AssertionError(f"record 去重失败: {ud.word_count}")
        cands = ud.get_user_candidates("nihao", limit=10)
        if cands != [("你好", 2), ("昵好", 1)]:
            raise AssertionError(f"用户候选排序错误: {cands}")
        if ud.get_frequency_bonus("你好") != 100:
            raise AssertionError(f"频率加成错误: {ud.get_frequency_bonus('你好')}")
        if ud.get_user_candidates("buCunZai"):
            raise AssertionError("不存在的拼音不应返回候选")

        ud.save()
        if not os.path.isfile(config.USER_DICT_PATH):
            raise AssertionError("用户词典未落盘到临时路径")

        reloaded = UserDict()
        reloaded.load()
        if reloaded.word_count != 2:
            raise AssertionError(f"用户词典 JSON 往返条数不一致: {reloaded.word_count}")
        if reloaded.get_user_candidates("nihao") != cands:
            raise AssertionError("用户词典 JSON 往返后候选不一致")
        if reloaded.get_top_words(2)[0][:2] != ("你好", "nihao"):
            raise AssertionError(f"get_top_words 首位错误: {reloaded.get_top_words(2)[:1]}")
        checks.append("用户词典：record 累加/去重 -> 候选排序 -> JSON 存取往返一致")
    finally:
        config.USER_DICT_PATH = original_path
        for name in os.listdir(tmpdir):
            try:
                os.remove(os.path.join(tmpdir, name))
            except OSError:
                pass
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass

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

    print(f"selfcheck ok: print 输入法无头核心逻辑（{'; '.join(checks)}）"
          f" [{time.time() - started:.2f}s]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
