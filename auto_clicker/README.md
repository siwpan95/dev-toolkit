# 鼠标连点器 (auto_clicker)

> 仓库：<https://gitee.com/siwpan/auto_clicker> ｜ 许可：MIT（见 [LICENSE](LICENSE)）

一个用 Python 写的 GUI 鼠标连点器。**已做模块化拆分**，点击引擎、热键、界面各司其职，方便维护和二次开发。

## 功能

- **点击频率**：间隔(毫秒级) + 随机抖动(±毫秒)，让点击不规律、规避反作弊检测
- **鼠标按键**：左键 / 右键 / 中键
- **点击类型**：单击 / 双击
- **点击位置**：当前光标位置 / 固定坐标（支持「拾取坐标」，3 秒后取鼠标位置）
- **重复**：无限 / 指定次数（到点自动停）
- **启动前延迟**：防误触保护，给手挪开鼠标的时间
- **热键**：自定义 开始/停止 热键（默认空格），`Esc` 永远紧急停止
- **设置自动保存**：关掉再开，上次配置还在（`settings.json`）
- **安全底线**：保留 pyautogui 的 FAILSAFE，鼠标甩到屏幕四角即紧急中止

## 目录结构

```
auto_clicker/
├── main.py / main.pyw    # 入口（main.pyw 无控制台）
├── core/
│   ├── config.py         # 配置默认值 + JSON 加载/保存
│   └── clicker.py        # ClickEngine：纯逻辑点击引擎（可独立测试）
├── input/
│   └── hotkeys.py        # HotkeyManager：全局热键（含降级提示）
└── ui/
    └── app.py            # AutoClickerApp：tkinter 界面
```

## 快速开始

```bash
pip install pyautogui keyboard
python main.pyw          # 日常使用（无黑框）
# 或 python main.py      # 带控制台，方便看报错
```

打包成 exe（可选）：

```bash
pip install pyinstaller
pyinstaller -w -F main.pyw
```

## 重要：Windows 权限

- 全局热键依赖 `keyboard` 安装系统级钩子。**若未用管理员权限运行**，会注册失败（现象：`⚠ 全局热键注册失败`）。
  - 解决：右键「以管理员身份运行」启动；或只用界面上的「开始/停止」按钮。
- 若目标程序（游戏/软件）本身以**管理员**运行，连点器也得用管理员跑，否则输入会被系统的 UIPI 隔离拦截（"发了但没反应"）。
- macOS 需在「系统设置 → 隐私与安全性 → 辅助功能」里给终端/IDE 授权。

## 依赖

- Python >= 3.8
- pyautogui, keyboard（第三方）；tkinter（标准库）
