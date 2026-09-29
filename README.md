# Pomodmer —— Cordis 内核 + 本地 Web UI 的番茄钟

仓库：<https://gitee.com/siwpan/pomodmer>（公开，MIT）

> 由 **cordis-table-app v1.0.0** 改造（2026-09-29 回滚到 v1.0.0 后转向番茄钟）。
> 表格能力（Python + OpenPyXL）保留为**可选插件**，不再默认拉起。
> 规划与执行记录见 [`docs/POMODORO-PLAN.md`](./docs/POMODORO-PLAN.md)。

一个跑在本机的番茄钟：**计时权威在 Node 服务端，浏览器只负责渲染**。
刷新页面、切到后台、关掉标签页都不会让计时出错；进程被强杀重启后也不会"凭空补时"。

## 许可证

MIT License（见 [LICENSE](./LICENSE)），版权归 `siwpan` 所有。

## 快速开始

```bash
npm install            # 只装 cordis / loader / logger-console（已装可跳过）
npm run pom            # 启动番茄钟，自动打开 http://127.0.0.1:5173/
npm run smoke          # 冒烟测试（内核 + 番茄钟端到端）
```

桌面壳（可选，需要先 `npm install electron`）：

```bash
npm run electron       # Electron 桌面版：托盘 / 置顶 / Ctrl+Alt+Space 全局快捷键 / 原生通知
```

Windows 双击即用：`pomodmer.bat`（依赖缺失会自动 `npm install`）。

**xlsx 表格能力自动启用**：启动时探测本机 Python + openpyxl，探到就把表格/报表插件一并挂上
（`cordis.with-xlsx.json`），探不到就安静退回纯番茄钟，两种机器都不用改配置。
日志里会打印这次选了哪个清单以及原因。要强制启用/关闭：

```bash
POMODMER_CONFIG=cordis.with-xlsx.json npm run pom   # 强制启用（缺 Python 时报表会明确报错）
POMODMER_NO_XLSX=1 npm run pom                      # 主动关闭（不想让 Python 被拉起时）
node src/pom.mjs --config cordis.table.json         # 只挂表格服务，不挂番茄钟
```

启动参数：

```bash
node src/pom.mjs --port 8080        # 换端口（或环境变量 POMODMER_PORT）
node src/pom.mjs --no-open          # 不自动开浏览器（或 POMODMER_OPEN=0）
```

## 架构

```
浏览器（零框架，web/）                       只渲染：按 endAt 插值画进度环与倒计时
   │  POST /api/...（控制）      ▲  SSE /api/events（每秒 tick + 阶段事件）
   ▼                             │
Cordis 宿主（Node.js 22，零新增 npm 依赖）
  ├─ ctx.store    src/plugins/store.mjs     JSON 原子落盘（data/store.json）
  ├─ ctx.timer    src/plugins/timer.mjs     番茄钟状态机 + 权威计时
  └─ ctx.http     src/plugins/http.mjs      node:http 静态托管 + REST + SSE
  （可选）ctx.table  src/plugins/table.mjs ──JSON-RPC stdio──▶ python/rpc_server.py（OpenPyXL）
  （可选）ctx.report src/plugins/report.mjs  周报 xlsx（依赖 ctx.table）
  （可选）Electron 壳  electron/main.cjs ──spawn──▶ 上面的宿主，BrowserWindow 加载同一个 web/
```

- `cordis.json` 是插件清单（声明式入口）；`cordis.table.json` 只挂表格插件。
- 启动时按「显式 `--config` > `POMODMER_CONFIG` > 自动探测」选清单：探到 Python + openpyxl 就用
  `cordis.with-xlsx.json`（番茄钟 + 表格 + 报表），否则用 `cordis.json`。决策与原因每次都打进日志。
- 三个服务的加载顺序由 `inject` 依赖图推导：`store → timer → http`，无需手动编排。

## 复用既有表格能力（Python + OpenPyXL）

这套能力继承自 `cordis-table-app` v1.0.0，它不是"周报专用代码"，而是一个**通用表格服务**：
`ctx.table` 把表格操作经 JSON-RPC（stdio 行分隔）转发给常驻的 Python worker，宿主自己完全不碰 Excel。

| 分类 | 方法 | 说明 |
|---|---|---|
| 工作簿 | `createWorkbook(path, sheet)` | 新建工作簿并指定首个工作表名 |
| 工作表 | `addSheet(path, name)` | 追加工作表 |
| 写入 | `writeRows(path, sheet, startRow, startCol, rows)` | 批量写二维数组（空值写 `null` 即空单元格） |
| 写入 | `writeRows(..., { colTypes })` | 按列声明类型 `'datetime'`/`'date'`/`'number'`/`'text'`：把 ISO 串还原成 Excel **原生**类型，日期才能排序/筛选/做日期计算 |
| 写入 | `writeCell(path, sheet, row, col, value)` | 单格写 |
| 样式 | `styleHeader(path, sheet, row, ncols, opts)` | 表头底色/加粗/居中/边框（`opts.fill` / `opts.font_color`） |
| 样式 | `setColumnWidth(path, sheet, col, width)` | 列宽 |
| 样式 | `setNumberFormat(path, sheet, items)` | 批量数字格式：`items: [{ range: 'A2:A8', format: 'yyyy-mm-dd' }]` |
| 样式 | `freezePanes(path, sheet, cell)` | 冻结窗格（`'A2'` = 表头常驻） |
| 读取 | `readSheet(path, sheet)` | 读回 `{ rows, max_row, max_col }`（日期以 ISO 串返回） |
| 读取 | `sheetMeta(path, sheet, row)` | 冻结窗格 / 数字格式 / 值类型 —— 用来验证导出文件的**真实形态** |
| 落盘 | `save(path)` / `close(path)` | 保存（`close` 顺带移出 worker 的内存缓存） |
| 自检 | `ping()` | 返回 Python / openpyxl 版本 |

三种用法，同一份 worker 支撑：

1. **UI 点一下出报表**：周报按钮 → `POST /api/report` → `ctx.report.weekly({ days })`，四张表：概览 / 每日 / 会话 / 任务。
2. **命令行：任意 JSON → xlsx**（与番茄钟无关的通用小工具，换任何项目都能直接用）：

   ```bash
   npm run gen -- --json sample.json --out output/out.xlsx --sheet Data --header
   npm run demo        # 端到端演示：扫描 Cordis 包清单生成 xlsx 并回读校验
   ```

3. **写自己的插件复用 `ctx.table`**（不要绕开它直接调 Python）：

   ```js
   import { Service } from 'cordis'
   export class MyExport extends Service {
     static provide = 'myexport'
     static inject = ['store', 'timer']      // 只把**必需**依赖写进 inject
     async dump() {
       const t = this.ctx.get('table')        // 可选依赖：用 ctx.get，不要写进 inject
       if (!t) throw new Error('未启用表格能力：装好 Python + openpyxl 后重启即自动启用')
       const file = 'output/dump.xlsx'
       await t.createWorkbook(file, '数据')
       await t.writeRows(file, '数据', 1, 1, [['列A', '列B'], [1, 2]])
       await t.styleHeader(file, '数据', 1, 2)
       await t.save(file)
       return { file }
     }
   }
   ```

   > 可选依赖**写进 `inject` 会让插件永远停在 PENDING**（README 尾部「设计要点」有实测记录），
   > 所以允许降级的能力一律 `ctx.get('table')` 运行时取。

**移植到别的项目**：`src/plugins/table.mjs` + `src/core/bridge.mjs` + `python/rpc_server.py` 三件套，
清单里加一条 `{ "id": "table", "name": "./src/plugins/table.mjs" }` 即可。
解释器不硬编码任何盘符（PATH 扫描 + 常见安装目录，可用 `config.pythonBin` / `PYTHON_BIN` 覆盖），换机换系统都不用改代码。

三条纪律（都是踩过的坑）：

- **stdio 只走协议**：stdout 只允许一行一个 JSON-RPC 对象，被调库的任何 `print()` 都会污染通道 ——
  worker 用 `contextlib.redirect_stdout(sys.stderr)` 兜住，别去掉。
- **两端必须同为 UTF-8**：Windows 中文环境里 Python 默认按 gbk/cp936 解 stdio，UTF-8 中文会先变乱码、
  再退化成孤立代理字符，一路潜伏到 openpyxl 落盘才以 `surrogates not allowed` 炸出来。
  桥侧注入 `PYTHONIOENCODING=utf-8`，worker 侧 `_force_utf8_stdio()` 兜底，两道都要。
- **读回来的值必须能过 JSON，且响应序列化要在 try 内**：Excel 里的日期是 `datetime`、高精度数是
  `Decimal`、二进制是 `bytes`，`json.dumps` 一个都不认。worker 用 `_json_default` 统一转成
  ISO 串/数字/base64，并且把序列化也放进 `try` —— 否则**一个日期单元格就能让 `json.dumps` 抛错、
  掀翻主循环带走整个 worker**，此后所有调用都变成 `python worker exited`（这个坑真实发生过，别改回去）。
- **工作簿按 `path` 缓存在 Python 内存**：写完必须 `save`（或 `close`）才落盘；同一 path 复用同一份工作簿。

## 番茄工作法规则（落地实现）

| 规则 | 实现 |
|---|---|
| 专注 25 分钟 / 短休 5 分钟 / 每 4 个番茄长休 15–30 分钟 | `settings.focusMs / shortMs / longMs / longEvery`，均可在 UI 设置面板改 |
| 番茄不可分割，提前结束不算完成 | `skip` 记录 `completed=false, reason='skipped'`；`round` 不增加 |
| 中断即作废 | `void` 记录 `reason='void'`，当前番茄归零 |
| 系统休眠/进程挂起不静默补时 | tick 空档 > 10s 判定为挂起 → 当前番茄按作废处理（`reason='suspend'`） |
| 退出期间到点不算完成 | 重启恢复时记录 `reason='shutdown'` 且 `completed=false` |

## 计时为什么准

1. **不累加 tick 次数**：进度永远现算 `remaining = endAt - now`，`endAt` 是绝对时刻。
2. **不用 `setInterval`**：递归 `setTimeout` 且对齐到整秒边界（目标时间固定），不累积漂移。
3. **时钟分工**：`Date.now()`（墙钟）负责开始/结束时刻与落盘；
   `performance.now()`（单调钟）只用于调度耗时观测。
4. **前端不推进时间**：SSE 每秒下发 `endAt` 与服务端 `now`，浏览器按本地插值渲染。

## 功能（P0 + P1）

**P0**：番茄钟核心 —— 专注/短休/长休自动流转、开始/暂停/继续/重置/跳过/作废、
可配置时长与长休间隔、自动开休息、提示音与滴答声、桌面通知、亮/暗主题。

**P1**：任务清单（番茄归属，实际/预估对比）、统计面板（今日/连续天数/最近 7 天柱状图/
12 周热力图/每任务进度条）、中断记录（内部/外部 + 计划外事件列表）、数据导出/导入 JSON。

**P2**：周报 xlsx 导出（复用 Python OpenPyXL，四张表：概览/每日/会话/任务；日期是 Excel 原生日期、
带数字格式、表头冻结）、白噪音与棕噪音（Web Audio 实时合成）、迷你窗（独立小窗只显示倒计时）、
Windows 原生气泡通知（best-effort）、`pomodmer.bat` 自愈式启动器。

**P3（可选）**：Electron 桌面壳 —— 托盘常驻、窗口置顶、`Ctrl+Alt+Space` 全局快捷键、
原生阶段通知；装不了 Electron 也不影响浏览器模式。

## HTTP API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/state` | 全量快照（settings / tasks / runtime / 今日统计） |
| GET | `/api/events` | SSE：`hello` 快照 + 每秒 `tick` + `phase` / `session` / `settings` / `interrupt` / `imported` 事件 |
| POST | `/api/timer/start` `pause` `resume` `toggle` `reset` `skip` `void` | 控制 |
| PATCH | `/api/settings` | 改时长与开关（`focusMs` / `theme` 等，非法值被拒） |
| GET / POST | `/api/tasks` | 任务列表 / 新增 |
| PATCH / DELETE | `/api/tasks/:id` | 改任务 / 删任务 |
| PATCH | `/api/tasks/current` | 设当前任务（番茄完成后自动计到它头上） |
| GET | `/api/sessions?limit=100` | 历史会话 |
| GET | `/api/stats?days=7&weeks=12` | 统计：today / streak / recent / heat / byTask / total |
| GET / POST | `/api/unplanned` | 计划外事件列表 / 记录（`kind`: internal\|external） |
| DELETE | `/api/unplanned/:id` | 删除一条中断记录 |
| GET / POST | `/api/report` | 周报能力探测 / 生成 xlsx（未启用时 GET 给提示、POST 返回 501） |
| GET | `/api/export` | 导出全部数据（JSON 附件） |
| POST | `/api/import` | 导入数据（校验失败返回 400；导入后停在暂停态） |

> 路由顺序坑：`/api/tasks/current` 必须排在 `/api/tasks/:id` 之前，否则会被当成 `id='current'` 的任务。

## 数据

`data/store.json`（已 gitignore，属个人专注记录）：

```jsonc
{
  "settings": { "focusMs": 1500000, "shortMs": 300000, "longMs": 900000, "longEvery": 4, ... },
  "tasks":    [ { "id", "title", "estimate", "spent", "done", "createdAt" } ],
  "sessions": [ { "id", "type", "taskId", "plannedMs", "startAt", "endAt", "actualMs", "completed", "interrupts", "reason" } ],
  "unplanned":[ { "id", "kind": "internal|external", "note", "at", "phase", "taskId" } ],
  "runtime":  { "phase", "running", "endAt", "remainingMs", "startedAt", "plannedMs", "round", "currentTaskId", "interrupts" }
}
```

写入是**原子**的（写 `.tmp` 再 `rename`）；数据文件损坏时自动备份为 `.broken-<ts>` 并回退默认配置。

## 目录

```
pomodmer/
├─ LICENSE / README.md / docs/POMODORO-PLAN.md
├─ cordis.json              插件清单（默认：store + timer + http）
├─ cordis.table.json        插件清单（可选：仅 table，xlsx 能力）
├─ cordis.with-xlsx.json    插件清单（可选：番茄钟 + table + report，启用周报）
├─ pomodmer.bat             自愈式启动器（Windows 双击即用）
├─ electron/                main.cjs 主进程 / start.mjs 启动器 / make-icon.mjs + icon.png
├─ web/                     index.html / app.js / style.css（零框架前端）
├─ python/rpc_server.py     OpenPyXL 工作者（可选能力用）
└─ src/
   ├─ pom.mjs               应用入口
   ├─ boot.mjs              宿主启动/关停（入口/CLI/测试共用）
   ├─ core/bridge.mjs       JsonRpcBridge（stdio 行分隔 JSON-RPC）
   ├─ plugins/store.mjs     StoreService（ctx.store）
   ├─ plugins/timer.mjs     TimerService（ctx.timer）
   ├─ plugins/http.mjs      HttpService（ctx.http）
   ├─ plugins/table.mjs     TableService（ctx.table，可选）
   ├─ demo.mjs / cli.mjs    xlsx 演示与命令行工具（走 cordis.table.json）
   ├─ _smoke.mjs            Cordis 内核冒烟
   └─ _smoke_pom.mjs        番茄钟端到端冒烟（真实 HTTP）
```

## 设计要点（Cordis 4.0.0-rc.10 实测）

- `ctx.plugin()` / `loader.create()` 的效果是**异步执行**的，注册后必须 `await`，服务才会挂上。
- 服务的初始化用 `[Service.init]()`，返回清理函数（或 Promise of 清理函数），
  fiber dispose 时自动执行 —— 定时器、HTTP server、SSE 连接都在这里回收。
- Cordis **没有 `ctx.stop()`**；根 fiber 的 dispose 语义是"重启"。正确关停 =
  逆序 `await entry.fiber.dispose()` 顶层入口（`boot.mjs` 的 `stopHost` 已封装）。
- 服务间只通过 `ctx.<key>` 查找，不 import 具体实现；依赖用 `static inject = [...]` 声明。
  **可选依赖不要写进 `inject`**（否则插件永远 PENDING），用 `ctx.get('table')` 在用的时候取。

## Electron 踩坑（实测）

- 环境里若有 `ELECTRON_RUN_AS_NODE=1`，`electron.exe` 会退化成纯 Node：
  `require('electron')` 返回的是**二进制路径字符串**，症状是 `app.whenReady()` 报 undefined。
  该变量在启动前就被读取，main 进程里改来不及 → 用 `electron/start.mjs` 在 spawn 前删掉它。
- Electron 主进程**不支持** `import { app } from 'electron'` 的命名导出（44.4.5 实测），
  本项目 `package.json` 是 `type: module`，所以主进程写成 `main.cjs`（CommonJS）。
- 国内安装必须配镜像：`ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/`（约 100MB）。

## 路线图

- **P0（已完成，tag v2.0.0）**：Cordis 宿主 + store/timer/http 三插件 + 本地 Web UI + 端到端冒烟。
- **P1（已完成，tag v2.1.0）**：任务清单 + 番茄归属、统计与热力图、中断记录、亮/暗主题、快捷键、导入导出。
- **P2（已完成，tag v2.2.0）**：周报 xlsx（复用 ctx.table）、白噪音/棕噪音、迷你窗、原生通知、`pomodmer.bat` 启动器。
- **P3（已完成，tag v2.2.0）**：Electron 桌面壳（托盘 / 置顶 / `Ctrl+Alt+Space` / 原生通知），仅 devDependencies，装不了也不影响浏览器模式。

详见 [`docs/POMODORO-PLAN.md`](./docs/POMODORO-PLAN.md)。
