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
├── pools/                  # 词语池（按字数分档）
│   ├── title_A/words.json  # 1–2 字
│   ├── title_B/words.json  # 3–4 字
│   └── title_C/words.json  # 5 字以上
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
| 开始 / 暂停 | 启动或暂停滚动 |
| 重置 | 回到顶部 |
| 全屏 | 切换全屏 |
| 速度 / 字号 | 实时调节滚动速度与正文字号 |
| 镜像 | 水平翻转（配合反光板） |
| 正文区 | `contenteditable`，可粘贴自定义题目或故事 |

**快捷键：** `空格` 播放/暂停 · `↑/↓` 调速 · `M` 镜像 · `N` 重新出题。

## 发行版（Windows 便携版）

发行版以 **便携压缩包** 形式提供，无需安装、无需联网，解压即用：

```
SantiTeleprompter-1.0.0-portable-win-x64.7z.001
└── SantiTeleprompter/
    ├── 启动提词器.bat          # 双击即可启动
    ├── 使用说明.txt
    ├── SantiTeleprompter.exe   # 主程序（Electron 运行时，已内置）
    └── resources/app/          # 应用代码 + 词库 + 运行时依赖
```

**下载与使用：**

1. 前往 [Releases](https://gitee.com/siwpan/santi-teleprompter/releases) 下载
   `SantiTeleprompter-1.0.0-portable-win-x64.7z.001`
2. 用 7-Zip / WinRAR / Bandizip 解压（单卷，直接解压）
3. 进入 `SantiTeleprompter` 目录，双击 `启动提词器.bat`（或 `SantiTeleprompter.exe`）

> 可对照 `SantiTeleprompter-1.0.0-portable-win-x64.sha256.txt` 校验下载完整性。

**自己构建便携包：**

```bash
# 1) 安装依赖（含 electron 二进制，建议国内镜像）
ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/ npm install

# 2) 将 node_modules/electron/dist 复制为便携目录，
#    并在其 resources/app/ 下放入 public、src、pools、cordis.yml
#    与运行时依赖（cordis、yaml、cosmokit、@standard-schema/spec）
#    产物目录：build/SantiTeleprompter/

# 3) 用 7-Zip 打包为单卷
7za a -t7z -mx=5 -v90m dist/SantiTeleprompter-1.0.0-portable-win-x64.7z build/SantiTeleprompter
```

> 说明：本项目亦配置了 `electron-builder`（`npm run dist`，可生成 NSIS 安装程序）。
> 但由于其依赖树庞大、在受限网络下安装缓慢，官方发行采用上述 **便携压缩包** 方案：
> 直接复用已安装的 Electron 运行时 + 应用代码，零额外下载、体积可控（约 74 MB）。

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

词库内容来自对《文学少女》「三题故事」玩法的整理与联网检索补充，欢迎按需扩充 `pools/` 下的词语池。
