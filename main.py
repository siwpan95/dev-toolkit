"""字幕工具 GUI 入口（Tkinter，中文界面）。

功能：
  ① 从视频提取字幕流（ffmpeg -map 0:s:0）
  ② 打开 / 编辑 / 保存 .srt（文本区按条目显示时间码+文本，可编辑）
  ③ 烧录字幕到视频（subtitles 滤镜硬编码）
  ④ 翻译占位：调用 core.translate_hook（默认原样返回，可接翻译 API）

铁律：本文件仅作为 GUI 入口；无显示器环境不要实例化 Tk()。
      Tk() 只在 `if __name__ == '__main__':` 守卫内创建。
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import core


class SubtitleApp:
    """字幕工具主窗口。

    所有 ffmpeg 交互委托给 core 模块；UI 仅负责中文交互与状态展示。
    """

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("字幕工具 Subtitle Tool")
        self.root.geometry("860x620")

        self.current_srt_path: str | None = None

        self._build_widgets()
        self._update_ffmpeg_status()

    # ------------------------------------------------------------------ UI
    def _build_widgets(self) -> None:
        """构建工具栏、编辑区与状态栏。"""
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=6, pady=6)

        actions = [
            ("提取字幕", self.on_extract),
            ("打开 SRT", self.on_open_srt),
            ("翻译", self.on_translate),
            ("保存 SRT", self.on_save_srt),
            ("烧录字幕", self.on_burn),
        ]
        for label, cmd in actions:
            ttk.Button(toolbar, text=label, command=cmd).pack(
                side=tk.LEFT, padx=3
            )

        # 编辑区：按条目显示时间码 + 文本，可编辑
        editor_frame = ttk.LabelFrame(self.root, text="字幕编辑区（每条：序号/时间码/文本）")
        editor_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=4)

        self.text_area = scrolledtext.ScrolledText(
            editor_frame, wrap=tk.WORD, font=("Consolas", 11)
        )
        self.text_area.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # 状态栏
        self.status = tk.StringVar(value="就绪")
        status_bar = ttk.Label(
            self.root, textvariable=self.status, relief=tk.SUNKEN, anchor=tk.W
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _update_ffmpeg_status(self) -> None:
        """在状态栏显示 ffmpeg 是否可用。"""
        exe = core.ffmpeg_path()
        if exe:
            self.set_status(f"ffmpeg 可用：{exe}")
        else:
            self.set_status("未检测到 ffmpeg（提取/烧录功能需系统安装 ffmpeg）")

    def set_status(self, msg: str) -> None:
        """更新状态栏文本。"""
        self.status.set(msg)

    # ------------------------------------------------------------------ 功能
    def on_extract(self) -> None:
        """选择视频并提取字幕流。"""
        video = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[("视频文件", "*.mp4 *.mkv *.avi *.mov *.flv *.webm"), ("全部", "*.*")],
        )
        if not video:
            return
        out_srt = filedialog.asksaveasfilename(
            title="保存字幕为",
            defaultextension=".srt",
            filetypes=[("SRT 字幕", "*.srt")],
        )
        if not out_srt:
            return

        ok, msg = core.extract_subtitles(video, out_srt)
        if ok:
            self.current_srt_path = out_srt
            self._load_into_editor(out_srt)
            messagebox.showinfo("完成", msg)
        else:
            messagebox.showwarning("无法提取", msg)
        self.set_status(msg)

    def on_open_srt(self) -> None:
        """打开并解析 .srt 到编辑区。"""
        path = filedialog.askopenfilename(
            title="打开 SRT 字幕",
            filetypes=[("SRT 字幕", "*.srt"), ("全部", "*.*")],
        )
        if not path:
            return
        self._load_into_editor(path)
        self.current_srt_path = path
        self.set_status(f"已打开：{path}")

    def _load_into_editor(self, path: str) -> None:
        """读取 .srt 文件并规范化为可编辑文本填入编辑区。"""
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                raw = fh.read()
        except (OSError, UnicodeDecodeError) as exc:
            messagebox.showerror("读取失败", f"无法读取文件：{exc}")
            return

        blocks = core.parse_srt(raw)
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", core.serialize_srt(blocks))

    def on_save_srt(self) -> None:
        """从编辑区解析并规范化保存 .srt。"""
        raw = self.text_area.get("1.0", tk.END)
        try:
            blocks = core.parse_srt(raw)
        except Exception as exc:  # noqa: BLE001 - 友好提示解析错误
            messagebox.showerror("解析失败", f"字幕内容有误：{exc}")
            return

        if not blocks:
            messagebox.showwarning("空内容", "编辑区没有可保存的字幕条目。")
            return

        path = self.current_srt_path
        if not path:
            path = filedialog.asksaveasfilename(
                title="保存字幕为",
                defaultextension=".srt",
                filetypes=[("SRT 字幕", "*.srt")],
            )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(core.serialize_srt(blocks))
        except OSError as exc:
            messagebox.showerror("保存失败", f"无法写入文件：{exc}")
            return

        self.current_srt_path = path
        self.set_status(f"已保存：{path}（共 {len(blocks)} 条）")
        messagebox.showinfo("完成", f"已保存 {len(blocks)} 条字幕到 {path}")

    def on_translate(self) -> None:
        """对编辑区字幕文本调用翻译占位函数（默认原样返回）。"""
        raw = self.text_area.get("1.0", tk.END)
        try:
            blocks = core.parse_srt(raw)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("解析失败", f"字幕内容有误：{exc}")
            return

        if not blocks:
            messagebox.showwarning("空内容", "没有可翻译的字幕条目。")
            return

        texts = [b["text"] for b in blocks]
        translated = core.translate_hook(texts)  # 默认原样返回（可接 API）
        if len(translated) != len(texts):
            messagebox.showerror("翻译异常", "翻译返回条目数不一致，已中止。")
            return

        for blk, new_text in zip(blocks, translated):
            blk["text"] = new_text

        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", core.serialize_srt(blocks))
        self.set_status(f"翻译完成（占位：原样返回 {len(blocks)} 条）")

    def on_burn(self) -> None:
        """选择视频与字幕并烧录（硬编码）字幕。"""
        video = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[("视频文件", "*.mp4 *.mkv *.avi *.mov *.flv *.webm"), ("全部", "*.*")],
        )
        if not video:
            return
        srt = self.current_srt_path or filedialog.askopenfilename(
            title="选择 SRT 字幕",
            filetypes=[("SRT 字幕", "*.srt"), ("全部", "*.*")],
        )
        if not srt:
            return
        out_video = filedialog.asksaveasfilename(
            title="保存烧录后视频",
            defaultextension=".mp4",
            filetypes=[("MP4", "*.mp4"), ("MKV", "*.mkv"), ("全部", "*.*")],
        )
        if not out_video:
            return

        self.set_status("正在烧录字幕，请稍候……")
        self.root.update_idletasks()
        ok, msg = core.burn_subtitles(video, srt, out_video)
        if ok:
            messagebox.showinfo("完成", msg)
        else:
            messagebox.showwarning("烧录失败", msg)
        self.set_status(msg)


def main() -> None:
    """GUI 入口（仅在直接运行时创建 Tk 窗口）。"""
    root = tk.Tk()
    SubtitleApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
