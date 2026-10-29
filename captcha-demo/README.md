# captcha_demo（人机验证演示系统）

基于 tkinter 的人机验证（验证码）演示系统，采用 MVVM 架构，使用 tkinter Canvas 绘制界面，覆盖 6 类验证码识别交互。

## 语言 / 类型
- 类型：Python 桌面 GUI 程序（tkinter，MVVM 架构）
- 语言：Python 3

## 目录要点
- `main.py` —— 程序入口（`python main.py`）
- `config/` —— 配置（captcha_config.json）
- `model/` —— 数据模型（Model）
- `viewmodel/` —— 业务逻辑（ViewModel）
- `view/` —— 界面（tkinter Canvas 绘制，View）
- `fix_docstrings.py` —— 文档字符串修复小工具

覆盖的验证码类型：文字、滑块、拼图、点击、旋转、拖拽排序。

## 运行方式与依赖
- 运行：`python main.py`（需图形界面环境）
- 依赖：仅 Python 标准库（tkinter），无第三方依赖

## 测试状态
- py_compile 语法检查通过（13/13 文件）；GUI 程序按规范未运行。
