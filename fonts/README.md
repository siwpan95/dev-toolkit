# fonts

中文字体资源库 + 字体复制工具 —— 本地中文字体库（TTF/TTC/OTF 数百个）与一个 Tkinter 字体浏览/复制工具。

## 语言 / 类型
- Python（Tkinter GUI 工具）+ 字体资源数据

## 目录要点
- `font_downloader.py` —— Tkinter 中文字体复制工具（浏览本地源目录、选择并复制字体）
- `font_downloader2.py` —— 增强版字体工具（带下载器与并发下载，`requirements.txt` 的依赖是给它的）
- `本地/` —— 本地字体库（约 382 个字体文件：TTF/TTC/OTF）｜**不入库**（体积大）
- `etc/` —— 字体压缩包（99 个 .zip）；`download_fonts/` —— 下载缓存目录｜**不入库**
- `run.bat` —— 启动脚本；`.font_downloader_config.json` —— 工具配置

## 运行方式与依赖
- 运行：`run.bat`（等价于 `python font_downloader.py`）。
- GUI 工具本体只用 tkinter 标准库；`font_downloader2.py` 的下载器需 `requirements.txt`
  里的 `beautifulsoup4` / `curl_cffi` / `requests`。
- 本仓自带 `.venv`（不入库）。其基准解释器随机器迁移过，本机现为 `G:\Python314`。

## 仓库说明
- 本仓只入库**工具代码**；字体本体与压缩包是本地资源池，体积大且可重新下载，故由 `.gitignore` 排除。
- 2026-10-26 由 `G:\assets\fonts` 迁入 `G:\repos\fonts`（合并同类项：此前它不在 allin 治理范围内，
  registry 条目 `fonts` 的 `path: assets/fonts` 又解析到 `G:\allin\assets\fonts`，属**根错配**，
  导致 `check:repos` 长期报「path 不存在」）。现 `path: repos/fonts` 为真，并已建仓发布到
  `siwpan/fonts`。

## 测试状态
- `py_compile` 语法检查通过（2 个 .py 文件）。
- GUI 程序，仅编译未运行；字体资源为数据文件，不参与运行。
