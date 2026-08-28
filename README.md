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
- `build_rime_freq.py` —— 构建 rime-ice 词频产物（候选排序数据源）
- `本地/` —— 本地字体；`cache/` —— 索引缓存

## 候选词频数据来源（借鉴记账）

候选排序使用 rime-ice 词库的真实词频（升级前为按词典顺序的启发式值）：

- 上游：[rime-ice](https://github.com/iDvel/rime-ice)（GPLv3）的 `cn_dicts/base.dict.yaml`、`ext.dict.yaml`；组成词库：华宇野风词库、THUOCL、现代汉语常用词表、腾讯词向量（上游多源合并去重、按「拼音顺序、权重逆序」调频）。
- 用法：词/成语候选按词频降序；rime 未收录的罕见词回退启发式垫底；print 词库之外的 rime 常用词（约 30 万条，权重 ≥100）并入候选。
- 生成：`python build_rime_freq.py`（自动探测 `G:\shurufa\full_compiled\cn_dicts`，或 `--src` 指定）→ `dictionary/rime_ice/{rime_freq.pkl, rime_words.pkl, SOURCE.txt}`；产物**不入版本库**，随安装包 datas 分发。
- 许可口径：程序本体 MIT；词频数据沿用 rime-ice 口径（GPLv3），随包 `dictionary/rime_ice/SOURCE.txt` 供溯源。

## 运行方式与依赖
- 运行：`F:\Python314\python.exe main.py`（右 Shift 切换中英文，输入拼音后数字/空格选词）。
- 依赖：`pynput`、`pyperclip`。详见 `requirements.txt`。

## 测试状态
- `py_compile` 语法检查：项目自身代码通过；`dictionary/MakeMeAHanzi/.../stats.py` 为第三方字典附带的 Python 2 脚本，语法不兼容 Python 3（非本工具代码）。
- 需全局键盘钩子 + 桌面交互，本次仅编译未运行。
