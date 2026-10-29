"""图形界面与程序入口。

GUI 只负责「展示参数 + 触发控制」，所有点击逻辑都委托给 core.clicker.ClickEngine，
热键委托给 input.hotkeys.HotkeyManager。界面与逻辑彻底解耦，方便日后换 UI 或加测试。

线程安全：keyboard 的热键回调跑在它的监听器线程里，这里统一用 root.after(0, ...)
把真实操作切回主线程，避免跨线程碰 tkinter。
"""

import os
import tkinter as tk
from tkinter import ttk

from core.config import load_settings, save_settings, DEFAULTS
from core.clicker import ClickEngine
from input.hotkeys import HotkeyManager

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.json")


class AutoClickerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("鼠标连点器")
        self.root.geometry("320x560")
        self.root.resizable(True, True)

        self.settings = load_settings(SETTINGS_PATH)
        self.engine = ClickEngine()
        self.hotkeys = HotkeyManager(
            toggle_key=self.settings["hotkey"], stop_key="esc"
        )

        self._build_vars()
        self._build_ui()
        self._apply_settings_to_widgets()
        self._setup_hotkeys()
        self._update_status()

    # ------------------------------------------------------------------ #
    # 变量
    # ------------------------------------------------------------------ #
    def _build_vars(self):
        s = self.settings
        self.interval_var = tk.StringVar(value=str(s["interval_ms"]))
        self.jitter_var = tk.StringVar(value=str(s["jitter_ms"]))
        self.button_var = tk.StringVar(value=s["button"])
        self.click_type_var = tk.StringVar(value=s["click_type"])
        self.repeat_mode_var = tk.StringVar(value=s["repeat_mode"])
        self.repeat_count_var = tk.StringVar(value=str(s["repeat_count"]))
        self.location_mode_var = tk.StringVar(value=s["location_mode"])
        self.fixed_x_var = tk.StringVar(value=str(s["fixed_x"]))
        self.fixed_y_var = tk.StringVar(value=str(s["fixed_y"]))
        self.start_delay_var = tk.StringVar(value=str(s["start_delay_ms"]))
        self.hotkey_var = tk.StringVar(value=s["hotkey"])

    # ------------------------------------------------------------------ #
    # 界面搭建
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        root = self.root
        pad = {"padx": 8, "pady": 4}

        # ---- 频率 ----
        f_freq = ttk.LabelFrame(root, text="点击频率")
        f_freq.pack(fill="x", **pad)
        ttk.Label(f_freq, text="间隔(毫秒)").grid(row=0, column=0, sticky="w")
        ttk.Entry(f_freq, textvariable=self.interval_var, width=10).grid(row=0, column=1)
        ttk.Label(f_freq, text="随机抖动(±毫秒)").grid(row=1, column=0, sticky="w")
        ttk.Entry(f_freq, textvariable=self.jitter_var, width=10).grid(row=1, column=1)
        ttk.Label(f_freq, text="抖动让点击不规律，规避反作弊检测").grid(row=2, column=0, columnspan=2, sticky="w")

        # ---- 鼠标按键 ----
        f_btn = ttk.LabelFrame(root, text="鼠标按键")
        f_btn.pack(fill="x", **pad)
        for i, (val, txt) in enumerate([("left", "左键"), ("right", "右键"), ("middle", "中键")]):
            ttk.Radiobutton(f_btn, text=txt, value=val, variable=self.button_var,
                           command=self._apply).grid(row=0, column=i, sticky="w")

        # ---- 点击类型 ----
        f_type = ttk.LabelFrame(root, text="点击类型")
        f_type.pack(fill="x", **pad)
        ttk.Radiobutton(f_type, text="单击", value="single", variable=self.click_type_var,
                        command=self._apply).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(f_type, text="双击", value="double", variable=self.click_type_var,
                        command=self._apply).grid(row=0, column=1, sticky="w")

        # ---- 点击位置 ----
        f_loc = ttk.LabelFrame(root, text="点击位置")
        f_loc.pack(fill="x", **pad)
        ttk.Radiobutton(f_loc, text="当前光标位置", value="current", variable=self.location_mode_var,
                        command=self._on_location_change).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Radiobutton(f_loc, text="固定坐标", value="fixed", variable=self.location_mode_var,
                        command=self._on_location_change).grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Label(f_loc, text="X").grid(row=2, column=0, sticky="e")
        ttk.Entry(f_loc, textvariable=self.fixed_x_var, width=8).grid(row=2, column=1, sticky="w")
        ttk.Label(f_loc, text="Y").grid(row=3, column=0, sticky="e")
        ttk.Entry(f_loc, textvariable=self.fixed_y_var, width=8).grid(row=3, column=1, sticky="w")
        self.pick_btn = ttk.Button(f_loc, text="拾取坐标(3秒后取鼠标位置)", command=self._pick_location)
        self.pick_btn.grid(row=4, column=0, columnspan=2, sticky="w", pady=2)

        # ---- 重复 ----
        f_rep = ttk.LabelFrame(root, text="重复")
        f_rep.pack(fill="x", **pad)
        ttk.Radiobutton(f_rep, text="无限", value="infinite", variable=self.repeat_mode_var,
                        command=self._on_repeat_change).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(f_rep, text="指定次数", value="count", variable=self.repeat_mode_var,
                        command=self._on_repeat_change).grid(row=0, column=1, sticky="w")
        ttk.Label(f_rep, text="次数").grid(row=1, column=0, sticky="e")
        ttk.Entry(f_rep, textvariable=self.repeat_count_var, width=10).grid(row=1, column=1, sticky="w")

        # ---- 启动保护 + 热键 ----
        f_opt = ttk.LabelFrame(root, text="其它")
        f_opt.pack(fill="x", **pad)
        ttk.Label(f_opt, text="启动前延迟(毫秒, 防误触)").grid(row=0, column=0, sticky="w")
        ttk.Entry(f_opt, textvariable=self.start_delay_var, width=10).grid(row=0, column=1)
        ttk.Label(f_opt, text="开始/停止热键").grid(row=1, column=0, sticky="w")
        ttk.Entry(f_opt, textvariable=self.hotkey_var, width=10).grid(row=1, column=1)
        ttk.Label(f_opt, text="例: space / f6 / ctrl+shift+a；Esc 始终紧急停止").grid(row=2, column=0, columnspan=2, sticky="w")

        # 让所有 Entry 在失焦或回车时应用
        for var in (self.interval_var, self.jitter_var, self.repeat_count_var,
                    self.fixed_x_var, self.fixed_y_var, self.start_delay_var, self.hotkey_var):
            pass  # Entry 控件在下方统一绑定
        for ent in root.winfo_children():
            self._bind_entry(ent)

        # ---- 控制按钮 ----
        f_ctrl = ttk.Frame(root)
        f_ctrl.pack(fill="x", **pad)
        self.toggle_btn = ttk.Button(f_ctrl, text="开始 (空格)", command=self._toggle)
        self.toggle_btn.pack(side="left", padx=4)
        ttk.Button(f_ctrl, text="应用设置", command=self._apply).pack(side="left", padx=4)

        # ---- 状态 ----
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(root, textvariable=self.status_var, foreground="blue").pack(pady=4)
        self.warn_var = tk.StringVar(value="")
        self.warn_label = ttk.Label(root, textvariable=self.warn_var, foreground="red")
        self.warn_label.pack(pady=2)

        ttk.Label(root, text="安全：鼠标甩到屏幕四角可紧急中止(FAILSAFE)").pack(pady=2)

    def _bind_entry(self, widget):
        """递归给所有 Entry 绑定 失焦/回车 -> 应用。"""
        if isinstance(widget, ttk.Entry):
            widget.bind("<FocusOut>", lambda e: self._apply())
            widget.bind("<Return>", lambda e: self._apply())
        elif widget.winfo_children():
            for child in widget.winfo_children():
                self._bind_entry(child)

    # ------------------------------------------------------------------ #
    # 设置同步
    # ------------------------------------------------------------------ #
    def _to_int(self, var, default):
        try:
            return int(var.get())
        except (ValueError, TypeError):
            return default

    def _apply_settings_to_widgets(self):
        # 切换时刷新「固定坐标 / 次数」相关控件的可用状态
        self._on_location_change()
        self._on_repeat_change()

    def _on_location_change(self):
        self._apply()

    def _on_repeat_change(self):
        self._apply()

    def _apply(self):
        """读取界面 -> 写入引擎 -> 保存 -> 刷新状态摘要。"""
        s = dict(self.settings)
        s["interval_ms"] = max(1, self._to_int(self.interval_var, DEFAULTS["interval_ms"]))
        s["jitter_ms"] = max(0, self._to_int(self.jitter_var, 0))
        s["button"] = self.button_var.get()
        s["click_type"] = self.click_type_var.get()
        s["repeat_mode"] = self.repeat_mode_var.get()
        s["repeat_count"] = max(1, self._to_int(self.repeat_count_var, 1))
        s["location_mode"] = self.location_mode_var.get()
        s["fixed_x"] = self._to_int(self.fixed_x_var, 0)
        s["fixed_y"] = self._to_int(self.fixed_y_var, 0)
        s["start_delay_ms"] = max(0, self._to_int(self.start_delay_var, 0))

        new_hotkey = self.hotkey_var.get().strip().lower() or "space"
        s["hotkey"] = new_hotkey

        # 同步到引擎
        for k in ("button", "click_type", "interval_ms", "jitter_ms",
                  "repeat_mode", "repeat_count", "location_mode",
                  "fixed_x", "fixed_y", "start_delay_ms"):
            setattr(self.engine, k, s[k])

        # 热键变了要重新注册
        if new_hotkey != self.hotkeys.toggle_key:
            self.hotkeys.toggle_key = new_hotkey
            self._setup_hotkeys()

        self.settings = s
        save_settings(SETTINGS_PATH, s)
        self._update_status()

    # ------------------------------------------------------------------ #
    # 热键
    # ------------------------------------------------------------------ #
    def _setup_hotkeys(self):
        ok = self.hotkeys.setup(
            toggle_callback=lambda: self.root.after(0, self._toggle),
            stop_callback=lambda: self.root.after(0, self._force_stop),
        )
        if not ok:
            self.warn_var.set(
                "⚠ 全局热键注册失败（多半是没用管理员权限运行）。\n"
                "请用「右键 -> 以管理员身份运行」启动，或只用界面按钮控制。"
            )
        else:
            self.warn_var.set("")

    # ------------------------------------------------------------------ #
    # 控制
    # ------------------------------------------------------------------ #
    def _toggle(self):
        if self.engine.is_running:
            self.engine.stop()
        else:
            self.engine.start()
        self._update_status()

    def _force_stop(self):
        self.engine.stop()
        self._update_status()

    def _pick_location(self):
        """进入拾取模式：3 秒倒计时后取当前鼠标坐标填入固定坐标。"""
        self.location_mode_var.set("fixed")
        self.pick_btn.configure(state="disabled")
        self.status_var.set("请把鼠标移到目标位置… 3")
        self._pick_countdown(3)

    def _pick_countdown(self, n):
        if n <= 0:
            import pyautogui
            x, y = pyautogui.position()
            self.fixed_x_var.set(str(x))
            self.fixed_y_var.set(str(y))
            self._apply()
            self.pick_btn.configure(state="normal")
            self.status_var.set(f"已拾取坐标 ({x}, {y})")
            return
        self.status_var.set(f"请把鼠标移到目标位置… {n}")
        self.root.after(1000, lambda: self._pick_countdown(n - 1))

    # ------------------------------------------------------------------ #
    # 状态刷新（轮询，主线程安全）
    # ------------------------------------------------------------------ #
    def _update_status(self):
        eng = self.engine
        if eng.is_running:
            remain = eng.delay_remaining
            if remain > 0:
                self.status_var.set(f"启动倒计时: {remain:.1f}s")
            else:
                self.status_var.set(f"运行中 — 已点击 {eng.clicks_done} 次")
            self.toggle_btn.configure(text="停止 (空格)")
        else:
            if eng.clicks_done:
                self.status_var.set(f"已停止 — 共点击 {eng.clicks_done} 次")
            else:
                self.status_var.set("就绪")
            self.toggle_btn.configure(text="开始 (空格)")
        # 持续轮询
        self.root.after(120, self._update_status)


def main():
    root = tk.Tk()
    AutoClickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
