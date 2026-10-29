"""renamer 图形界面入口（Tkinter，中文 UI）。

默认 dry-run：只在用户勾选「执行重命名」且预览无风险时才真正改动磁盘。
无显示器环境下请勿直接实例化 Tk()；本模块所有 GUI 创建都放在
`if __name__ == '__main__':` 守卫内，导入本模块不会触发任何 GUI 行为，
便于在无头环境仅测试 core.py 纯逻辑。
"""

from __future__ import annotations

import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import core

# 需要阻止执行的风险状态
_BLOCKING = {"conflict", "empty", "overwrite", "invalid"}
# 状态 -> 中文说明
_STATUS_TEXT = {
    "ok": "可重命名",
    "conflict": "冲突(重名)",
    "empty": "空名",
    "overwrite": "会覆盖",
    "invalid": "非法字符",
}


class RenamerApp:
    """renamer 主窗口应用程序。"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("正则批量重命名 - renamer")
        self.root.geometry("760x560")
        self.root.resizable(True, True)

        self.folder_var = tk.StringVar()
        self.pattern_var = tk.StringVar(value=r"a_(\d+)")
        self.repl_var = tk.StringVar(value=r"b_\1")
        self.recursive_var = tk.BooleanVar(value=False)
        self.execute_var = tk.BooleanVar(value=False)

        self._build_widgets()
        self._refresh_preview()

    # ------------------------- UI 构建 -------------------------
    def _build_widgets(self) -> None:
        # 顶部：文件夹选择
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="文件夹：").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.folder_var, width=50).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=4
        )
        ttk.Button(top, text="选择文件夹", command=self._choose_folder).pack(side=tk.LEFT)

        # 中部：正则参数
        mid = ttk.Frame(self.root, padding=(8, 0))
        mid.pack(fill=tk.X)
        ttk.Label(mid, text="正则表达式 pattern：").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(mid, textvariable=self.pattern_var).grid(
            row=0, column=1, sticky=tk.EW, padx=4, pady=2
        )
        ttk.Label(mid, text="替换模板 repl：").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(mid, textvariable=self.repl_var).grid(
            row=1, column=1, sticky=tk.EW, padx=4, pady=2
        )
        mid.columnconfigure(1, weight=1)

        # 选项行
        opt = ttk.Frame(self.root, padding=(8, 4))
        opt.pack(fill=tk.X)
        ttk.Checkbutton(
            opt, text="递归子目录", variable=self.recursive_var,
            command=self._refresh_preview,
        ).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(
            opt, text="执行重命名（取消勾选则仅预览、不改动文件）",
            variable=self.execute_var, command=self._on_execute_toggle,
        ).pack(side=tk.LEFT)
        ttk.Button(opt, text="刷新预览", command=self._refresh_preview).pack(side=tk.RIGHT)

        # 实时预览：绑定输入变化
        self.pattern_var.trace_add("write", lambda *a: self._refresh_preview())
        self.repl_var.trace_add("write", lambda *a: self._refresh_preview())

        # 预览列表
        list_frame = ttk.Frame(self.root, padding=(8, 4))
        list_frame.pack(fill=tk.BOTH, expand=True)
        cols = ("old", "new", "status")
        self.tree = ttk.Treeview(
            list_frame, columns=cols, show="headings", height=18
        )
        self.tree.heading("old", text="原文件名")
        self.tree.heading("new", text="新文件名")
        self.tree.heading("status", text="状态")
        self.tree.column("old", width=300)
        self.tree.column("new", width=300)
        self.tree.column("status", width=120)
        self.tree.tag_configure("bad", foreground="red")
        self.tree.tag_configure("ok", foreground="black")
        vsb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 底部状态栏 + 执行
        bottom = ttk.Frame(self.root, padding=8)
        bottom.pack(fill=tk.X)
        self.summary_var = tk.StringVar(value="未选择文件夹")
        ttk.Label(bottom, textvariable=self.summary_var).pack(side=tk.LEFT)
        self.execute_btn = ttk.Button(
            bottom, text="开始重命名", command=self._do_execute, state=tk.DISABLED
        )
        self.execute_btn.pack(side=tk.RIGHT)

    # ------------------------- 交互逻辑 -------------------------
    def _choose_folder(self) -> None:
        path = filedialog.askdirectory(title="选择要重命名的文件夹")
        if path:
            self.folder_var.set(path)
            self._refresh_preview()

    def _on_execute_toggle(self) -> None:
        # 勾选执行时，仅当无风险才允许点击按钮
        self._update_execute_button()

    def _update_execute_button(self) -> None:
        if not self.execute_var.get():
            self.execute_btn.configure(state=tk.DISABLED)
            return
        # 统计当前预览中的风险条目
        blocking = sum(
            1 for item in self._last_preview
            if item.get("status") in _BLOCKING
        )
        if blocking > 0:
            self.execute_btn.configure(state=tk.DISABLED)
            self.summary_var.set(
                f"存在 {blocking} 个风险项（冲突/空名/覆盖/非法），已阻止执行，请修正后重试"
            )
        else:
            self.execute_btn.configure(state=tk.NORMAL)

    def _refresh_preview(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)
        folder = self.folder_var.get().strip()
        self._last_preview = []
        if not folder or not os.path.isdir(folder):
            self.summary_var.set("请先选择有效的文件夹")
            self._update_execute_button()
            return

        pattern = self.pattern_var.get()
        repl = self.repl_var.get()
        recursive = self.recursive_var.get()

        try:
            preview = core.preview_renames(folder, pattern, repl, recursive)
        except re.error as exc:
            messagebox.showerror("正则表达式错误", f"pattern 不合法：\n{exc}")
            self.summary_var.set("正则表达式错误，请检查 pattern")
            self._update_execute_button()
            return

        self._last_preview = preview
        counts = {k: 0 for k in _STATUS_TEXT}
        for item in preview:
            st = item.get("status", "ok")
            counts[st] = counts.get(st, 0) + 1
            tag = "bad" if st in _BLOCKING else "ok"
            self.tree.insert(
                "", tk.END,
                values=(item["old"], item["new"], _STATUS_TEXT.get(st, st)),
                tags=(tag,),
            )

        total = len(preview)
        ok_n = counts.get("ok", 0)
        risk_n = sum(counts.get(k, 0) for k in _BLOCKING)
        self.summary_var.set(
            f"共 {total} 项 ｜ 可重命名 {ok_n} ｜ 风险 {risk_n}"
            f"（冲突 {counts['conflict']} / 空名 {counts['empty']} / "
            f"覆盖 {counts['overwrite']} / 非法 {counts['invalid']}）"
        )
        self._update_execute_button()

    def _do_execute(self) -> None:
        if not self.execute_var.get():
            messagebox.showinfo("提示", "请先勾选「执行重命名」。默认仅预览、不改动文件。")
            return
        blocking = sum(
            1 for item in self._last_preview
            if item.get("status") in _BLOCKING
        )
        if blocking > 0:
            messagebox.showwarning(
                "已阻止", f"存在 {blocking} 个风险项，执行前必须消除所有冲突/覆盖/空名/非法。"
            )
            return

        ok_n = sum(1 for item in self._last_preview if item.get("status") == "ok")
        if ok_n == 0:
            messagebox.showinfo("提示", "没有可重命名的文件。")
            return

        confirm = messagebox.askyesno(
            "确认执行",
            f"即将真正重命名 {ok_n} 个文件，此操作不可自动撤销。\n是否继续？",
        )
        if not confirm:
            return

        done, skipped = core.apply_renames(self._last_preview, only_status="ok")
        messagebox.showinfo(
            "完成", f"成功重命名 {done} 个文件，跳过 {skipped} 个。"
        )
        self._refresh_preview()


def main() -> None:
    """GUI 入口。无头环境下不应调用此函数。"""
    root = tk.Tk()
    RenamerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
