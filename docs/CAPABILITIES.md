# Pomodmer 完整能力说明

> 对应版本 `pomodmer@2.2.0`（表格能力 P1–P4 全部完成态）。
> 本文以**代码为准**逐条列清"有什么、怎么用、边界在哪"；每条都能在源码里找到对应实现。
> 规划与执行记录见 [`POMODORO-PLAN.md`](./POMODORO-PLAN.md)；快速上手看仓库根 [`README.md`](../README.md)。

---

## 0. 一句话说清它是什么

跑在本机的番茄钟：**计时权威在 Node 服务端**（`endAt` 绝对时刻），浏览器只负责渲染；
数据存单文件 JSON；在此之上复用了从 `cordis-table-app` 继承的 **Python + OpenPyXL 表格能力**，
做成"导出 → 在 Excel 里改 → 导回"的完整闭环。

---

## 1. 运行形态与依赖

| 维度 | 现状 |
|---|---|
| 运行时 | Node.js 22（实测 22.22.2），`type: module` |
| npm 依赖 | 3 个：`cordis`、`@cordisjs/plugin-loader`、`@cordisjs/plugin-logger-console`；`electron` 是可选 devDependency |
| 表格能力依赖 | Python 3 + `openpyxl`（可选；Pillow 仅权威源的渲染方法需要，且是**懒导入**） |
| 端口 | 默认 `127.0.0.1:5173`，只监听回环地址（不对外暴露） |
| 进程模型 | 单 Node 宿主进程 +（启用表格能力时）1 个常驻 Python worker 子进程 |
| 数据 | 单文件 JSON，原子写（写 `.tmp` 再 rename） |

---

## 2. 插件拓扑与生命周期

宿主由 `src/boot.mjs` 启动：`new Context()` → 接 console 日志导出器 → 装 Loader → 按清单加载插件 → `loader.await()`。
关停走"逆序 `await entry.fiber.dispose()`"，各服务的 `[Service.init]()` 返回的清理函数在此回收定时器 / HTTP / SSE / Python worker。

| 服务 | 文件 | 必选？ | 职责 |
|---|---|---|---|
| `ctx.store` | `src/plugins/store.mjs` | 必选 | 持久化层：JSON 原子写、坏档备份回退、**唯一写入口** `update(fn)` |
| `ctx.timer` | `src/plugins/timer.mjs` | 必选 | 番茄钟状态机 + 权威计时 + 任务 / 中断 / 统计 |
| `ctx.http` | `src/plugins/http.mjs` | 必选 | `node:http` 静态托管 `web/` + REST + SSE |
| `ctx.table` | `src/plugins/table.mjs` | 可选 | 表格服务：JSON-RPC stdio 桥 → Python OpenPyXL worker（**由权威源同步，勿手改**） |
| `ctx.report` | `src/plugins/report.mjs` | 可选 | xlsx 双向：周报 / 全量导出 + 回灌导入 |
| Electron 壳 | `electron/main.cjs` | 可选 | 托盘 / 置顶 / 全局快捷键 / 原生通知，加载同一份 `web/` |

依赖声明纪律：只把**必需**依赖写进 `static inject`；`table` 是可选依赖，`report` 一律用
`ctx.get('table')` 运行时取（写进 `inject` 会让插件永远停在 PENDING）。

---

## 3. HTTP API 全量

所有接口都在 `127.0.0.1` 上；未列出的路径走静态托管，越界路径返回 403。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/state` | 全量快照：`settings` / `tasks` / `runtime`，另含 `today` 统计 |
| GET | `/api/events` | SSE：连接即下发 `hello` 快照，运行中每秒 `tick`，阶段事件 `phase`/`session`/`settings`/`interrupt`/`imported`/`report` |
| POST | `/api/timer/start` | 开始专注（可带 `taskId`） |
| POST | `/api/timer/pause` | 暂停（冻结剩余时间到服务端） |
| POST | `/api/timer/resume` | 继续 |
| POST | `/api/timer/toggle` | 开始/暂停切换（全局快捷键走这条） |
| POST | `/api/timer/reset` | 重置当前阶段 |
| POST | `/api/timer/skip` | 跳过（记 `completed=false, reason='skipped'`，不计番茄） |
| POST | `/api/timer/void` | 作废当前番茄（记 `reason='void'`，round 不变） |
| PATCH | `/api/settings` | 改时长与开关，非法值被拒（`focusMs` 最小 1s、`theme` 只认 light/dark 等） |
| GET | `/api/tasks` | 任务列表 |
| POST | `/api/tasks` | 新增任务（`title`/`estimate`） |
| PATCH | `/api/tasks/:id` | 改任务（`title`/`estimate`/`done`） |
| DELETE | `/api/tasks/:id` | 删任务（若为当前任务则一并清空引用） |
| PATCH | `/api/tasks/current` | 设当前任务（番茄完成后 `spent` 自增到它头上） |
| GET | `/api/sessions?limit=100` | 历史会话（按时间倒序） |
| GET | `/api/stats?days=7&weeks=12` | `today` / `streak` / `recent` / `heat` / `byTask` / `total` |
| GET | `/api/unplanned` | 计划外事件列表 |
| POST | `/api/unplanned` | 记一条（`kind`: `internal`\|`external`，非法值归一化为 `internal`） |
| DELETE | `/api/unplanned/:id` | 删除一条 |
| GET | `/api/report` | 能力探测：`{ available, hint }`（未启用时 hint 说明是哪种原因） |
| POST | `/api/report` | 生成周报并返回**磁盘路径**（脚本/定时任务用） |
| GET | `/api/export` | 导出全部数据（JSON 附件，可被 `/api/import` 再吃回去） |
| GET | `/api/export?format=xlsx` | xlsx 附件下载：`scope=all`（默认，5 张表）/ `scope=weekly&days=N`（4 张表）；响应头 `X-Pomodmer-Info` 带摘要 |
| POST | `/api/import` | JSON **替换式**导入（校验失败 400；导入后一律停在暂停态） |
| POST | `/api/import/xlsx?mode=preview\|apply` | xlsx **去重追加**回灌：`preview` 只算不写，`apply` 才落库 |

路由顺序坑（已在代码里规避）：`/api/tasks/current` 必须排在 `/api/tasks/:id` 之前。

---

## 4. 数据模型与磁盘文件

`data/store.json`（已 gitignore，属个人专注记录）：

```jsonc
{
  "version": 1,
  "settings": {
    "focusMs": 1500000, "shortMs": 300000, "longMs": 900000, "longEvery": 4,
    "autoStartBreak": true, "autoStartFocus": false,
    "sound": true, "tick": false, "notify": true, "nativeToast": false,
    "ambient": "off",          // off | white | brown
    "theme": "light"           // light | dark
  },
  "tasks":    [ { "id", "title", "estimate", "spent", "done", "createdAt" } ],
  "sessions": [ { "id", "type", "taskId", "plannedMs", "startAt", "endAt", "actualMs", "completed", "interrupts", "reason" } ],
  "unplanned":[ { "id", "kind": "internal|external", "note", "at", "phase", "taskId" } ],
  "runtime":  { "phase", "running", "endAt", "remainingMs", "startedAt", "plannedMs", "round", "currentTaskId", "interrupts" }
}
```

- `sessions[].reason` 取值：`void` / `skipped` / `suspend`（tick 空档 > 10s 判为系统挂起）/ `shutdown`（退出期间到点，不静默补时）/ `null`（正常完成）。
- 写入是**原子**的；数据文件损坏时自动备份为 `.broken-<ts>` 并回退默认配置。
- 其它落盘位置：`output/*.xlsx`（导出产物，已 gitignore）、`tools/table-kit.lock.json`（表格三件套来源锁，**入仓**）。

---

## 5. Web UI 全部功能（零框架，`web/` 三文件）

| 区域 | 能力 |
|---|---|
| 计时区 | 进度环 + 倒计时（按服务端 `endAt` 本地插值）；按钮：开始/暂停/继续、重置、跳过、作废、迷你窗；阶段标签与配色（专注/短休/长休） |
| 任务清单 | 增删、选中为当前任务、标记完成、显示 `实际/预估` 番茄数 |
| 统计 | 今日 / 连续天数 / 最近 7 天柱状图 / 12 周热力图 / 每任务进度（**纯 SVG 手绘**，不引图表库） |
| 中断记录 | 记内部/外部中断 + 备注，列表倒序，可删 |
| 设置 | 专注/短休/长休时长、长休间隔、自动开始休息/专注、提示音、滴答声、浏览器通知、Windows 原生气泡、白噪音（关/白/棕）、主题 |
| 数据区 | 导出 JSON、导出 xlsx、导入 JSON、**回灌 xlsx**（先预览"新增/更新/跳过"再确认）、导出周报 xlsx |
| 快捷键 | 空格 = 开始/暂停（输入框/按钮聚焦时不触发）；任务标题与中断备注里 Enter 提交 |
| 实时性 | SSE 驱动：计时、阶段切换、统计、导入结果都会自动刷新 |

白噪音与提示音用 Web Audio **实时合成**，不带任何音频资产；迷你窗是独立小窗，只显示倒计时并轮询 `/api/state`。

---

## 6. 启动方式 / 配置开关

```bash
npm run pom                    # 启动（自动探测表格能力；自动开浏览器）
node src/pom.mjs --port 8080   # 换端口
node src/pom.mjs --no-open     # 不开浏览器
node src/pom.mjs --config cordis.table.json   # 指定插件清单
pomodmer.bat                   # Windows 双击即用（缺依赖自动 npm install；ASCII-only 以免 cmd 代码页乱码）
```

| 环境变量 | 作用 |
|---|---|
| `POMODMER_PORT` / `POMODMER_HOST` | 监听端口 / 地址 |
| `POMODMER_OPEN=0` | 不自动开浏览器 |
| `POMODMER_CONFIG` | 指定插件清单（优先于自动探测） |
| `POMODMER_NO_XLSX=1` | 主动关闭表格能力（不拉起 Python） |
| `POMODMER_TRACE` | 打开计时循环的耗时日志（`timer: tick cost=…`） |
| `PYTHON_BIN` | 指定 Python 解释器（优先于自发现；也可用配置项 `table.config.pythonBin`） |
| `CORDIS_PKG_SRC` | 仅 `npm run demo`：指定要扫描的源码目录 |

**插件清单一览**：`cordis.json`（默认：store+timer+http）、`cordis.table.json`（仅 table）、
`cordis.with-xlsx.json`（番茄钟 + table + report）。启动时的选择顺序是
**显式 `--config` > `POMODMER_CONFIG` > 自动探测 > `cordis.json`**，每次启动都会在日志里打印"选了哪个清单 + 为什么"。

表格能力自动探测：扫"项目 `.venv` → `py -3` → PATH → 用户级/系统级/各盘符常见落点"，
挑第一个能 `import openpyxl` 的解释器（带 memo 与超时预算，探不到就安静退回纯番茄钟）。

---

## 7. 表格能力三件套（24 个 RPC 方法）

`src/core/bridge.mjs` + `src/plugins/table.mjs` + `python/rpc_server.py` 合称三件套。
协议：一行一个 JSON-RPC 2.0 对象走 stdio；**stdout 只承载协议**，日志与异常栈走 stderr。

| 分类 | 方法（JS 侧 `ctx.table.*`） |
|---|---|
| 工作簿 | `ping` `createWorkbook` `addSheet` `save` `close` |
| 写入 | `writeRows(…, { colTypes })`（`text`/`number`/`datetime`/`date`/`time`，把 ISO 串还原成 Excel 原生类型） `writeCell` `setCellText` |
| 样式 | `styleHeader` `setColumnWidth` `setNumberFormat` `freezePanes` `setCellFill` `setBorders` `setComment` |
| 结构 | `mergeCells` |
| 读取 | `readSheet`（日期以 ISO 串返回） `sheetMeta`（冻结窗格 / 数字格式 / 值类型 / 合并区 / 批注） |
| 地图/VTT（本项目未使用） | `readMap` `renderMapPng` `renderToken` `genDungeon` `exportDonjon` `importDonjon` |

**单一权威源 + 来源锁**（防两个仓库再次静默分叉）：

```bash
npm run sync:kit     # 从 cordis-table-app 同步三件套，并更新 tools/table-kit.lock.json
npm run check:kit    # 体检：锁↔本地（权威源在场时再比对源），不一致即报错
```

`tools/table-kit.json` 声明同步清单；`tools/table-kit.lock.json` 记录**来源仓库 + 提交号 + 每文件 sha256**
（哈希按行尾归一计算，`core.autocrlf` 差异不会被误判成漂移）。手改三件套而不走同步，
`check:kit` 与冒烟第 13 节会立刻报红。

**三条纪律**：stdio 只走协议（被调库的 `print()` 会污染通道）；两端必须同为 UTF-8
（Windows 中文环境默认 gbk，会退化成孤立代理字符并炸在落盘那一刻）；
读回的原始值必须能过 JSON，且响应序列化要在 `try` 内（否则一个日期单元格就能弄死整个 worker）。

---

## 8. 命令行工具

| 命令 | 说明 |
|---|---|
| `npm run smoke` | 冒烟：`src/_smoke.mjs`（内核）+ `src/_smoke_pom.mjs`（番茄钟与表格能力端到端） |
| `npm run gen -- --json x.json --out o.xlsx --sheet Data --header` | 通用 JSON → xlsx（数组的数组或对象数组自动取表头） |
| `npm run demo` | 端到端演示：扫描 Cordis 包清单生成 xlsx 并读回校验 |
| `npm run icon` | 生成 Electron 图标 |
| `npm run electron` | 启动 Electron 桌面壳 |
| `npm run sync:kit` / `check:kit` | 表格三件套同步 / 体检 |

---

## 9. Electron 桌面壳（可选）

托盘常驻（关闭窗口=最小化到托盘，计时继续，气泡提示）· 窗口置顶（托盘菜单勾选）·
全局快捷键 `Ctrl+Alt+Space` = 开始/暂停 · 阶段切换原生通知 · 加载同一份 `web/`。
装不了 Electron 不影响浏览器模式；`ELECTRON_RUN_AS_NODE` 存在时 `electron/start.mjs` 会在 spawn 前清掉它。

---

## 10. 测试与验收

- `npm run smoke` → 期望 **ALL PASS（EXIT=0）**：`src/_smoke.mjs`（Cordis 内核，6 项输出）+
  `src/_smoke_pom.mjs`（**25 个测试节次 + 结果汇总，121 处 `ok(...)` 断言**），
  覆盖启动 → 状态 → 设置 → 计时流转 → 跳过/作废 → 任务 CRUD → 静态资源与路径穿越 →
  SSE → 任务归属 → 中断 CRUD → 统计 → 导出导入 → 主题 → 落盘与重启恢复 →
  周报 xlsx → xlsx 数据形态 → 联合套件能力 → 全量导出 → 回灌（预览/幂等/往返不翻倍）→
  导出面（scope/days）→ 资产自检（含文档存在性）→ 来源锁 → 自动启用决策。
- 权威源 `cordis-table-app`：`npm test`（内核冒烟 + 地图演示 + 程序化生成 + DonJon 互通往返 600 格比对）。
- 数据落 `os.tmpdir()`、端口由系统分配，冒烟不污染真实 `data/store.json`、不抢端口。

---

## 11. 已知限制与风险（诚实清单）

| # | 限制 / 风险 | 影响 |
|---|---|---|
| 1 | `JsonRpcBridge.call()` **没有超时**，worker 卡住时 Promise 永不 settle | 导出/回灌请求会永久挂起，UI 停在"正在生成…"，只能重启宿主；**尚未修** |
| 2 | 单 worker、调用串行 | 一次大导出会阻塞同一 worker 上的其它表格调用 |
| 3 | Python 侧 `WORKBOOKS` 按 path 常驻内存 | 长期运行且频繁导入会缓慢占用内存（`close` 会顺带落盘，故未主动调用） |
| 4 | xlsx 时间只有秒精度 | 回灌改用 ±2 秒容差去重；日期按**本机时区**渲染，跨时区/DST 未专门测试 |
| 5 | 回灌只认本应用导出的表头名 | 外来自定义表头需先改列名（或后续加列映射配置） |
| 6 | 回灌**不做删除** | Excel 里删掉的行不会从库里消失（有意为之，避免误删历史）；要清空请用 JSON 替换式导入 |
| 7 | 回灌的 `plannedMs` 用 `actualMs` 兜底 | xlsx 没有"计划时长"列，故导入的会话"实际/计划"恒为 1:1 |
| 8 | 数据是单文件 JSON，无多实例锁 | 同时运行两个宿主指向同一 `data/store.json` 会互相覆盖 |
| 9 | 无浏览器端点击级自动化测试 | 冒烟覆盖 HTTP 与静态自检；UI 交互靠手工验证 |

---

## 12. 文档与源码地图

| 想了解 | 看这里 |
|---|---|
| 快速上手 / 常用命令 | [`README.md`](../README.md) |
| 完整能力与边界 | 本文 |
| 规划、决策、执行记录 | [`POMODORO-PLAN.md`](./POMODORO-PLAN.md) |
| 宿主启动关停 | `src/boot.mjs` |
| 权威计时状态机 | `src/plugins/timer.mjs` |
| REST/SSE 与静态托管 | `src/plugins/http.mjs` |
| 表格服务与导出/回灌 | `src/plugins/table.mjs`、`src/plugins/report.mjs` |
| Python worker 协议 | `python/rpc_server.py` |
| 三件套同步工具 | `tools/sync-table-kit.mjs` + `tools/table-kit.json` |
