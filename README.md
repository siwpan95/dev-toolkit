# pdf

> 仓库：<https://gitee.com/siwpan/pdf> ｜ 许可：MIT（见 [LICENSE](LICENSE)）
> 注：文中 <PATH> 为路径占位符，请替换为你本机实际的目录 / 可执行文件路径。

简易 PDF 阅读器 —— 基于 PyMuPDF 与 Pillow 的 Tkinter 桌面 PDF 阅读器，附若干物理教材 PDF 样本。
独立仓 siwpan/pdf（本地 `<PATH>`）。

## 语言 / 类型
- Python（Tkinter GUI）

## 目录要点
- `main.py` —— GUI 入口（打开 PDF、翻页、缩放显示）
- `title/` —— 示例 PDF（朗道理论物理教程等 11 本）
- `requirements.txt` —— 依赖声明

## 运行方式与依赖
- 运行：`python main.py`
- 依赖：`PyMuPDF`（fitz）、`Pillow`。

## 测试状态
- `py_compile` 语法检查通过（1 个 .py 文件）。
- GUI 程序（需 PyMuPDF），本次仅编译未运行。

## 发布面与许可

- gitee：siwpan/pdf，release `v1.0.0`（Windows 可执行程序，PyInstaller）。
- 许可：MIT · Copyright (c) 2026 siwpan
