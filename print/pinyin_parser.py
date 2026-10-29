# -*- coding: utf-8 -*-
"""
拼音解析器
负责将用户输入的拼音字符串分割为合法音节，生成候选词列表。

核心功能:
  1. 拼音音节分割 (如 "nihao" → ["ni", "hao"])
  2. 候选词生成与排序
  3. 智能纠错与模糊匹配
"""

from typing import List, Optional, Tuple

from pinyin_syllables import PINYIN_SYLLABLES
from pinyin_dict import get_pinyin_dict


def segment_pinyin(raw: str) -> List[List[str]]:
    """
    将拼音字符串分割为所有可能的音节组合。
    例如 "nihao" → [["ni", "hao"], ...]
    
    使用贪心 + 回溯算法，优先长音节匹配。
    
    Args:
        raw: 用户输入的拼音字符串（无声调），如 "nihao"
    
    Returns:
        所有可能的分割方案列表
    """
    if not raw:
        return []

    s = raw.lower().strip()
    results = []
    _dfs_segment(s, 0, [], results)

    # 按分割方案质量排序：
    # 1. 优先分割数量少的（即音节更长的方案）
    # 2. 音节数量相同则优先第一个音节更长的
    results.sort(key=lambda seg: (len(seg), -len(seg[0]) if seg else 0))
    return results


def _dfs_segment(s: str, start: int, path: List[str], results: List[List[str]]):
    """
    深度优先搜索分割拼音字符串。
    优先匹配长音节，最多保留20种分割方案。
    """
    if len(results) >= 20:
        return
    if start >= len(s):
        results.append(path[:])
        return

    # 尝试从当前位置匹配所有可能的音节（从长到短）
    for end in range(min(start + 7, len(s)), start, -1):
        candidate = s[start:end]
        if candidate in PINYIN_SYLLABLES:
            path.append(candidate)
            _dfs_segment(s, end, path, results)
            path.pop()

    # 如果当前方案没有匹配任何音节，也尝试单字符跳过
    # （处理用户还在输入中的情况）


def segment_pinyin_greedy(raw: str) -> Optional[List[str]]:
    """
    贪心分割拼音，支持分隔符 ' 手动指定音节边界。
    
    "nihao" → ["ni", "hao"]
    "xianshi" → ["xian", "shi"]
    "nv'er" → ["nv", "er"]   (分隔符指定边界)
    """
    if not raw:
        return []

    s = raw.lower().strip()
    result = []

    # 先按分隔符 ' 分割
    if "'" in s:
        for part in s.split("'"):
            if part:
                sub_result = segment_pinyin_greedy(part)
                if sub_result:
                    result.extend(sub_result)
                else:
                    result.append(part)
        return result

    i = 0
    while i < len(s):
        matched = False
        # 从最长可能音节开始尝试
        for end in range(min(i + 7, len(s)), i, -1):
            candidate = s[i:end]
            if candidate in PINYIN_SYLLABLES:
                result.append(candidate)
                i = end
                matched = True
                break
        if not matched:
            # 无法匹配，保留剩余部分（可能是输入中）
            if i < len(s):
                result.append(s[i:])
            break
    return result


# ============================================================
# 候选词生成器
# ============================================================

class CandidateGenerator:
    """
    候选词生成器
    根据分割后的拼音音节列表，从字典中查找候选词，
    并生成多级候选（单字、词语、成语）。
    """

    def __init__(self):
        self._dict = get_pinyin_dict()

    def ensure_dict_loaded(self):
        """确保字典已加载"""
        self._dict.load_all()

    def generate(self, syllables: List[str]) -> List[Tuple[str, str]]:
        """
        根据拼音音节列表生成候选词列表。
        
        Args:
            syllables: 分割后的拼音音节列表，如 ["ni", "hao"]
        
        Returns:
            [(候选词, 类型标签), ...]
            类型标签: "字", "词", "成语"
        """
        if not syllables:
            return []

        results = []
        pinyin_str = "".join(syllables)

        # 1. 精确匹配：查找词语和成语
        if self._dict.is_word_loaded:
            words = self._dict.lookup_word(pinyin_str)
            for word, freq in words:
                results.append((word, freq, "词"))

        if self._dict.is_idiom_loaded:
            idioms = self._dict.lookup_idiom(pinyin_str)
            for idiom, freq in idioms:
                results.append((idiom, freq, "成语"))

        # 2. 单字组合候选（按音节分别查找单字并组合）
        if self._dict.is_char_loaded and len(syllables) > 1:
            self._generate_char_combinations(syllables, results)

        # 3. 如果只有一个音节，直接查单字
        if self._dict.is_char_loaded and len(syllables) == 1:
            chars = self._dict.lookup_char(syllables[0])
            for char, freq in chars:
                results.append((char, freq, "字"))

        # 4. 对于多音节，也把每个音节的第一个单字候选单独列出
        if len(syllables) > 1 and self._dict.is_char_loaded:
            for syl in syllables:
                chars = self._dict.lookup_char(syl)
                for i, (char, freq) in enumerate(chars[:3]):
                    results.append((char, freq + 200, "字"))

        # 去重（优先保留字典中的"词"类型，其次保留频率最低的）
        seen = {}
        for item in results:
            word = item[0]
            if word not in seen:
                seen[word] = item
            else:
                existing_type = seen[word][2]
                new_type = item[2]
                # 字典词优先于组词，组词优先于单字
                type_priority = {"词": 0, "成语": 1, "组词": 2, "字": 3}
                if type_priority.get(new_type, 9) < type_priority.get(existing_type, 9):
                    seen[word] = item
                elif new_type == existing_type and item[1] < seen[word][1]:
                    seen[word] = item

        # 排序：词 > 成语 > 组词 > 字，同类型按频率升序
        type_order = {"词": 0, "成语": 1, "组词": 2, "字": 3}
        sorted_results = sorted(
            seen.values(),
            key=lambda x: (type_order.get(x[2], 9), x[1], -len(x[0]))
        )

        # 限制候选总数
        return [(item[0], item[2]) for item in sorted_results[:50]]

    def _generate_char_combinations(
        self,
        syllables: List[str],
        results: List[Tuple[str, int, str]]
    ):
        """
        为多音节输入生成单字组合候选。
        例如 ["ni", "hao"] → ["你好", "尼好", ...]
        """
        if len(syllables) > 8:
            return  # 太长不处理

        # 为每个音节获取前N个单字候选
        per_syl_chars = []
        for syl in syllables:
            chars = self._dict.lookup_char(syl)
            if not chars:
                return
            per_syl_chars.append(chars[:5])  # 每个音节取前5个

        # 生成组合
        from itertools import product
        for combo in product(*per_syl_chars):
            combined_word = "".join(c[0] for c in combo)
            combined_freq = sum(c[1] for c in combo) + len(syllables) * 10
            results.append((combined_word, combined_freq, "组词"))

    def quick_lookup(self, pinyin: str) -> List[Tuple[str, str]]:
        """
        快速查阅某个拼音对应的所有候选（不分词）。
        pinyin: 完整拼音连写，如 "nihao"
        """
        self.ensure_dict_loaded()
        syllables = segment_pinyin_greedy(pinyin)
        if syllables:
            return self.generate(syllables)
        return []
