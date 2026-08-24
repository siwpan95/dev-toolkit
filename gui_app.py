# -*- coding: utf-8 -*-
"""
gui_app.py — CryptoGUI 主类
只负责界面布局和事件绑定，所有业务逻辑通过 pipeline / compare 调用
"""
import os
import threading

try:
    import tkinter as tk
    from tkinter import filedialog
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False
    tk = filedialog = None

from .config import CryptoConfig, COMPRESS_ALGOS
from .utils import format_size
from .crypto_core import compute_sha256
from .pipeline import process_file, decrypt_file
from .compare import compare_compress_algorithms
from .gui_widgets import (
    THEME,
    draw_rounded_rect, draw_section_card, draw_label,
    draw_btn, draw_dropdown, draw_slider, draw_entry,
    draw_checkbox, draw_progress,
)


class CryptoGUI:
    """tkinter Canvas 图形界面"""

    def __init__(self):
        self.root = None
        self.canvas = None
        self.input_path = None
        self.output_dir = None
        self.password_var = None
        self.keyfile_var = None
        self.algo_var = None
        self.cipher_var = None
        self.level_var = None
        self.bomb_var = None
        self.bomb_layers_var = None
        self.skip_compress_var = None
        self.log_lines = []
        self._progress_y = 0
        self._progress_w = 0
        self._log_area = None

    # ==================== 日志 ====================

    def log(self, msg):
        self.log_lines.append(msg)
        if len(self.log_lines) > 200:
            self.log_lines = self.log_lines[-200:]
        self._redraw_log()

    # ==================== 入口 ====================

    def run(self):
        if not TK_AVAILABLE:
            print("❌ tkinter 不可用（可能是无头环境），请使用 CLI 模式")
            self._run_cli()
            return

        self.root = tk.Tk()
        self.root.withdraw()

        self.input_path       = tk.StringVar()
        self.output_dir       = tk.StringVar()
        self.password_var     = tk.StringVar()
        self.keyfile_var      = tk.StringVar(value="")
        self.algo_var         = tk.StringVar(value="zlib")
        self.cipher_var       = tk.StringVar(value="AES-256-GCM")
        self.level_var        = tk.IntVar(value=6)
        self.bomb_var         = tk.BooleanVar(value=False)
        self.bomb_layers_var  = tk.IntVar(value=3)
        self.skip_compress_var = tk.BooleanVar(value=False)

        self.root.title("🔐 通用文件加密/压缩工具")
        self.root.geometry("860x700")
        self.root.configure(bg=THEME["bg"])
        self.root.resizable(True, True)

        self.canvas = tk.Canvas(self.root, bg=THEME["canvas"], highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda e: self._draw_all())

        self._draw_all()
        self.root.deiconify()
        self.root.mainloop()

    def _run_cli(self):
        print("=" * 60)
        print("  🔐 通用文件加密/压缩工具 (CLI)")
        print("=" * 60)
        print("命令: encrypt <文件> | decrypt --encrypted <文件> --keyfile <密钥>")
        print("      compress <文件> | decompress <文件>")
        print(f"\n确保已安装: pip install cryptography")

    # ==================== 全量重绘 ====================

    def _draw_all(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 100 or h < 100:
            return

        self._draw_header(w)
        y = 65
        y = self._draw_file_section(w, y) + 10
        y = self._draw_settings_section(w, y) + 10
        y = self._draw_actions_section(w, y) + 10
        y = self._draw_progress_section(w, y) + 10
        self._draw_log_section(w, y, h - y - 5)

    # ==================== 各区域绘制 ====================

    def _draw_header(self, w):
        self.canvas.create_rectangle(0, 0, w, 56, fill=THEME["primary"], outline="")
        self.canvas.create_text(w // 2, 28, text="🔐  通用文件加密 & 压缩工具",
                                fill="#ffffff", font=("Microsoft YaHei", 16, "bold"))

    def _draw_file_section(self, w, y):
        draw_section_card(self.canvas, w, y, 90, "📂 文件选择")
        y += 28

        draw_label(self.canvas, y, "输入文件:")
        self.canvas.create_rectangle(130, y, w - 100, y + 26,
                                     fill=THEME["input_bg"], outline=THEME["border"])
        fname = os.path.basename(self.input_path.get()) if self.input_path.get() else "（未选择文件）"
        display_name = fname if len(fname) <= 55 else fname[:52] + "..."
        self.canvas.create_text(138, y + 13, text=display_name, fill=THEME["text"],
                                anchor="w", font=("Microsoft YaHei", 9))
        draw_btn(self.canvas, w - 95, y, 90, 26, "📂 浏览",
                 self._select_input, THEME["surface_light"])
        y += 34

        draw_label(self.canvas, y, "输出目录:")
        self.canvas.create_rectangle(130, y, w - 100, y + 26,
                                     fill=THEME["input_bg"], outline=THEME["border"])
        odir = self.output_dir.get() or "（同输入目录）"
        display_odir = odir if len(odir) <= 55 else "..." + odir[-52:]
        self.canvas.create_text(138, y + 13, text=display_odir, fill=THEME["text"],
                                anchor="w", font=("Microsoft YaHei", 9))
        draw_btn(self.canvas, w - 95, y, 90, 26, "📁 选择",
                 self._select_output, THEME["surface_light"])
        y += 44
        return y

    def _draw_settings_section(self, w, y):
        draw_section_card(self.canvas, w, y, 190, "⚙️ 设置")
        y += 28

        draw_label(self.canvas, y, "压缩算法:")
        draw_dropdown(self.canvas, self.root, 130, y, 145, self.algo_var,
                      ["zlib", "lzma", "bz2"], self._draw_all)
        draw_label(self.canvas, y, "级别:", 290)
        draw_slider(self.canvas, 335, y + 18, 220, self.level_var, 0, 9, self._draw_all)
        y += 38

        draw_label(self.canvas, y, "加密算法:")
        draw_dropdown(self.canvas, self.root, 130, y, 145, self.cipher_var,
                      ["AES-256-GCM", "AES-256-CBC"], self._draw_all)
        draw_label(self.canvas, y, "密码:", 290)
        draw_entry(self.canvas, self.root, 335, y, 200, self.password_var,
                   "（可选，不填则随机生成密钥）")
        y += 38

        draw_checkbox(self.canvas, y, self.bomb_var, "💣 压缩炸弹包装", self._draw_all)
        draw_label(self.canvas, y, "层数:", 175)
        draw_slider(self.canvas, 215, y + 18, 100, self.bomb_layers_var, 1, 10, self._draw_all)
        draw_checkbox(self.canvas, y, self.skip_compress_var, "⏭️ 跳过压缩(仅加密)",
                      self._draw_all, 335)
        y += 36

        if self.input_path.get() and os.path.exists(self.input_path.get()):
            fsz = format_size(os.path.getsize(self.input_path.get()))
            sha = compute_sha256(self.input_path.get())
            info = f"大小: {fsz}  |  SHA256: {sha[:32]}..."
            self.canvas.create_text(130, y + 6, text=info, fill=THEME["text_dim"],
                                    anchor="w", font=("Consolas", 8))
        y += 22
        return y

    def _draw_actions_section(self, w, y):
        draw_section_card(self.canvas, w, y, 58, "🎬 操作")
        y += 28

        btn_count = 5
        btn_w = (w - 50) // btn_count - 8
        x_start = 25
        btns = [
            ("🔒 加密+压缩", THEME["primary"],       self._do_encrypt),
            ("🔓 解密",      "#2e8b57",               self._do_decrypt),
            ("📦 仅压缩",    THEME["surface_light"],  self._do_compress_only),
            ("📤 解压",      THEME["surface_light"],  self._do_decompress_only),
            ("📊 算法对比",  "#c8a22e",               self._do_compare),
        ]
        for i, (label, color, cmd) in enumerate(btns):
            bx = x_start + i * (btn_w + 8)
            draw_btn(self.canvas, bx, y + 16, btn_w, 30, label, cmd, color, fontsize=10)
        y += 55
        return y

    def _draw_progress_section(self, w, y):
        draw_section_card(self.canvas, w, y, 34, "📊 进度")
        self._progress_y = y + 14
        self._progress_w = w - 50
        return y + 32

    def _draw_log_section(self, w, y, max_h):
        draw_section_card(self.canvas, w, y, max_h, "📋 日志")
        self._log_area = (25, y + 22, w - 25, y + max_h - 10)
        self._redraw_log()
        return y + max_h

    def _redraw_log(self):
        if self._log_area is None or self.canvas is None:
            return
        x1, y1, x2, y2 = self._log_area
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=THEME["input_bg"],
                                     outline=THEME["border"])
        lines = self.log_lines[-25:]
        for i, line in enumerate(lines):
            color = THEME["text_dim"]
            if "✅" in line:
                color = THEME["success"]
            elif "❌" in line or "失败" in line:
                color = THEME["danger"]
            elif "⚠" in line:
                color = THEME["warning"]
            elif "=" in line:
                color = THEME["primary"]
            self.canvas.create_text(x1 + 8, y1 + 8 + i * 18, text=line,
                                    fill=color, anchor="w", font=("Consolas", 8))

    # ==================== 文件选择 ====================

    def _select_input(self):
        path = filedialog.askopenfilename(title="选择输入文件")
        if path:
            self.input_path.set(path)
            self._draw_all()

    def _select_output(self):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_dir.set(path)
            self._draw_all()

    # ==================== 后台执行 ====================

    def _run_in_thread(self, target, *args):
        def wrapper():
            try:
                target(*args)
            except Exception as e:
                self.log(f"❌ 异常: {e}")
                import traceback
                self.log(traceback.format_exc()[:200])
        threading.Thread(target=wrapper, daemon=True).start()

    def _update_progress(self, val):
        draw_progress(self.canvas, self._progress_y, self._progress_w, val)

    # ==================== 操作绑定 ====================

    def _do_encrypt(self):
        if not self.input_path.get():
            self.log("⚠️  请先选择输入文件")
            return
        self.log_lines.clear()
        self.log("🔒 开始加密+压缩流程...")
        self._update_progress(0)

        config = CryptoConfig()
        config.compress_algo = self.algo_var.get()
        config.compress_level = self.level_var.get()
        config.encrypt_cipher = self.cipher_var.get()
        config.compression_bomb = self.bomb_var.get()
        config.compression_bomb_layers = self.bomb_layers_var.get()
        config.enable_integrity = True

        def run():
            pwd = self.password_var.get() or None
            results = process_file(
                self.input_path.get(),
                self.output_dir.get() or None,
                config, pwd,
                skip_compress=self.skip_compress_var.get(),
                log_callback=self.log,
                progress_callback=self._update_progress,
            )
            self.log("")
            if results.get("key_file"):
                self.keyfile_var.set(results["key_file"])

        self._run_in_thread(run)

    def _do_decrypt(self):
        if not self.input_path.get():
            self.log("⚠️  请先选择加密文件 (.bin)")
            return
        if not self.keyfile_var.get():
            kf = filedialog.askopenfilename(
                title="选择密钥文件", filetypes=[("JSON", "*.json")]
            )
            if not kf:
                return
            self.keyfile_var.set(kf)
        self.log_lines.clear()
        self.log("🔓 开始解密...")
        self._update_progress(0)

        def run():
            ok = decrypt_file(
                self.input_path.get(),
                self.keyfile_var.get(),
                log_callback=self.log,
                progress_callback=self._update_progress,
            )
            if ok:
                self.log("\n✅ 解密完成！")

        self._run_in_thread(run)

    def _do_compress_only(self):
        if not self.input_path.get():
            self.log("⚠️  请先选择输入文件")
            return
        from .compress_core import generic_compress
        self.log_lines.clear()
        algo = self.algo_var.get()
        level = self.level_var.get()
        ext = COMPRESS_ALGOS[algo]["ext"]
        output = self.input_path.get() + ext
        self.log(f"📦 仅压缩 ({COMPRESS_ALGOS[algo]['name']}, 级别 {level})...")
        self._update_progress(30)

        def run():
            ok, info = generic_compress(self.input_path.get(), output, algo=algo, level=level)
            if ok:
                self._update_progress(100)
                self.log(f"✅ 压缩成功: {format_size(info['input_size'])} → "
                         f"{format_size(info['output_size'])} ({info['ratio']})")
                self.log(f"   输出: {output}")
            else:
                self.log(f"❌ 压缩失败: {info.get('error')}")

        self._run_in_thread(run)

    def _do_decompress_only(self):
        if not self.input_path.get():
            self.log("⚠️  请先选择压缩文件")
            return
        from .compress_core import generic_decompress
        self.log_lines.clear()
        output = self.input_path.get() + "_decompressed"
        self.log(f"📤 解压: {os.path.basename(self.input_path.get())}...")
        self._update_progress(30)

        def run():
            ok, info = generic_decompress(self.input_path.get(), output)
            if ok:
                self._update_progress(100)
                self.log(f"✅ 解压成功 ({info.get('algo', '?')}): "
                         f"{format_size(info['actual_size'])}")
                if info.get("verified"):
                    self.log("   ✅ 大小校验通过")
                self.log(f"   输出: {output}")
            else:
                self.log(f"❌ 解压失败: {info.get('error')}")

        self._run_in_thread(run)

    def _do_compare(self):
        if not self.input_path.get():
            self.log("⚠️  请先选择输入文件")
            return
        self.log_lines.clear()
        fname = os.path.basename(self.input_path.get())
        fsz = format_size(os.path.getsize(self.input_path.get()))
        self.log(f"📊 压缩算法对比: {fname} ({fsz})")
        self.log("=" * 46)
        self.log(f"{'算法':<10} {'级别':<6} {'压缩后':<12} {'比率':<10}")
        self.log("-" * 46)
        self._update_progress(10)

        def run():
            try:
                results = compare_compress_algorithms(self.input_path.get(), levels=(1, 6, 9))
                progress = 10
                for algo in ["zlib", "lzma", "bz2"]:
                    progress += 20
                    self._update_progress(progress)
                    for lv in [1, 6, 9]:
                        info = results.get(algo, {}).get(lv, {})
                        if "error" in info:
                            self.log(f"{COMPRESS_ALGOS[algo]['name']:<10} {lv:<6} {'失败':<12} -")
                        else:
                            self.log(
                                f"{COMPRESS_ALGOS[algo]['name']:<10} "
                                f"{lv:<6} {format_size(info['output_size']):<12} "
                                f"{info['ratio']:<10}"
                            )
                self._update_progress(100)
                self.log("-" * 46)
                self.log("✅ 对比完成！")
            except Exception as e:
                self.log(f"❌ 对比失败: {e}")

        self._run_in_thread(run)
