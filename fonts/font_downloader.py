"""
中文字体复制工具
功能：从本地源目录浏览、选择并复制中文字体到目标目录
数据源：
  - fonts_data.json    — 已知字体元数据（显示名称、风格、预览文字等）
  - font_sources.json  — 在线来源网站参考（非下载用）
作者：工具箱系列
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import json
import os
import shutil
import webbrowser
from pathlib import Path

# ─────────────────────────────────────────────
# 缓存加载
# ─────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent

_fonts_cache = None
_style_filter_cache = None
_sources_cache = None


def _load_json(filename):
    path = SCRIPT_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"找不到数据文件：{path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_fonts_config():
    global _fonts_cache, _style_filter_cache
    if _fonts_cache is None:
        data = _load_json("fonts_data.json")
        _fonts_cache = data.get("fonts", [])
        _style_filter_cache = data.get("style_filter", ["全部"])
    return _fonts_cache, _style_filter_cache


def _get_sources_config():
    global _sources_cache
    if _sources_cache is None:
        _sources_cache = _load_json("font_sources.json")
    return _sources_cache


# ─────────────────────────────────────────────
# 来源网站弹窗（保留，仅供参考用）
# ─────────────────────────────────────────────

class SourceBrowserWindow(tk.Toplevel):
    """浏览所有来源网站（来自 font_sources.json）"""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("🌐 字体来源网站")
        self.geometry("680x520")
        self.resizable(True, True)
        self.configure(bg="#f5f5f5")
        self.transient(parent)
        self.grab_set()

        sources = _get_sources_config()

        header = tk.Frame(self, bg="#2c2c2c", pady=10)
        header.pack(fill=tk.X)
        tk.Label(header, text="🌐 免费可商用字体来源网站",
                 font=("微软雅黑", 13, "bold"), bg="#2c2c2c", fg="white").pack()
        tk.Label(header, text="以下网站均提供免费商用字体，可用于手动下载",
                 font=("微软雅黑", 9), bg="#2c2c2c", fg="#aaa").pack()

        canvas = tk.Canvas(self, bg="#f5f5f5", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#f5f5f5")

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=(6, 0))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 目录源
        dirs = sources.get("directory_sources", [])
        categories = {}
        for d in dirs:
            cat = d.get("category", "其他")
            categories.setdefault(cat, []).append(d)

        for cat, items in categories.items():
            cat_frame = tk.LabelFrame(scroll_frame, text=f"  {cat}",
                                      bg="#f5f5f5", font=("微软雅黑", 10, "bold"),
                                      fg="#555", padx=8, pady=6)
            cat_frame.pack(fill=tk.X, pady=(4, 8))
            for d in items:
                self._make_source_row(cat_frame, d)

        bottom = tk.Frame(self, bg="#ddd", height=28)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(bottom, text="提示：下载前请确认字体授权协议（SIL OFL / Apache 等），保留授权来源以备商用",
                 bg="#ddd", fg="#555", font=("微软雅黑", 8)).pack(padx=10)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.protocol("WM_DELETE_WINDOW", lambda: (canvas.unbind_all("<MouseWheel>"), self.destroy()))

    def _make_source_row(self, parent, source):
        row = tk.Frame(parent, bg=parent["bg"], pady=2)
        row.pack(fill=tk.X)

        btn = tk.Label(row, text=f"  {source['name']}  ",
                       font=("微软雅黑", 10, "bold"),
                       fg="#2a7ae2", bg=parent["bg"], cursor="hand2")
        btn.pack(side=tk.LEFT)
        btn.bind("<Button-1>", lambda e, u=(source.get("homepage") or source["url"]): webbrowser.open(u))

        desc = source.get("description", "")
        tk.Label(row, text=desc, font=("微软雅黑", 9),
                 bg=parent["bg"], fg="#888", anchor="w", wraplength=480).pack(
                     side=tk.LEFT, padx=(8, 0))

        if source.get("free_commercial"):
            tk.Label(row, text="✓可商用", font=("微软雅黑", 8),
                     bg=parent["bg"], fg="#4caf50").pack(side=tk.RIGHT, padx=4)


# ─────────────────────────────────────────────
# 主窗口
# ─────────────────────────────────────────────

class FontDownloaderApp:
    # 支持的字体文件扩展名
    FONT_EXTS = (".ttf", ".otf", ".ttc", ".woff", ".woff2")

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("中文字体复制工具")
        self.root.geometry("1000x680")
        self.root.resizable(True, True)
        self.root.configure(bg="#f5f5f5")

        # 目标目录（字体复制到哪里）
        self.save_dir = SCRIPT_DIR / "fonts"
        self.save_dir.mkdir(exist_ok=True)

        # 源目录（字体从哪里来 — 默认系统字体目录）
        self.source_dir = Path("C:/Windows/Fonts")

        self._copy_thread: threading.Thread | None = None
        self._cancel_flag = threading.Event()

        self._build_ui()
        self._refresh_list()

    # ── UI 构建 ──────────────────────────────

    def _build_ui(self):
        # 顶部工具栏
        toolbar = tk.Frame(self.root, bg="#2c2c2c", pady=6)
        toolbar.pack(fill=tk.X)

        tk.Label(toolbar, text="🈶 中文字体复制工具", font=("微软雅黑", 14, "bold"),
                 bg="#2c2c2c", fg="white").pack(side=tk.LEFT, padx=14)

        # 按钮行
        btn_row = tk.Frame(toolbar, bg="#2c2c2c")
        btn_row.pack(side=tk.RIGHT, padx=10)
        tk.Button(btn_row, text="🌐 字体来源",
                  command=lambda: SourceBrowserWindow(self.root),
                  bg="#fbbc05", fg="#222", font=("微软雅黑", 10),
                  relief=tk.FLAT, padx=10, pady=3, cursor="hand2").pack(side=tk.RIGHT)

        # 源目录行
        source_row = tk.Frame(self.root, bg="#e0e8f0", pady=4, padx=10)
        source_row.pack(fill=tk.X)

        tk.Label(source_row, text="📁 源目录（字体来源）：", bg="#e0e8f0",
                 font=("微软雅黑", 10)).pack(side=tk.LEFT)
        self.source_var = tk.StringVar(value=str(self.source_dir))
        tk.Entry(source_row, textvariable=self.source_var, width=50,
                 font=("Consolas", 9)).pack(side=tk.LEFT, padx=4)
        tk.Button(source_row, text="📂 选择源目录", command=self._choose_source_dir,
                  bg="#5b9bd5", fg="white", relief=tk.FLAT, padx=8, pady=2,
                  cursor="hand2").pack(side=tk.LEFT, padx=2)
        tk.Button(source_row, text="🔄 刷新列表", command=self._refresh_list,
                  bg="#5b9bd5", fg="white", relief=tk.FLAT, padx=8, pady=2,
                  cursor="hand2").pack(side=tk.LEFT, padx=2)

        tk.Label(source_row, text=f"支持格式：{', '.join(self.FONT_EXTS)}",
                 bg="#e0e8f0", fg="#666", font=("微软雅黑", 8)).pack(side=tk.RIGHT)

        # 目标目录行
        dest_row = tk.Frame(self.root, bg="#f0f0f0", pady=4, padx=10)
        dest_row.pack(fill=tk.X)

        tk.Label(dest_row, text="💾 目标目录（复制到）：", bg="#f0f0f0",
                 font=("微软雅黑", 10)).pack(side=tk.LEFT)
        self.dir_var = tk.StringVar(value=str(self.save_dir))
        tk.Entry(dest_row, textvariable=self.dir_var, width=50,
                 font=("Consolas", 9)).pack(side=tk.LEFT, padx=4)
        tk.Button(dest_row, text="📂 选择目录", command=self._choose_dir,
                  bg="#6c757d", fg="white", relief=tk.FLAT, padx=8, pady=2,
                  cursor="hand2").pack(side=tk.LEFT, padx=2)
        tk.Button(dest_row, text="📁 打开目录", command=self._open_dir,
                  bg="#6c757d", fg="white", relief=tk.FLAT, padx=8, pady=2,
                  cursor="hand2").pack(side=tk.LEFT, padx=2)

        # 搜索 & 筛选栏
        filterbar = tk.Frame(self.root, bg="#e8e8e8", pady=6, padx=10)
        filterbar.pack(fill=tk.X)

        tk.Label(filterbar, text="搜索:", bg="#e8e8e8").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh_list())
        tk.Entry(filterbar, textvariable=self.search_var, width=20).pack(side=tk.LEFT, padx=4)

        _, style_filter = _get_fonts_config()
        tk.Label(filterbar, text="风格:", bg="#e8e8e8").pack(side=tk.LEFT, padx=(16, 0))
        self.style_var = tk.StringVar(value="全部")
        style_cb = ttk.Combobox(filterbar, textvariable=self.style_var,
                                values=style_filter, state="readonly", width=10)
        style_cb.pack(side=tk.LEFT, padx=4)
        style_cb.bind("<<ComboboxSelected>>", lambda _: self._refresh_list())

        tk.Label(filterbar, text="共", bg="#e8e8e8").pack(side=tk.LEFT, padx=(16, 0))
        self.count_var = tk.StringVar(value="0")
        tk.Label(filterbar, textvariable=self.count_var, bg="#e8e8e8",
                 font=("微软雅黑", 10, "bold"), fg="#2a7ae2").pack(side=tk.LEFT)
        tk.Label(filterbar, text="款字体", bg="#e8e8e8").pack(side=tk.LEFT)

        # 主体区域
        main = tk.Frame(self.root, bg="#f5f5f5")
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 0))

        # ── 左侧列表 ──
        left = tk.Frame(main, bg="#f5f5f5", width=380)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        left.pack_propagate(False)

        cols = ("name_cn", "style", "size", "license")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("name_cn", text="字体名称")
        self.tree.heading("style",   text="风格")
        self.tree.heading("size",    text="大小")
        self.tree.heading("license", text="类型")
        self.tree.column("name_cn", width=180)
        self.tree.column("style",   width=70)
        self.tree.column("size",    width=70)
        self.tree.column("license", width=55)

        vsb = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # ── 右侧详情 & 操作 ──
        right = tk.Frame(main, bg="white", relief=tk.RIDGE, bd=1)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))

        self.detail_name = tk.Label(right, text="← 选择一款字体", font=("微软雅黑", 16, "bold"),
                                    bg="white", fg="#222", anchor="w")
        self.detail_name.pack(fill=tk.X, padx=16, pady=(16, 4))

        self.detail_sub = tk.Label(right, text="", font=("微软雅黑", 10),
                                   bg="white", fg="#666", anchor="w")
        self.detail_sub.pack(fill=tk.X, padx=16)

        ttk.Separator(right, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=16, pady=8)

        self.detail_desc = tk.Label(right, text="", font=("微软雅黑", 10),
                                    bg="white", fg="#444", anchor="w",
                                    wraplength=460, justify=tk.LEFT)
        self.detail_desc.pack(fill=tk.X, padx=16, pady=(0, 8))

        # 预览区
        preview_frame = tk.LabelFrame(right, text="  预览  ", bg="white",
                                      font=("微软雅黑", 9), fg="#666")
        preview_frame.pack(fill=tk.X, padx=16, pady=4)
        self.preview_label = tk.Label(preview_frame, text="", font=("微软雅黑", 18),
                                      bg="#fafafa", fg="#222", pady=14, wraplength=450)
        self.preview_label.pack(fill=tk.X, padx=8, pady=8)

        # 文件选择（如果字体有多个文件）
        file_frame = tk.Frame(right, bg="white")
        file_frame.pack(fill=tk.X, padx=16, pady=(8, 0))
        tk.Label(file_frame, text="选择文件：", bg="white", font=("微软雅黑", 10)).pack(side=tk.LEFT)
        self.file_var = tk.StringVar()
        self.file_cb = ttk.Combobox(file_frame, textvariable=self.file_var,
                                    state="readonly", width=40)
        self.file_cb.pack(side=tk.LEFT, padx=6)

        # 源路径显示
        self.source_path_label = tk.Label(right, text="", bg="white", fg="#888",
                                          font=("Consolas", 8), anchor="w")
        self.source_path_label.pack(fill=tk.X, padx=16, pady=(4, 0))

        ttk.Separator(right, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=16, pady=10)

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(right, variable=self.progress_var,
                                        maximum=100, length=460)
        self.progress.pack(padx=16, fill=tk.X)

        self.status_var = tk.StringVar(value="就绪 — 请先设置源目录")
        tk.Label(right, textvariable=self.status_var, bg="white",
                 fg="#555", font=("Consolas", 9), anchor="w").pack(fill=tk.X, padx=16, pady=2)

        # ── 按钮区 ──
        btn_frame = tk.Frame(right, bg="white")
        btn_frame.pack(fill=tk.X, padx=16, pady=(6, 14))

        self.copy_btn = tk.Button(btn_frame, text="📋 复制选中字体",
                                  command=self._start_copy,
                                  bg="#2a7ae2", fg="white", font=("微软雅黑", 11, "bold"),
                                  relief=tk.FLAT, padx=16, pady=6, cursor="hand2")
        self.copy_btn.pack(side=tk.LEFT)

        self.copy_all_btn = tk.Button(btn_frame, text="📋 批量复制全部",
                                      command=self._copy_all_fonts,
                                      bg="#444", fg="white", font=("微软雅黑", 10),
                                      relief=tk.FLAT, padx=10, pady=6, cursor="hand2")
        self.copy_all_btn.pack(side=tk.LEFT, padx=8)

        self.cancel_btn = tk.Button(btn_frame, text="✕ 取消",
                                    command=self._cancel_copy,
                                    bg="#e44", fg="white", font=("微软雅黑", 10),
                                    relief=tk.FLAT, padx=10, pady=6, cursor="hand2",
                                    state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT)

        # ── 底部状态栏 ──
        statusbar = tk.Frame(self.root, bg="#ddd", height=22)
        statusbar.pack(fill=tk.X, side=tk.BOTTOM)
        self.bottom_status = tk.Label(statusbar,
                                      text="提示：将字体文件放入「源目录」，然后选择并复制到「目标目录」",
                                      bg="#ddd", fg="#555", font=("微软雅黑", 9), anchor="w")
        self.bottom_status.pack(side=tk.LEFT, padx=10)

        self.local_label = tk.Label(statusbar, text="", bg="#ddd", fg="#2a7ae2",
                                    font=("微软雅黑", 9), anchor="e")
        self.local_label.pack(side=tk.RIGHT, padx=10)
        self._update_local_count()

        self._current_font_data = None

    # ── 数据 ────────────────────────────────

    def _get_known_metadata(self, filename: str) -> dict | None:
        """根据文件名匹配 fonts_data.json 中的已知字体元数据"""
        name_lower = filename.lower()
        known_fonts, _ = _get_fonts_config()
        for kf in known_fonts:
            # 匹配方式：文件名包含已知字体的关键词
            keywords = kf.get("keywords", [])
            # 默认用 name_cn 和 name 作为关键词
            if not keywords:
                keywords = [kf.get("name_cn", ""), kf.get("name", "")]
            for kw in keywords:
                if kw and kw.lower() in name_lower:
                    return kf
        return None

    def _scan_source_dir(self):
        """扫描源目录，返回字体条目列表"""
        source = self._get_source_dir()
        if not source or not source.exists():
            return []

        fonts = []
        for f in sorted(source.iterdir()):
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            if ext not in self.FONT_EXTS:
                continue

            stat = f.stat()
            size_mb = stat.st_size / (1024 * 1024)

            # 尝试匹配已知元数据
            meta = self._get_known_metadata(f.name)

            if meta:
                name_cn = meta.get("name_cn", f.stem)
                style = meta.get("style", "未知")
                preview_text = meta.get("preview", name_cn)
                license_info = meta.get("license", "-")
                desc = meta.get("desc", f"本地字体文件：{f.name}")
            else:
                name_cn = f.stem
                style = self._guess_style(f.name)
                preview_text = f.stem
                license_info = "-"
                desc = f"本地字体文件：{f.name}"

            fonts.append({
                "name": f.stem,
                "name_cn": name_cn,
                "filename": f.name,
                "filepath": str(f),
                "filepath_obj": f,
                "style": style,
                "size_mb": f"{size_mb:.1f} MB",
                "size_bytes": stat.st_size,
                "source": "local",
                "license": license_info,
                "desc": desc,
                "preview": preview_text,
                "variants": [{
                    "weight": f"{f.name}  ({size_mb:.1f} MB)",
                    "filepath": str(f),
                    "filepath_obj": f,
                    "size_mb": f"{size_mb:.1f} MB",
                }],
            })

        return fonts

    @staticmethod
    def _guess_style(filename: str) -> str:
        """根据文件名猜测字体风格"""
        lower = filename.lower()
        if any(w in lower for w in ["黑", "hei", "sans", "gothic"]):
            return "无衬线"
        if any(w in lower for w in ["宋", "song", "serif", "明"]):
            return "衬线"
        if any(w in lower for w in ["楷", "kai"]):
            return "楷体"
        if any(w in lower for w in ["隶", "li"]):
            return "隶书"
        if any(w in lower for w in ["行", "xing"]):
            return "行书"
        if any(w in lower for w in ["草", "cao"]):
            return "草书"
        if any(w in lower for w in ["圆", "yuan", "round"]):
            return "圆体"
        if any(w in lower for w in ["hand", "手写", "brush", "毛笔"]):
            return "手写"
        return "未知"

    def _refresh_list(self):
        kw = self.search_var.get().strip().lower()
        style_f = self.style_var.get()

        self.tree.delete(*self.tree.get_children())
        shown = []
        for f in self._scan_source_dir():
            if kw and kw not in f["name"].lower() and kw not in f["name_cn"].lower():
                continue
            st = f.get("style", "")
            if style_f != "全部" and st != style_f:
                continue
            shown.append(f)

        for f in shown:
            self.tree.insert("", tk.END, iid=f["name"],
                             values=(f["name_cn"], f.get("style", "-"),
                                     f.get("size_mb", "?"), f["filename"].split(".")[-1].upper()))

        self.count_var.set(str(len(shown)))
        source = self._get_source_dir()
        if source and source.exists():
            self.status_var.set(f"已扫描源目录：{source}  —  发现 {len(shown)} 个字体文件")
        else:
            self.status_var.set("请先设置包含字体文件的「源目录」")

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        name = sel[0]
        data = next((f for f in self._scan_source_dir() if f["name"] == name), None)
        if not data:
            return
        self._current_font_data = data

        self.detail_name.config(text=f"{data['name_cn']}  ({data['filename']})")
        self.detail_sub.config(
            text=f"风格：{data.get('style', '-')}    体积：{data.get('size_mb', '?')}    格式：{data['filename'].split('.')[-1].upper()}")
        self.detail_desc.config(text=data.get("desc", ""))
        self.preview_label.config(text=data.get("preview", data["name_cn"]))

        variants = data.get("variants") or []
        files_list = [v.get("weight", f"文件 {i+1}") for i, v in enumerate(variants)]
        self.file_cb["values"] = files_list
        if files_list:
            self.file_cb.current(0)

        # 显示源文件路径
        fp = data.get("filepath", "")
        self.source_path_label.config(text=f"源文件：{fp}" if fp else "")

    # ── 目录管理 ─────────────────────────────

    def _get_source_dir(self):
        d = Path(self.source_var.get())
        return d if d.exists() else None

    def _get_save_dir(self):
        d = Path(self.dir_var.get()).resolve()
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _choose_source_dir(self):
        d = filedialog.askdirectory(title="选择字体源目录",
                                    initialdir=self.source_var.get())
        if d:
            self.source_dir = Path(d).resolve()
            self.source_var.set(str(self.source_dir))
            self._refresh_list()

    def _choose_dir(self):
        d = filedialog.askdirectory(title="选择字体保存目录",
                                    initialdir=self.dir_var.get())
        if d:
            self.save_dir = Path(d).resolve()
            self.dir_var.set(str(self.save_dir))

    def _open_dir(self):
        os.startfile(str(self._get_save_dir()))

    def _update_local_count(self):
        d = self._get_save_dir()
        count = sum(1 for f in d.iterdir() if f.suffix.lower() in self.FONT_EXTS) if d.exists() else 0
        self.local_label.config(text=f"目标目录已有：{count} 个文件")

    # ── 复制逻辑 ─────────────────────────────

    def _set_copying(self, copying: bool):
        state = tk.DISABLED if copying else tk.NORMAL
        self.copy_btn.config(state=state)
        self.copy_all_btn.config(state=state)
        self.cancel_btn.config(state=tk.NORMAL if copying else tk.DISABLED)

    def _start_copy(self):
        """复制当前选中的字体文件"""
        if not self._current_font_data:
            messagebox.showinfo("提示", "请先在左侧列表中选择一款字体")
            return
        data = self._current_font_data
        variants = data.get("variants") or []
        if not variants:
            messagebox.showerror("错误", "该字体没有可复制的文件")
            return
        idx = max(0, self.file_cb.current())
        self._copy_files([variants[idx]], data)

    def _copy_all_fonts(self):
        """批量复制当前列表显示的全部字体"""
        all_fonts = self._scan_source_dir()
        if not all_fonts:
            messagebox.showinfo("提示", "源目录中没有发现字体文件")
            return

        if not messagebox.askyesno("确认批量复制",
                                   f"即将复制全部 {len(all_fonts)} 款字体到目标目录\n\n"
                                   f"目标：{self._get_save_dir()}\n\n确定继续？"):
            return

        # 每款字体取第一个 variant
        all_variants = []
        for f in all_fonts:
            v = f.get("variants", [])
            if v:
                all_variants.append((v[0], f))

        self._copy_files_flat(all_variants)

    def _copy_files(self, variants, font_data):
        """复制选中的变体文件"""
        self._cancel_flag.clear()
        self._set_copying(True)
        self.progress_var.set(0)

        self._copy_thread = threading.Thread(
            target=self._copy_worker,
            args=([(v, font_data) for v in variants],),
            daemon=True,
        )
        self._copy_thread.start()

    def _copy_files_flat(self, variants_with_data):
        """批量复制（不依赖当前选中字体）"""
        self._cancel_flag.clear()
        self._set_copying(True)
        self.progress_var.set(0)

        self._copy_thread = threading.Thread(
            target=self._copy_worker,
            args=(variants_with_data,),
            daemon=True,
        )
        self._copy_thread.start()

    def _cancel_copy(self):
        self._cancel_flag.set()
        self.status_var.set("已请求取消，等待当前文件结束…")

    def _copy_worker(self, variants_with_data):
        """后台复制线程"""
        save_dir = self._get_save_dir()
        total = len(variants_with_data)

        for idx, (v, font_data) in enumerate(variants_with_data):
            if self._cancel_flag.is_set():
                self._ui(self.status_var.set, "已取消复制")
                break

            src_path = v.get("filepath_obj") or Path(v["filepath"])
            if not src_path.exists():
                self._ui(self.status_var.set, f"❌ 源文件不存在：{src_path}")
                self._ui(messagebox.showerror, "复制失败",
                         f"字体：{font_data.get('name_cn','?')}\n文件：{src_path}\n\n源文件已不存在，请刷新列表。")
                continue

            filename = src_path.name
            dest = save_dir / filename

            if dest.exists():
                self._ui(self.status_var.set, f"[{idx+1}/{total}] 已存在，跳过：{filename}")
                self._ui(self.progress_var.set, (idx + 1) / total * 100)
                continue

            self._ui(self.status_var.set, f"[{idx+1}/{total}] 复制中：{filename}")
            try:
                self._copy_file(src_path, dest, idx, total)
            except Exception as e:
                self._ui(self.status_var.set, f"复制失败：{e}")
                self._ui(messagebox.showerror, "复制失败", f"文件：{filename}\n错误：{e}")
                continue

        if not self._cancel_flag.is_set():
            self._ui(self.status_var.set, f"✅ 全部复制完成！保存至：{save_dir}")
            self._ui(self.progress_var.set, 100)

        self._ui(self._set_copying, False)
        self._ui(self._update_local_count)

    @staticmethod
    def _copy_file(src: Path, dest: Path, file_idx: int, total_files: int):
        """带进度的文件复制"""
        total_bytes = src.stat().st_size
        copied = 0
        chunk_size = 1024 * 1024  # 1 MB chunks for local copy

        with open(src, "rb") as fsrc, open(dest, "wb") as fdst:
            while True:
                chunk = fsrc.read(chunk_size)
                if not chunk:
                    break
                fdst.write(chunk)
                copied += len(chunk)

        # 保留原始文件的修改时间
        shutil.copystat(str(src), str(dest))

    # ── 工具方法 ─────────────────────────────

    @staticmethod
    def _fmt_size(b: int) -> str:
        if b <= 0:
            return "0 B"
        for unit in ("B", "KB", "MB", "GB"):
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} GB"

    def _ui(self, fn, *args):
        """线程安全地调用 UI 函数"""
        self.root.after(0, fn, *args)


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────

def main():
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    FontDownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
