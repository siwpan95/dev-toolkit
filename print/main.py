# -*- coding: utf-8 -*-
"""
中文拼音输入法 - 入口文件

基于本地字典与字体，使用 Python 实现的中文拼音输入法。

架构模块:
  config.py              - 全局配置管理
  pinyin_syllables.py    - 拼音音节表
  pinyin_dict.py         - 拼音字典管理器（加载本地字典构建索引）
  pinyin_parser.py       - 拼音解析器（音节分割、候选词生成）
  user_dict.py           - 用户词典（学习功能）
  ime_ui.py              - 候选窗口 UI（tkinter）
  keyboard_handler.py    - 全局键盘监听与管理
  ime_core.py            - 输入法核心引擎（状态机、模块协调）

数据来源:
  - chinese-dictionary   : 20,000+ 汉字、320,000+ 词语、50,000+ 成语
  - CC-CEDICT            : 120,000+ 中英对照词条
  - 本地字体库           : 200+ 中文字体文件

使用方法:
  1. 安装依赖: pip install -r requirements.txt
  2. 运行程序: python main.py
  3. 按右 Shift 切换中英文
  4. 输入拼音，数字键/空格选择候选词
  5. 按 Esc 取消输入

热键说明:
  右 Shift    - 切换中英文输入模式
  字母键 A-Z - 输入拼音
  数字键 1-9 - 选择候选词
  空格/回车  - 选择第一个候选词
  逗号 ,     - 向前翻页
  句号 .     - 向后翻页
  上/下箭头  - 翻页
  Esc        - 取消当前输入
"""

import sys
import os
import ctypes

# ============================================================
# DPI 感知必须在导入 tkinter 之前设置，否则在高分屏上窗口位置会完全错误
# ============================================================
if sys.platform == "win32":
    try:
        # Windows 8.1+ 推荐方式
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
    except AttributeError:
        # Windows Vista/7 降级方案
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# 确保能找到模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ime_core import ImeCore


def main():
    """程序入口"""
    try:
        ime = ImeCore()
        ime.run()
    except KeyboardInterrupt:
        print("\n[退出] 用户中断")
    except Exception as e:
        print(f"[错误] 程序异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
