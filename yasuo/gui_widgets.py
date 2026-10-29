# -*- coding: utf-8 -*-
"""
gui_widgets.py — tkinter Canvas 组件库
只依赖 tkinter，不 import 任何业务逻辑模块
"""

# ==================== 颜色主题 ====================
THEME = {
    "bg":            "#1e1e2e",
    "surface":       "#282840",
    "surface_light": "#313150",
    "primary":       "#7c5cfc",
    "primary_hover": "#9b7efd",
    "success":       "#50fa7b",
    "warning":       "#ffb86c",
    "danger":        "#ff5555",
    "text":          "#e0e0f0",
    "text_dim":      "#9090b0",
    "border":        "#404060",
    "input_bg":      "#1a1a2e",
    "canvas":        "#1e1e2e",
}


def draw_rounded_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
    """在 Canvas 上绘制圆角矩形"""
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def draw_section_card(canvas, w, y, h, title):
    draw_rounded_rect(canvas, 15, y, w - 15, y + h, 8,
                      fill=THEME["surface"], outline=THEME["border"])
    canvas.create_text(24, y + 14, text=title, fill=THEME["text"],
                       anchor="w", font=("Microsoft YaHei", 10, "bold"))
    canvas.create_line(24, y + 22, 24 + len(title) * 14, y + 22,
                       fill=THEME["primary"], width=1)


def draw_label(canvas, y, text, x=None):
    px = x if x is not None else 24
    canvas.create_text(px, y + 13, text=text, fill=THEME["text_dim"],
                       anchor="w", font=("Microsoft YaHei", 9))


def draw_btn(canvas, x, y, bw, bh, text, cmd, color=None, fontsize=9):
    if color is None:
        color = THEME["primary"]
    draw_rounded_rect(canvas, x, y, x + bw, y + bh, 4, fill=color, outline="")
    t = canvas.create_text(x + bw // 2, y + bh // 2, text=text,
                           fill="#ffffff", font=("Microsoft YaHei", fontsize))
    canvas.tag_bind(t, "<Button-1>", lambda e, c=cmd: c())
    hit = canvas.create_rectangle(x, y, x + bw, y + bh, fill="", outline="")
    canvas.tag_bind(hit, "<Button-1>", lambda e, c=cmd: c())


def draw_dropdown(canvas, root, x, y, dw, var, options, callback):
    """模拟下拉框"""
    import tkinter as tk
    val = var.get()
    draw_rounded_rect(canvas, x, y, x + dw, y + 26, 4,
                      fill=THEME["input_bg"], outline=THEME["border"])
    t = canvas.create_text(x + 8, y + 13, text=val, fill=THEME["text"],
                           anchor="w", font=("Microsoft YaHei", 9))
    arrow = canvas.create_text(x + dw - 10, y + 13, text="▼", fill=THEME["text_dim"],
                               font=("Microsoft YaHei", 8))

    def on_click(e):
        menu = tk.Menu(root, tearoff=0, bg=THEME["surface"],
                       fg=THEME["text"], activebackground=THEME["primary"])
        for opt in options:
            menu.add_command(label=opt, command=lambda o=opt: [var.set(o), callback()])
        menu.post(root.winfo_pointerx(), root.winfo_pointery())

    canvas.tag_bind(t, "<Button-1>", on_click)
    canvas.tag_bind(arrow, "<Button-1>", on_click)


def draw_slider(canvas, x, y, sw, var, vmin, vmax, callback):
    """模拟滑块 — 点击不同位置设置值"""
    steps = vmax - vmin + 1
    step_w = sw / (steps - 1) if steps > 1 else sw
    cur = var.get()
    cur_x = x + (cur - vmin) / max(1, vmax - vmin) * sw

    canvas.create_line(x, y, x + sw, y, fill=THEME["border"], width=2)
    for i in range(steps):
        cx = x + i * step_w
        canvas.create_line(cx, y - 6, cx, y + 6, fill=THEME["border"], width=1)

    draw_rounded_rect(canvas, cur_x - 7, y - 10, cur_x + 7, y + 10, 3,
                      fill=THEME["primary"], outline="")

    def on_click(e):
        rel_x = max(0, min(sw, e.x - x))
        val = vmin + int(rel_x / sw * (vmax - vmin) + 0.5)
        val = max(vmin, min(vmax, val))
        var.set(val)
        callback()

    hit = canvas.create_rectangle(x - 5, y - 14, x + sw + 5, y + 14, fill="", outline="")
    canvas.tag_bind(hit, "<Button-1>", on_click)


def draw_entry(canvas, root, x, y, ew, var, placeholder=""):
    """模拟输入框，点击弹出对话框"""
    import tkinter as tk
    draw_rounded_rect(canvas, x, y, x + ew, y + 26, 4,
                      fill=THEME["input_bg"], outline=THEME["border"])
    val = var.get() or placeholder
    display_val = val if len(val) <= 28 else val[:25] + "..."
    color = THEME["text_dim"] if not var.get() else THEME["text"]
    t = canvas.create_text(x + 8, y + 13, text=display_val, fill=color,
                           anchor="w", font=("Microsoft YaHei", 9))

    def on_click(e):
        dlg = tk.Toplevel(root)
        dlg.title("输入密码")
        dlg.geometry("360x120")
        dlg.configure(bg=THEME["bg"])
        dlg.transient(root)
        dlg.grab_set()
        tk.Label(dlg, text="输入 AES 密钥密码（可选）:", bg=THEME["bg"],
                 fg=THEME["text"], font=("Microsoft YaHei", 9)).pack(pady=(15, 5))
        entry = tk.Entry(dlg, show="*", bg=THEME["input_bg"],
                         fg=THEME["text"], insertbackground=THEME["text"],
                         font=("Microsoft YaHei", 11), width=35)
        entry.pack(pady=5)
        entry.insert(0, var.get())
        entry.focus_set()

        def confirm():
            var.set(entry.get())
            dlg.destroy()

        tk.Button(dlg, text="确认", command=confirm,
                  bg=THEME["primary"], fg="#fff",
                  font=("Microsoft YaHei", 9)).pack(pady=5)
        dlg.bind("<Return>", lambda e: confirm())

    canvas.tag_bind(t, "<Button-1>", on_click)


def draw_checkbox(canvas, y, var, text, callback, x=None):
    cx = x if x is not None else 24
    checked = var.get()
    fill = THEME["primary"] if checked else THEME["input_bg"]
    draw_rounded_rect(canvas, cx, y + 1, cx + 18, y + 19, 3,
                      fill=fill, outline=THEME["border"])
    if checked:
        canvas.create_text(cx + 9, y + 10, text="✓", fill="#fff",
                           font=("Microsoft YaHei", 10, "bold"))
    t = canvas.create_text(cx + 24, y + 10, text=text, fill=THEME["text_dim"],
                           anchor="w", font=("Microsoft YaHei", 9))

    def toggle(e):
        var.set(not var.get())
        callback()

    canvas.tag_bind(t, "<Button-1>", toggle)
    hit = canvas.create_rectangle(cx, y, cx + 18, y + 20, fill="", outline="")
    canvas.tag_bind(hit, "<Button-1>", toggle)


def draw_progress(canvas, progress_y, progress_w, val):
    """更新进度条"""
    if progress_w <= 0:
        return
    canvas.create_rectangle(25, progress_y, 25 + progress_w, progress_y + 14,
                             fill=THEME["surface"], outline=THEME["border"])
    fill_w = int(progress_w * val / 100)
    draw_rounded_rect(canvas, 25, progress_y, 25 + fill_w, progress_y + 14, 4,
                      fill=THEME["primary"], outline="")
    canvas.create_text(25 + progress_w // 2, progress_y + 7,
                       text=f"{val}%", fill=THEME["text"],
                       font=("Microsoft YaHei", 8, "bold"))
