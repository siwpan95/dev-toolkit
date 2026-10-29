"""配置与持久化。

把所有可调参数集中在一处，并提供 默认值 / 从 JSON 加载 / 保存 三个能力。
设置文件写在主程序同目录下的 settings.json，实现「关掉再开，配置还在」。
"""

from pathlib import Path

# 所有可调参数的默认值。新增字段时只改这里即可。
DEFAULTS = {
    "button": "left",          # 鼠标按键: left / right / middle
    "click_type": "single",    # 点击类型: single / double
    "interval_ms": 100,        # 点击间隔(毫秒)
    "jitter_ms": 0,            # 随机抖动(±毫秒)，用于规避规律性检测
    "repeat_mode": "infinite", # 重复模式: infinite / count
    "repeat_count": 100,       # 指定次数模式下的目标点击数
    "location_mode": "current",# 点击位置: current(当前光标) / fixed(固定坐标)
    "fixed_x": 0,              # 固定坐标 X
    "fixed_y": 0,              # 固定坐标 Y
    "start_delay_ms": 0,       # 启动前延迟(误触保护)
    "hotkey": "space",         # 开始/停止 热键
}

# 字段类型，用于加载时做最基础的类型校正，避免脏数据让程序崩。
_TYPES = {
    "button": str,
    "click_type": str,
    "interval_ms": int,
    "jitter_ms": int,
    "repeat_mode": str,
    "repeat_count": int,
    "location_mode": str,
    "fixed_x": int,
    "fixed_y": int,
    "start_delay_ms": int,
    "hotkey": str,
}


def _coerce(key, value):
    """按已知类型把值转一下；转不动就回退到默认值。"""
    try:
        return _TYPES[key](value)
    except (TypeError, ValueError):
        return DEFAULTS[key]


def load_settings(path):
    """读取设置文件，与默认值合并。文件损坏/不存在都安全回退到默认。"""
    p = Path(path)
    if not p.exists():
        return dict(DEFAULTS)
    try:
        raw = p.read_text(encoding="utf-8")
        data = __import__("json").loads(raw)
    except Exception:
        return dict(DEFAULTS)
    merged = dict(DEFAULTS)
    for key in DEFAULTS:
        if key in data:
            merged[key] = _coerce(key, data[key])
    return merged


def save_settings(path, settings):
    """把当前设置写回 JSON（保留中文，便于人眼核对）。"""
    import json
    try:
        Path(path).write_text(
            json.dumps(settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        # 写入失败不该中断程序（比如只读目录）。静默忽略即可。
        pass
