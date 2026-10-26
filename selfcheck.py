#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pdf 无头自检（headless self-check）。

验证点（不打开任何窗口）：
  1. GUI 入口 main.py 可在无窗口环境导入，且导入时不创建 Tk 根窗口；
  2. 渲染管线数据往返：fitz 渲染页 -> PPM 字节流 -> PIL 解码，尺寸一致；
     再经 PNG 编码/解码后尺寸仍一致；
  3. 翻页状态推进：next_page / prev_page 的首末页边界（第 1 页不再前翻、
     末页不再后翻），即 main.PDFReader 的真实方法；
  4. 缩放生效：apply_zoom 后渲染像素按倍率变化；非法缩放（<=0）夹到 0.1。

约束：只用标准库 + 项目既有依赖（PyMuPDF / Pillow，见 requirements.txt），
不新增依赖、不联网、不落盘。GUI 控件在本进程内用最小桩件替代，
主逻辑仍调用 main.PDFReader 的真实方法（无窗口、无 mainloop）。
"""
import io
import os
import sys
import time
import traceback


def _setup_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


class _StubLabel:
    """替代 tk.Label：仅记录文本。"""

    def __init__(self):
        self.text = ""

    def config(self, **kwargs):
        if "text" in kwargs:
            self.text = kwargs["text"]

    configure = config


class _StubCanvas:
    """替代 tk.Canvas：记录最后绘制的图像与滚动区域。"""

    def __init__(self):
        self.image = None
        self.scrollregion = None
        self.cleared = 0

    def delete(self, _tag):
        self.cleared += 1
        self.image = None

    def create_image(self, _x, _y, **kwargs):
        self.image = kwargs.get("image")

    def configure(self, **kwargs):
        if "scrollregion" in kwargs:
            self.scrollregion = kwargs["scrollregion"]


class _StubVar:
    """替代 tk.DoubleVar。"""

    def __init__(self, value=1.0):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class _StubPhotoImage:
    """替代 PIL.ImageTk.PhotoImage：不依赖 Tk，只保存图像尺寸。"""

    def __init__(self, image):
        self.image = image
        self.width = image.width
        self.height = image.height


def _make_reader(module, sample):
    """用桩件装配 main.PDFReader 实例（绕过 __init__ 里的控件创建）。

    sample 可以是文件路径，也可以是（兜底时）内存 PDF 字节流。
    """
    import fitz

    reader = module.PDFReader.__new__(module.PDFReader)
    if isinstance(sample, (bytes, bytearray)):
        reader.doc = fitz.open(stream=bytes(sample), filetype="pdf")
    else:
        reader.doc = fitz.open(sample)
    reader.current_page = 0
    reader.zoom = 1.0
    reader.zoom_var = _StubVar(1.0)
    reader.page_label = _StubLabel()
    reader.canvas = _StubCanvas()
    reader.img_tk = None
    return reader


def _pick_sample():
    """优先取 title/ 下最小的样例 PDF；缺失时用 fitz 现造 2 页文档。"""
    import fitz

    title_dir = os.path.join(BASE_DIR, "title")
    candidates = []
    if os.path.isdir(title_dir):
        for name in os.listdir(title_dir):
            if name.lower().endswith(".pdf"):
                full = os.path.join(title_dir, name)
                candidates.append((os.path.getsize(full), full))
    if candidates:
        candidates.sort()
        return candidates[0][1], True

    # 兜底：内存中生成一份两页 PDF（不落盘）
    doc = fitz.open()
    for i in range(2):
        page = doc.new_page(width=300, height=200)
        page.insert_text((40, 100), f"pdf selfcheck page {i + 1}")
    return doc.tobytes(), False


def run_checks():
    import fitz
    from PIL import Image

    import main

    checks = []

    # --- 1. 入口可无窗口导入 -------------------------------------------------
    import tkinter

    if tkinter._default_root is not None:
        raise RuntimeError("导入 main 时创建了 Tk 根窗口，入口不再是无头安全的")
    checks.append("入口 main.py 可无窗口导入（未创建 Tk 根窗口）")

    # 用桩件替换 ImageTk（真实 PhotoImage 需要 Tk），其余逻辑保持项目原样
    main.ImageTk = type("_ImageTkStub", (), {"PhotoImage": _StubPhotoImage})

    sample, from_repo = _pick_sample()
    reader = _make_reader(main, sample)
    total = len(reader.doc)
    if total < 1:
        raise RuntimeError("样例 PDF 页数为 0")

    # --- 2. 渲染 + PPM/PIL 数据往返 -----------------------------------------
    page = reader.doc.load_page(0)
    pix = page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0), alpha=False)

    reader.show_page()
    if reader.page_label.text != f"页码: 1/{total}":
        raise AssertionError(f"页标签错误: {reader.page_label.text!r}")
    first_img = reader.canvas.image.image
    if first_img.size != (pix.width, pix.height):
        raise AssertionError(f"渲染尺寸与页面不符: {first_img.size} vs {(pix.width, pix.height)}")
    if first_img.mode != "RGB":
        raise AssertionError(f"渲染图应为 RGB，实际 {first_img.mode}")

    # PPM -> PIL -> PNG -> PIL 往返，尺寸与像素数保持一致
    ppm = pix.tobytes("ppm")
    roundtrip = Image.open(io.BytesIO(ppm))
    if roundtrip.size != (pix.width, pix.height):
        raise AssertionError(f"PPM 往返尺寸不一致: {roundtrip.size} vs {(pix.width, pix.height)}")
    if len(roundtrip.tobytes()) != pix.width * pix.height * 3:
        raise AssertionError("PPM 往返像素数据长度不一致")
    buf = io.BytesIO()
    roundtrip.save(buf, format="PNG")
    buf.seek(0)
    if Image.open(buf).size != roundtrip.size:
        raise AssertionError("PNG 落盘格式往返尺寸不一致")
    checks.append(f"渲染管线往返：{pix.width}x{pix.height} 页 -> PPM -> PIL -> PNG 尺寸一致")

    # --- 3. 翻页状态推进与边界 ----------------------------------------------
    reader.current_page = 0
    reader.next_page()
    if reader.current_page != 1:
        raise AssertionError(f"next_page 未推进: {reader.current_page}")
    if reader.page_label.text != f"页码: 2/{total}":
        raise AssertionError(f"翻页后页标签错误: {reader.page_label.text!r}")

    reader.prev_page()
    if reader.current_page != 0:
        raise AssertionError(f"prev_page 未回退: {reader.current_page}")
    reader.prev_page()  # 已在首页，不应越界
    if reader.current_page != 0:
        raise AssertionError(f"首页 prev_page 越界: {reader.current_page}")

    reader.current_page = total - 1
    reader.show_page()
    reader.next_page()  # 已在末页，不应越界
    if reader.current_page != total - 1:
        raise AssertionError(f"末页 next_page 越界: {reader.current_page}")
    checks.append(f"翻页状态推进：首/末页边界正确（共 {total} 页，首页不再前翻、末页不再后翻）")

    # --- 4. 缩放生效与夹取 ---------------------------------------------------
    reader.current_page = 0
    reader.zoom = 1.0
    reader.zoom_var.set(1.0)
    reader.show_page()
    base_w, base_h = reader.canvas.image.width, reader.canvas.image.height

    reader.zoom_var.set(2.0)
    reader.apply_zoom()
    big_w, big_h = reader.canvas.image.width, reader.canvas.image.height
    if abs(big_w - 2 * base_w) > 2 or abs(big_h - 2 * base_h) > 2:
        raise AssertionError(f"2.0 倍缩放未生效: {base_w}x{base_h} -> {big_w}x{big_h}")

    reader.zoom_var.set(0.0)  # 非法缩放应被夹到 0.1
    reader.apply_zoom()
    if abs(reader.zoom - 0.1) > 1e-9:
        raise AssertionError(f"非法缩放未夹取: zoom={reader.zoom}")
    small_w = reader.canvas.image.width
    if not (0 < small_w < base_w):
        raise AssertionError(f"0.1 倍缩放渲染尺寸异常: {small_w}")
    checks.append(f"缩放生效：1.0x={base_w}x{base_h}，2.0x={big_w}x{big_h}，0 被夹为 0.1x={small_w}")

    reader.doc.close()
    return checks, from_repo


def main() -> int:
    _setup_stdout()
    started = time.time()
    try:
        checks, from_repo = run_checks()
    except Exception as exc:
        print(f"selfcheck FAIL: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1

    source = "title/ 样例 PDF" if from_repo else "内存生成的两页 PDF"
    print(f"selfcheck ok: pdf 无头核心逻辑（{source}，{', '.join(checks)}）"
          f" [{time.time() - started:.2f}s]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
