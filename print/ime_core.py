# -*- coding: utf-8 -*-
"""
输入法核心引擎
管理输入法状态机，协调各个模块之间的交互。

状态流转:
  IDLE --(Shift)--> ENABLED
  ENABLED --(字母键)--> TYPING
  TYPING --(选择候选)--> COMMITTED --(自动)--> ENABLED
  TYPING --(Esc/Shift)--> IDLE

模块交互:
  keyboard_handler ──┬──> ime_core ──┬──> pinyin_parser ──> pinyin_dict
                      │               │
                      │               ├──> ime_ui (候选窗口)
                      │               │
                      │               └──> user_dict (记录)
                      │
                      └──> pyperclip (上屏)
"""

import logging
import threading
import time
from typing import List, Optional, Tuple

import pyperclip

import config
from ime_ui import CandidateWindow
from keyboard_handler import ImeKeyboardHandler
from pinyin_parser import CandidateGenerator, segment_pinyin_greedy
from user_dict import get_user_dict

logger = logging.getLogger("ime_core")


class ImeCore:
    """
    输入法核心引擎
    
    职责:
    1. 管理输入法状态（空闲/输入中）
    2. 接收键盘事件，协调字典查询和候选词生成
    3. 管理候选窗口的显示和更新
    4. 处理候选词选择和上屏
    """

    # 状态常量
    STATE_IDLE = "idle"          # 空闲（英文模式）
    STATE_ENABLED = "enabled"   # 中文模式待输入
    STATE_TYPING = "typing"     # 正在输入拼音
    STATE_COMMITTED = "committed"  # 已提交

    def __init__(self):
        self._state = self.STATE_IDLE
        self._ime_enabled = False

        # 模块
        self._keyboard = ImeKeyboardHandler()
        self._candidate_gen = CandidateGenerator()
        self._ui: Optional[CandidateWindow] = None
        self._user_dict = get_user_dict()

        # 候选词状态
        self._current_candidates: List[Tuple[str, str]] = []
        self._current_page = 0
        self._current_pinyin = ""

        # 光标位置跟踪
        self._cursor_x = 0
        self._cursor_y = 0

        # 是否已初始化
        self._initialized = False

    # ============================================================
    # 初始化
    # ============================================================

    def initialize(self):
        """初始化输入法（启动后台任务）"""
        if self._initialized:
            return

        print("=" * 50)
        print("  中文拼音输入法 v2.0")
        print("  基于本地字典与字体")
        print("=" * 50)

        # 加载用户词典
        self._user_dict.load()

        # 在后台线程加载字典
        print("[加载] 后台加载字典中...")
        load_thread = threading.Thread(
            target=self._candidate_gen.ensure_dict_loaded,
            daemon=True,
        )
        load_thread.start()

        # 注册键盘回调
        self._keyboard.on_toggle(self._on_toggle_ime)
        self._keyboard.on_input_update(self._on_input_update)
        self._keyboard.on_candidate_select(self._on_select_candidate)
        self._keyboard.on_cancel_input(self._on_cancel_input)
        self._keyboard.on_page_change(self._on_page_change)

        # 启动键盘监听
        self._keyboard.start()

        # 初始化 UI（需要在主线程创建）
        self._ui = CandidateWindow(on_select=self._on_ui_select)
        self._ui.hide()

        self._initialized = True
        print("[就绪] 按右 Shift 键切换中英文输入模式")
        print("[提示] 拼音输入: 字母键 | 选择: 1-9数字键/空格")
        print("[提示] 翻页: ,./上下箭头 | 取消: Esc")
        print("=" * 50)

    # ============================================================
    # 回调处理
    # ============================================================

    def _on_toggle_ime(self):
        """切换中英文模式"""
        was_typing = self._state == self.STATE_TYPING
        self._ime_enabled = not self._ime_enabled

        # 同步 keyboard_handler 状态（修复 UI 不显示的问题）
        self._keyboard.toggle_ime(self._ime_enabled)

        if self._ime_enabled:
            self._state = self.STATE_ENABLED
            self._get_cursor_position()
            print("[模式] 中文输入")
        else:
            self._state = self.STATE_IDLE
            self._clear_candidates()
            self._keyboard.clear_buffer()
            print("[模式] 英文输入")

    def _on_input_update(self, pinyin: str):
        """拼音输入更新"""
        if not self._ime_enabled:
            return

        if not pinyin:
            self._state = self.STATE_ENABLED
            self._clear_candidates()
            return

        self._state = self.STATE_TYPING
        self._current_pinyin = pinyin

        # 解析拼音，生成候选词
        syllables = segment_pinyin_greedy(pinyin)
        if syllables:
            # 检查最后一个音节是否是完整音节
            # 如果不是，说明用户可能还在输入中
            full_syllables = []
            for syl in syllables:
                # 简化判断：检查是否为有效音节
                from pinyin_syllables import PINYIN_SYLLABLES
                full_syllables.append(syl)

            candidates = self._candidate_gen.generate(full_syllables)
        else:
            candidates = []

        # 用户词典候选词优先
        user_candidates = self._user_dict.get_user_candidates(pinyin, limit=10)
        user_items = [
            (word, "用户") for word, _ in user_candidates
            if word not in [c[0] for c in candidates]
        ]

        # 合并候选词：用户词 > 词语 > 成语 > 单字
        all_candidates = user_items + candidates
        self._current_candidates = all_candidates
        self._current_page = 0

        # 更新 UI
        self._update_ui()

    def _on_select_candidate(self, index: int):
        """通过键盘选择候选词"""
        if self._state != self.STATE_TYPING:
            return

        # 计算全局索引
        global_idx = self._current_page * config.CANDIDATES_PER_PAGE + index
        if 0 <= global_idx < len(self._current_candidates):
            word, word_type = self._current_candidates[global_idx]
            self._commit_word(word)

    def _on_cancel_input(self):
        """取消输入"""
        self._clear_candidates()
        self._state = self.STATE_ENABLED

    def _on_page_change(self, delta: int):
        """翻页"""
        if self._state != self.STATE_TYPING:
            return
        new_page = self._current_page + delta
        total = len(self._current_candidates)
        max_pages = max(1, (total + config.CANDIDATES_PER_PAGE - 1) // config.CANDIDATES_PER_PAGE)
        new_page = max(0, min(new_page, max_pages - 1))
        if new_page != self._current_page:
            self._current_page = new_page
            self._update_ui()

    def _on_ui_select(self, word: str, pinyin: str):
        """UI 鼠标点击候选词"""
        self._commit_word(word)

    # ============================================================
    # 候选词管理
    # ============================================================

    def _clear_candidates(self):
        """清除候选词"""
        self._current_candidates = []
        self._current_page = 0
        self._current_pinyin = ""
        self._state = self.STATE_ENABLED
        if self._ui:
            ui = self._ui  # 捕获引用，避免竞态
            ui._root.after(0, ui.hide)

    def _update_ui(self):
        """更新候选窗口（线程安全：通过 after 调度到主线程）"""
        if not self._ui:
            return

        # 捕获数据快照，避免在非主线程修改被 tkinter 读取时产生竞态
        ui = self._ui
        root = ui._root
        pinyin = self._current_pinyin
        candidates = list(self._current_candidates)
        page = self._current_page
        cursor_x = self._cursor_x
        cursor_y = self._cursor_y

        def _do_update():
            if not candidates and not pinyin:
                ui.hide()
                return
            ui.update_candidates(pinyin, candidates, page)
            ui.show(
                cursor_x + config.WINDOW_OFFSET_X,
                cursor_y + config.WINDOW_OFFSET_Y,
            )

        root.after(0, _do_update)

    # ============================================================
    # 上屏
    # ============================================================

    def _commit_word(self, word: str):
        """
        提交候选词到屏幕。
        1. 记录到用户词典
        2. 通过剪贴板粘贴到当前焦点窗口
        3. 清除候选词
        """
        if not word:
            return

        # 记录到用户词典
        self._user_dict.record(word, self._current_pinyin)

        try:
            # 通过剪贴板上屏
            pyperclip.copy(word)

            # 模拟 Ctrl+V 粘贴
            import time as _time
            _time.sleep(0.05)

            from pynput.keyboard import Controller, Key
            kb_controller = Controller()
            with kb_controller.pressed(Key.ctrl):
                kb_controller.press('v')
                kb_controller.release('v')
            _time.sleep(0.02)

        except Exception as e:
            logger.error(f"上屏失败: {e}")
            # 降级方案：仅复制到剪贴板
            pyperclip.copy(word)
            print(f"[上屏] 已复制到剪贴板: {word}")

        print(f"[选择] {word} ({self._current_pinyin})")

        # 清除状态
        self._clear_candidates()
        self._keyboard.clear_buffer()

        # 定期保存用户词典
        self._user_dict.save()

    # ============================================================
    # 光标位置
    # ============================================================

    def _get_cursor_position(self):
        """获取当前光标位置（DPI 感知）"""
        try:
            import ctypes
            from ctypes import wintypes

            point = wintypes.POINT()
            # GetPhysicalCursorPos 在 DPI 感知进程中等效于 GetCursorPos
            try:
                ctypes.windll.user32.GetPhysicalCursorPos(ctypes.byref(point))
            except AttributeError:
                ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
            self._cursor_x = point.x
            self._cursor_y = point.y
        except Exception:
            # 非 Windows 或失败时使用屏幕中心
            import tkinter as tk
            temp = tk.Tk()
            temp.withdraw()
            sw = temp.winfo_screenwidth()
            sh = temp.winfo_screenheight()
            temp.destroy()
            self._cursor_x = sw // 2
            self._cursor_y = sh // 3

    # ============================================================
    # 运行
    # ============================================================

    def run(self):
        """运行输入法（阻塞主线程）"""
        self.initialize()

        # 运行 tkinter 主循环（必须从主线程调用）
        try:
            if self._ui and self._ui._root:
                self._ui._root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def shutdown(self):
        """关闭输入法"""
        print("[关闭] 正在保存数据和释放资源...")
        self._user_dict.save()
        self._keyboard.stop()
        if self._ui:
            self._ui.destroy()
        print("[关闭] 输入法已停止")

    # ============================================================
    # 状态查询
    # ============================================================

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_enabled(self) -> bool:
        return self._ime_enabled
