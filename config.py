# -*- coding: utf-8 -*-
"""
输入法配置文件
管理所有路径、热键、UI参数等配置
"""

import os
import sys

# ============================================================
# 基础路径
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_DIR = os.path.join(BASE_DIR, "dictionary")
LOCAL_DIR = os.path.join(BASE_DIR, "本地")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

# 字典子路径
CHAR_BASE_PATH = os.path.join(
    DICT_DIR, "chinese-dictionary", "chinese-dictionary-main",
    "character", "char_base.json"
)
WORD_DICT_PATH = os.path.join(
    DICT_DIR, "chinese-dictionary", "chinese-dictionary-main",
    "word", "word.json"
)
IDIOM_DICT_PATH = os.path.join(
    DICT_DIR, "chinese-dictionary", "chinese-dictionary-main",
    "idiom", "idiom.json"
)
CEDICT_PATH = os.path.join(
    DICT_DIR, "CC-CEDICT", "cedict_ts.u8"
)

# 缓存文件
CHAR_INDEX_CACHE = os.path.join(CACHE_DIR, "char_index.pkl")
WORD_INDEX_CACHE = os.path.join(CACHE_DIR, "word_index.pkl")
IDIOM_INDEX_CACHE = os.path.join(CACHE_DIR, "idiom_index.pkl")

# 用户词典
USER_DICT_PATH = os.path.join(BASE_DIR, "user_dict.json")

# ============================================================
# 热键配置
# ============================================================
# 切换输入法开关
TOGGLE_HOTKEY = "shift"          # 按右 Shift 切换中英文
# 翻页键
PAGE_DOWN_KEY = "."              # 句号向后翻页
PAGE_UP_KEY = ","                # 逗号向前翻页

# ============================================================
# UI 配置
# ============================================================
CANDIDATE_WINDOW_WIDTH = 400
CANDIDATE_WINDOW_HEIGHT = 260
CANDIDATES_PER_PAGE = 9          # 每页显示9个候选词（对应数字键1-9）
CANDIDATE_FONT_SIZE = 16         # 候选词字体大小
PINYIN_FONT_SIZE = 12            # 拼音显示字体大小
CANDIDATE_FONT_NAME = "微软雅黑"

# 字体路径（候选词显示字体）
DEFAULT_FONT_PATH = None         # None 表示使用系统默认字体

# 颜色配置
BG_COLOR = "#FFFFFF"             # 窗口背景色
BORDER_COLOR = "#CCCCCC"         # 边框颜色
CANDIDATE_COLOR = "#333333"      # 候选词颜色
PINYIN_COLOR = "#999999"         # 拼音显示颜色
HIGHLIGHT_COLOR = "#E8F4FD"      # 高亮背景色
HIGHLIGHT_TEXT_COLOR = "#0066CC" # 高亮文字色

# 窗口与光标的偏移
WINDOW_OFFSET_X = 5
WINDOW_OFFSET_Y = 25

# 输入缓冲区最大长度
MAX_INPUT_LENGTH = 64

# ============================================================
# 字典加载配置
# ============================================================
# 是否加载词语词典（word.json 约60MB，首次加载较慢）
LOAD_WORD_DICT = True
# 是否加载成语词典
LOAD_IDIOM_DICT = True
# 是否强制重新构建缓存
FORCE_REBUILD_CACHE = False
# 词语候选最大数量（限制搜索广度，提升性能）
MAX_WORD_CANDIDATES = 200
# 成语候选最大数量
MAX_IDIOM_CANDIDATES = 100
# 单字候选最大数量
MAX_CHAR_CANDIDATES = 100

# ============================================================
# 创建必要目录
# ============================================================
os.makedirs(CACHE_DIR, exist_ok=True)
