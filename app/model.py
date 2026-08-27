"""Model 层 — 数据与业务逻辑。

负责从 helloworld 目录中随机读取一种语言的 Hello World 源码，
并维护当前展示状态（是否已显示、当前语言、当前消息内容）。
视图与控制器不应直接读写文件，统一经由本层。
"""

import os
import random

from .config import LANGUAGE_MAP, LANGUAGES, HELLOWORLD_DIR


class MessageModel:
    def __init__(self):
        self._message = ""
        self._is_displayed = False
        self._helloworld_dir = HELLOWORLD_DIR
        self._language = ""
        self._metadata = {}

    @property
    def message(self) -> str:
        return self._message

    @property
    def language(self) -> str:
        return self._language

    @property
    def metadata(self) -> dict:
        """当前语言的增强元数据（范式/年份/设计者/简介）。"""
        return self._metadata

    @property
    def is_displayed(self) -> bool:
        return self._is_displayed

    def random_helloworld(self) -> None:
        """随机选取一种语言的 Hello World 程序"""
        if not os.path.isdir(self._helloworld_dir):
            self._language = "Unknown"
            self._message = "Hello, World!"
            return
        files = [f for f in os.listdir(self._helloworld_dir) if f.startswith("deepseek_")]
        if not files:
            self._language = "Unknown"
            self._message = "Hello, World!"
            return
        chosen = random.choice(files)
        # 从文件名提取语言关键字: deepseek_<lang>_<date>_<hash>.ext
        parts = chosen.split("_")
        lang_key = parts[1] if len(parts) >= 2 else "unknown"
        self._language = LANGUAGE_MAP.get(lang_key, lang_key.title())
        self._metadata = LANGUAGES.get(lang_key, {})
        filepath = os.path.join(self._helloworld_dir, chosen)
        with open(filepath, "r", encoding="utf-8") as f:
            self._message = f.read().strip()

    def toggle_display(self) -> None:
        """切换消息显示状态"""
        self._is_displayed = not self._is_displayed
