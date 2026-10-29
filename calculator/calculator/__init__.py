"""calculator —— MVC 架构的终端计算器（含密码学解密玩法）。

分层约定（这次拆分真正落实的部分）：

    config      ── 常量/主题/布局，所有层都只依赖它，层与层之间互不依赖
    engine      ── 表达式求值（词法→语法→求值），取代 eval
    crypto      ── 密码学工具，纯函数
    easter_eggs ── 彩蛋表
    model       ── 状态与业务规则，不认识 tkinter
    view        ── 纯渲染，不认识 model
    controller  ── 接线与副作用
    app         ── 组合根

依赖方向严格单向：``app → controller → {model, view} → config``。
Model 与 View 之间**不存在** import 关系（旧版 View 的类型注解里
直接写了 ``CalculatorModel``，属于隐性耦合，已改为只接收展示数据）。

运行::

    python main.py            # 仓库根目录的入口
    python -m calculator      # 包入口
"""

from __future__ import annotations

__version__ = "2.0.0"

__all__ = ["__version__"]
