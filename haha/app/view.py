"""View 层 — 用户界面 (tkinter)。

只负责界面展示与用户交互事件的暴露，不包含任何业务逻辑。
通过 set_start_command / set_message_click 把界面事件委托给控制器处理。
"""

import tkinter as tk
from tkinter import font as tkfont
from typing import Optional


class MainView(tk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master, bg='#2b2b2b')
        self.master = master
        self.pack(fill=tk.BOTH, expand=True)

        # 配置主窗口
        master.title("Hello")
        master.attributes('-fullscreen', True)
        master.configure(bg='#2b2b2b')

        # 创建字体
        self.custom_font = tkfont.Font(family="Arial", size=72, weight="bold")

        # 创建小部件
        self.create_widgets()

        # 绑定事件
        master.bind('<Escape>', self.exit_fullscreen)

    def create_widgets(self) -> None:
        # 倒计时标签（居中显示倒计时数字）
        self.countdown_label = tk.Label(
            self,
            text="",
            font=self.custom_font,
            fg="#FFD700",
            bg="#2b2b2b"
        )

        # 语言名称标签
        self.lang_label = tk.Label(
            self,
            text="",
            font=("Arial", 28, "italic"),
            fg="#00BFFF",
            bg="#2b2b2b"
        )

        # 增强元数据标签（范式 / 诞生年 / 设计者）
        self.meta_label = tk.Label(
            self,
            text="",
            font=("Arial", 16),
            fg="#FFA500",
            bg="#2b2b2b",
            wraplength=1400,
            justify=tk.CENTER
        )

        # 代码展示标签（等宽字体，支持换行）
        self.code_label = tk.Label(
            self,
            text="",
            font=("Consolas", 18),
            fg="#00FF7F",
            bg="#2b2b2b",
            justify=tk.LEFT,
            anchor=tk.N,
            wraplength=1400
        )

        # 一句话简介标签
        self.blurb_label = tk.Label(
            self,
            text="",
            font=("Arial", 14, "italic"),
            fg="#AAAAAA",
            bg="#2b2b2b",
            wraplength=1400,
            justify=tk.CENTER
        )

        # 消息容器帧
        self.message_frame = tk.Frame(self, bg="#2b2b2b")

        # START按钮
        self.start_button = tk.Button(
            self,
            text="START",
            font=("Arial", 24, "bold"),
            bg="#4CAF50",
            fg="white",
            activebackground="#45a049",
            activeforeground="white",
            relief=tk.RAISED,
            borderwidth=3
        )
        self.start_button.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    def start_countdown(self, seconds: int, on_finish) -> None:
        """显示倒计时，结束后执行回调"""
        self.start_button.place_forget()  # 隐藏按钮
        self.countdown_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        self._update_countdown(seconds, on_finish)

    def _update_countdown(self, remaining: int, on_finish) -> None:
        """递归更新倒计时数字"""
        if remaining > 0:
            self.countdown_label.config(text=str(remaining))
            self.master.after(1000, self._update_countdown, remaining - 1, on_finish)
        else:
            self.countdown_label.place_forget()  # 隐藏倒计时
            on_finish()

    def show_message(self, language: str, code: str, meta: Optional[dict] = None) -> None:
        """显示语言名称、增强元数据与代码"""
        self.lang_label.config(text=f"\U0001F5E3 {language}")

        # 拼接元数据行：范式 | 诞生 | 设计者
        bits = []
        if meta:
            if meta.get("paradigm"):
                bits.append(f"范式：{meta['paradigm']}")
            if meta.get("year"):
                bits.append(f"诞生：{meta['year']}")
            if meta.get("designer"):
                bits.append(f"设计者：{meta['designer']}")
            self.blurb_label.config(text=meta.get("blurb", ""))
        else:
            self.blurb_label.config(text="")
        self.meta_label.config(text="    |    ".join(bits))

        self.code_label.config(text=code)
        self.message_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        self.lang_label.pack(pady=(0, 4))
        self.meta_label.pack(pady=(0, 12))
        self.code_label.pack()
        self.blurb_label.pack(pady=(12, 0))

    def hide_message(self) -> None:
        """隐藏消息"""
        self.lang_label.pack_forget()
        self.meta_label.pack_forget()
        self.code_label.pack_forget()
        self.blurb_label.pack_forget()
        self.message_frame.place_forget()
        self.start_button.place(relx=0.5, rely=0.5, anchor=tk.CENTER)  # 重新显示按钮

    def set_start_command(self, command) -> None:
        """设置START按钮的命令"""
        self.start_button.config(command=command)

    def set_message_click(self, command) -> None:
        """绑定点击消息时的事件"""
        self.message_frame.bind('<Button-1>', command)
        self.lang_label.bind('<Button-1>', command)
        self.code_label.bind('<Button-1>', command)

    def exit_fullscreen(self, event: Optional[tk.Event] = None) -> None:
        """退出全屏"""
        self.master.attributes('-fullscreen', False)
