# print

中文拼音输入法 —— 基于本地字典与字体、用 Python 实现的拼音输入法（tkinter 候选窗口 + 全局键盘监听）。

## 语言 / 类型
- Python（Tkinter UI + pynput 全局键盘钩子）+ 大量中文字典数据

## 目录要点
- `main.py` —— 入口；`ime_core.py` —— 输入法核心引擎（状态机）
- `pinyin_syllables.py` / `pinyin_dict.py` / `pinyin_parser.py` —— 音节表、字典索引、音节分割与候选生成
- `user_dict.py` / `user_dict.json` —— 用户词典（学习功能）
- `ime_ui.py` —— 候选窗口 UI；`keyboard_handler.py` —— 全局键盘监听
- `config.py` —— 配置；`dictionary/` —— 中文字典数据（chinese-dictionary、CC-CEDICT、chinese-poetry 等）
- `本地/` —— 本地字体；`cache/` —— 缓存

## 运行方式与依赖
- 运行：`F:\Python314\python.exe main.py`（右 Shift 切换中英文，输入拼音后数字/空格选词）。
- 依赖：`pynput`、`pyperclip`。详见 `requirements.txt`。

## 测试状态
- `py_compile` 语法检查：项目自身代码通过；`dictionary/MakeMeAHanzi/.../stats.py` 为第三方字典附带的 Python 2 脚本，语法不兼容 Python 3（非本工具代码）。
- 需全局键盘钩子 + 桌面交互，本次仅编译未运行。
