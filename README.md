# calculator · Calculator ∞ Alchemia 解密终端

> 独立仓 siwpan/calculator（本地 G:\repos\calculator）。终端计算器（MVC 架构 + 密码学功能），零外部依赖、纯鼠标交互。
> 已并入街机 arcade（siwpan/arcade，games/calculator 目录，选单壳内以独立子进程启动）。

## 功能

- **MVC 架构**：Model（状态与业务逻辑，observer 通知）/ View（纯渲染，绝不直接调用 Model）/ Controller（接线与副作用管理）——无外部依赖。
- **密码学功能**：内置加密/解密类玩法（Alchemia 解密终端风格）。
- **交互**：鼠标点击操作（零键盘依赖），适合街机选单壳嵌入。

## 运行

```bash
python calculator.py
```

或经街机选单：`python G:\repos\arcade\main.py`（games/calculator）。

## 谱系

- master = 现行版（MVC + 密码学）；mvvm 重写版已转 tag `mvvm`。
- 发行面：随街机 arcade `v1.0.0-arcade` 分发（本仓亦有独立 v1.0.0 发布记录）。

## 许可

MIT · Copyright (c) 2026 siwpan
