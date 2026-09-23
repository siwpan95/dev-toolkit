# Yasuo — 通用文件加密/压缩工具

> 仓库：<https://gitee.com/siwpan/yasuo> ｜ 许可：MIT（见 [LICENSE](LICENSE)）

全功能文件加密与压缩工具，支持对称加密和无损压缩。

## 功能

- **无损压缩** — zlib / lzma / bz2 三种算法
- **对称加密** — AES-256-GCM / AES-256-CBC，密钥派生 + SHA256 完整性校验
- **压缩对比** — 内置算法对比工具，选择最优方案
- **压缩炸弹** — 高压缩率打包功能
- **GUI 界面** — Tkinter 可视化操作
- **命令行支持** — `python -m yasuo`

## 快速开始

```bash
# 安装依赖
pip install pycryptodome

# GUI 模式
python yasuo.py

# CLI 模式
python -m yasuo
```

## 项目结构

```
yasuo/
├── yasuo.py              # 顶层入口脚本
├── yasuo/                # Python 包
│   ├── __init__.py       # 包导出
│   ├── __main__.py       # python -m yasuo 入口
│   ├── config.py         # 配置类
│   ├── crypto_core.py    # 加密核心 (AESCipher, 密钥生成, SHA256)
│   ├── compress_core.py  # 压缩核心 (zlib/lzma/bz2)
│   ├── pipeline.py       # 处理流水线
│   ├── compare.py        # 压缩算法对比
│   ├── utils.py          # 工具函数
│   ├── gui_app.py        # GUI 主程序
│   └── gui_widgets.py    # GUI 组件
```

## 依赖

- Python >= 3.8
- pycryptodome (AES)
- 标准库: zlib, lzma, bz2, hashlib, secrets, tkinter
