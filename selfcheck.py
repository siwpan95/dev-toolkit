"""haha 无头自检 —— 不创建 Tk 窗口，只验证数据层与状态机。

只使用标准库 + 项目自身模块（app.config / app.model），
不 import app.view / app.controller / main（GUI 装配层）。

验证点：
1. LANGUAGE_MAP 必须与 LANGUAGES 派生结果一致，元数据字段齐全；
2. random_helloworld() 的「文件名 -> 语言 -> 源码内容 -> 元数据」链路与磁盘一致；
3. toggle_display() 的显示状态按 False -> True -> False 推进。

运行：python selfcheck.py
"""

import os
import random
import sys
import traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.config import HELLOWORLD_DIR, LANGUAGES, LANGUAGE_MAP
from app.model import MessageModel

RANDOM_SEED = 20261026
DRAWS = 60
META_FIELDS = ("name", "ext", "paradigm", "year", "designer", "blurb")


def _display_name(lang_key):
    """与 MessageModel.random_helloworld 相同的「文件名词 -> 显示名」推导。"""
    return LANGUAGE_MAP.get(lang_key, lang_key.title())


def _scan_helloworld():
    """扫描 helloworld/，返回 {显示名: {源码内容, ...}}。"""
    contents = {}
    if not os.path.isdir(HELLOWORLD_DIR):
        return contents
    for fname in sorted(os.listdir(HELLOWORLD_DIR)):
        if not fname.startswith("deepseek_"):
            continue
        parts = fname.split("_")
        if len(parts) < 2:
            continue
        with open(os.path.join(HELLOWORLD_DIR, fname), encoding="utf-8") as f:
            text = f.read().strip()
        contents.setdefault(_display_name(parts[1]), set()).add(text)
    return contents


def check_language_tables():
    """功能点 1：LANGUAGE_MAP 是 LANGUAGES 的派生视图，且元数据字段完整。"""
    derived = {key: meta["name"] for key, meta in LANGUAGES.items()}
    if LANGUAGE_MAP != derived:
        diff = sorted(set(derived.items()) ^ set(LANGUAGE_MAP.items()))[:3]
        return "LANGUAGE_MAP 与 LANGUAGES 派生结果不一致，例：%r" % (diff,)

    broken = sorted(
        key for key, meta in LANGUAGES.items()
        if any(field not in meta for field in META_FIELDS)
    )
    if broken:
        return "LANGUAGES 元数据缺字段：%r" % (broken[:3],)

    if len(LANGUAGES) < 50:
        return "LANGUAGES 条目只有 %d 条，明显少于 helloworld 附属演示的规模" % len(LANGUAGES)
    return ""


def check_random_roundtrip():
    """功能点 2：随机取样后，语言名/源码内容/增强元数据必须与磁盘一致。"""
    contents = _scan_helloworld()
    if not contents:
        return "helloworld 目录不可用或没有 deepseek_* 源文件：%s" % HELLOWORLD_DIR

    model = MessageModel()
    if model.is_displayed or model.message or model.language:
        return "MessageModel 初始状态应为「空消息、未显示」"

    random.seed(RANDOM_SEED)
    seen_languages = set()
    with_metadata = 0
    for i in range(DRAWS):
        model.random_helloworld()
        if model.is_displayed:
            return "第 %d 次取样意外改变了 is_displayed" % i
        if not model.message or not model.language:
            return "第 %d 次取样后 message/language 为空" % i
        if model.language not in contents:
            return "第 %d 次取样语言 %r 不在源文件语言集合中" % (i, model.language)
        if model.message not in contents[model.language]:
            return "第 %d 次取样内容与 %r 的源文件不一致" % (i, model.language)
        if model.metadata:
            with_metadata += 1
            if model.metadata.get("name") != model.language:
                return "第 %d 次取样 metadata.name=%r 与 language=%r 不一致" % (
                    i, model.metadata.get("name"), model.language)
        seen_languages.add(model.language)

    if len(seen_languages) < 2:
        return "%d 次随机取样只命中 1 种语言，随机性可疑" % DRAWS
    if with_metadata == 0:
        return "取样从未命中 LANGUAGES 增强元数据，元数据链路未被使用"
    return ""


def check_display_state():
    """功能点 3：toggle_display 的状态按 False -> True -> False 推进。"""
    model = MessageModel()
    if model.is_displayed:
        return "初始 is_displayed 应为 False"

    model.toggle_display()
    if not model.is_displayed:
        return "第一次 toggle_display 后 is_displayed 仍为 False"

    model.random_helloworld()
    if not model.is_displayed:
        return "random_helloworld() 不应清除显示状态"

    model.toggle_display()
    if model.is_displayed:
        return "第二次 toggle_display 后 is_displayed 仍为 True"
    return ""


def main():
    checks = [
        ("language tables derived from LANGUAGES", check_language_tables),
        ("random_helloworld file->language->message->metadata", check_random_roundtrip),
        ("toggle_display state progression", check_display_state),
    ]
    for label, func in checks:
        try:
            err = func()
        except Exception:
            print("FAIL: %s raised" % label)
            traceback.print_exc()
            return 1
        if err:
            print("FAIL: %s: %s" % (label, err))
            return 1

    print("selfcheck ok: validated %d things -- %s" % (
        len(checks), "; ".join(label for label, _ in checks)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
