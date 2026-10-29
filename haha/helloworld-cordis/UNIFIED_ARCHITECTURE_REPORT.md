# Unified Multi-Language Hello, World! — A Cordis Architecture Report

**项目：** `helloworld-cordis`
**宿主：** `haha/helloworld/`（76 个源文件，每种语言一份 Hello, World!）
**日期：** 2026-10-14
**参考架构：** [`siwpan/lab` → `chess-cordis`](https://gitee.com/siwpan/lab)、[`siwpan/weiqi_lab` → `harness`](https://gitee.com/siwpan/weiqi_lab)
**状态：** ✅ 已跑通 —— 直接使用真实 `cordis@4.0.0-rc.10` + `@cordisjs/plugin-loader@1.0.0-rc.7`，
无 vendored 副本；`helloworld/` 下源文件**零改动、零依赖、cordis-unaware**；
本机实测 **9 种语言真正执行通过**，连同 2 个受控对照变体共 **11 个组件**，全部命中黄金值；
`src/host.js` 与 `src/stress.js` 均退出 `0`。

---

## 1. 结论先行

`helloworld/` 目录原本是 **76 个互不相干的静态文件**：每种语言一个 Hello, World!，
没有一个脚本能把它们跑起来、也无法验证它们是对的。

现在它们被统一在一套 Cordis 组合架构下：

- 每种语言是一个**一等 Cordis 组件**，由真正的 `@cordisjs/plugin-loader` 按
  `config/cordis.yml` 声明式挂载；
- 挂载哪些语言是**数据**，不是代码（空间维可组合性）；
- 任何语言都能在**运行时**被摘掉再装回，其副作用（注册表项、OS 子进程）自动回滚
  （时间维可组合性 / 可逆效应）；
- 一致性判据是 **语言无关常量 `Hello, World!`**，性质上等价于参考项目里的 perft 黄金值。

本机实测结果（`node src/host.js`）：

```
=== Cordis HelloHarness: 跨语言 Hello, World! 共识校验 ===
黄金值 = "Hello, World!"   已挂载组件 = 11

  id            语言           载体          耗时    输出
  --------------------------------------------------------------------------
  bash           Bash           subprocess     406ms  "Hello, World!"
  perl           Perl           subprocess     249ms  "Hello, World!"
  powershell     PowerShell     subprocess    1907ms  "Hello, World!"
  python         Python         subprocess     895ms  "Hello, World!"
  typescript     TypeScript     subprocess     321ms  "Hello, World!"
  vb             VB.NET         subprocess     301ms  "Hello, World!"
  javascript-fork JavaScript     subprocess     302ms  "Hello, World!"
  javascript     JavaScript     embedded         2ms  "Hello, World!"
  lua            Lua            embedded       109ms  "Hello, World!"
  sql            SQL            embedded         1ms  "Hello, World!"
  python-warm    Python         gateway          2ms  "Hello, World!"

共识值      : "Hello, World!"
与黄金值一致 : YES
OVERALL: ALL LANGUAGES AGREE ON GOLDEN        (process exit code 0)
```

9 种真正跑起来的语言：**Bash、JavaScript、Lua、Perl、PowerShell、Python、SQL、TypeScript、VB.NET**
（`javascript-fork` / `python-warm` 是同一份源文件的对照变体，见 §5）。

---

## 2. 为什么这套东西值得存在（联网调研结论）

### 2.1 Cordis 是什么

- **作者**：Yifan Shi（Shigma），Koishi 聊天机器人框架的作者。Cordis 从 Koishi v4 的
  插件内核里抽出来，2022 年独立发布，MIT 协议。仓库 `github.com/cordiverse/cordis`。
- **定位**：*构建框架的框架* —— 它本身不提供任何业务能力（无 HTTP / DB / 调度），
  只提供**能力如何被组合**：插件装卸、依赖注入、生命周期管理。
- **生产验证**：这套设计在 Koishi 生态里跑了 4 年、4000+ 社区插件。
- **内核极小**：运行时零依赖，核心只依赖 `cosmokit` 与 `@standard-schema/spec` 桥接层。

### 2.2 理论基础：时空可组合性

论文《A Programming Paradigm for Spatiotemporal Composability》
（Yifan Shi，北京大学 + DeepSeek-AI；Wei Zhang，北京大学；Tianyi Cui，DeepSeek-AI）
把「软件该怎么被组合」拆成正交的两轴：

| 轴 | 维度 | 机制 | 回答的问题 |
|----|------|------|-----------|
| **时间维可组合性** | *when* | **可逆效应**（revertible effects） | 一个组件在运行中对进程造成的改动，能否在正确的时刻被撤回，且不影响他人？ |
| **空间维可组合性** | *where / 依赖图* | **响应式协效应**（reactive coeffects） | 当活的依赖图发生变化（提供者出现/消失/替换）时，组件能否保持一致？ |

作者坦承的局限是：验证目前集中在**单一生态（Koishi）、单一语言（TypeScript）**。
这两个项目（`chess-cordis` 十语言国际象棋引擎、本项目 76 语言 Hello, World!）
正是在这一开放问题上继续往「多语言舰队」方向推。

### 2.3 调研里最有价值的一条：DeepSeek Harness 也在用它

2026-08-13 DeepSeek 发布的 Harness 开发者预览版，把 Cordis（`@deepseek-ai/cordis`，MIT）
当作核心插件系统 vendor 进来。公开材料对 Cordis 能力的三点归纳，恰好就是本项目依赖的三点：

1. **依赖注入**：`ctx.<key>` 查找 + `inject` 声明依赖，框架自动排这序；
2. **一切皆插件 / 服务**：功能开关不再写死成 if/else，挂载卸载是一行；
3. **可逆副作用**：注册时就记录「怎么撤销」，卸载时一键干净回滚 —— 真正的热重载由此成立。

---

## 3. 架构

```
                    ┌──────────────────────────────────────────┐
                    │          Cordis Context (ctx)             │
                    │   Proxy 化 DI 容器 + Fiber 生命周期        │
                    │   + 真实 @cordisjs/plugin-loader          │
                    │     (ctx.loader.root / ctx.loader.resolve)│
                    └──────────────────────────────────────────┘
                                      │
        ┌─────────────────────────────┼──────────────────────────────┐
        │                             │                              │
 ┌──────▼─────────┐        ┌──────────▼──────────┐      ┌───────────▼──────────┐
 │ HelloRegistry  │        │   HelloHarness      │      │   语言组件 (78 条)     │
 │ 共享单例(非    │        │  (Service)          │      │  embedded: js,lua,sql │
 │ ctx Service)   │        │  run()/formatReport │      │  subprocess: py,ts,   │
 │                │        └─────────────────────┘      │    bash,perl,vb,ps…   │
 │ register/unreg │◀────── 从它读全部已挂载组件          │  gateway: python-warm │
 └────────┬───────┘                                     └───────────┬───────────┘
          │                                                         │
          └──────────────  settleContract: greet() -> stdout ◀───────┘
```

**核心契约**（鸭子类型、语言无关），三种载体共享：

```js
{
  id, language, family, carrier, file,
  greet() -> string | Promise<string>   // 该程序打印到 stdout 的东西
}
```

### 3.1 三种载体：同一个契约，三种运输方式

| 载体 | 运行时在哪 | per-call 成本 | 本机实例 |
|------|-----------|---------------|----------|
| **embedded** | 加载进 Cordis 主进程 | 零 IPC，只有计算 | JavaScript(`node:vm`)、SQL(`node:sqlite`)、Lua(`fengari`) |
| **subprocess** | 每次调用 fork/exec | 每次付一遍解释器冷启动 | Python、TypeScript、PowerShell、Bash、Perl、VB.NET |
| **gateway** | 常驻 worker，握手一次后反复调用 | 冷启动只付一次 + 一遍 JSON-stdio 往返 | Python 热版（`drivers/gateway.py`） |

`subprocess` 与 `gateway` 是本项目相对参考架构**多出来的一层**：
`chess-cordis` 只有 native/subprocess 两种，且二者的 IPC 对比依赖 js↔ts 的巧合
（同一份逻辑、一个解释执行一个编译成 CJS）。本项目把「预热」单独做成第三种载体，
于是可以在**同一份源文件**上做严格受控对照（见 §5）。

### 3.2 为什么 registry 是模块单例而不是 Cordis Service

`Service.provide` 会**按 Fiber 解析实例**。loader 把每种语言挂在各自 Fiber 下，
若把注册表做成 Service，harness 在根 ctx 会拿到 N 份互不相干的注册表 ——
参考项目 `chess-cordis` §3.1 明确记录了这个坑。

本项目沿用修正后的结论：registry 是模块级单例（`export const helloRegistry`），
每个插件直接 import。**身份**由单例保证，**时间维语义仍交给 Cordis**：
每个组件挂载时用 `ctx.effect()` 登记撤销动作，卸载时 Cordis 自动执行。

### 3.3 JSON-stdio 协议（gateway 载体）

每行一个 JSON 对象，与参考项目的子进程协议同构：

```jsonc
{"ready": true}                                          // worker → host，握手
{"id":"1","cmd":"hello","file":"…/deepseek_python_….py"} // host → worker
{"id":"1","ok":true,"out":"Hello, World!\n"}             // worker → host
{"id":"1","ok":false,"error":"…"}                        // 失败
```

`drivers/gateway.py` 对 `.py` 采用**在本进程内 exec + `redirect_stdout` 截获**，
而不是再 fork 一层子进程 —— 冷启动只在握手时付一次。非 Python 文件退化到 `subprocess.run`。

---

## 4. 数据才是硬道理：76 种语言去哪了

`node tools/bootstrap.mjs` 会扫描 `helloworld/`、查语言知识库、探测工具链，
然后生成两份 YAML。**没工具链就 disabled 并写明原因 —— 不假绿。**

```
扫描 76 个源文件 → 识别 76 种语言
清单已就绪：11 个组件可挂载，67 个因缺工具链 disabled
  ENABLED : bash, javascript, lua, perl, powershell, python, sql, typescript, vb,
            python-warm, javascript-fork
```

disabled 的 67 项，每条都给了可执行的原因与配方，例如：

```
-  cpp          C++      原因: 本机未找到工具链 g++
-  go           Go       原因: 本机未找到工具链 go
-  java         Java     原因: 本机未找到工具链 javac
-  ruby         Ruby     原因: 可选依赖未安装：npm i @ruby/3.2-wasm-wasi
-  brainfuck    Brainfuck 原因: 尚无可用适配器（esolang 未实现 VM）
-  mercury      Mercury  原因: Mercury 编译器 mmc 与 Windows 的 mmc.exe 同名，自动探测不可靠
```

**C++/Go/Java/Rust 等一旦装上工具链，只要重跑一次 `bootstrap.mjs` 就会点亮** ——
宿主、加载器、校验器不需要任何改动。这与参考项目当年「找到工具链后就点亮 cpp/go/rust」
的路径完全一致，只是把这一步自动化了。

### 4.1 一个必须提醒自己的陷阱：`mmc` 误判

第一版探针把 Mercury 判为「可用」，因为它在 `C:\Windows\system32` 找到了 `mmc.exe` ——
那是 **Microsoft Management Console**，不是 Mercury 编译器。若真去执行它还会拉起 GUI。
已改为显式 `never:<原因>` 放弃自动探测。**自动探测的结果必须能用才算数。**

---

## 5. 跨语言耗时表（实测，`node src/timing.js`）

5 次采样、已预热。这些数字是 **harness 层面的真实成本**，不是语言本身的微基准。

```
  rank  id              语言           载体          min    中位    平均    最大
  ------------------------------------------------------------------------------
     1  sql            SQL            embedded         0ms    0ms     0ms    0ms
     2  python-warm    Python         gateway          0ms    0ms   0.4ms    1ms
     3  javascript     JavaScript     embedded         0ms    1ms   0.6ms    1ms
     4  lua            Lua            embedded         1ms    1ms   1.4ms    2ms
     5  vb             VB.NET         subprocess     119ms  134ms   134ms  150ms
     6  perl           Perl           subprocess     222ms  229ms   238ms  262ms
     7  javascript-fork JavaScript     subprocess     273ms  287ms 289.8ms  316ms
     8  typescript     TypeScript     subprocess     316ms  333ms 329.8ms  350ms
     9  bash           Bash           subprocess     381ms  417ms 416.8ms  452ms
    10  python         Python         subprocess     830ms  849ms 855.8ms  886ms
    11  powershell     PowerShell     subprocess    1822ms 1883ms1899.8ms 1997ms
```

### 5.1 两组受控对照（这是 gateway 载体存在的全部理由）

```
[对照 A] javascript(embedded) vs javascript-fork(subprocess) —— 纯 fork 开销
    javascript      平均 1.6ms
    javascript-fork 平均 300.2ms
    → javascript-fork 比 javascript 慢 188×（同一份源文件，仅载体不同）

[对照 B] python(subprocess 冷启动) vs python-warm(gateway 预热) —— 解释器冷启动开销
    python          平均 840ms
    python-warm     平均 0.4ms
    → python 比 python-warm 慢 2100×（同一份源文件，仅载体不同）
```

**读法**：差距完全不来自语言快慢 —— 同一份源文件、同一段逻辑，只是换了运输方式。
Hello, World! 级别的计算量几乎为零，所以量出来的基本就是**纯粹的进程创建 + 解释器冷启动**。

顺带两个观察：

- **PowerShell 是本机最贵的** (~1.9s/次)。Windows PowerShell 5.1 的启动成本如此之高，
  若将来真要在 Windows 上批量驱动 ps1，必须走 gateway 载体，不能一次一 fork。
- **VB.NET 的 134ms 是纯运行开销**（编译发生在挂载期，且产物有缓存），
  这让它在所有 subprocess 载体里排第一 —— 编译一次、跑很多次的典型优势。

---

## 6. 时间维：热插拔压力测试（实测，`node src/stress.js`）

```
[PASS] baseline: 组件按清单挂载 — bash,javascript,javascript-fork,lua,perl,powershell,python,python-warm,sql,typescript,vb
[PASS] baseline: 全部组件输出黄金值 — 11 个组件
[PASS] hot-swap subprocess: 已从注册表注销 — id=python
[PASS] hot-swap subprocess: 摘除期间其余组件照常服务 — 10 个组件
[PASS] hot-swap subprocess: 重新挂载并通过校验 — 11 个组件
[PASS] hot-swap embedded: 已从注册表注销 — id=javascript
[PASS] hot-swap embedded: 摘除期间其余组件照常服务 — 10 个组件
[PASS] hot-swap embedded: 重新挂载并通过校验 — 11 个组件
[PASS] hot-swap gateway: 已从注册表注销 — id=python-warm
[PASS] hot-swap gateway: 子进程已被回收 — pid=29956
[PASS] hot-swap gateway: 摘除期间其余组件照常服务 — 10 个组件
[PASS] hot-swap gateway: 重新挂载并通过校验 — 11 个组件
---
STRESS TEST: ALL PHASES PASS (temporal composability verified)   (process exit code 0)
```

三种载体各挑一个代表做了完整的「摘除 → 别人照常 → 装回」循环。
**gateway 那一组额外验证了 OS 子进程真的被杀**（打印了 PID 并确认回收），
不是只把注册表项删掉了事 —— 这正是论文「可逆效应」要求的东西。

---

## 7. 踩过的坑（按痛苦程度排序）

1. **`spawnSync` 在本机会 EBUSY 失败**，异步 `spawn` 正常。
   所有端口统一只用异步 `spawn`；诊断脚本若图省事用 `spawnSync` 会得到完全错误的结论。
2. **Windows 编译器不退出**：`vbc.exe` 编译完、产物写好了，进程却一直挂着不退，
   `'close'` 事件永远不来（有子进程继承了管道句柄）。改为**以 `'exit'` 为准 + 留 40ms 排空**。
3. **只看一次产物存在还不够**：`vbc` 会先把产物写出来再收尾，抢在下一阶段前判定成功，
   就会出现「刚才还在、转眼没了」。改为**连续 3 次采样 size 不变且非空**才算完工，
   之后才杀编译器。
4. **`vbc` 拒绝绝对路径输入**：`-out:E:/…/x.exe absolute-src.vb` 静默失败；
   `-out:E:\…\x.exe relative-src.vb` + `cwd=源目录` 才成立。且 **MS 编译器把 `/` 当选项前缀**，
   路径模板里不能出现 `E:/…`。
5. **`mmc` 假绿**（见 §4.1）。
6. **`await` 不能省**：embedded 有的是同步返回，subprocess/gateway 返回 Promise。
   `await` 非 Promise 是 no-op，所以同一段代码能同时服务三种载体；但**漏掉 await 会把
   Promise 塞进 `rec.out`**，症状是静默的全部 ERR 而没有报错 —— 参考项目在 §6.5 记录过同一个坑，
   本项目一开始就堵上了。
7. **loader 的 `update()` 收数组**，不是按 id 建的 map（传对象会 `map is not a function`）。
8. **ESM 模块名必须是相对路径或 file:// URL**：`'JsChess/chessCore.js'` 会被 Node 以
   `protocol 'e:' not supported` 拒绝。
9. 曾把 vbc 的编译产物误写进 `helloworld/`（`B.exe`、`c4.exe`），**已删除**，目录恢复为 76 个源文件。

---

## 8. 与参考项目的对应关系

| 维度 | `chess-cordis`（参考） | 本项目 `helloworld-cordis` |
|------|----------------------|---------------------------|
| Cordis 来源 | `cordis` 真实包，无 vendor | 同样：`cordis@4.0.0-rc.10` + `@cordisjs/plugin-loader@1.0.0-rc.7` |
| 引擎独立性 | `*Chess` 零依赖、cordis-unaware | `helloworld/*` 零依赖、cordis-unaware、**一个字节没改** |
| 一致性判据 | perft 黄金节点数 | `Hello, World!` 黄金字符串 |
| 载体数量 | 2（native / subprocess） | **3**（embedded / subprocess / gateway） |
| 语言规模 | 10 | **76 声明，9 真跑** |
| 清单来源 | 手写 `cordis.yml` | **自动生成**（扫描 + 工具链探测） |
| 时间维验证 | ✅ stress.js | ✅ stress.js，三种载体各一轮，含进程回收断言 |
| 性能对照 | js ↔ ts 顺带对比 | **同一份源文件的严格受控对照** |

---

## 9. 还能往下做什么

- **点亮更多语言**：装 gcc / go / rustup / JDK / dotnet SDK → `node tools/bootstrap.mjs`。
  C / C++ / Go / Rust / Java / C# / F# 的配方已经在 `lang-db.mjs` 里写好了。
- **Ruby**：`npm i @ruby/3.2-wasm-wasi`（约 96MB），embedded 载体的 code path 已写好，
  未安装时自动 disabled 并提示安装命令。
- **深奥语言**：Brainfuck / Befunge / Malbolge / Ook / INTERCAL / LOLCODE / Shakespeare
  没有公开工具链，需要在 `src/ports/embedded.mjs` 里加 tiny VM 适配器出一个就能点亮。
- **每届归一化**：GUI 语言（PostScript、Smalltalk、GDScript）和 XSLT 的「输出」定义各不相同，
  目前按「stdout 首行」判定，接进来的第一步是把它们的输出规范写清楚。
