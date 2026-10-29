"""求值错误类型。

单独成模块，让 Model 可以精确区分错误原因（除零 / 语法 / 溢出），
而不是像旧实现那样一律吞成 ``except Exception: return "fool"``。
"""

from __future__ import annotations


class CalcError(Exception):
    """表达式求值失败。``code`` 供上层做差异化展示或记录。"""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        self.message = message or code
        super().__init__(self.message)


#: 错误码 → 展示文案。旧版对所有失败一律返回 "fool"，
#: 这里保留 "fool" 作为默认文案以维持既有观感，但内部可区分。
ERROR_LABELS: dict[str, str] = {
    "empty": "0",
    "syntax": "fool",
    "div0": "fool",
    "overflow": "fool",
    "nan": "fool",
    "too_long": "fool",
    "power": "fool",      # ** 幂运算已被禁用（旧版白名单放行了它 → 可卡死 UI）
    "char": "fool",
}
