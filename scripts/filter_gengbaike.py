"""Gengbaike 词条过滤：从原始抓取结果中筛出「适合作为三题故事题目」的通用梗。

设计原则（对应 SKILL/README 中「精选高质量词条」策略）
---------
三题故事的题目应当是一个**具象、可联想、能展开叙事的意象或短语**。
因此需要剔除：
  * 饭圈 / CP 名 / 粉丝口号 —— 对非粉丝无意义（「从开始到未来，只为王俊凯」）
  * 真实人名、游戏 ID、平台昵称
  * 品牌 / 产品 / 平台运营活动名
  * 低俗、涉性、涉政、地域攻击等敏感内容
  * 纯符号、纯数字、纯英文缩写、含括号补充说明
  * 过长（> 12 字）或过短（< 2 字，单字梗难以独立成题）
  * 需要在特定语境才能理解的一次性热梗（通过黑名单词根识别）

输出: data/gengbaike_selected.json —— [{"word": "...", "tags": [...]}, ...]
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RAW = os.path.join(DATA, "gengbaike_raw.json")
OUT = os.path.join(DATA, "gengbaike_selected.json")

# ---- 黑名单：出现即整条剔除 ----
BLACKLIST = [
    # 饭圈 / CP / 粉丝向
    "王俊凯", "王源", "易烊千玺", "肖战", "王一博", "蔡徐坤", "鹿晗", "黄子韬",
    "朱一龙", "龚俊", "张哲瀚", "罗云熙", "檀健次", "丁程鑫", "宋亚轩", "刘耀文",
    "杨洋", "白鹿", "赵露思", "迪丽热巴", "古力娜扎", "杨紫", "郑爽", "范冰冰",
    "时代少年团", "TFBOYS", "EXO", "BLACKPINK", "SNH48", "火箭少女",
    "粉丝", "应援", "打榜", "超话", "cp粉", "CP粉", "唯粉", "站姐", "私生",
    "出道", "选秀", "打call", "控评", "安利", "塌房", "爱豆", "idol", "偶像",
    "男团", "女团", "男神", "女神", "老公", "老婆粉",
    # 涉政 / 敏感
    "港独", "台独", "藏独", "建国", "文革", "六四", "新疆", "西藏", "南海",
    "武汉八勇士", "政治局", "共产党", "国民党", "总统", "选举", "游行", "抗议",
    "疫情", "封城", "核酸", "清零", "方舱", "李文亮", "白纸",
    # 低俗 / 涉性
    "性", "色情", "嫖", "卖淫", "约炮", "炮", "裸", "肉", "簧", "黄图", "开车",
    "顶族", "绿茶", "白莲花", "小三", "出轨", "绿帽", "舔狗", "备胎", "海王",
    "字母圈", "sugar", "包养", "约", "骚", "浪", "贱", "婊", "逼", "屌",
    # 违法行为 / 风险
    "赌博", "赌", "博彩", "毒品", "违禁", "代购", "羊毛党", "刷单", "诈骗",
    "割韭菜", "资金盘", "传销", "外挂", "破解", "盗版",
    # 品牌 / 平台 / 产品运营活动
    "淘宝", "天猫", "京东", "拼多多", "抖音", "快手", "B站", "b站", "哔哩哔哩",
    "微博", "小红书", "知乎", "微信", "支付宝", "王者荣耀", "原神", "和平精英",
    "英雄联盟", "LOL", "Steam", "steam", "Epic", "任天堂", "索尼", "微软",
    "苹果", "华为", "小米", "OPPO", "vivo", "麦当劳", "肯德基", "星巴克",
    "蜜雪冰城", "瑞幸", "双十一", "双十二", "618", "双11", "购物节",
    # 直播/主播
    "主播", "直播", "打赏", "礼物", "连麦", "PK", "弹幕", "up主", "UP主",
    # 低质谐音缩写 / 单字无义缩写（人工复核后加入）
    "歇b", "翔是", "希是", "T是", "儿白", "口胡", "虾男", "六模",
    "吊州", "泽合", "加去", "闻西", "铁T", "男娘", "十男九漏",
    "低配", "下头", "装b", "傻逼", "SB", "sb", "装逼", "恶心", "心机",
]

# ---- 分类标签（命中则打 tag，用于前端筛选）----
# 注意：要求关键词长度 ≥ 2 才做「包含」匹配，避免单字（花/海/云/风）大面积误命中。
TAG_RULES = [
    ("ACG", ["动漫", "动画", "漫画", "番剧", "二次元", "手办", "声优", "cosplay",
             "火影", "海贼", "柯南", "高达", "进击的巨人", "银魂", "奥特曼",
             "特摄", "galgame", "游戏王", "虚拟主播", "纸片人"]),
    ("游戏", ["游戏", "副本", "装备", "开黑", "上分", "掉分", "挂机", "氪金",
             "抽卡", "欧皇", "非酋", "赛季", "排位", "存档", "速通", "打野",
             "辅助", "输出", "奶妈", "boss"]),
    ("网络流行语", ["网络", "流行语", "表情包", "段子", "热词", "缩写", "弹幕",
                 "梗", "沙雕", "整活", "玩梗"]),
    ("情绪心态", ["焦虑", "破防", "摆烂", "躺平", "内卷", "内耗", "治愈",
                 "致郁", "社恐", "社牛", "孤独", "emo", "尴尬", "社死",
                 "耐心", "压力", "崩溃", "纠结", "迷茫"]),
    ("生活日常", ["上班", "打工", "加班", "通勤", "宿舍", "学生", "考试",
                 "食堂", "外卖", "奶茶", "减肥", "熬夜", "摸鱼", "养生",
                 "剁手", "赖床", "快递", "网购", "房租", "存款", "钱包",
                 "睡衣", "被窝", "闹钟", "地铁", "公交", "排队", "打折"]),
    ("人际关系", ["朋友", "情侣", "恋爱", "暗恋", "告白", "分手", "相亲",
                 "社交", "兄弟", "姐妹", "同学", "室友", "同事", "亲戚",
                 "父母", "爸妈", "老板", "对象", "相亲", "搭讪", "边界"]),
    ("文艺意象", ["月亮", "星空", "黄昏", "夏天", "秋天", "冬天", "春天",
                 "雨后", "海边", "日落", "月光", "灯火", "背影", "窗台",
                 "诗集", "老照片", "旧时光", "童年", "回忆", "沉默"]),
    ("怪诞日常", ["龙卷风", "天花板", "木乃伊", "龙卷", "外星", "平行宇宙",
                 "时空", "穿越", "重开", "转世", "复活", "变异", "实验",
                 "解构", "抽象", "行为艺术"]),
]

# 含这些语素的词，多半是「一次性热梗 / 事件名 / 需特定语境」，难以独立成题
DROP_PATTERNS = [
    r"是什么", r"怎么", r"如何", r"为什么", r"多少", r"哪些",
    r"指南", r"教程", r"攻略", r"盘点", r"合集", r"大全", r"排行榜",
    r"事件", r"风波", r"争议", r"回应", r"声明", r"道歉", r"辟谣",
    r"第\d+", r"\d{4}年", r"\d+月", r"\d+日",
    # 数值化 / 版本化命名（1260式社死、1023、1818造星工厂）
    r"^\d", r"\d+式", r"\d+版", r"\d+代", r"式[^\w]?$",
    # 句式化热梗（需要整句话才成立，不适合做题）
    r"^[^，。]{0,4}[，。！？]", r"[，。！？]$",
    r"^[你我他她它这那].{0,2}[吗呢吧啊]$",
    # 具体人物 / 地点 / 作品名残留
    r"^[麦克][^，，]{0,3}$",
    r"(奥特曼|高达|柯南|火影|海贼|高达|战锤|原神|王者)$",
]

# 「必须整句才成立」的口语化前后缀
DROP_PREFIX = ["什么是", "为什么", "怎么", "如何", "今天", "明天", "昨天",
               "今年", "去年", "明年", "晚上", "早上", "中午", "第", ]
DROP_SUFFIX = ["了没", "了吗", "不", "吧", "呢", "啊", "吗", "警告",
               "现状", "现场", "时刻", "模式", "警告", "警告"]

CN = re.compile(r"[\u4e00-\u9fff]")
# 允许作为「梗」的常见虚词/口语结尾（此时不判为句子）
OK_TAIL = ("人", "党", "族", "系", "控", "君", "帝", "神", "侠", "客",
           "狗", "猫", "猪", "王", "后", "长", "员", "师", "手", "心", "体")


def has_sensitive(word: str) -> bool:
    low = word.lower()
    for b in BLACKLIST:
        if b.lower() in low:
            return True
    return False


def is_noise(word: str) -> bool:
    # 纯符号 / 空
    if not re.search(r"[\w\u4e00-\u9fff]", word):
        return True
    # 含括号补充说明 —— 说明是消歧义条目，题目里不好看
    if re.search(r"[（(【\[]", word):
        return True
    # 纯英文 / 纯数字 / 纯字母数字混合
    if not CN.search(word):
        return True
    # 中文占比过低（如 "KKSK"、"a1高闪" 里的中文太少）
    cn = len(CN.findall(word))
    if cn == 0 or cn / len(word) < 0.5:
        return True
    # 含 URL / @ / # / 数字
    if re.search(r"[@#/\\]|http|www\.|\.(com|cn|net)", word, re.I):
        return True
    if re.search(r"\d", word):
        return True
    # 长度：作为三题题目，2-8 字最合用
    if len(word) < 2 or len(word) > 8:
        return True
    # 首尾词过滤（句式化 / 口语化）
    for p in DROP_PREFIX:
        if word.startswith(p):
            return True
    for s in DROP_SUFFIX:
        if word.endswith(s) and not word.endswith(OK_TAIL):
            return True
    # 包含句读标点 → 是句子不是词
    if re.search(r"[，。！？；、,.!?;]", word):
        return True
    # 一次性热梗 / 事件名
    for p in DROP_PATTERNS:
        if re.search(p, word):
            return True
    # 连续重复字符（水贴）
    if re.search(r"(.)\1{2,}", word):
        return True
    return False


def tag_of(word: str):
    tags = []
    low = word.lower()
    for name, kws in TAG_RULES:
        for k in kws:
            if k.lower() in low:
                tags.append(name)
                break
    return tags


def main():
    if not os.path.exists(RAW):
        print(f"缺少 {RAW}，请先运行 scrape_gengbaike.py", file=sys.stderr)
        sys.exit(1)
    raw = json.load(open(RAW, encoding="utf-8"))
    print(f"原始 {len(raw)} 条")

    kept = {}
    stats = {"sensitive": 0, "noise": 0, "dup": 0}
    for item in raw:
        w = item["word"].strip()
        if has_sensitive(w):
            stats["sensitive"] += 1
            continue
        if is_noise(w):
            stats["noise"] += 1
            continue
        if w in kept:
            stats["dup"] += 1
            continue
        kept[w] = {"word": w, "tags": tag_of(w), "id": item.get("id")}

    print(f"剔除: 敏感 {stats['sensitive']} / 噪音 {stats['noise']} / 重复 {stats['dup']}")
    print(f"保留 {len(kept)} 条")

    out = sorted(kept.values(), key=lambda x: (-len(x["tags"]), x["word"]))
    os.makedirs(DATA, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"-> {OUT}")

    # 分档预览
    from collections import Counter
    bylen = Counter()
    for v in out:
        n = len(v["word"])
        bylen["A(2)" if n <= 2 else "B(3-4)" if n <= 4 else "C(5+)"] += 1
    print("按字数分档:", dict(bylen))
    tagc = Counter(t for v in out for t in v["tags"])
    print("标签分布:", dict(tagc.most_common()))
    print("\n样本:")
    for v in out[:40]:
        print("   ", v["word"], v["tags"])


if __name__ == "__main__":
    main()
