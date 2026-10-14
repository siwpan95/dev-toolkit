# helloworld-cordis

把 `../helloworld/` 下 **76 种语言** 的 Hello, World! 源文件，收编成 **Cordis 的一等组件**。

源文件一个字节都不改；怎么把它们跑起来，全部由本项目负责 —— 与参考项目
[`lab/chess-cordis`](https://gitee.com/siwpan/lab) 的架构边界保持一致（引擎零依赖、
cordis-unaware，胶水只存在于 harness 层）。

## 一句话原理

> **空间维**：挂载哪些语言 = 数据（`config/cordis.yml`），不是代码。
> **时间维**：任何语言都能在运行时摘掉/装回，它的副作用自动回滚。

## 快速开始

```bash
cd helloworld-cordis
npm install

node tools/bootstrap.mjs   # 扫描 helloworld/ → 生成 config/cordis.yml（换机器后必须重跑）
npm start                  # 跨语言共识校验（退出码 0 = 全绿）
npm run stress             # 时间维热插拔压力测试
npm run timing             # 跨语言耗时表
npm run probe              # 单独看工具链探测结果
```

## 目录

```
config/
  cordis.yml       ★ 唯一的组合真相：78 条组件声明（含 2 个对照变体）
  languages.yml      语言知识库 + 本机工具链探测结论
src/
  host.js            入口：Context → loader → 清单 → harness
  loader.mjs         把清单喂给真正的 @cordisjs/plugin-loader
  registry.mjs       HelloRegistry（共享单例，不是 Service —— 见文件头注释）
  harness.mjs        HelloHarness（Service）：跨语言共识校验
  probe.mjs          工具链探测
  stress.js  timing.js
  ports/
    embedded.mjs     进程内载体：node:vm / node:sqlite / fengari(Lua)
    subprocess.mjs   一次性子进程载体（解释器 / 编译型语言）
    gateway.mjs      常驻 JSON-stdio 网关载体
    common.mjs       输出归一化、模板替换、带可逆效应的注册
drivers/
  gateway.py         常驻 worker（harness 胶水）
tools/
  lang-db.mjs        「语言 → 运行方式」知识库
  bootstrap.mjs      扫描 + 探测 + 生成两份 yml
```

## 三种载体

| 载体 | 谁在里面跑 | 成本 | 本机的实例 |
|------|-----------|------|-----------|
| `embedded` | 运行时就在 Cordis 主进程里 | 零 IPC，仅计算 | JavaScript(vm)、SQL(node:sqlite)、Lua(fengari) |
| `subprocess` | 每次调用 fork/exec 一个解释器 | 每次付一遍冷启动 | Python、TypeScript、PowerShell、Bash、Perl、VB.NET |
| `gateway` | 常驻 worker，握手一次后反复调用 | 冷启动只付一次 | Python 热版（`drivers/gateway.py`） |

> **关于 `config/*.yml`** —— 两份清单含本机绝对路径，且可由 `tools/bootstrap.mjs` 逐台机器重新生成，
> 因此**不入库**（已在根 `.gitignore` 排除）。新克隆下来先 `npm install`，再跑一次 `node tools/bootstrap.mjs`。

## 往里加一种语言

1. 把源文件丢进 `../helloworld/`；
2. 在 `tools/lang-db.mjs` 补一条：`run` / `build` 模板 + `requires`（工具链或 `npm:<pkg>`）；
3. `node tools/bootstrap.mjs`。

宿主、加载器、校验器一行都不用改。

详见 [`UNIFIED_ARCHITECTURE_REPORT.md`](./UNIFIED_ARCHITECTURE_REPORT.md)。
