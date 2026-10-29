# -*- coding: utf-8 -*-
"""
输入法候选窗口 UI
使用 tkinter 绘制候选词窗口，支持键盘选择候选词
"""

import tkinter as tk
from tkinter import font as tkfont
from typing import Callable, List, Optional, Tuple

import config


class CandidateWindow:
    """
    候选词浮动窗口
    
    功能:
    - 显示拼音输入内容
    - 显示候选词列表（带编号）
    - 支持键盘上下翻页
    - 支持鼠标点击选择
    """

    def __init__(self, on_select: Optional[Callable] = None):
        """
        Args:
            on_select: 选中候选词时的回调函数 (word, pinyin) -> None
        """
        self._on_select = on_select
        self._root: Optional[tk.Tk] = None
        self._visible = False

        # 当前状态
        self._pinyin_input = ""       # 当前输入的拼音
        self._candidates: List[Tuple[str, str]] = []  # [(词, 类型), ...]
        self._current_page = 0
        self._total_pages = 0

        # UI 元素
        self._pinyin_label: Optional[tk.Label] = None
        self._candidate_labels: List[tk.Label] = []
        self._candidate_numbers: List[tk.Label] = []
        self._page_label: Optional[tk.Label] = None

        # 字体
        self._candidate_font = None
        self._pinyin_font = None
        self._number_font = None

        self._setup_ui()

    def _setup_ui(self):
        """初始化 tkinter 窗口"""
        self._root = tk.Tk()
        self._root.title("")
        self._root.overrideredirect(True)  # 无边框窗口
        self._root.attributes("-topmost", True)  # 置顶
        self._root.attributes("-alpha", 0.95)  # 微微透明

        # 窗口大小
        self._root.geometry(
            f"{config.CANDIDATE_WINDOW_WIDTH}x{config.CANDIDATE_WINDOW_HEIGHT}"
        )

        # 背景
        self._root.configure(bg=config.BG_COLOR)

        # 创建边框效果（内边距frame）
        self._main_frame = tk.Frame(
            self._root, bg=config.BG_COLOR,
            highlightbackground=config.BORDER_COLOR,
            highlightthickness=1,
        )
        self._main_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # 顶部内边距
        self._top_spacer = tk.Frame(self._main_frame, bg=config.BG_COLOR, height=8)
        self._top_spacer.pack(fill=tk.X)
        self._top_spacer.pack_forget()

        # 字体设置
        try:
            self._candidate_font = tkfont.Font(
                family=config.CANDIDATE_FONT_NAME,
                size=config.CANDIDATE_FONT_SIZE,
            )
        except Exception:
            self._candidate_font = tkfont.Font(size=config.CANDIDATE_FONT_SIZE)

        try:
            self._pinyin_font = tkfont.Font(
                family=config.CANDIDATE_FONT_NAME,
                size=config.PINYIN_FONT_SIZE,
            )
        except Exception:
            self._pinyin_font = tkfont.Font(size=config.PINYIN_FONT_SIZE)

        try:
            self._number_font = tkfont.Font(
                family=config.CANDIDATE_FONT_NAME,
                size=config.CANDIDATE_FONT_SIZE,
                weight="bold",
            )
        except Exception:
            self._number_font = tkfont.Font(
                size=config.CANDIDATE_FONT_SIZE, weight="bold"
            )

        # 拼音显示区域
        self._pinyin_frame = tk.Frame(
            self._main_frame, bg=config.BG_COLOR, height=30
        )
        self._pinyin_frame.pack(fill=tk.X, padx=12, pady=(8, 2))
        self._pinyin_frame.pack_propagate(False)

        self._pinyin_label = tk.Label(
            self._pinyin_frame,
            text="",
            font=self._pinyin_font,
            fg=config.PINYIN_COLOR,
            bg=config.BG_COLOR,
            anchor="w",
        )
        self._pinyin_label.pack(fill=tk.BOTH, expand=True)

        # 分隔线
        self._separator = tk.Frame(
            self._main_frame, bg=config.BORDER_COLOR, height=1
        )

        # 候选词列表区域
        self._candidate_frame = tk.Frame(self._main_frame, bg=config.BG_COLOR)
        self._candidate_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=2)

        # 创建候选词标签（最多9个，对应数字键1-9）
        self._candidate_labels = []
        self._candidate_numbers = []
        for i in range(config.CANDIDATES_PER_PAGE):
            row_frame = tk.Frame(self._candidate_frame, bg=config.BG_COLOR)
            row_frame.pack(fill=tk.X, pady=1)

            # 数字标签
            num_label = tk.Label(
                row_frame,
                text=str(i + 1),
                font=self._number_font,
                fg=config.HIGHLIGHT_TEXT_COLOR,
                bg=config.BG_COLOR,
                width=2,
                anchor="e",
            )
            num_label.pack(side=tk.LEFT, padx=(0, 6))

            # 候选词标签
            cand_label = tk.Label(
                row_frame,
                text="",
                font=self._candidate_font,
                fg=config.CANDIDATE_COLOR,
                bg=config.BG_COLOR,
                anchor="w",
            )
            cand_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

            self._candidate_numbers.append(num_label)
            self._candidate_labels.append(cand_label)

        # 底部翻页提示
        self._bottom_frame = tk.Frame(self._main_frame, bg=config.BG_COLOR, height=24)
        self._bottom_frame.pack(fill=tk.X, padx=12, pady=(2, 6))
        self._bottom_frame.pack_propagate(False)

        self._page_label = tk.Label(
            self._bottom_frame,
            text="",
            font=self._pinyin_font,
            fg=config.PINYIN_COLOR,
            bg=config.BG_COLOR,
            anchor="e",
        )
        self._page_label.pack(side=tk.RIGHT)

        # 隐藏窗口
        self._root.withdraw()
        # 强制刷新以确保窗口状态同步（否则 deiconify 可能无效）
        self._root.update_idletasks()

    def show(self, x: int, y: int):
        """在指定位置显示窗口"""
        if not self._root:
            return
        self._root.geometry(f"+{x}+{y}")
        self._root.deiconify()
        # 无边框窗口必须显式 lift 和更新才能确保显示
        self._root.lift()
        self._root.update_idletasks()
        self._visible = True

    def hide(self):
        """隐藏窗口"""
        if self._root:
            self._root.withdraw()
        self._visible = False

    def update_candidates(
        self,
        pinyin_input: str,
        candidates: List[Tuple[str, str]],
        page: int = 0,
    ):
        """
        更新候选词显示。
        
        Args:
            pinyin_input: 当前输入的拼音字符串
            candidates: 候选词列表 [(词, 类型), ...]
            page: 当前页码（从0开始）
        """
        self._pinyin_input = pinyin_input
        self._candidates = candidates
        self._current_page = page

        total = len(candidates)
        per_page = config.CANDIDATES_PER_PAGE
        self._total_pages = max(1, (total + per_page - 1) // per_page)
        if page >= self._total_pages:
            page = self._total_pages - 1
            self._current_page = page

        # 更新拼音显示
        if self._pinyin_label:
            self._pinyin_label.config(text=pinyin_input or "")

        # 计算当前页候选
        start_idx = page * per_page
        end_idx = min(start_idx + per_page, total)
        page_candidates = candidates[start_idx:end_idx]

        # 更新分隔线显示
        if pinyin_input:
            self._separator.pack(fill=tk.X, padx=12, before=self._candidate_frame)
        else:
            self._separator.pack_forget()

        # 更新候选词标签
        for i in range(config.CANDIDATES_PER_PAGE):
            if i < len(page_candidates):
                word, word_type = page_candidates[i]
                display = f"{word}　{word_type}" if word_type else word
                self._candidate_labels[i].config(text=display)
                self._candidate_numbers[i].config(text=str(i + 1))
                # 恢复默认颜色
                self._candidate_labels[i].config(
                    fg=config.CANDIDATE_COLOR, bg=config.BG_COLOR
                )
                self._candidate_numbers[i].config(
                    fg=config.HIGHLIGHT_TEXT_COLOR, bg=config.BG_COLOR
                )
                # 绑定点击事件
                self._candidate_labels[i].bind(
                    "<Button-1>",
                    lambda e, idx=start_idx + i: self._on_click(idx),
                )
                self._candidate_numbers[i].bind(
                    "<Button-1>",
                    lambda e, idx=start_idx + i: self._on_click(idx),
                )
            else:
                self._candidate_labels[i].config(text="")
                self._candidate_numbers[i].config(text="")
                self._candidate_labels[i].unbind("<Button-1>")
                self._candidate_numbers[i].unbind("<Button-1>")

        # 更新翻页提示
        if self._page_label:
            if self._total_pages > 1:
                self._page_label.config(
                    text=f"{page + 1}/{self._total_pages}  ,.翻页"
                )
            else:
                self._page_label.config(text="")

        # 动态调整窗口高度
        self._adjust_window_size(len(page_candidates))

    def _on_click(self, index: int):
        """鼠标点击候选词"""
        if 0 <= index < len(self._candidates):
            word, word_type = self._candidates[index]
            if self._on_select:
                self._on_select(word, self._pinyin_input)

    def _adjust_window_size(self, candidate_count: int):
        """根据候选词数量动态调整窗口大小"""
        if candidate_count == 0:
            height = 60
        else:
            height = 80 + candidate_count * 28
        height = max(60, min(height, config.CANDIDATE_WINDOW_HEIGHT))
        self._root.geometry(f"{config.CANDIDATE_WINDOW_WIDTH}x{height}")

    def select_candidate(self, index: int):
        """通过索引选择候选词"""
        if 0 <= index < len(self._candidates):
            word, word_type = self._candidates[index]
            if self._on_select:
                self._on_select(word, self._pinyin_input)

    def highlight_candidate(self, index: int, highlight: bool = True):
        """高亮/取消高亮指定候选词"""
        # 计算在当前页的位置
        start_idx = self._current_page * config.CANDIDATES_PER_PAGE
        local_idx = index - start_idx
        if 0 <= local_idx < len(self._candidate_labels):
            if highlight:
                self._candidate_labels[local_idx].config(
                    bg=config.HIGHLIGHT_COLOR,
                    fg=config.HIGHLIGHT_TEXT_COLOR,
                )
            else:
                self._candidate_labels[local_idx].config(
                    bg=config.BG_COLOR,
                    fg=config.CANDIDATE_COLOR,
                )

    @property
    def total_pages(self) -> int:
        return self._total_pages

    @property
    def current_page(self) -> int:
        return self._current_page

    @property
    def is_visible(self) -> bool:
        return self._visible

    def destroy(self):
        """销毁窗口"""
        if self._root:
            self._root.destroy()
            self._root = None
