# -*- coding: utf-8 -*-
"""
用户词典
记录用户输入的词语和频率，实现学习功能。
常用的词语会被提升优先级。
"""

import json
import os
import time
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

import config


class UserDict:
    """
    用户词典管理器
    - 记录用户选中的词语
    - 统计使用频率
    - 持久化到 JSON 文件
    """

    def __init__(self):
        self._words: Dict[str, Dict] = {}  # {word: {pinyin, count, last_used}}
        self._dirty = False
        self._loaded = False

    def load(self):
        """从文件加载用户词典"""
        if self._loaded:
            return
        path = config.USER_DICT_PATH
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._words = json.load(f)
                print(f"[用户词典] 已加载 {len(self._words)} 条记录")
            except Exception as e:
                print(f"[用户词典] 加载失败: {e}")
                self._words = {}
        self._loaded = True

    def save(self):
        """保存用户词典到文件"""
        if not self._dirty:
            return
        try:
            with open(config.USER_DICT_PATH, "w", encoding="utf-8") as f:
                json.dump(self._words, f, ensure_ascii=False, indent=2)
            self._dirty = False
        except Exception as e:
            print(f"[用户词典] 保存失败: {e}")

    def record(self, word: str, pinyin: str):
        """
        记录用户选中的词。
        
        Args:
            word: 用户选中的词
            pinyin: 对应的拼音（无声调连写）
        """
        if not word or not pinyin:
            return
        if word not in self._words:
            self._words[word] = {
                "pinyin": pinyin,
                "count": 0,
                "last_used": 0,
            }
        self._words[word]["count"] += 1
        self._words[word]["last_used"] = time.time()
        self._dirty = True

    def get_user_candidates(self, pinyin: str, limit: int = 20) -> List[Tuple[str, int]]:
        """
        获取该拼音下的用户自定义候选词。
        
        Returns:
            [(词, 得分), ...] 按使用频率排序
        """
        results = []
        for word, info in self._words.items():
            if info.get("pinyin", "") == pinyin:
                score = info.get("count", 0)
                results.append((word, score))
        # 按使用次数降序
        results.sort(key=lambda x: -x[1])
        return results[:limit]

    def get_frequency_bonus(self, word: str) -> int:
        """
        获取用户对该词的使用频率加成。
        用于在全局候选排序时提升常用词排名。
        """
        if word in self._words:
            return self._words[word].get("count", 0) * 50
        return 0

    def get_top_words(self, limit: int = 50) -> List[Tuple[str, str, int]]:
        """
        获取使用频率最高的词。
        
        Returns:
            [(词, 拼音, 次数), ...]
        """
        sorted_words = sorted(
            self._words.items(),
            key=lambda x: -x[1].get("count", 0)
        )
        return [
            (word, info.get("pinyin", ""), info.get("count", 0))
            for word, info in sorted_words[:limit]
        ]

    @property
    def word_count(self) -> int:
        return len(self._words)


# 全局单例
_user_dict_instance: Optional[UserDict] = None


def get_user_dict() -> UserDict:
    """获取全局用户词典实例"""
    global _user_dict_instance
    if _user_dict_instance is None:
        _user_dict_instance = UserDict()
    return _user_dict_instance
