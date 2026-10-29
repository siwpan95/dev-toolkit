"""配置层 —— 全应用唯一事实来源。

拆分的第一个收益：原先这些常量散落在 Model（限制值）、View（配色、
字体、按钮表）两处，Controller 还要跨层去 View 拿 ``BUTTON_TOKENS``。
现在集中在这里，Model / View / Controller 都只依赖本模块，互不依赖。

本模块不 import tkinter，纯数据，可在无 GUI 环境下测试。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Final


# ─────────────────────────────────────────────────────────────
#  行为限制
# ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Limits:
    """输入与求值的边界。全部为不可变配置，便于测试时整体替换。"""

    max_chars: int = 13            # 表达式最大字符数
    max_digit_presses: int = 4     # 数字/小数点最多按几次
    triple_same_reset: int = 3     # 连按同一键 N 次 → 清空
    triple_backspace_quit: int = 3 # 连按退格 N 次 → 退出
    triple_equals_shuffle: int = 3 # 连按等号 N 次 → 打乱键盘

    # ── 求值护栏：原先完全缺失 ──
    # 旧实现用 eval()，白名单放行 "**"，于是 9**9**9 能把 UI 直接算死。
    # 新引擎根本不识别 ** 运算符，这里再叠一层结果规模上限兜底。
    max_result_abs: float = 1e15   # 结果绝对值上限，超出视为溢出
    max_result_digits: int = 13    # 结果格式化后的最大字符数
    float_format: str = ".6f"      # 与旧版一致的浮点格式化


LIMITS: Final[Limits] = Limits()


# ─────────────────────────────────────────────────────────────
#  主题配色
# ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Theme:
    """配色方案。抽成 dataclass 后支持换肤（``replace(theme, ...)``）。"""

    name: str = "catppuccin-mocha"

    bg: str = "#1e1e2e"
    display_bg: str = "#181825"
    display_fg: str = "#cdd6f4"
    expr_fg: str = "#6c7086"
    sep_color: str = "#313244"

    btn_num: str = "#313244"
    btn_op: str = "#45475a"
    btn_eq: str = "#89b4fa"
    btn_back: str = "#f38ba8"
    btn_cmd: str = "#a6e3a1"      # 密码学命令键（新增，原先没有）
    btn_fg: str = "#cdd6f4"
    btn_eq_fg: str = "#1e1e2e"

    btn_dis: str = "#2a2a3a"
    btn_dis_fg: str = "#555577"

    btn_num_hv: str = "#3b3b50"
    btn_op_hv: str = "#525368"
    btn_eq_hv: str = "#9cc5fb"
    btn_back_hv: str = "#f5a0b4"
    btn_cmd_hv: str = "#b8edb4"


THEME: Final[Theme] = Theme()

# 亮色备选：演示主题可替换性（原先配色写死在 View，无法换肤）
THEME_LIGHT: Final[Theme] = replace(
    THEME,
    name="catppuccin-latte",
    bg="#eff1f5",
    display_bg="#e6e9ef",
    display_fg="#4c4f69",
    expr_fg="#8c8fa1",
    sep_color="#ccd0da",
    btn_num="#ccd0da",
    btn_op="#bcc0cc",
    btn_eq="#1e66f5",
    btn_back="#d20f39",
    btn_cmd="#40a02b",
    btn_fg="#4c4f69",
    btn_eq_fg="#eff1f5",
    btn_dis="#dce0e8",
    btn_dis_fg="#a0a4b0",
    btn_num_hv="#dcdee5",
    btn_op_hv="#acb0be",
    btn_eq_hv="#4c84f7",
    btn_back_hv="#e14b67",
    btn_cmd_hv="#5cb04a",
)


# ─────────────────────────────────────────────────────────────
#  键盘布局
# ─────────────────────────────────────────────────────────────
EMPTY: Final[str] = "□"   # 占位格：占网格但不响应（沿用旧行为）

# 四则运算键与数字键
OPERATORS: Final[frozenset[str]] = frozenset({"+", "-", "×", "÷", "(", ")"})

#: 默认列数（小键盘用；字母面板用 6 列，见 :data:`ALPHA_LAYOUT`）
GRID_COLS: Final[int] = 4


@dataclass(frozen=True)
class Layout:
    """一份键盘布局：按键序列 + 列数。

    列数是数据而不是常量，因为字母面板用 6 列才不会把窗口撑成
    一条竖条（4 列要 11 行，6 列只要 8 行）。
    """

    tokens: tuple[str, ...]
    cols: int = GRID_COLS


#: 数字小键盘（初始布局）。最后一格原先是无功能的 □，
#: 现改为 "#" —— 密码学功能的唯一入口（旧版这一格纯占位，
#: 导致全部密码学代码永远执行不到）。
NUMPAD_LAYOUT: Final[Layout] = Layout(
    (
        "(", ")", "←", "÷",
        "7", "8", "9", "×",
        "4", "5", "6", "-",
        "1", "2", "3", "+",
        "0", ".", "=", "#",
    ),
    cols=4,
)

#: 密码学模式选择面板。旧版这 9 个模式一个都进不去。
CRYPTO_MENU_LAYOUT: Final[Layout] = Layout(
    (
        "caesar", "hash", "key", "xor",
        "vig", "rot13", "b64", "salt",
        "pwd", "ESC", EMPTY, EMPTY,
    ),
    cols=4,
)

#: 密码学文本输入面板（6 列）。旧版 xor / key / ecb 这类字母彩蛋键
#: 在小键盘上永远按不出来，整个 CryptoUtils 是死代码；现在字母与数字
#: 都齐备，"文本 密钥"、"sha256"、"位数" 都输得进去。
ALPHA_LAYOUT: Final[Layout] = Layout(
    (
        "a", "b", "c", "d", "e", "f",
        "g", "h", "i", "j", "k", "l",
        "m", "n", "o", "p", "q", "r",
        "s", "t", "u", "v", "w", "x",
        "y", "z", "0", "1", "2", "3",
        "4", "5", "6", "7", "8", "9",
        "_", ":", "←", "EXE",
        "ESC", EMPTY, EMPTY, EMPTY,
    ),
    cols=6,
)

#: 这些键在任何布局下都不参与「达到上限就置灰」的逻辑
ALWAYS_ACTIVE: Final[frozenset[str]] = frozenset({"←", "=", "#", "ESC", "EXE", EMPTY})

BTN_FONT: Final[tuple] = ("Consolas", 16, "bold")
BTN_FONT_SMALL: Final[tuple] = ("Consolas", 11, "bold")
EXPR_FONT: Final[tuple] = ("Consolas", 13)

#: 显示字号按长度分档：(最大长度, 字体)
DISPLAY_FONT_TIERS: Final[list[tuple[int, tuple]]] = [
    (6,  ("Consolas", 30, "bold")),
    (9,  ("Consolas", 24, "bold")),
    (10, ("Consolas", 18, "bold")),
    (16, ("Consolas", 13, "bold")),
]
DISPLAY_FONT_MIN: Final[tuple] = ("Consolas", 11, "bold")
