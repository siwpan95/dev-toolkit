import tkinter as tk
from tkinter import filedialog, ttk
import fitz  # PyMuPDF
from PIL import Image, ImageTk
import io

class PDFReader:
    def __init__(self, root):
        self.root = root
        self.root.title("简易 PDF 阅读器")
        self.root.geometry("900x700")

        # PDF 相关变量
        self.doc = None          # fitz.Document
        self.current_page = 0    # 当前页码（从0开始）
        self.zoom = 1.0          # 缩放倍数
        self.img_tk = None       # 当前显示的 PhotoImage

        # ---------- 工具栏 ----------
        toolbar = tk.Frame(root, bd=1, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        btn_open = tk.Button(toolbar, text="打开PDF", command=self.open_pdf)
        btn_open.pack(side=tk.LEFT, padx=2, pady=2)

        btn_prev = tk.Button(toolbar, text="上一页", command=self.prev_page)
        btn_prev.pack(side=tk.LEFT, padx=2, pady=2)

        btn_next = tk.Button(toolbar, text="下一页", command=self.next_page)
        btn_next.pack(side=tk.LEFT, padx=2, pady=2)

        tk.Label(toolbar, text="缩放:").pack(side=tk.LEFT, padx=(10,0))
        self.zoom_var = tk.DoubleVar(value=1.0)
        zoom_spin = ttk.Spinbox(toolbar, from_=0.1, to=5.0, increment=0.1,
                                textvariable=self.zoom_var, width=5,
                                command=self.apply_zoom)
        zoom_spin.pack(side=tk.LEFT, padx=2)
        zoom_spin.bind("<Return>", lambda e: self.apply_zoom())

        self.page_label = tk.Label(toolbar, text="页码: ")
        self.page_label.pack(side=tk.LEFT, padx=10)

        # ---------- 主显示区域（带滚动条） ----------
        main_frame = tk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(main_frame, bg='gray')
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        v_scroll = tk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll = tk.Scrollbar(root, orient=tk.HORIZONTAL, command=self.canvas.xview)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        # 鼠标滚轮翻页 / 滚动
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)       # Windows
        self.canvas.bind("<Button-4>", self.on_mouse_wheel_up)     # Linux 向上
        self.canvas.bind("<Button-5>", self.on_mouse_wheel_down)   # Linux 向下

        # 键盘翻页
        self.root.bind("<Left>", lambda e: self.prev_page())
        self.root.bind("<Right>", lambda e: self.next_page())

    # ---------- 核心功能 ----------
    def open_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not file_path:
            return
        self.doc = fitz.open(file_path)
        self.current_page = 0
        self.zoom = 1.0
        self.zoom_var.set(1.0)
        self.show_page()

    def show_page(self):
        """渲染当前页面并显示到 Canvas"""
        if self.doc is None:
            return
        total = len(self.doc)
        if total == 0:
            return
        self.page_label.config(text=f"页码: {self.current_page+1}/{total}")

        # 渲染 PDF 页面为图像
        page = self.doc.load_page(self.current_page)
        mat = fitz.Matrix(self.zoom, self.zoom)  # 缩放矩阵
        pix = page.get_pixmap(matrix=mat, alpha=False)

        # 转为 PIL Image
        img = Image.open(io.BytesIO(pix.tobytes("ppm")))
        self.img_tk = ImageTk.PhotoImage(img)

        # 更新 Canvas
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.img_tk)
        self.canvas.configure(scrollregion=(0, 0, img.width, img.height))

    def apply_zoom(self):
        try:
            z = self.zoom_var.get()
            if z <= 0:
                z = 0.1
            self.zoom = z
        except:
            pass
        self.show_page()

    def next_page(self):
        if self.doc and self.current_page < len(self.doc) - 1:
            self.current_page += 1
            self.show_page()

    def prev_page(self):
        if self.doc and self.current_page > 0:
            self.current_page -= 1
            self.show_page()

    # 鼠标滚轮支持（Windows / Linux 两种事件）
    def on_mouse_wheel(self, event):
        """Windows 滚轮: 向上翻页(Delta>0)，向下翻页(Delta<0)"""
        if event.delta > 0:
            self.prev_page()
        else:
            self.next_page()

    def on_mouse_wheel_up(self, event):
        self.prev_page()

    def on_mouse_wheel_down(self, event):
        self.next_page()


if __name__ == "__main__":
    root = tk.Tk()
    app = PDFReader(root)
    root.mainloop()