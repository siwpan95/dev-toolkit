# -*- coding: utf-8 -*-
"""
构建 rime-ice 词频产物（print 输入法候选排序数据源）

借鉴记账（来源）:
  - rime-ice 输入方案（iDvel/rime-ice，GPLv3）的 cn_dicts 词库：
    * base.dict.yaml —— 华宇野风词库 / THUOCL / 现代汉语常用词表 / 腾讯词向量
      （多源合并去重、按「拼音顺序、权重逆序」调频，见其文件头注释）
    * ext.dict.yaml  —— 扩展词库（同口径）
    * tencent.dict.yaml / 41448.dict.yaml / others.dict.yaml 无拼音字段，本脚本不使用；
      8105.dict.yaml 为通用规范汉字表（单字，词频由 char_base.json 覆盖），不并入。
  - 本脚本仅做「词条 + 拼音 + 权重」解析与导出，不改写上游数据；
    产物不入版本库（dictionary/ 已在 .gitignore），仅随安装包 datas 分发；
    程序本体 MIT，词频数据口径与许可注记见 README「数据来源」。

用法:
  python build_rime_freq.py [--src <cn_dicts 目录>] [--min-weight 100] [--max-add 300000]

输出:
  dictionary/rime_ice/rime_freq.pkl    {词(≥2字): 权重}，同词多源取最大权重
  dictionary/rime_ice/rime_words.pkl   {词: (拼音, 权重)}，print 词库(word/idiom)之外的
                                       扩充词，权重 ≥ min-weight，按权重降序取前 max-add
  dictionary/rime_ice/SOURCE.txt       来源与生成信息（随包分发，供货溯源）
"""

import argparse
import os
import pickle
import re
import sys
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_DIR = os.path.join(BASE_DIR, "dictionary")
RIME_OUT_DIR = os.path.join(DICT_DIR, "rime_ice")

# 默认词库源：**不写死盘符**（铁律 5）—— 优先环境变量 RIME_SRC；未设置时由 main() 提示用 --src 指定
DEFAULT_SRC = os.environ.get("RIME_SRC", "")
SOURCE_FILES = ["base.dict.yaml", "ext.dict.yaml"]

# 词条合法性：CJK 汉字 + 常用 ASCII（跳过含生僻/特殊符号的词条）
_VALID_WORD = re.compile(r"^[\u4e00-\u9fffA-Za-z0-9·]+$")

# 排除 print 词库已有词条（word.json + idiom.json）
WORD_JSON = os.path.join(
    DICT_DIR, "chinese-dictionary", "chinese-dictionary-main", "word", "word.json")
IDIOM_JSON = os.path.join(
    DICT_DIR, "chinese-dictionary", "chinese-dictionary-main", "idiom", "idiom.json")


def parse_yaml_dict(path):
    """解析 rime 词库 yaml：跳过注释/元信息行，返回 [(词, 拼音, 权重), ...]"""
    entries = []
    skipped = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n").rstrip("\r")
            if not line or line.startswith("#") or line.startswith("---"):
                continue
            if re.match(r"^[A-Za-z_][A-Za-z0-9_.]*:", line):
                continue  # yaml 元信息行（name:/sort:/import_tables: 等）
            parts = line.split("\t")
            if len(parts) != 3 or not parts[1].strip():
                skipped += 1
                continue
            word, pinyin, weight = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if not word or not pinyin or not weight.isdigit():
                skipped += 1
                continue
            if not _VALID_WORD.match(word) or len(word) < 2:
                skipped += 1
                continue
            entries.append((word, pinyin, int(weight)))
    return entries, skipped


def load_existing_words():
    """加载 print 现有 word.json / idiom.json 的词条集合（用于扩充去重）"""
    import json
    existing = set()
    for p in (WORD_JSON, IDIOM_JSON):
        if not os.path.exists(p):
            print(f"[提示] 未找到 {p}，扩充去重将跳过该文件")
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            for entry in data:
                w = entry.get("word", "")
                if w:
                    existing.add(w)
        except Exception as e:
            print(f"[警告] 读取 {p} 失败: {e}")
    return existing


def main():
    parser = argparse.ArgumentParser(description="构建 rime-ice 词频产物")
    parser.add_argument("--src", default=None, help="cn_dicts 目录（默认读环境变量 RIME_SRC）")
    parser.add_argument("--min-weight", type=int, default=100,
                        help="扩充词最小权重（默认 100）")
    parser.add_argument("--max-add", type=int, default=300000,
                        help="扩充词条数上限（按权重降序，默认 30 万）")
    args = parser.parse_args()

    src = args.src
    if not src:
        src = DEFAULT_SRC
        if not os.path.isdir(src):
            print(f"[错误] 默认词库源不存在（环境变量 RIME_SRC = {src!r}）")
            print("  请用 --src 指定 rime-ice cn_dicts 目录，或设置 RIME_SRC，或从 "
                  "https://github.com/iDvel/rime-ice 下载后解压。")
            sys.exit(1)
    if not os.path.isdir(src):
        print(f"[错误] 词库源目录不存在: {src}")
        sys.exit(1)

    t0 = time.time()
    freq_map = {}   # 词 -> 最大权重
    words_all = {}  # 词 -> (拼音, 权重)（同词多源取最大权重者）
    total = 0
    for name in SOURCE_FILES:
        p = os.path.join(src, name)
        if not os.path.exists(p):
            print(f"[提示] 跳过缺失文件: {name}")
            continue
        entries, skipped = parse_yaml_dict(p)
        for word, pinyin, weight in entries:
            total += 1
            if weight > freq_map.get(word, 0):
                freq_map[word] = weight
                words_all[word] = (pinyin, weight)
        print(f"[解析] {name}: {len(entries)} 条 (跳过 {skipped})")

    print(f"[解析] 合计 {total} 条，去重后 {len(freq_map)} 词")

    # 扩充词：排除 print 已有词库，按权重过滤与截断
    existing = load_existing_words()
    print(f"[去重] print 现有词库 {len(existing)} 词")
    cand = [(w, py, wt) for w, (py, wt) in words_all.items()
            if w not in existing and wt >= args.min_weight]
    cand.sort(key=lambda x: -x[2])
    rime_words = {w: (py, wt) for w, py, wt in cand[: args.max_add]}
    print(f"[扩充] 候选 {len(cand)} 词，收录 {len(rime_words)} 词 "
          f"(权重>={args.min_weight}, 上限 {args.max_add})")

    # 词长分布（供调参参考）
    from collections import Counter
    len_hist = Counter(len(w) for w in freq_map)
    print(f"[分布] 词长直方: {dict(sorted(len_hist.items()))}")

    os.makedirs(RIME_OUT_DIR, exist_ok=True)
    with open(os.path.join(RIME_OUT_DIR, "rime_freq.pkl"), "wb") as f:
        pickle.dump(freq_map, f, pickle.HIGHEST_PROTOCOL)
    with open(os.path.join(RIME_OUT_DIR, "rime_words.pkl"), "wb") as f:
        pickle.dump(rime_words, f, pickle.HIGHEST_PROTOCOL)
    with open(os.path.join(RIME_OUT_DIR, "SOURCE.txt"), "w", encoding="utf-8") as f:
        f.write(
            "rime-ice 词频数据来源注记（build_rime_freq.py 生成）\n"
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"来源: rime-ice (iDvel/rime-ice, GPLv3) cn_dicts: {SOURCE_FILES}\n"
            f"  组成词库: 华宇野风词库 / THUOCL / 现代汉语常用词表 / 腾讯词向量 / 通用规范汉字表 8105\n"
            f"统计: 词频表 {len(freq_map)} 词; 扩充词 {len(rime_words)} 词 (权重>={args.min_weight})\n"
            f"用途: print 输入法候选排序 (程序 MIT; 词频数据沿用 rime-ice 口径)\n"
        )
    print(f"[完成] 输出: {RIME_OUT_DIR} (耗时 {time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
