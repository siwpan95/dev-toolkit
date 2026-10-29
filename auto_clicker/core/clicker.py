"""点击引擎核心。

把「自动点击」这件事从 GUI 里彻底剥出来，做成一个纯逻辑、可独立测试的引擎：
- 不依赖 tkinter，不依赖任何界面
- 在守护线程里跑循环，主线程(或 GUI)随时可以 start()/stop()
- 支持 左/右/中键、单击/双击、间隔+随机抖动、次数/无限、当前光标/固定坐标
- 启动前延迟(误触保护)，期间可被 stop() 打断
- 保留 pyautogui 的 FAILSAFE：鼠标甩到屏幕四角即紧急中止
- 暴露 clicks_done / delay_remaining 供界面做实时状态展示
"""

import threading
import time
import random

import pyautogui

# 守住安全底线：甩鼠标到屏幕四角可立刻中止，绝不关闭。
pyautogui.FAILSAFE = True


class ClickEngine:
    def __init__(self):
        # ---- 可调参数（由 GUI / 配置文件填充）----
        self.button = "left"          # left / right / middle
        self.click_type = "single"    # single / double
        self.interval_ms = 100
        self.jitter_ms = 0            # 间隔的随机浮动范围(±毫秒)
        self.repeat_mode = "infinite" # infinite / count
        self.repeat_count = 0
        self.location_mode = "current"# current / fixed
        self.fixed_x = 0
        self.fixed_y = 0
        self.start_delay_ms = 0       # 启动前延迟，防误触

        # ---- 运行状态 ----
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()
        self._delay_deadline = None   # 启动延迟的截止时间戳
        self.clicks_done = 0

    # ------------------------------------------------------------------ #
    # 对外只读状态
    # ------------------------------------------------------------------ #
    @property
    def is_running(self):
        return self._running

    @property
    def delay_remaining(self):
        """还剩多少秒进入正式点击（用于界面倒计时）。"""
        if self._delay_deadline is None:
            return 0.0
        return max(0.0, self._delay_deadline - time.time())

    # ------------------------------------------------------------------ #
    # 控制
    # ------------------------------------------------------------------ #
    def start(self):
        if self._running:
            return
        self._running = True
        self.clicks_done = 0
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        if not self._running:
            return
        self._stop_event.set()

    # ------------------------------------------------------------------ #
    # 内部
    # ------------------------------------------------------------------ #
    def _do_click(self):
        if self.location_mode == "fixed":
            pyautogui.click(x=self.fixed_x, y=self.fixed_y, button=self.button)
        elif self.click_type == "double":
            pyautogui.doubleClick(button=self.button)
        else:
            pyautogui.click(button=self.button)

    def _loop(self):
        # 启动前延迟：给用户把鼠标挪开 / 准备目标的时间，期间可被打断。
        if self.start_delay_ms > 0:
            self._delay_deadline = time.time() + self.start_delay_ms / 1000.0
            if self._stop_event.wait(self.start_delay_ms / 1000.0):
                self._delay_deadline = None
                self._running = False
                return
            self._delay_deadline = None

        target = self.repeat_count if self.repeat_mode == "count" else None

        while not self._stop_event.is_set():
            try:
                self._do_click()
            except pyautogui.FailSafeException:
                # 用户甩鼠标到角落触发了紧急中止
                break

            self.clicks_done += 1
            if target is not None and self.clicks_done >= target:
                break

            # 可中断的带抖动睡眠：基础间隔 ± 随机浮动
            jitter = random.uniform(-self.jitter_ms, self.jitter_ms) / 1000.0
            sleep_t = max(0.0, self.interval_ms / 1000.0 + jitter)
            if self._stop_event.wait(sleep_t):
                break

        self._running = False
