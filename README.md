# 远子学姐的三题故事 · 提词器

一个为「三题故事」而生的提词器。给定三个词语为题，限时写成美妙的故事——就像《文学少女》（野村美月）里远子学姐每天给心叶出的题目一样。

> 三个词语为题，写出美妙的故事。

## 关于「三题故事」

在《文学少女》中，远子学姐（天野远子）会以三个词语为题，要求心叶在限定时间内写出一段故事，随后「吃」掉稿纸作出点评。本工具把这一玩法数字化：自动从词语池抽题、全屏滚动播放、可调速度与字号，帮助你专注于写作本身。

## 功能特性

- **自动出题**：从 A / B / C 三档词语池各随机抽取 1 个词，组成「三题」。
  - A 档：1–2 字（如「云」「雪」「血柱」）
  - B 档：3–4 字（如「竹叶船」「草莓大福」）
  - C 档：5 字以上（如「艾菲尔铁塔」「鲱鱼原意大利面」）
- **多来源词库**：内置三套词源 —— 文学少女原作（101 条）+ 通用词表（6157 条，清华 THUOCL）+ 梗百科精选（1622 条），合计 7880 条。顶栏可勾选参与出题的词源。
- **全屏提词**：黑底白字、大字号、平滑滚动，适合作为提词 / 灵感墙。
- **播放控制**：开始 / 暂停 / 重置，进度条实时显示。
- **可调参数**：滚动速度、正文字号实时调节。
- **镜像模式**：一键水平翻转，便于配合提词反光板使用。
- **离线内容**：内置词库 + 手动粘贴。正文区域可自由编辑，随时粘贴你自己的题目或故事。
- **双形态**：Electron 桌面全屏窗口（主），亦可纯网页运行（备选）。

## 目录结构

```
santi-teleprompter/
├── cordis.yml              # 运行配置（端口、默认速度/字号、镜像）
├── package.json            # 依赖与脚本
├── pools/                  # 词语池（按字数分档，每档三源标签）
│   ├── readme.md           # 词库结构与构建说明
│   ├── title_A/words.json  # 1–2 字
│   ├── title_B/words.json  # 3–4 字
│   └── title_C/words.json  # 5 字以上
├── scripts/                # 词库抓取与重建脚本（见 pools/readme.md）
│   ├── scrape_gengbaike.py     # 抓梗百科原始词条
│   ├── filter_gengbaike.py     # 过滤敏感/低质词条
│   ├── fetch_general_words.py  # 抓 THUOCL 开源词表
│   ├── build_pools.py          # 合并三源，写入 pools/title_*/words.json
│   └── data/                   # 中间产物（gitignore）
├── public/                 # 前端（原生 HTML/CSS/JS）
│   ├── index.html
│   ├── style.css
│   └── app.js
└── src/                    # 后端（cordis 服务 + Electron 入口）
    ├── index.js            # cordis 启动 / 网页版入口
    ├── topics.js           # 词语池加载与随机出题服务
    ├── plugin-server.js    # HTTP 服务与静态托管
    ├── config.js           # 读取 cordis.yml
    └── electron-main.js    # Electron 主进程（全屏窗口）
```

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` `/style.css` `/app.js` | 静态资源 |
| GET | `/api/topics/random?sources=a,b` | 从 A/B/C 各抽 1 词组成三题；可选 `sources` 过滤词源（缺省 = 全部） |
| GET | `/api/pools` | 各档词条总数（兼容旧接口） |
| GET | `/api/sources` | 词源清单 + 标签 + 各档按来源的词条数 |
| GET | `/api/config` | `cordis.yml` 中的前端默认值 |

## 快速开始

### 环境要求

- Node.js ≥ 22
- npm

### 安装依赖

```bash
npm install
```

> 说明：`electron` 二进制体积较大。若官方源下载缓慢，可设置国内镜像后安装：
> ```bash
> ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/ npm install
> # 若 npm 跳过 postinstall，手动执行：
> node node_modules/electron/install.js
> ```

### 运行

**桌面版（Electron 全屏窗口，推荐）：**

```bash
npm start
```

**网页版（备选，本地无界面外壳）：**

```bash
npm run web
# 浏览器打开 http://localhost:8787
```

## 使用说明

| 操作 | 说明 |
| --- | --- |
| 远子出题 | 从 A/B/C 三档各抽一词，刷新三题 |
| 词源 | 顶栏勾选参与出题的词源（文学少女 / 通用词表 / 梗百科） |
| 开始 / 暂停 | 启动或暂停滚动 |
| 重置 | 回到顶部 |
| 全屏 | 切换全屏 |
| 速度 / 字号 | 实时调节滚动速度与正文字号 |
| 镜像 | 水平翻转（配合反光板） |
| 正文区 | `contenteditable`，可粘贴自定义题目或故事 |

**快捷键：** `空格` 播放/暂停 · `↑/↓` 调速 · `M` 镜像 · `N` 重新出题。

## 发行版（Windows）

提供三种发行方式，按需选用：

| 方式 | 文件 | 体积 | 适用场景 |
| --- | --- | --- | --- |
| **NSIS 安装程序**（推荐） | `SantiTeleprompter-Setup-1.1.0.exe` | 约 73 MB | 标准安装流程，带卸载项与开始菜单/桌面快捷方式 |
| **单文件便携版** | `SantiTeleprompter-1.1.0-portable.exe` | 约 67 MB | 单个 exe，免解压直接运行 |
| **便携压缩包** | `SantiTeleprompter-1.1.0-portable-win-x64.7z` | 约 74 MB | 免安装，解压即用（含完整 Electron 运行时） |

> 三类安装包均内置 **v1.1.0 词库（7880 词，三源混合）**。下载后可对照同目录
> `SantiTeleprompter-1.1.0.sha256.txt` 校验完整性。

### 方式一：NSIS 安装程序（推荐，electron-builder）

标准 Windows 安装向导，自动创建开始菜单与桌面快捷方式，支持自定义安装目录：

1. 前往 [Releases](https://gitee.com/siwpan/santi-teleprompter/releases) 下载
   `SantiTeleprompter-Setup-1.1.0.exe`
2. 双击运行，按向导完成安装
3. 从开始菜单或桌面快捷方式启动

卸载可通过「设置 → 应用」或安装目录下的 `Uninstall 远子学姐的三题故事提词器.exe`。

### 方式二：单文件便携版（electron-builder）

单个 exe，免解压、免安装，双击即运行（数据写入用户目录，不污染系统）：

1. 前往 [Releases](https://gitee.com/siwpan/santi-teleprompter/releases) 下载
   `SantiTeleprompter-1.1.0-portable.exe`
2. 双击运行即可

### 方式三：便携压缩包（零下载依赖）

无需安装、无需联网，解压即用：

```
SantiTeleprompter-1.1.0-portable-win-x64.7z
└── SantiTeleprompter/
    ├── 启动提词器.bat          # 双击即可启动
    ├── 使用说明.txt
    ├── SantiTeleprompter.exe   # 主程序（Electron 运行时，已内置）
    └── resources/app/          # 应用代码 + 词库 + 运行时依赖
```

**下载与使用：**

1. 前往 [Releases](https://gitee.com/siwpan/santi-teleprompter/releases) 下载
   `SantiTeleprompter-1.1.0-portable-win-x64.7z`
2. 用 7-Zip / WinRAR / Bandizip 解压（单卷，直接解压）
3. 进入 `SantiTeleprompter` 目录，双击 `启动提词器.bat`（或 `SantiTeleprompter.exe`）

> 可对照 `SantiTeleprompter-1.1.0.sha256.txt` 校验下载完整性。

### 自行构建发行版

**构建 NSIS 安装程序与单文件便携版（electron-builder）：**

```bash
ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/ npm install
npm run dist          # 同时产出 nsis + portable
# 或仅构建其一：
npm run dist:nsis     # SantiTeleprompter-Setup-1.1.0.exe
npm run dist:portable # SantiTeleprompter-1.1.0-portable.exe
```

产物输出至 `release/`：

```
release/
├── SantiTeleprompter-Setup-1.1.0.exe      # NSIS 安装程序
├── SantiTeleprompter-Setup-1.1.0.exe.blockmap
└── SantiTeleprompter-1.1.0-portable.exe   # 单文件便携版
```

**构建便携压缩包（零额外依赖）：**

```bash
# 1) 安装依赖（含 electron 二进制，建议国内镜像）
ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/ npm install

# 2) 将 node_modules/electron/dist 复制为便携目录，
#    并在其 resources/app/ 下放入 public、src、pools、cordis.yml
#    与运行时依赖（cordis、yaml、cosmokit、@standard-schema/spec）
#    产物目录：build/SantiTeleprompter/

# 3) 用 7-Zip 打包为单卷
7za a -t7z -mx=5 dist/SantiTeleprompter-1.1.0-portable-win-x64.7z build/SantiTeleprompter
```

**构建说明与已知约束：**

- `package.json` 的 `build.win.signAndEditExecutable` 设为 `false`：跳过 rcedit 重写 exe 版本信息。
  该步骤仅影响 exe 的「属性 → 详细信息」展示，不影响功能；在部分 Windows 环境下 rcedit
  会因文件瞬时占用而报 `Unable to commit changes`，关闭后可稳定构建。
- 首次构建会下载 `winCodeSign`、`nsis`、`nis-resources` 等二进制工具包（约 7.6 MB）。
  若官方源缓慢，可设 `ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/`。
- `winCodeSign` 包含两条 macOS 符号链接（`libcrypto.dylib`、`libssl.dylib`）。
  在无符号链接权限的 Windows 上，7-Zip 解压会报「客户端没有所需的特权」并以 exit 2 结束，
  导致 electron-builder 中止。**这些文件与 Windows 构建无关**，解决办法是让 7-Zip 跳过它们：

  ```bash
  # 7zip-bin 支持环境变量切换到系统 PATH 中的 7za（7zip-bin/index.js）
  export USE_SYSTEM_7ZA=true
  # 并在 PATH 前置一个包装脚本，拦截 winCodeSign 解压并追加排除参数：
  #   -x!darwin\10.12\lib\libcrypto.dylib
  #   -x!darwin\10.12\lib\libssl.dylib
  ```

- 两个目标（nsis / portable）共用同一个 `release/win-unpacked` 目录。
  若在同一命令中连续构建，建议先移出旧的 `win-unpacked`，
  或分两次调用 `npm run dist:nsis` / `npm run dist:portable`，
  以确保 exe 元数据步骤从干净状态开始。
- **portable 目标会从已存在的同名 exe 读取版本号用于命名**：重建前请先删除旧的
  `SantiTeleprompter-*-portable.exe`，否则新包会被错误命名为旧版本号。

## 技术栈

- **[cordis](https://github.com/cordiverse/cordis)** `4.0.0-rc.8` — 插件化运行时，承载出题服务与 HTTP 服务。
- **Electron** `30.x` — 桌面全屏外壳。
- **原生前端** — 无框架，`requestAnimationFrame` 驱动滚动，零额外依赖。

## 许可证

[MIT License](./LICENSE) · Copyright (c) 2026 siwpan

## 仓库约定

本仓库遵循 Gitee 推荐的最小仓库规范，包含三件套：

- `README.md`（本文件）
- `LICENSE`（MIT）
- `.gitignore`

词库内容来自三套来源：原作《文学少女》「三题故事」的人工整理、清华大学 THUOCL 开放中文词库、以及 [梗百科 gengbaike.cn](https://gengbaike.cn) 的精选流行语。
抓取与重建脚本位于 `scripts/`，详见 [`pools/readme.md`](./pools/readme.md)。
通用词表替代了《现代汉语词典》《辞海》（二者正文受版权保护不可分发），THUOCL 是许可更宽松的同类开源替代。
