"""全局热键管理。

封装 keyboard 库，提供：
- 一个可自定义的 开始/停止 热键（默认空格）
- 一个永远生效的 Esc 紧急停止
- 注册失败时（典型：Windows 没用管理员权限装全局钩子 -> PermissionError）
  优雅降级：返回 False 并让上层提示用户，而不是让整个程序崩。

注意：keyboard 的回调跑在它自己的监听器线程里，调用方（GUI）应当把
真实操作切回主线程执行，避免跨线程操作界面。
"""

import keyboard


class HotkeyManager:
    def __init__(self, toggle_key="space", stop_key="esc"):
        self.toggle_key = toggle_key
        self.stop_key = stop_key
        self._toggle_id = None
        self._stop_id = None
        self.available = False  # 注册是否成功

    def setup(self, toggle_callback, stop_callback):
        """注册热键。成功返回 True，失败(无权限等)返回 False。"""
        self.teardown()
        try:
            self._toggle_id = keyboard.add_hotkey(self.toggle_key, toggle_callback)
            self._stop_id = keyboard.add_hotkey(self.stop_key, stop_callback)
            self.available = True
            return True
        except Exception as exc:
            # 常见：PermissionError: [WinError 5] 拒绝访问
            self.available = False
            self._toggle_id = self._stop_id = None
            self._last_error = str(exc)
            return False

    def teardown(self):
        for hid in (self._toggle_id, self._stop_id):
            if hid is not None:
                try:
                    keyboard.remove_hotkey(hid)
                except Exception:
                    pass
        self._toggle_id = self._stop_id = None

    @property
    def last_error(self):
        return getattr(self, "_last_error", "")
