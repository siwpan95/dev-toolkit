# -*- coding: utf-8 -*-
"""
拼音字典管理器
负责加载本地字典数据，构建拼音到汉字/词语的倒排索引，并提供查询接口。

数据源:
  - char_base.json   : 单字字典 (20,902 汉字，含拼音和频率)
  - word.json        : 词语字典 (320,000+ 词条，含拼音)
  - idiom.json       : 成语字典 (50,000+ 成语，含拼音)
"""

import json
import os
import pickle
import re
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import config
from pinyin_syllables import PINYIN_SYLLABLES


# ============================================================
# 拼音工具函数
# ============================================================

def strip_tone(pinyin: str) -> str:
    """
    去除拼音中的声调符号，返回无声调拼音。
    同时标准化特殊 Unicode 字符（如 IPA 风格字符）。
    例如: "nǐ" → "ni", "hǎo" → "hao", "lǜ" → "lv", "ɡuó" → "guo"
    """
    tone_map = {
        'ā': 'a', 'á': 'a', 'ǎ': 'a', 'à': 'a',
        'ē': 'e', 'é': 'e', 'ě': 'e', 'è': 'e',
        'ī': 'i', 'í': 'i', 'ǐ': 'i', 'ì': 'i',
        'ō': 'o', 'ó': 'o', 'ǒ': 'o', 'ò': 'o',
        'ū': 'u', 'ú': 'u', 'ǔ': 'u', 'ù': 'u',
        'ǖ': 'v', 'ǘ': 'v', 'ǚ': 'v', 'ǜ': 'v',
        # 鼻音 m, n, ng 的声调
        'ḿ': 'm', 'm̄': 'm', 'ń': 'n', 'ň': 'n', 'ǹ': 'n',
    }
    # 特殊字符标准化：某些字典使用 IPA 风格字符
    char_map = {
        'ɡ': 'g',  # U+0261 LATIN SMALL LETTER SCRIPT G → 普通 g
        'ɑ': 'a',  # U+0251 LATIN SMALL LETTER ALPHA → 普通 a
        'ü': 'v',  # 统一 ü → v
        'Ü': 'v',
    }
    result = []
    for ch in pinyin:
        if ch in tone_map:
            result.append(tone_map[ch])
        elif ch in char_map:
            result.append(char_map[ch])
        else:
            result.append(ch)
    return ''.join(result)


def strip_tone_numbers(pinyin: str) -> str:
    """去除数字声调标记（CC-CEDICT格式）"""
    return re.sub(r'[1-5]', '', pinyin).replace('u:', 'v').replace('U:', 'v')


def normalize_pinyin(pinyin: str) -> str:
    """
    标准化拼音字符串，去除声调、空格等。
    "nǐ hǎo" → "nihao"
    """
    no_tone = strip_tone(pinyin)
    no_tone = no_tone.replace(' ', '').replace("'", '').replace('’', '')
    return no_tone.lower()


def is_displayable_char(ch: str) -> bool:
    """
    判断字符是否可以在常见系统中正常显示。
    过滤掉 CJK 扩展区罕见字（如 𰇹 等）。
    """
    if not ch:
        return False
    cp = ord(ch)
    # 基本 CJK (U+4E00 - U+9FFF)
    if 0x4E00 <= cp <= 0x9FFF:
        return True
    # CJK 扩展 A (U+3400 - U+4DBF)
    if 0x3400 <= cp <= 0x4DBF:
        return True
    # 全角拉丁/数字/符号
    if 0xFF00 <= cp <= 0xFFEF:
        return True
    # ASCII
    if cp < 0x80:
        return True
    # 基本 CJK 兼容 (常用)
    if cp <= 0xF900:
        return True
    # 其他扩展区过滤
    return False


def split_pinyin_spaced(pinyin: str) -> List[str]:
    """
    将空格分隔的带调拼音分割为音节列表（已去调）。
    "nǐ hǎo" → ["ni", "hao"]
    """
    parts = pinyin.strip().split()
    return [strip_tone(p).lower() for p in parts if p]


# ============================================================
# 字典管理器
# ============================================================

class PinyinDict:
    """
    拼音字典管理器
    - 加载 char_base.json → 构建单字倒排索引
    - 加载 word.json → 构建词语倒排索引
    - 加载 idiom.json → 构建成语倒排索引
    - 支持缓存加速加载
    """

    def __init__(self):
        # 倒排索引: {pinyn_syllables: [(word, freq), ...]}
        # key 是无声调拼音连写，如 "nihao"
        self._char_index: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
        self._word_index: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
        self._idiom_index: Dict[str, List[Tuple[str, int]]] = defaultdict(list)

        # 已加载标志
        self._char_loaded = False
        self._word_loaded = False
        self._idiom_loaded = False

    # ---- 单字字典 ----

    def load_char_dict(self, force_rebuild: bool = False):
        """加载单字字典"""
        if self._char_loaded:
            return
        if not force_rebuild and os.path.exists(config.CHAR_INDEX_CACHE):
            self._load_cache("char", config.CHAR_INDEX_CACHE)
        else:
            self._build_char_index()
            self._save_cache("char", config.CHAR_INDEX_CACHE)
        self._char_loaded = True

    def _build_char_index(self):
        """从 char_base.json 构建单字倒排索引"""
        path = config.CHAR_BASE_PATH
        if not os.path.exists(path):
            print(f"[警告] 单字字典不存在: {path}")
            return

        print("[字典] 正在构建单字索引...")
        start = time.time()
        count = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip().rstrip(",")  # 去除末尾逗号
                if not line or line in ("[", "]"):
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                char = entry.get("char", "")
                # 过滤无法显示的罕见字符
                if not is_displayable_char(char):
                    continue
                pinyins = entry.get("pinyin", [])
                freq = entry.get("frequency", 999)

                for py in pinyins:
                    norm = normalize_pinyin(py)
                    if norm:
                        self._char_index[norm].append((char, freq))
                        count += 1

        elapsed = time.time() - start
        print(f"[字典] 单字索引完成: {len(self._char_index)} 个拼音音节, "
              f"{count} 条记录, 耗时 {elapsed:.2f}s")

    # ---- 词语字典 ----

    def load_word_dict(self, force_rebuild: bool = False):
        """加载词语字典"""
        if self._word_loaded or not config.LOAD_WORD_DICT:
            return
        if os.path.exists(config.WORD_DICT_PATH):
            if not force_rebuild and os.path.exists(config.WORD_INDEX_CACHE):
                self._load_cache("word", config.WORD_INDEX_CACHE)
            else:
                self._build_word_index()
                self._save_cache("word", config.WORD_INDEX_CACHE)
        self._word_loaded = True

    def _build_word_index(self):
        """从 word.json 构建词语倒排索引"""
        path = config.WORD_DICT_PATH
        if not os.path.exists(path):
            print(f"[警告] 词语字典不存在: {path}")
            return

        print("[字典] 正在构建词语索引 (文件较大，约需30-60秒)...")
        start = time.time()
        count = 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[错误] 加载词语字典失败: {e}")
            return

        for entry in data:
            word = entry.get("word", "")
            pinyin = entry.get("pinyin", "")
            if not word or not pinyin:
                continue
            # 跳过长词（>6字）以减少索引大小，加快搜索
            if len(word) > 6:
                continue
            syllables = split_pinyin_spaced(pinyin)
            key = "".join(syllables)
            if key:
                # 频率：假设常见度与词的长度和字典位置有关
                freq = max(0, 1000 - len(word) * 10 - count % 500)
                self._word_index[key].append((word, freq))
                count += 1

        elapsed = time.time() - start
        print(f"[字典] 词语索引完成: {len(self._word_index)} 个拼音键, "
              f"{count} 条记录, 耗时 {elapsed:.2f}s")

    # ---- 成语字典 ----

    def load_idiom_dict(self, force_rebuild: bool = False):
        """加载成语字典"""
        if self._idiom_loaded or not config.LOAD_IDIOM_DICT:
            return
        if os.path.exists(config.IDIOM_DICT_PATH):
            if not force_rebuild and os.path.exists(config.IDIOM_INDEX_CACHE):
                self._load_cache("idiom", config.IDIOM_INDEX_CACHE)
            else:
                self._build_idiom_index()
                self._save_cache("idiom", config.IDIOM_INDEX_CACHE)
        self._idiom_loaded = True

    def _build_idiom_index(self):
        """从 idiom.json 构建成语倒排索引"""
        path = config.IDIOM_DICT_PATH
        if not os.path.exists(path):
            print(f"[警告] 成语字典不存在: {path}")
            return

        print("[字典] 正在构建成语索引...")
        start = time.time()
        count = 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[错误] 加载成语字典失败: {e}")
            return

        for entry in data:
            word = entry.get("word", "")
            pinyin = entry.get("pinyin", "")
            if not word or not pinyin:
                continue
            if len(word) > 8:
                continue
            syllables = split_pinyin_spaced(pinyin)
            key = "".join(syllables)
            if key:
                freq = max(0, 500 - count % 200)
                self._idiom_index[key].append((word, freq))
                count += 1

        elapsed = time.time() - start
        print(f"[字典] 成语索引完成: {len(self._idiom_index)} 个拼音键, "
              f"{count} 条记录, 耗时 {elapsed:.2f}s")

    # ---- 加载所有 ----

    def load_all(self, force_rebuild: bool = False):
        """加载所有字典"""
        self.load_char_dict(force_rebuild)
        self.load_word_dict(force_rebuild)
        self.load_idiom_dict(force_rebuild)

    # ---- 缓存读写 ----

    def _load_cache(self, name: str, path: str):
        """从 pickle 文件加载缓存的索引"""
        try:
            with open(path, "rb") as f:
                index = pickle.load(f)
            if isinstance(index, dict):
                if name == "char":
                    self._char_index = defaultdict(list, index)
                elif name == "word":
                    self._word_index = defaultdict(list, index)
                elif name == "idiom":
                    self._idiom_index = defaultdict(list, index)
            print(f"[字典] 从缓存加载 {name} 索引: {path}")
        except Exception as e:
            print(f"[警告] 缓存加载失败 ({name}): {e}")

    def _save_cache(self, name: str, path: str):
        """保存索引到 pickle 缓存"""
        try:
            index = None
            if name == "char":
                index = dict(self._char_index)
            elif name == "word":
                index = dict(self._word_index)
            elif name == "idiom":
                index = dict(self._idiom_index)
            if index is not None:
                with open(path, "wb") as f:
                    pickle.dump(index, f, pickle.HIGHEST_PROTOCOL)
                print(f"[字典] 已缓存 {name} 索引: {path}")
        except Exception as e:
            print(f"[警告] 缓存保存失败 ({name}): {e}")

    # ---- 查询接口 ----

    def lookup_char(self, pinyin: str) -> List[Tuple[str, int]]:
        """
        按拼音查找单字候选。
        pinyin: 无声调拼音，如 "ni", "hao"
        返回: [(汉字, 频率), ...] 按频率升序排列（去重）
        """
        results = self._char_index.get(pinyin.lower(), [])
        # 去重：同音字取最小频率
        seen = {}
        for char, freq in results:
            if char not in seen or freq < seen[char]:
                seen[char] = freq
        deduped = [(k, v) for k, v in seen.items()]
        return sorted(deduped, key=lambda x: x[1])[:config.MAX_CHAR_CANDIDATES]

    def lookup_word(self, pinyin: str) -> List[Tuple[str, int]]:
        """
        按拼音查找词语候选。
        pinyin: 无声调拼音连写，如 "nihao"
        返回: [(词语, 频率), ...]
        """
        results = self._word_index.get(pinyin.lower(), [])
        seen = {}
        for word, freq in results:
            if word not in seen or freq < seen[word]:
                seen[word] = freq
        deduped = [(k, v) for k, v in seen.items()]
        return sorted(deduped, key=lambda x: (x[1], -len(x[0])))[:config.MAX_WORD_CANDIDATES]

    def lookup_idiom(self, pinyin: str) -> List[Tuple[str, int]]:
        """
        按拼音查找成语候选。
        pinyin: 无声调拼音连写，如 "yijibannai"
        返回: [(成语, 频率), ...]
        """
        results = self._idiom_index.get(pinyin.lower(), [])
        seen = {}
        for word, freq in results:
            if word not in seen or freq < seen[word]:
                seen[word] = freq
        deduped = [(k, v) for k, v in seen.items()]
        return sorted(deduped, key=lambda x: x[1])[:config.MAX_IDIOM_CANDIDATES]

    @property
    def is_char_loaded(self) -> bool:
        return self._char_loaded

    @property
    def is_word_loaded(self) -> bool:
        return self._word_loaded

    @property
    def is_idiom_loaded(self) -> bool:
        return self._idiom_loaded


# ============================================================
# 全局单例
# ============================================================

_pinyin_dict_instance: Optional[PinyinDict] = None


def get_pinyin_dict() -> PinyinDict:
    """获取全局字典实例（懒加载）"""
    global _pinyin_dict_instance
    if _pinyin_dict_instance is None:
        _pinyin_dict_instance = PinyinDict()
    return _pinyin_dict_instance
