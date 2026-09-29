# Pomodmer —— 番茄钟改造规划（基于 cordis-table-app v1.0.0）

> 目标形态（已确认）：**保留 Cordis + Node 内核 + 本地 Web UI**，Electron 作为**后期可选桌面壳**（P3）。
> 进度：P0 已开始执行（见文末「执行记录」）。

---

## 0. 已完成：回滚到 v1.0.0

| 项 | 结果 | 证据 |
|---|---|---|
| 回滚方式 | `git reset --hard v1.0.0`（直接硬回滚，未建备份分支） | `HEAD is now at 3434c6d` |
| 回滚前 HEAD | `1d44c5e 修复 Python 自发现不完整 + 补 .venv 忽略项` | `git log` |
| 回滚后 HEAD | `3434c6d cordis-table-app: MIT 许可证 + 去除本地盘符硬编码` | `git log --oneline -3` |
| 移除的 v1.1/v1.2 文件 | `src/map_cli.mjs`、`src/map_demo.mjs`、`src/map_dj.mjs`、`src/map_gen.mjs` | 文件树对比 |
| 恢复通道 | tag `v1.1.0` / `v1.2.0` 仍在（未删），随时可 `git reset --hard v1.2.0` | `git tag -l` → v1.0.0/v1.1.0/v1.2.0 |
| 回滚后冒烟 | `node src/_smoke.mjs` 通过，EXIT=0 | 输出 `entries count => 1`、`disposed OK` |
| 工作区 | 干净，无未提交改动 | `git status --short` 空 |

回滚后文件树（15 个受版本控制文件）：

```
.gitignore  LICENSE  README.md  cordis.json  package-lock.json  package.json
python/rpc_server.py  sample.json
src/_local_plugin.mjs  src/_smoke.mjs  src/boot.mjs  src/cli.mjs
src/core/bridge.mjs  src/demo.mjs  src/plugins/table.mjs
```

---

## 1. 现状盘点（实测，非推测）

| 维度 | 实测值 | 对番茄钟的意义 |
|---|---|---|
| Node | `v22.22.2` | 可用 `node:http`、`node:sqlite`、原生 ESM |
| npm 依赖 | 仅 `cordis` / `@cordisjs/plugin-loader` / `@cordisjs/plugin-logger-console` | **无 express / ws / 前端框架**，新增 UI 必须零第三方依赖 |
| `node:sqlite` | 可用（`DatabaseSync, StatementSync`），带 ExperimentalWarning | 零依赖持久化**可选方案**（实验性 API，升级风险） |
| Python | `E:\Python314\python.exe` = 3.13.14，`openpyxl 3.1.5` 已装 | 现有 OpenPyXL 桥可留作 P2 周报导出 |
| 插件机制 | `cordis.json` entries → Loader 声明式加载，`Service` 子类 `provide('table')` | 番茄钟各能力应拆成**独立 Cordis 服务插件**，沿用同一套模式 |
| 宿主启动 | `src/boot.mjs` 的 `bootHost/stopHost` 被入口/CLI/测试三方共用 | 新能力直接挂 entries，避免启动路径漂移 |
| 现有 CLI | `src/cli.mjs` = JSON→xlsx 生成器 | 可改造或并列新增 `pomodoro` 子命令 |

**可复用资产**：`boot.mjs`（宿主生命周期）、`core/bridge.mjs`（JSON-RPC stdio 桥）、
`python/rpc_server.py`（Python worker 协议层）、`plugins/table.mjs`（Service 插件范式）、
`_smoke.mjs`（冒烟骨架）、`.gitignore`（已含 node_modules / output / vendor / \_\_pycache\_\_）。

---

## 2. 联网调研结论

### 2.1 番茄工作法规则（权威口径，Francesco Cirillo, 1992）

| 规则 | 标准值 | 说明 |
|---|---|---|
| 专注单元 | 25 min | 一个「番茄钟」，**不可分割**，不存在半个番茄 |
| 短休息 | 5 min（3–5 min 亦可） | 每完成 1 个番茄后 |
| 长休息 | 15–30 min | **每 4 个番茄后** |
| 中断处理 | 内部/外部中断 | 紧急 → 当前番茄**作废**重来；非紧急 → 记「计划外事件」+ 打逗号标记，继续当前番茄 |
| 提前完成 | 不可提前结束 | 继续检查/回顾任务直到响铃 |
| 任务拆分 | >5–7 个番茄的任务要拆小；<1 个番茄的零碎活动合并 | 影响任务清单的数据模型 |
| 五阶段闭环 | 规划 → 跟踪 → 记录 → 处理 → 可视化 | 我们的 P1 统计/热力图即「可视化」阶段 |

来源：百度百科《番茄工作法》/《番茄钟》、番茄工作法中文站 pomodorotechnique.cn、光明网转央视新闻科普。

### 2.2 参考实现特性对比

| 产品 | 技术栈 | 值得抄的点 | 不抄的点 |
|---|---|---|---|
| **Pomotroid**（开源 v1.4.0） | Vue + Electron + Vuex | 主题(JSON 可配)、迷你模式、置顶、滴答声、桌面通知、活动日志 | Electron 体积大、需打包分发 |
| Pomotroid 三层架构 | 表现层 / 业务层(状态机) / 系统层(主进程计时) | **计时放在与 UI 隔离的进程** —— 正是我们「服务端权威」策略的理论依据 | — |
| 极简网页番茄钟（多篇实现） | 原生 HTML/CSS/JS | 零依赖、SVG 进度环（`strokeDashoffset` + `rotate(-90deg)`）、Web Audio 合成音、localStorage 防刷新 | localStorage 单页方案，进程一关就没了 |
| Focus To-Do / TickTick | 商业 | 任务清单 + 番茄归属 + 统计报表 | 云同步、账号体系（本地工具不需要） |

**关键共识**：所有认真做计时的实现，都把「计时推进」和「UI 渲染」解耦 —— 我们把它落在
Node 宿主（权威）↔ 浏览器（纯渲染）这条边界上，天然契合现有 Cordis 宿主架构。

### 2.3 技术要点（踩坑预报，均有出处）

1. **禁止 `setInterval` 累加计数**。回调迟到会累积漂移；后台标签页被浏览器节流到 ~1s 甚至更久。
   正确做法：以**绝对目标时间** `endAt` 为锚，每次 tick 现算 `remaining = endAt - now`，
   用「递归 setTimeout + 固定目标时间」校正（不是 `setTimeout(1000)` 的朴素递归）。
2. **时钟源**：Node 侧用 `performance.now()`（node:perf\_hooks）或 `process.hrtime.bigint()`
   度量时长；长期运行不要用 `Date.now()` 做漂移校正——系统时钟调整会让它前进/后退。
   落盘时间戳仍用 `Date.now()`（墙钟），两者分工明确。
3. **后台/隐藏标签页**：前端定时器不可信；改用 **SSE 推送** + 服务端权威，
   并在 `visibilitychange` 回到前台时立即拉一次快照强制重绘。
4. **提示音零资产**：`AudioContext` + `OscillatorNode` + `GainNode` 实时合成
   （如 587Hz→880Hz 滑音 / 三连 beep / 880+660 交替），`exponentialRampToValueAtTime` 做淡出防爆音。
   硬约束：**必须在用户手势（点「开始」）后 `resume()`**，否则被自动播放策略静音；
   `OscillatorNode` 是一次性节点，`stop()` 后不可复用，每次 new。
5. **桌面通知**：`Notification API`；`http://127.0.0.1` 属 secure context，localhost 可直接申请权限，无需 HTTPS。
6. **系统休眠**：S3 待机恢复后墙钟会跳变。不能静默补时——应检测 gap 超阈值 → 标记该 session `interrupted`。

---

## 3. 目标架构

```
                        ┌──────────────────────── 浏览器（纯渲染，零框架） ────────────────────────┐
                        │  web/index.html · app.js · style.css                                   │
                        │  · SVG 进度环 + 大字倒计时                                              │
                        │  · 只做「读快照 + 渲染」，绝不自己推进时间                               │
                        │  · Web Audio 合成提示音 / Notification API 通知                          │
                        └───────────────┬──────────────────────────▲─────────────────────────────┘
                                        │ REST (POST /api/...)      │ SSE (GET /api/events, 1s tick)
┌───────────────────────────────────────▼──────────────────────────┴─────────────────────────────┐
│ Cordis 宿主 (Node.js 22, 零新增 npm 依赖)      src/boot.mjs  bootHost()/stopHost()              │
│  ├─ ctx.store   StoreService    持久化（默认 JSON 文件；可选 node:sqlite）        数据层         │
│  ├─ ctx.timer   TimerService    番茄钟状态机（核心，纯逻辑无 IO）                 领域层         │
│  ├─ ctx.http    HttpService     node:http 静态托管 + REST + SSE                  接入层         │
│  ├─ ctx.report  ReportService   P2：inject ['table'] 复用 OpenPyXL 导出 xlsx      报表层         │
│  └─ ctx.table   TableService    既有资产（保留/裁撤待定）  ──JSON-RPC stdio──▶ python worker    │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
                                   cordis.json entries 声明式装配（不改 boot.mjs 逻辑）
```

**为什么这样分层**：Cordis 的 `inject` 让启动顺序由依赖图推导，不用手动编排；
每个服务都是可独立卸载/热重载的插件 —— 与现有 `TableService` 完全同构，学习成本为零。

**关于 Electron（P3 可选壳）**：Electron **不改架构，只换外壳** —— 它只是把同一个 `web/` 目录装进
`BrowserWindow`（`win.loadURL('http://127.0.0.1:<port>')` 或 `loadFile`），Cordis 宿主照旧在
Node 主进程里跑。因此 P0–P2 全部产出可直接复用，Electron 是纯增量：

```
Electron 主进程 ──spawn──▶ src/pom.mjs（Cordis 宿主 + HTTP/SSE）──▶ BrowserWindow 加载 web/
```

安装要点（菜鸟教程 https://www.runoob.com/electron/electron-install.html ）：
`npm install electron --save-dev`；国内必须加镜像否则下载超时 ——
`ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/`（可 `npm config set` 永久化）；
`package.json` 加 `"main": "electron/main.js"` 与 `"scripts": { "electron": "electron ." }`；
打包另需 `electron-builder`。**风险**：Electron 体积 ~100MB，依赖网络下载，与「零新增 npm 依赖」冲突 →
故定为 P3，且必须是 `devDependencies` + 可选，主功能不得依赖它。

### 状态机（TimerService）

```
        start                        时间到
 idle ─────────▶ focus(25m) ─────────────────▶ (第 n 个番茄, n % 4 != 0) ──▶ short(5m)
                   ▲   │                                                          │
                   │   └── pause / resume / reset / skip ──────────────────────────┘
                   │                                      (n % 4 == 0) ──▶ long(15~30m)
                   └──────────────────────────────────────────────────────────────┘
 中断：void（作废，不计完成，interrupts++） / 系统休眠 gap 超阈值 → 自动标记 interrupted
```

---

## 4. 数据模型（初稿）

```jsonc
// data/store.json（默认；gitignore 或可选提交，待定）
{
  "settings": {
    "focusMs": 1500000, "shortMs": 300000, "longMs": 900000,
    "longEvery": 4,                 // 每 4 个番茄长休
    "autoStartBreak": true, "autoStartFocus": false,
    "sound": true, "tick": false, "notify": true
  },
  "tasks":   [ { "id": "t1", "title": "写 P0 代码", "estimate": 3, "spent": 1, "done": false, "createdAt": 0 } ],
  "sessions": [ { "id": "s1", "type": "focus|short|long", "taskId": "t1",
                  "plannedMs": 1500000, "startAt": 0, "endAt": 0,
                  "actualMs": 0, "completed": true, "interrupts": 0 } ],
  "runtime": { "phase": "focus", "endAt": 0, "pausedMs": 0, "round": 2, "currentTaskId": "t1" }
}
```

- 统计（今日番茄数 / 总专注时长 / 连续天数 / 每任务番茄数）**全部由 sessions 派生，不单独存**。
- 单一写入口：`ctx.store` 负责原子落盘（写临时文件 + rename），避免 Ctrl+C 杀死进程时写坏 JSON。

### 接口草案

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 静态 UI（web/） |
| GET | `/api/state` | 全量快照（settings/tasks/runtime/today 统计） |
| GET | `/api/events` | **SSE**：每秒 `tick`（含 `remainingMs`）+ `phase` 变更事件 |
| POST | `/api/timer/start` \| `pause` \| `resume` \| `reset` \| `skip` \| `void` | 控制 |
| GET/POST/PATCH/DELETE | `/api/tasks` | 任务 CRUD |
| PATCH | `/api/settings` | 改时长/开关（立即生效，运行中的番茄按策略处理） |
| GET | `/api/stats?range=day\|week` | 统计（P1） |
| POST | `/api/export/xlsx` | 周报导出（P2，走 OpenPyXL 桥） |

---

## 5. 路线图（P0 → P1 → P2，每批自带验收）

### P0 —— 能跑起来的最小番茄钟

| # | 任务 | 产出 |
|---|---|---|
| P0-1 | 项目身份切换：package.json `name` → `pomodmer`，scripts 增 `pom`；cordis.json 增条目 | 可 `npm run pom` 启动 |
| P0-2 | `StoreService`：JSON 落盘 + 原子写 + 开机恢复 | `src/plugins/store.mjs` |
| P0-3 | `TimerService`：状态机 + 递归 setTimeout 目标时间校正 + 事件发射 | `src/plugins/timer.mjs` |
| P0-4 | `HttpService`：`node:http` 静态托管 + REST + SSE | `src/plugins/http.mjs` |
| P0-5 | Web UI：SVG 进度环、大字倒计时、开始/暂停/重置/跳过、设置面板 | `web/index.html|app.js|style.css` |
| P0-6 | Web Audio 合成提示音 + 阶段自动流转（focus↔short→long） | 前端 + 状态机 |
| P0-7 | 冒烟测试扩展：启宿主 → 打 REST → 断言状态迁移 → 关停 | `src/_smoke.mjs` |

**P0 验收（全部要实测，不许"看起来没问题"）**
1. `npm run pom` 启动后打印 `http://127.0.0.1:<port>`，端口可配（`POMODMER_PORT`）。
2. 浏览器打开显示 25:00，开始/暂停/重置/跳过四个按钮均生效。
3. 用 `settings.focusMs=60000` 跑完整一轮：到点自动切 5 分钟短休并**响提示音**。
4. **刷新页面**倒计时继续（服务端权威，非 localStorage 兜底）。
5. **关标签页 3 分钟**再打开，剩余时间正确（误差 < 1s）。
6. kill 进程重启，`runtime` 恢复；gap 超阈值时该 session 被标记 `interrupted` 而非静默补时。
7. `package.json` 的 `dependencies` **一个字都不改**（零新增 npm 依赖）。
8. `git status` 干净 + `npm run smoke` EXIT=0。

### P1 —— 真能日常使用

| # | 任务 |
|---|---|
| P1-1 | 任务清单 CRUD + 番茄归属（`taskId`），估番茄数 vs 实际对比 |
| P1-2 | Notification API 桌面通知（授权流程 + 开关） |
| P1-3 | 统计面板：今日番茄数 / 专注总时长 / 连续天数 / 每任务分布 |
| P1-4 | 热力图 + 柱状图（**纯 CSS/SVG 手绘，不引图表库**） |
| P1-5 | 中断记录（内部/外部 + 计划外事件列表），对应番茄工作法第 4 条 |
| P1-6 | 主题（亮/暗 + 自定义色）、键盘快捷键（空格开始/暂停） |
| P1-7 | 数据导出/导入 JSON |

### P2 —— 好用 & 复用既有资产

| # | 任务 |
|---|---|
| P2-1 | `ReportService` 走既有 `ctx.table`（JSON-RPC → Python OpenPyXL）导出周报 xlsx |
| P2-2 | 白噪音/滴答声（Web Audio 噪声 buffer + 衰减包络） |
| P2-3 | 迷你模式 / 置顶窗（浏览器 kiosk 小窗 or `--app=<url>` 启动参数） |
| P2-4 | Windows 托盘 + 原生 Toast（若坚持零依赖，用 `node:child_process` 调 PowerShell；否则留 TODO） |
| P2-5 | 单文件分发：Node SEA 打包 或 自愈式 .bat 启动器（自动拉起 + 开浏览器） |
| P2-6 | README 全量重写（架构图/规则/API/截图）+ 打 tag |

### P3 —— Electron 桌面壳（可选，不阻塞 P0–P2）

| # | 任务 | 说明 |
|---|---|---|
| P3-1 | `npm i -D electron`（配 `ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/`） | 仅 devDependencies，网络失败不影响主功能 |
| P3-2 | `electron/main.js`：`app.whenReady` → spawn `src/pom.mjs` → `BrowserWindow` 加载 `http://127.0.0.1:<port>` | 主进程托管 Cordis 宿主，渲染进程只加载现有 web/ |
| P3-3 | 桌面能力补齐：托盘图标 + 最小化到托盘、`setAlwaysOnTop` 迷你窗、全局快捷键、原生 Notification | 这些是纯 Web UI 做不到的部分 |
| P3-4 | `electron-builder` 打安装包（可选） | 二进制不入仓，仅文档标注 |

**验收**：`npm run electron` 弹出桌面窗，倒计时与浏览器版一致；关窗退到托盘继续计时；关闭时宿主进程被正确回收（不残留 node/python）。

---

## 6. 版本与仓库卫生

- 包名 `pomodmer`，**保留** `cordis-table-app` 血统说明（README 注明"由 cordis-table-app v1.0.0 改造"），MIT + `siwpan` 不变。
- 版本号建议 **`v2.0.0`**（语义化：用途改变 = breaking）；若想新开序列则用 `pomodmer-v1.0.0` 前缀标签，避免与既有 v1.0.0 撞名。
- 硬约束延续：第三方内核源码（`vendor/`）不入仓；`node_modules/`、`output/`、`data/` 视情况进 `.gitignore`；令牌/密钥绝不入仓。
- 提交节奏：按你一贯要求 —— **每批（P0/P1/P2）完成 + 验证通过后，单独提交并推送 Gitee，再开下一优先级**。

---

## 7. 决策点（2026-09-29 全哥拍板：全部按推荐项执行）

| # | 问题 | 决策 | 依据 |
|---|---|---|---|
| 1 | **Python / OpenPyXL 桥是否保留？** | ✅ **保留，但降级为可选插件**（`cordis.table.json` 单独清单，默认不拉起） | 复用既有资产；不装 Python 也能跑主功能（P2 周报导出时用） |
| 2 | **持久化用哪种？** | ✅ **JSON 文件起步**（`data/store.json`，原子写） | 稳、零依赖；`node:sqlite` 是实验性 API，升级有变，留作 P2 开关 |
| 3 | **要不要"真桌面"能力？** | ✅ **P0–P2 纯浏览器；P3 加 Electron 桌面壳**（仅 devDep，可失败） | 零新增 npm 依赖是硬约束；托盘/置顶/全局快捷键留给 Electron |
| 4 | **Gitee 仓库怎么处理？** | ✅ **原地改名**，保留 `cordis-table-app` 仓库与全部历史 | 资产与历史永远保全；README 注明血统 |

> **2026-09-29 追加修订（决策 1）**：原决策"降级为可选插件、默认不拉起"实际效果是**能力休眠** ——
> 除了写代码的人，没人会记得每次启动都设 `POMODMER_CONFIG=cordis.with-xlsx.json`。
> 已改为**按需自动启用**：启动时探测本机 Python + openpyxl，探到就自动挂
> `cordis.with-xlsx.json`，探不到安静退回纯番茄钟；显式 `--config` / `POMODMER_CONFIG` 仍然优先，
> `POMODMER_NO_XLSX=1` 可主动关闭。详见 §8「表格能力复活」。

---

## 8. 执行记录

### 2026-09-29 · P0 完成（实测通过）

| 交付 | 文件 | 状态 |
|---|---|---|
| 持久化 | `src/plugins/store.mjs`（JSON 原子写、坏档备份回退） | 完成 |
| 状态机 + 权威计时 | `src/plugins/timer.mjs` | 完成 |
| 接入层 | `src/plugins/http.mjs`（node:http + REST + SSE） | 完成 |
| 前端 | `web/index.html` / `app.js` / `style.css` | 完成 |
| 入口 | `src/pom.mjs`（`--port/--host/--no-open/--config`） | 完成 |
| 端到端冒烟 | `src/_smoke_pom.mjs` | 33 项 **ALL PASS**（EXIT=0） |
| 项目身份 | `package.json` → `pomodmer@2.0.0`；`cordis.json` → store/timer/http；新增 `cordis.table.json` | 完成 |
| 文档 | `README.md` 全量重写 | 完成 |

**P0 验收逐条结果**

| # | 验收项 | 结果 |
|---|---|---|
| 1 | `npm run pom` 启动并打印地址、端口可配 | ✅ 实测 `POMODMER_PORT=5199` → `http://127.0.0.1:5199/`，HTTP 200 |
| 2 | 开始/暂停/重置/跳过可用 | ✅ 冒烟第 4、6 节 |
| 3 | 到点自动切短休 | ✅ focus(3s) → short，round=1，落库 completed=true |
| 4 | 刷新页面倒计时继续 | ✅ 服务端权威（暂停 1s 后剩余时间冻结不变） |
| 5 | 关标签页再打开时间正确 | ✅ 同一机制；另有 `visibilitychange` 回前台重拉快照 |
| 6 | 进程重启不静默补时 | ✅ 记录 `reason='shutdown'` 且 `completed=false`，冻结为暂停态 |
| 7 | `dependencies` 一字未改 | ✅ 仍为 cordis / plugin-loader / logger-console |
| 8 | `npm run smoke` EXIT=0 | ✅ 内核冒烟 + 番茄钟端到端冒烟均 0 |

**待办**：P0 提交（需授权）→ P1。

### 2026-09-29 08:0x · P1 完成（实测通过）

| 交付 | 说明 |
|---|---|
| 任务清单 + 番茄归属 | UI 增删改选，番茄完成后 `spent` 自增，与 `estimate` 对比 |
| 统计面板 | 今日 / 连续天数 / 最近 7 天柱状图 / 12 周热力图 / 每任务进度条（纯 SVG 手绘，不引图表库） |
| 中断记录 | 番茄工作法「计划外事件」：内部/外部 + 备注 + 时间，可删 |
| 亮/暗主题 | 存 `settings.theme`，CSS 变量 `[data-theme]` 切换 |
| 快捷键 | 空格 开始/暂停（输入框/按钮聚焦时不触发） |
| 导入导出 | `/api/export`（附件）/ `/api/import`（校验失败 400，导入后停在暂停态） |
| 后端扩展 | `timer.stats()` / `recordInterrupt()` / `listUnplanned()` / `reload()`；`store.snapshot()` / `replace()` |

**冒烟**：`node src/_smoke_pom.mjs` → **59 项 ALL PASS**（EXIT=0），新增 9b（任务归属）/ 9c（中断 CRUD）/
9d（统计形状 + streak）/ 9e（导出导入 + 非法导入 400）/ 9f（主题归一化）。

**修掉的两个真 bug**：
1. 路由顺序 —— `/api/tasks/:id` 前缀分支吃掉了 `/api/tasks/current`（表现为"选当前任务无效"）。
2. `StoreService` 漏了 `get unplanned()` —— `ctx.store.unplanned` 为 undefined，列表接口 500。

### 2026-09-29 08:2x–08:4x · P2 + P3 完成（实测通过）

| 交付 | 说明 | 验证 |
|---|---|---|
| P2-1 周报 xlsx | `src/plugins/report.mjs`（ctx.report），复用 `ctx.table` → Python OpenPyXL；四张表 概览/每日/会话/任务 | 真实生成并**回读校验**：「每日」= 表头+7 天，「概览」= 表头+9 项 |
| P2-2 白噪音 | Web Audio 实时合成白噪音/棕噪音（零音频资产），仅专注且计时中播放 | 静态自检 + 手工可听 |
| P2-3 迷你窗 | 独立小窗只显示倒计时 + 开始/跳过（每 500ms 拉 `/api/state`） | 静态自检 |
| P2-4 原生通知 | `src/core/toast.mjs` 借 PowerShell NotifyIcon 气泡；best-effort，失败不影响主功能 | 默认关闭，可开关 |
| P2-5 启动器 | `pomodmer.bat`（ASCII-only，依赖缺失自动 `npm install`） | 文件就位 |
| P3 Electron 壳 | `electron/main.cjs` + `start.mjs` + `make-icon.mjs`/`icon.png`；托盘/置顶/`Ctrl+Alt+Space`/原生阶段通知 | **实机跑通**：`[electron] 就绪：http://127.0.0.1:5173` |

**冒烟**：`node src/_smoke_pom.mjs` → **ALL PASS**（EXIT=0），新增第 11 节（周报 xlsx 端到端，
含 with-xlsx 清单启动 + 回读校验）与第 12 节（P2/P3 资产自检）。

**修掉/绕过的三个坑**：
1. Electron 44.4.5 主进程**不支持** `import { app } from 'electron'` 命名导出 → 主进程改写 `main.cjs`（CommonJS）。
2. 本机环境带 `ELECTRON_RUN_AS_NODE=1` → electron.exe 退化成纯 Node（`require('electron')` 返回路径字符串，
   `app.whenReady()` undefined）。该变量启动前就被读取，必须**在 spawn 子进程前删掉** → 新增 `electron/start.mjs`。
3. Electron 二进制首次安装未落地（`node_modules/electron` 无 `dist/`）→ 显式跑
   `ELECTRON_MIRROR=... node node_modules/electron/install.js` 补齐（158MB，npmmirror 可用）。

### 2026-09-29 · 表格能力复活：从「记得设环境变量」到「能跑就自动带上」（实测通过）

**背景**：`ctx.table`（Cordis → JSON-RPC stdio → Python OpenPyXL）是从 `cordis-table-app` 继承的既有资产，
在 P2 只被周报用了一条链路；而"可选插件 + 手动设 `POMODMER_CONFIG`"的启用方式让它事实上休眠 ——
装没装 Python 的机器都得先知道这个环境变量才用得上。

| 交付 | 文件 | 说明 |
|---|---|---|
| 解释器探测复用 | `src/plugins/table.mjs` | 抽出 `probeTableWorker()`（返回 `{bin, openpyxl, anyBin}`）+ memo；`resolvePythonBin()` 语义不变（显式指定仍权威、缺依赖仍回退让 Python 自己报错） |
| 清单自动选择 | `src/boot.mjs` | 新增 `resolveConfigPath()`：显式 `--config` > `POMODMER_CONFIG` > 自动探测 > `cordis.json`；每次启动打印"选了哪个清单 + 为什么" |
| 提示与前端 | `http.mjs` / `report.mjs` / `web/app.js` | 能力不在场时区分三种原因（没装 Python / 装了缺 openpyxl / 被 `POMODMER_NO_XLSX=1` 关闭）；前端直接渲染服务端 hint，不再自己编文案 |
| 冒烟 | `src/_smoke_pom.mjs` | 新增第 8 节两断言（未挂报表时探测接口给可读原因）+ 第 13 节（自动决策与探测结果一致、显式/env/opt-out 优先级） |
| 文档 | `README.md` | 新增「复用既有表格能力」章节：10 个 RPC 方法表、三种用法（UI 周报 / `npm run gen` 通用 JSON→xlsx / 自写插件骨架）、移植三件套、三条纪律 |

**验证**（都是实测，不是推断）：

- 决策四条分支：默认（本机探到 `G:\Python314\python.exe`）→ `cordis.with-xlsx.json`；
  `POMODMER_NO_XLSX=1` / `POMODMER_CONFIG` / 显式 `--config` → 各自正确优先；清空 `PATH` 模拟无 Python → 退回 `cordis.json` 且**不**误报"缺 openpyxl"。
- 首次探测 421ms（之后走 memo，TableService 不再重复探测）；自动探测另设 2.5s/候选 + 4s 总预算，防个别占位解释器把启动拖长。
- 端到端（不给任何清单）：`ctx.table=true ctx.report=true`、5 个入口、`GET /api/report` → `available:true`、
  `POST /api/report` → 真实产出四张表 xlsx、关停后 python worker 已回收（进程数 before=after）。
- 关闭态：`POMODMER_NO_XLSX=1` → 3 个入口、`available:false`、`POST` 返回 501 且提示明确说明是主动关闭。
- `npm run smoke` → **ALL PASS**（EXIT=0）。

**顺带修掉的一个真 bug**（第 8 节断言抓到的方向）：`anyBin` 原先会把列表尾部的裸名 `python3`
当成"存在"，导致根本没装 Python 的机器被提示成"装了 Python 但缺 openpyxl"，指错排查方向；
现在 `anyBin` 只认确认存在的绝对路径。

### 2026-09-29 · P1：让导出的 xlsx 在 Excel 里真正可用（实测通过）

**优先级判断**（表格能力后续工作四选一）：先修"数据可用性"，而不是先加新出口。理由：
① 现有周报把日期写成文本，Excel 里没法排序/筛选/做日期计算 —— 报表的"可分析"价值被削掉一半；
② 探测时发现一个更严重的缺陷：**一个日期单元格就能弄死整个 Python worker**（见下），
   而它是"从 Excel 导入"这类反向能力的前置条件。加新功能前先让现有链路站得住。

| 交付 | 文件 | 说明 |
|---|---|---|
| 修 worker 崩溃 | `python/rpc_server.py` | `json.dumps` 原本在 `try` 之外：`read_sheet` 撞上 `datetime` 单元格 → `TypeError` 掀翻主循环 → **进程退出**，此后所有调用都是 `python worker exited`。现在响应序列化也在 `try` 内，并加 `_json_default`（datetime/date/time → ISO 串、timedelta → 秒、Decimal → float、bytes → base64） |
| 真实类型写入 | `python/rpc_server.py` / `table.mjs` | `write_rows` 支持 `col_types`（`text`/`number`/`datetime`/`date`/`time`）：把宿主给的 ISO 串还原成 Excel 原生类型；解析失败原样写入，不为类型好看丢数据 |
| 数字格式 / 冻结窗格 / 元信息 | 同上 | 新增 `set_number_format`（一次多段区域）、`freeze_panes`、`sheet_meta`（冻结窗格 + 数字格式 + 值类型，用于验证文件真实形态） |
| 周报升级 | `src/plugins/report.mjs` | 日期/时间列改真实 datetime（本地时区，不用 `toISOString()` 免得差时区）、`yyyy-mm-dd` / `yyyy-mm-dd hh:mm` 数字格式、四张表全部冻结表头 |
| 冒烟 | `src/_smoke_pom.mjs` | 新增 11b 共 8 条：日期是原生类型、数字格式正确、表头冻结、带日期的文件能读回、**读日期后 worker 仍存活**（崩溃回归） |

**验证**：

- 崩溃复现（改动前）：外部 xlsx 含一个 `datetime` 单元格 → `read_sheet` → worker `exit code=1`，连 `ping` 都不再响应。
  改动后：返回 `"2026-09-29T09:00:00"`，随后 `ping` 正常。
- 落盘文件由**独立 Python 进程**重新打开核对（不信宿主内存里的对象）：四张表 `freeze_panes=A2`，
  「每日」`A2` 为真日期 + `yyyy-mm-dd`，「会话」时间列为 `yyyy-mm-dd hh:mm`。
- `npm run smoke` → **ALL PASS**（EXIT=0）。

**过程中修掉的两个自己写出来的 bug**（都靠断言抓到）：
1. `ws["B10"]`（单格）返回的是 `Cell` 而非 tuple，`set_number_format` 直接迭代它 → `'Cell' object is not iterable`；
   现在先归一成列表。
2. `table.mjs` 把 JS 侧 `colTypes` 原样过桥，worker 读的是 `col_types` → 类型声明静默失效。
   **同时发现自己的断言太弱**：文本日期也能匹配 ISO 正则，所以只测字符串形态会假绿 ——
   改成查 `sheet_meta.value_types`。

### 后续优先级（已定序，按序推进）

| 顺序 | 工作 | 状态 |
|---|---|---|
| P1 | xlsx 数据可用性（真实日期/数字格式/冻结表头/worker 崩溃） | ✅ 本轮完成 |
| P2 | 全量数据 xlsx 导出（复用同一层 `ctx.table`，与 JSON 备份互补） | 待做 |
| P3 | Excel → 任务/会话导入（`readSheet` 反向；合并策略需先确认） | 待做（依赖 P1 的读回健壮性） |
| P4 | 打包为可复用插件（三件套抽包） | 暂缓（缺第二个真实消费者） |

### 2026-09-29 · P4：表格能力三件套统一到权威源（第二个消费者出现，实测通过）

**优先级变更**：原计划 P4"打包为可复用插件"因"缺第二个真实消费者"暂缓；本轮确认
第二个消费者是 `G:\repos\cordis-table-app`（本项目的前身、也是表格能力的超集）。
更关键的是：**分叉成本已经被实测证明，不再是假设** —— 同一个"日期单元格杀死 worker"的缺陷
在两边各自踩了一遍（两边 worker 的 `json.dumps` 都在 `try` 之外）；UTF-8 那个坑也是两边各修一次。
故 P4 提到 P2/P3 之前先做。

| 交付 | 位置 | 说明 |
|---|---|---|
| 权威源加固 | `cordis-table-app`（worker/table.mjs/bridge.mjs） | 把 pomodmer 侧 P1 的加固整体回流：序列化进 `try` + `_json_default`、`col_types` 原生类型写入、`set_number_format`/`freeze_panes`/`sheet_meta`（并补 `merged`/`comments`）；`py -3` 这类"命令 + 参数"候选原先永远探活失败，改为统一按 `pythonCommandParts` 拆词 |
| 探测 API 合流 | 同上 | 权威源采纳 pomodmer 的 `probeTableWorker()`（memo + 超时预算 + `anyBin` 语义），并保留它自己更强的候选枚举（项目 `.venv` → `py -3` → PATH → 用户级/系统级/各盘符落点） |
| 来源锁 | `tools/table-kit.json` / `tools/table-kit.lock.json` | 声明权威源与同步清单；锁里记录**来源仓库 + 提交号 + 每文件 sha256** |
| 同步工具 | `tools/sync-table-kit.mjs` | `--check` 体检（锁↔本地、锁↔源）、`--lock-only` 仅查锁↔本地（不依赖权威源在场，可进 CI/smoke）、默认拒绝覆盖未登记的本地改动、`--force` 强推 |
| 冒烟 | `src/_smoke_pom.mjs` 第 11c / 13 节 | 11c：合并单元格 / 批注 / 改文本在 pomodmer 侧真的生效；13：三件套与来源锁一致 + 锁记录了权威源与提交号 |

**验证**：两侧全绿 ——
`cordis-table-app`：`npm test`（smoke + 地图演示 + DonJon 互通往返 600 格）通过，日期回归探针由
"worker exit code=1"变为正常返回并存活；
`pomodmer`：`npm run smoke` **ALL PASS**（EXIT=0），含联合套件新增能力与来源锁断言。
同步工具也做了实测：权威源改动后 `--check` 报"源已更新，本仓库还没同步"，同步后复检通过。

**顺带修掉**：`tools/sync-table-kit.mjs` 首版把 `defaultDir: "../cordis-table-app"` 按 `tools/` 解析，
结果找成了 `pomodmer/cordis-table-app`；相对路径必须按**仓库根**解析。

### 2026-09-29 · P2：全量数据 xlsx 导出（与 JSON 备份分工，实测通过）

**做了什么**：把"导出"这条出口从"只有最近 7 天的周报"扩到"整份数据"，
并明确两类文件的分工 —— **JSON 回灌备份 / xlsx 给人看与二次分析**。

| 交付 | 位置 | 说明 |
|---|---|---|
| 导出逻辑合流 | `src/plugins/report.mjs` | 抽出共用的 `_export({ days, scope, all, includeUnplanned })`：`weekly({days})` 与新增的 `full()` 走同一套建表逻辑，避免两套代码各自漂移；`spanDays()` 从最早一条会话算跨度（带 10 年上限，防脏时间戳把「每日」表撑爆） |
| 新表 | 同上 | 全量导出多一张「计划外事件」（时间/类型/备注/阶段/任务）—— 这些记录原先只有 JSON 带得走，人在 Excel 里根本看不到 |
| HTTP 出口 | `src/plugins/http.mjs` | `GET /api/export?format=xlsx`：生成后**以附件流回**（正确 MIME + `Content-Disposition`），并复用 `/api/report` 的能力提示（`_xlsxHint()` 抽成一处，前端不再自己编文案） |
| 前端 | `web/index.html` / `web/app.js` | 新增「导出数据 xlsx」按钮：按钮置灰 + "正在生成…" 反馈（生成要拉起 worker、写盘，没有反馈用户会反复点），拿到 blob 后触发下载并回显文件大小 |
| 冒烟 | `src/_smoke_pom.mjs` | 第 8 节：能力不在场时 501 + 可读原因、JSON 导出不受影响；第 11d 节：真实 HTTP 下载 → 落盘 → **用 openpyxl 读回**验证 5 张表/冻结/datetime 类型/统计区间=全部/事件内容落表 |

**验证**：`npm run smoke` → **ALL PASS**（EXIT=0）。

**顺带修掉一个测试脚手架的坑**：冒烟里的 `req()` 只发 `u.pathname`，把 query 悄悄丢了 ——
于是"断言 501"的用例实际打到了 `/api/export`（无 format）上，拿到 200 而假红。
已改为 `u.pathname + u.search`：断言打错路由的假红/假绿都必须杜绝。

### 2026-09-29 · P3：xlsx 回灌（去重追加 + 预览确认，实测通过）

**策略（用户拍板 A：全量回灌 + 去重追加）**：只新增 + 有限更新，**从不删除**已有记录；
导入前先预览（新增/更新/跳过各多少、哪些行被跳过及原因），确认后才落库。

| 交付 | 位置 | 说明 |
|---|---|---|
| 解析 | `src/plugins/report.mjs` `_parseXlsx()` | 认表头名、不认列序（表是给人改的，挪列不该导致错位）；三张表都可选，一张都没有才报错；解析不了的行走 warnings 而不是静默丢 |
| 预演 / 落库 | 同上 `_plan()` / `_commit()` | 预演纯读；落库走 `store.update()` 单写入口，只 push / 有限 update，绝不 splice；会话与事件按「任务」列标题反查 taskId |
| HTTP | `src/plugins/http.mjs` | `POST /api/import/xlsx?mode=preview\|apply`：原始字节收（`_rawBody`，不能像 JSON 那样当字符串拼）→ 落临时文件 → 交给 ctx.table 读 → 读完删；zip 魔数/空体/超 20MB 都给人话错误 |
| 前端 | `web/index.html` / `web/app.js` | 「回灌 xlsx」按钮 → 预览（按钮显示计划）→「确认导入」才落库；预览态与导入态都有禁用与文案反馈 |
| 冒烟 | `src/_smoke_pom.mjs` 第 11e 节 | 预览返回计划且**不改数据**；新任务按预估落库；会话按标题关联到任务；重复导入全跳过（幂等）；**原样回灌一条都不新增**；往返后历史规模不变；非 xlsx → 400 可读原因 |

**过程中被断言抓出来的两个真缺陷**（都不是"实现没写完"，而是"写完了但语义错"）：

1. **往返会把历史翻倍**：xlsx 只存到秒（手打的更是），而库里记录带毫秒。原先按毫秒精确比对去重，
   于是"导出后原样导回"把每条会话/事件都当新记录再插一遍 —— 这正是回灌功能最不能犯的错。
   改为**秒级容差窗口（±2 秒）**比对：番茄钟一条记录动辄几分钟，同类型两条差 2 秒内现实中不可能。
   独立探针先复现（`unplanned: add 2`，同一条「快递上门」进来两次），修完第 7 步"原样回灌"归零。
2. **空表占位行被当成真数据**：库里没有任务时，导出会写一行人类友好的「（无任务）」占位；
   导入侧把它当成了真任务，凭空造出一个叫「（无任务）」的任务。
   注意：**这个缺陷是冒烟抓到的、独立探针没抓到**（探针的数据正好非空）。现在写入与解析共用
   `EMPTY_TASKS` / `EMPTY_UNPLANNED` 常量，读写两侧不再各写一份字面量。

### 后续优先级（更新后）

> 本表的 P1–P4 指"表格能力后续工作"的编号，与 README 路线图的 P0–P3 无关。

| 顺序 | 工作 | 状态 |
|---|---|---|
| P1 | xlsx 数据可用性（真实日期/数字格式/冻结表头/worker 崩溃） | ✅ 完成 |
| P4 | 三件套统一到权威源（来源锁 + 同步工具 + 双向加固合流） | ✅ 完成 |
| P2 | 全量数据 xlsx 导出（复用同一层 `ctx.table`，与 JSON 备份分工） | ✅ 完成 |
| P3 | Excel → 任务/会话/事件回灌（去重追加 + 预览确认） | ✅ 本轮完成 |

表格能力四步到此收官：**导出（周报/全量）→ 人改 → 回灌**闭环打通，三件套有单一权威源与来源锁，
且每一步都有冒烟断言兜着。

## 9. 附：本轮调研来源
- 番茄工作法 / 番茄钟规则：百度百科词条、快懂百科、pomodorotechnique.cn 中文站、光明网（转央视新闻）
- Pomotroid（开源番茄钟，Vue+Electron，v1.4.0）：pomotroid.org、GitCode/AtomGit 项目镜像与二次开发文档
- JS 计时精度与后台节流：dev.to《Why setInterval Drifts and How to Fix It》、positioniseverything《Creating Accurate Timers in JavaScript》、xjavascript 精准计时、ufcn 后台标签页限频处理
- 零依赖音效/UI：华为云社区《基于纯原生 JS 与 Web API 构建零依赖高效番茄钟》、notadevblog《How I Generate Sound in My Focus Timer》、quickutil《Stopwatch & Timer Guide》
- Cordis 4 服务/插件机制：Cordis v4 源码解析（Context/Registry/Fiber/service/reflect）、DeepSeek Harness 官方 Services 文档
- Electron 安装：菜鸟教程 https://www.runoob.com/electron/electron-install.html（`npm i -D electron`、`ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/`、`main.js` + `BrowserWindow.loadFile`）
