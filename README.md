# 字幕工具（subtitle）

> 仓库：<https://gitee.com/siwpan/subtitle> ｜ 许可：MIT（见 [LICENSE](LICENSE)）
> 注：文中 <PATH> 为路径占位符，请替换为你本机实际的目录 / 可执行文件路径。

一个自包含的桌面字幕处理工具，基于 Tkinter + ffmpeg。面向中文用户，提供字幕提取、编辑、保存、烧录与翻译占位能力。

> **铁律 / 自包含说明**：本工具位于 `<PATH>`（独立仓 siwpan/subtitle），独立运行，**不 import 其他工具目录、不引入中心化共享核**。所有逻辑复制在自身目录内。

## 功能

1. **提取字幕**：从视频中提取第一条字幕流（`ffmpeg -map 0:s:0`）。若视频无字幕流，会给出友好提示而非崩溃。
2. **打开 / 编辑 / 保存 .srt**：在文本区按条目显示「序号 → 时间码 → 文本」，可直接编辑；保存时自动规范化（parse → serialize 往返）。
3. **烧录字幕**：使用 ffmpeg `subtitles` 滤镜将字幕**硬编码**进视频画面。
4. **翻译占位**：预留 `translate_hook(texts)` 函数，默认原样返回，注释中说明如何接入翻译 API，**不强制联网**。

## 文件结构

```
<PATH>
├── main.py            # Tkinter GUI 入口（仅 __main__ 守卫内创建 Tk）
├── core.py            # 纯逻辑 + ffmpeg 封装 + 参数拼接
├── requirements.txt   # 依赖说明（运行时需系统安装 ffmpeg）
├── README.md          # 本文件
└── test_smoke.py      # 冒烟测试（纯逻辑 + 参数拼接）
```

## 核心函数（core.py）

| 函数 | 说明 |
| --- | --- |
| `ffmpeg_path()` | 返回系统 ffmpeg 路径，未找到返回 `None` |
| `parse_srt(text)` | 解析 SRT 文本 → `list[{index, start, end, text}]` |
| `serialize_srt(blocks)` | 将条目列表序列化回标准 SRT 文本 |
| `extract_subtitles(video, out_srt)` | 提取字幕流，返回 `(ok, msg)` |
| `burn_subtitles(video, srt, out_video)` | 烧录字幕，返回 `(ok, msg)` |
| `translate_hook(texts)` | 翻译占位，默认原样返回 |
| `build_extract_args(...)` / `build_burn_args(...)` | **纯逻辑**拼接 ffmpeg 参数，便于测试 |

## 运行方式

### 1. 前提：安装 ffmpeg
本工具在「提取 / 烧录」时需要系统 ffmpeg。请下载并加入系统 PATH，或确保 `shutil.which("ffmpeg")` 能找到。

### 2. 启动 GUI
```bash
python <PATH>
```
> 注意：无显示器（headless）环境不要直接运行 GUI；请改用下方冒烟测试验证纯逻辑。

### 3. 冒烟测试（无需 ffmpeg / 无显示器）
```bash
python <PATH>
```
测试内容：
- 导入 `core`；
- `parse_srt` / `serialize_srt` 往返一致性（造一段 SRT，解析再序列化，比对条目数与文本）；
- ffmpeg 相关**仅测参数拼接**（`build_extract_args` / `build_burn_args`），不实际执行 ffmpeg。

## 已知限制

- **依赖 ffmpeg**：提取与烧录功能需系统安装 ffmpeg；未安装时这两个按钮会提示并安全退出，纯编辑/保存功能不受影响。
- **仅提取第一条字幕流**（`0:s:0`）：多语言多字幕流场景暂未提供选择界面。
- **翻译为占位实现**：`translate_hook` 默认原样返回，需自行接入翻译 API 才能实际翻译。
- **烧录性能**：硬编码字幕需重新编码，耗时与视频时长成正比；大文件请耐心等待（UI 在烧录前会刷新状态栏）。
- **SRT 专用**：当前仅支持 `.srt` 格式解析与写入，不支持 `.ass` / `.vtt` 等。
- **无显示器环境**：不可实例化 `Tk()`；GUI 仅在 `__main__` 守卫内启动。
