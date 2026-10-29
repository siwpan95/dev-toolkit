"""视图快照 —— Model 与 View 之间唯一的数据契约。

旧版的耦合点：``CalculatorView.on_model_change(self, model: "CalculatorModel")``
—— View 的方法签名里直接出现了 Model 类型，等于 View 必须认识 Model，
所谓「View 绝不直接调用 Model」只是没有调用，认知依赖仍在。

解法：Model 只产出这个不可变快照，View 只消费它。两边都只依赖本模块，
彼此零 import。副作用是 View 变得极易测试——喂一个 Snapshot 进去断言
渲染结果即可，连 Model 都不用构造。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class Mode(Enum):
    """键盘当前处于哪种布局。"""

    CALC = auto()          # 四则运算小键盘
    CRYPTO_MENU = auto()   # 密码学模式选择
    CRYPTO_INPUT = auto()  # 密码学文本输入（字母键盘）


class Action(Enum):
    """本次状态变更后，Controller 需要执行的副作用。View 不关心。"""

    NONE = auto()
    QUIT = auto()          # 连按退格 → 退出进程
    SHUFFLE = auto()       # 连按等号 → 打乱键盘
    LAYOUT_CHANGED = auto()  # 模式切换，需要重建键盘


@dataclass(frozen=True)
class Snapshot:
    """某一时刻 View 渲染所需的全部数据。"""

    display: str = "0"              # 大号结果行
    expr: str = ""                  # 小号表达式行
    hint: str = ""                  # 密码学模式下的输入提示
    mode: Mode = Mode.CALC
    action: Action = Action.NONE
    char_limit: bool = False        # 已达表达式长度上限
    digit_limit: bool = False       # 已达数字按键次数上限
    crypto_mode: str = ""           # 当前密码学模式名（菜单高亮用）
    history: tuple[str, ...] = field(default_factory=tuple)
