# -*- coding: utf-8 -*-
"""
renamer 装配自省（--dump-profile 等价物，agent 审计入口，2026-08-24）
"""
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def dump_profile() -> dict:
    return {
        "tool": "renamer",
        "description": "正则批量重命名",
        "entry": "main.py（Tk GUI）",
        "structure": "main.py + core.py（统一结构）",
        "deps": "标准库",
        "port": "无服务端口（端口分配表登记规则）",
    }


if __name__ == "__main__":
    profile = dump_profile()
    if "--json" in sys.argv:
        print(json.dumps(profile, ensure_ascii=False, indent=2))
    else:
        print("renamer 装配自省")
        for k, v in profile.items():
            print(f"  {k}: {v}")
