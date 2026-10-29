# calculator · Calculator ∞ Alchemia 解密终端

> 独立项目 siwpan/calculator（本地 E:\projects\calculator）。终端计算器（MVC 架构 + 密码学功能），零外部依赖、纯鼠标交互。

## 运行

```bash
python main.py
python -m calculator      # 等价
```

零外部依赖，只用标准库（tkinter / hashlib / secrets / base64）。

## 架构

原先是单文件 `calculator.py`（858 行，类都叫 MVC 但全部挤在一起）。
现按 src 布局拆成包，**依赖严格单向**：

```
app ──> controller ──> model ──> engine / crypto / easter_eggs
             │            └────────> config
             └──> view ──> config / snapshot
```

```
calculator/              # 包
├── config.py        限制常量 / 主题配色 / 键盘布局（唯一事实来源）
├── snapshot.py      Model → View 的数据契约，两边都只认它
├── engine/          表达式求值：tokenizer → parser → evaluator
│   ├── tokenizer.py   词法分析（不认识 `**`，从根上封死幂炸弹）
│   ├── parser.py      调度场算法，中缀 → 逆波兰式
│   └── evaluator.py   栈式求值 + 结果规模护栏
├── crypto.py        密码学工具（secrets 随机源 + 模式注册表）
├── easter_eggs.py   彩蛋表（同键多值轮换）
├── model.py         状态机，不 import tkinter
├── view.py          纯渲染，不 import model
├── controller.py    接线 + 副作用
└── app.py           组合根
main.py              入口
tests/               77 项单元测试 + GUI 冒烟
```

**Model 与 View 零 import 关系**：Model 产出 `Snapshot`，View 只消费 `Snapshot`。
**Controller 不碰布局常量**：只向 View 注册一个 `on_press(token)` 回调。

### 为什么入口叫 main.py 而不是 calculator.py

实测确认：包 `calculator/` 会**遮蔽**同名的 `calculator.py`（包优先于模块）。
若入口也叫 `calculator.py`，它永远无法被导入执行。因此入口命名为 `main.py`，
包名保持 `calculator`，两者不冲突。

## 功能

- **四则运算**：括号、优先级、一元负号、浮点格式化（与旧版完全一致，对拍 10 组零差异）。
- **密码学面板**：按 `#` 进入（原先是 `□` 占位格），选模式后用字母键盘输入，`EXE` 执行。
  支持 caesar / hash / key / xor / vig / rot13 / b64 / salt / pwd。
  字母键盘中 `_` 代表空格（用于 `文本 密钥` 这类双参数输入）。
- **彩蛋**：特殊组合触发，同键多次命中会**轮换**不同值
  （如 `128` → `aes-128` → `md5` → `nonce` → 回绕）。
- **交互彩蛋**：连按同一键三次清空、连按退格三次退出、连按等号三次打乱键盘。

## 测试

```bash
# 全量（无 tkinter 环境会自动跳过 GUI 冒烟）
PYTHONPATH=".:./tests" python -m unittest discover -s tests -p "test_*.py"
```

77 项：引擎 17 / 密码学 26 / Model 25 / GUI 冒烟 9。
核心层（config / engine / crypto / easter_eggs / model / snapshot）**不依赖 tkinter**，
在没有 GUI 的解释器上也能跑完整测试。

GUI 冒烟用 `Button.invoke()` 真点按钮，验证的是接线而非逻辑。

## 本次拆分修掉的缺陷

| 缺陷 | 证据 | 处理 |
|---|---|---|
| `SPECIAL_COMBOS` 重复键静默覆盖 | 68 条定义只剩 58 条生效；文档称 `128→aes-128`，实际输出 `nonce` | 改为 `dict[str, tuple]`，同键多值轮换，一条不丢 |
| `eval()` 白名单放行 `**` | `9**9**9` 通过校验 → 可把 UI 算死 | 换成三段式引擎，词法层直接拒 `**`，另加结果规模护栏 |
| 密码学功能 100% 不可达 | 无 `#` 键、无字母键，18 个字母彩蛋 17 个按不到，9 个模式全不可达 | `#` 键 + 可切换字母键盘，9 个模式全部实测跑通 |
| 分层违规 | View 方法签名写 `model: "CalculatorModel"`；Controller 遍历 View 的 `BUTTON_TOKENS` | 引入 `Snapshot` 契约；Controller 只注册回调 |
| 密钥用 `random` 生成 | Mersenne Twister 非密码学安全 | 改用 `secrets` |
| 无任何测试 | — | 补 77 项 |

四则运算行为与旧实现**零差异**（对拍 `1+1` `2×3` `7÷2` `1+2×3` `(1+2)×(3-1)`
`10-2-3` `100÷3` `0.5+0.25` `8÷2÷2` `1-1` 十组，结果全部一致）。

## 谱系

- master = 现行版（MVC 包结构 + 密码学）；mvvm 重写版在 tag `mvvm`；拆分前的单文件版在历史提交 `2960047`。
- 拆分前的入口为 `calculator.py`，现改为 `main.py`（原因见上）。

## 许可

MIT · Copyright (c) 2026 siwpan
