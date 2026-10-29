# -*- coding: utf-8 -*-
"""
键盘监听管理器
使用 pynput 监听全局键盘事件，处理输入法热键和拼音输入

功能:
- 全局键盘监听
- Shift 切换中英文模式
- 字母键输入拼音
- 数字键选择候选词
- 空格/回车选择首个候选
- Backspace 删除
- Esc 清除
- ,. 翻页
"""

import threading
from typing import Callable, Optional

from pynput import keyboard
from pynput.keyboard import Key, KeyCode

import config


class ImeKeyboardHandler:
    """
    输入法键盘处理
    """

    def __init__(self):
        self._listener: Optional[keyboard.Listener] = None
        self._thread: Optional[threading.Thread] = None

        # 输入法状态
        self._ime_enabled = False  # 中文输入模式开关
        self._input_buffer = ""    # 拼音输入缓冲区
        self._shift_pressed = False
        self._shift_alone = True   # Shift 是否单独按下（用于判断切换）
        self._ctrl_pressed = False  # Ctrl 是否按下（防止 Ctrl+V 被捕获）

        # 回调函数
        self._on_toggle: Optional[Callable] = None    # 切换中英文
        self._on_input: Optional[Callable] = None     # 输入拼音更新
        self._on_select: Optional[Callable] = None    # 选择候选词 (index)
        self._on_cancel: Optional[Callable] = None    # 取消输入
        self._on_page_change: Optional[Callable] = None  # 翻页 (delta)

    # ============================================================
    # 回调注册
    # ============================================================

    def on_toggle(self, callback: Callable):
        """注册中英文切换回调"""
        self._on_toggle = callback

    def on_input_update(self, callback: Callable):
        """注册拼音输入更新回调 callback(pinyin_str)"""
        self._on_input = callback

    def on_candidate_select(self, callback: Callable):
        """注册候选词选择回调 callback(index)"""
        self._on_select = callback

    def on_cancel_input(self, callback: Callable):
        """注册取消输入回调"""
        self._on_cancel = callback

    def on_page_change(self, callback: Callable):
        """注册翻页回调 callback(delta: int)"""
        self._on_page_change = callback

    # ============================================================
    # 键盘事件处理
    # ============================================================

    def _on_press(self, key):
        """键盘按下事件"""
        try:
            # 检查 Shift 切换
            if key == Key.shift_r or key == Key.shift:
                self._shift_pressed = True
                return

            # 追踪 Ctrl 状态（防止 Ctrl+V 等组合键被捕获为拼音输入）
            if key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r):
                self._ctrl_pressed = True
                return

            # Shift 和其他键组合按下（如 Shift+A），不是单独按 Shift
            if self._shift_pressed:
                self._shift_alone = False

            # Ctrl 组合键不处理（Ctrl+V 上屏不应被捕获为拼音）
            if self._ctrl_pressed:
                return

            # 非中文模式不处理
            if not self._ime_enabled:
                return

            # ---- 特殊键处理 ----
            # Esc: 取消输入
            if key == Key.esc:
                self._clear_buffer()
                if self._on_cancel:
                    self._on_cancel()
                return

            # Backspace: 删除最后一个字符
            if key == Key.backspace:
                if self._input_buffer:
                    self._input_buffer = self._input_buffer[:-1]
                    self._update_input()
                return

            # 空格: 选择第一个候选词
            if key == Key.space:
                if self._input_buffer:
                    if self._on_select:
                        self._on_select(0)
                return

            # 回车: 选择第一个候选词（同空格）
            if key == Key.enter:
                if self._input_buffer:
                    if self._on_select:
                        self._on_select(0)
                return

            # 翻页键
            key_str = self._get_key_char(key)
            if key_str == config.PAGE_DOWN_KEY:
                if self._on_page_change:
                    self._on_page_change(1)
                return
            if key_str == config.PAGE_UP_KEY:
                if self._on_page_change:
                    self._on_page_change(-1)
                return

            # 上箭头: 上一页
            if key == Key.up:
                if self._on_page_change:
                    self._on_page_change(-1)
                return

            # 下箭头: 下一页
            if key == Key.down:
                if self._on_page_change:
                    self._on_page_change(1)
                return

            # ---- 数字键选择候选词 ----
            if hasattr(key, "char") and key.char and key.char.isdigit():
                idx = int(key.char) - 1  # 1-9 → 0-8
                if self._input_buffer and 0 <= idx < config.CANDIDATES_PER_PAGE:
                    if self._on_select:
                        self._on_select(idx)
                return

            # ---- 字母键输入拼音 ----
            if hasattr(key, "char") and key.char and key.char.isalpha():
                ch = key.char.lower()
                if len(self._input_buffer) < config.MAX_INPUT_LENGTH:
                    self._input_buffer += ch
                    self._update_input()
                return

            # ---- 分音符支持 ----
            if hasattr(key, "char") and key.char == "'":
                self._input_buffer += "'"
                self._update_input()
                return

        except Exception as e:
            print(f"[键盘] 按键处理异常: {e}")

    def _on_release(self, key):
        """键盘释放事件"""
        # Ctrl 释放
        if key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r):
            self._ctrl_pressed = False

        if key == Key.shift_r or key == Key.shift:
            was_shift_alone = self._shift_alone
            self._shift_pressed = False
            self._shift_alone = True  # 重置
            # 仅在单独按 Shift（非组合键）时切换中英文
            if was_shift_alone and self._on_toggle:
                self._on_toggle()

    def _get_key_char(self, key) -> Optional[str]:
        """获取普通键的字符"""
        try:
            if hasattr(key, "char"):
                return key.char
        except Exception:
            pass
        return None

    # ============================================================
    # 输入缓冲区管理
    # ============================================================

    def _clear_buffer(self):
        """清空输入缓冲区"""
        self._input_buffer = ""

    def _update_input(self):
        """通知输入更新"""
        if self._on_input:
            self._on_input(self._input_buffer)

    def clear_buffer(self):
        """外部调用清空缓冲区"""
        self._clear_buffer()

    @property
    def buffer(self) -> str:
        return self._input_buffer

    @property
    def is_enabled(self) -> bool:
        return self._ime_enabled

    # ============================================================
    # 启动和停止
    # ============================================================

    def start(self):
        """启动键盘监听"""
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        """停止键盘监听"""
        if self._listener:
            self._listener.stop()
            self._listener = None

    def toggle_ime(self, enabled: Optional[bool] = None):
        """
        切换输入法状态。
        
        Args:
            enabled: True=开启, False=关闭, None=切换
        """
        if enabled is None:
            self._ime_enabled = not self._ime_enabled
        else:
            self._ime_enabled = enabled

        if not self._ime_enabled:
            self._clear_buffer()
