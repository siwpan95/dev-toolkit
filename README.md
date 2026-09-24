# Cordis 表格小应用（Cordis 内核 + OpenPyXL）

基于 **Cordis（Node.js 插件框架）作为应用内核**，
表格能力交给 **Python + OpenPyXL**，两者通过 **JSON-RPC stdio 桥** 连接。

> 即 `cordis-host-python-bridge` 模式：Cordis 宿主负责编排/插件化，Python 进程负责实际
> 的 Excel 读写；宿主不碰 Excel，Python 不碰编排。

## 许可证

本项目以 **MIT License** 开源（见 [LICENSE](./LICENSE)），版权归 `siwpan` 所有。
可自由使用、修改、分发，仅需保留版权与许可声明。

## 架构

```
Cordis 宿主 (Node.js)
  ├─ Context                      src/boot.mjs       进程根上下文
  ├─ @cordisjs/plugin-loader      声明式插件宿主（读 cordis.json 的 entries）
  ├─ ConsoleExporter              日志导出器（否则 loader 失败静默）
  └─ TableService extends Service 挂到 ctx.table     src/plugins/table.mjs
        └─ JsonRpcBridge (stdio)  src/core/bridge.mjs
              └─ python/rpc_server.py   OpenPyXL 工作者（零依赖 stdlib 协议层）
```

- `cordis.json` 是插件清单（唯一条目入口）：`{ "entries": [ { id, name, config } ] }`，
  其中 `name` 是相对项目根（baseUrl）的插件模块路径。
- 通过 loader 加载的插件 = `TableService`（构造器插件），它 `provide('table')`，对外暴露
  `ctx.table` 的一系列表格方法（createWorkbook / writeRows / styleHeader / readSheet / save ...）。
- 这些方法经 `JsonRpcBridge` 以"一行一 JSON-RPC"转发给 Python worker，由 OpenPyXL 执行。

## 源码来源

Cordis 内核由 `npm install` 安装（`cordis` / `@cordisjs/plugin-loader` / `@cordisjs/plugin-logger-console`），
与 `package.json` 中声明的版本一致。`vendor/cordis-main/` 仅用于在本机保留一份框架源码镜像，
**已被 `.gitignore` 排除，不随仓库分发**（第三方内核源码不入仓，见仓库卫生门禁）。

## 运行

```bash
# 进入本项目根目录（任意路径均可，无盘符硬编码）
npm install            # 装 cordis / loader / logger-console（已装可跳过）

# 演示：生成 output/cordis-packages.xlsx（含两张表）
npm start

# 通用生成：JSON -> xlsx
npm run gen -- --json sample.json --out output/sample.xlsx --sheet Data
```

> **Python 解释器自动发现**（无需硬编码路径，换机即用）：
> 1. `cordis.json` 里 table 条目的 `config.pythonBin`；
> 2. 环境变量 `PYTHON_BIN`；
> 3. 扫描系统 `PATH` + 常见安装目录（Windows `C:/Python3XX`、`%LOCALAPPDATA%/Programs/Python/...`，
>    macOS/Linux `/usr/bin/python3`、`/opt/homebrew/bin/python3` 等），挑第一个能 `import openpyxl` 的；
> 4. 兜底回退到 `PATH` 里的 `python3` / `python`。
>
> 推荐直接 `pip install openpyxl`（≥3.1），然后让程序自动发现即可。

## 设计要点（与 Cordis rc.10 实测一致）

- `ctx.plugin()` / `loader.create()` 的效果是**异步执行**的，注册后必须 `await` 一次，服务才会挂上。
- Cordis **没有 `ctx.stop()`**；根 fiber 的 dispose 语义是"重启"。正确关停 = 逆序 `await entry.fiber.dispose()`
  顶层入口，触发各服务的清理函数（此处 = 杀掉 Python worker），再兜底强杀。
- Python worker 的 stdout **只走 JSON-RPC**，所有日志/异常栈走 stderr，避免污染协议通道。
- 每个 RPC 方法 try/except 兜住，返回 JSON-RPC error，保证子进程不死。

## 目录

```
cordis-table-app/
├─ LICENSE                   MIT 许可证
├─ cordis.json              插件清单（声明式入口）
├─ python/rpc_server.py     OpenPyXL 工作者（JSON-RPC over stdio）
├─ src/
│  ├─ boot.mjs              宿主启动/关停（入口共用）
│  ├─ core/bridge.mjs       JsonRpcBridge（stdio 行分隔 JSON-RPC）
│  ├─ plugins/table.mjs     TableService（挂 ctx.table，含 Python 自发现）
│  ├─ demo.mjs              端到端演示（包清单表 + 演示表）
│  ├─ cli.mjs               通用 JSON -> xlsx 工具
│  └─ _smoke.mjs            冒烟测试（Cordis 内核可用性）
├─ vendor/cordis-main/      Cordis 内核源码镜像（可选，gitignore 排除）
└─ output/                 生成的 xlsx 产物（gitignore 排除）
```
