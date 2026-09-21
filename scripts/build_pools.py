"""把已抓取的原始素材整合为项目实际的词库文件 pools/title_A|B|C/words.json。

输入:
  scripts/data/general_words_raw.json    通用词表（THUOCL 等开源词表）
  scripts/data/gengbaike_selected.json   梗百科精选
  pools/title_*/words.json               既有词库（文学少女向，需保留）

输出（覆盖写）:
  pools/title_A/words.json   1-2 字
  pools/title_B/words.json   3-4 字
  pools/title_C/words.json   5 字以上

数据模型：{"word": "...", "source": "...", "tags": [...]}
  source ∈ {文学少女, 通用词表, 梗百科}
  兼容旧格式：读取时同时接受纯字符串。

分档规则（按汉字数）
  A: 1-2 字
  B: 3-4 字
  C: >=5 字
"""
import json
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")
POOLS = os.path.join(ROOT, "pools")

SRC_LITERATURE = "文学少女"
SRC_GENERAL = "通用词表"
SRC_MEME = "梗百科"

CN = re.compile(r"[\u4e00-\u9fff]")

# 通用词表里混进来的专有名词/术语，做题目并不合适
GENERAL_DROP = [
    r"^(一串|一株|一片|一棵)",         # 病虫害名录式堆叠
    r"(虫|螨|蝽|蛾|蝇|蚊|蚧|虱|螟|蚜)$",  # 昆虫细目（动物词库里极多）
    r"(科|属|目)$",                     # 生物分类
    r"(病|症|炎|癌|瘤|梗|栓)$",          # 医学（职业/食物库里混入）
    r"(酶|酸|素|苷|酯|酮|醛|胺|肽)$",     # 生化
    r"(法|条例|规定|标准|规范)$",         # 法规
    r"^第",                             # 序数
    # 地名 / 品种名 / 商号（做题目太具体）
    r"(省|市|县|镇|村|区|路|街|巷)$",
    r"^(北京|上海|广州|深圳|南京|杭州|苏州|成都|重庆|武汉|西安|天津)",
    r"(饭店|酒楼|餐厅|酒店|宾馆|公司|集团|工厂|超市|商行|老铺|铺子)$",
    r"(鸡|鸭|鹅|猪|牛|羊|犬|猫|兔|鸽|鱼|虾|蟹|贝)$",  # 具体品种（清远麻鸡、陇东黑山羊）
    r"^[上下左右前后东南西北中]$",
]

# 过于书面/成语化的四字短语占比很高，会淹没可具象化的词；但成语本身可用，
# 只要不是纯议论性的。这里剔除明显的议论/评价性成语。
GENERAL_DROP_REGEX_EXTRA = [
    r"^[不以无有是非]$",               # 论说式开头
    r"(主义|思想|制度|政策|方针|原则|措施|办法)$",
    r"(得失|是非|对错|优劣)$",
    # 化学式 / 农资 / 工业品（食物库长尾混入）
    r"(酸钾|酸钠|碳酸|磷酸|硫酸|硝酸|氯化|氢氧化)",
    r"(二氢|三氢|过氧|次氯)",
    r"(复合肥|尿素|微肥|冲施肥|叶面肥)$",
    # 医学病名（过长且不适合做题）
    r"(变态反应|综合征|综合症|功能不全|功能衰竭)$",
    r"(迟发型|急性|慢性|原发性|继发性)",
]

MULTI_CN = re.compile(r"[\u4e00-\u9fff]")


def cn_len(s: str) -> int:
    """按汉字个数计长（忽略标点/字母/数字）。"""
    return len(MULTI_CN.findall(s))


def keep_general(w: str) -> bool:
    if len(w) < 2 or len(w) > 12:
        return False
    if not CN.search(w):
        return False
    if re.search(r"[（(【\[，。！？；、,.!?;]", w):
        return False
    if re.search(r"\d", w):
        return False
    for p in GENERAL_DROP + GENERAL_DROP_REGEX_EXTRA:
        if re.search(p, w):
            return False
    # 中文占比过低
    if cn_len(w) / len(w) < 0.8:
        return False
    return True


def load_existing():
    """读取既有词库，保留原作（文学少女）词。

    备份优先：本脚本会覆盖写 pools/*/words.json，因此不能简单地把现文件当作
    「全部是文学少女」——它可能已经是上一轮生成的含 source 字段的版本。
    策略：
      * 若存在 pools/__backup/（用户手工提交的原始原作词），以其为准；
      * 否则读 scripts/data/pools_backup/；
      * 都没有：退回读现文件，但只认 source 为空/文学少女 的条目。
    """
    out = {}
    candidates = [
        os.path.join(POOLS, "__backup"),
        os.path.join(DATA, "pools_backup"),
    ]
    for backup in candidates:
        if os.path.isdir(backup):
            for key in ("title_A", "title_B", "title_C"):
                p = os.path.join(backup, key + "_words.json")
                try:
                    data = json.load(open(p, encoding="utf-8"))
                except Exception:
                    continue
                for it in data:
                    w = it if isinstance(it, str) else it.get("word")
                    if w:
                        out[w] = {"word": w, "source": SRC_LITERATURE, "tags": []}
            if out:
                return out

    # 无任何备份：退回读现文件，但只认原作来源
    for key in ("title_A", "title_B", "title_C"):
        p = os.path.join(POOLS, key, "words.json")
        try:
            data = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        for it in data:
            if isinstance(it, str):
                out[it] = {"word": it, "source": SRC_LITERATURE, "tags": []}
            elif it.get("source") in (None, "", SRC_LITERATURE):
                w = it.get("word")
                if w:
                    out[w] = {"word": w, "source": SRC_LITERATURE, "tags": []}
    return out


def main():
    # ---- 1. 文学少女既有词（最高优先级）----
    db = load_existing()
    print(f"既有（{SRC_LITERATURE}）: {len(db)}")

    # ---- 2. 通用词表 ----
    # 按词频取「常用段」：THUOCL 词表尾部是大量冷僻菜名/物种名/地名，
    # 对「三题故事」毫无价值，一并是噪音的主要来源。
    p = os.path.join(DATA, "general_words_raw.json")
    if os.path.exists(p):
        raw = json.load(open(p, encoding="utf-8"))
        items = raw["words"]
        freqs = sorted((it.get("freq", 0) for it in items), reverse=True)
        # 词频阈值：保留词频 >= 该值的词。THUOCL 长尾是海量冷僻物种名/菜名/地名，
        # 取 12% 分位可保证留下的基本是日常高频词。
        cut_rank = min(len(freqs) - 1, max(0, int(len(freqs) * 0.12)))
        threshold = freqs[cut_rank]
        n = 0
        skipped_freq = 0
        skipped_rule = 0
        for it in items:
            w = it["word"]
            tag = it.get("tag")
            if w in db:
                continue
            if it.get("freq", 0) < threshold:
                skipped_freq += 1
                continue
            if not keep_general(w):
                skipped_rule += 1
                continue
            db[w] = {"word": w, "source": SRC_GENERAL,
                     "tags": [tag] if tag else []}
            n += 1
        print(f"{SRC_GENERAL}: +{n}（词频阈值 {threshold}，取前 {cut_rank + 1}/{len(items)}；"
              f"按频率剔除 {skipped_freq}，按规则剔除 {skipped_rule}）")
    else:
        print(f"! 缺少 {p}，跳过通用词表", file=sys.stderr)

    # ---- 3. 梗百科 ----
    p = os.path.join(DATA, "gengbaike_selected.json")
    if os.path.exists(p):
        raw = json.load(open(p, encoding="utf-8"))
        n = 0
        for it in raw:
            w = it["word"]
            if w in db:
                continue
            db[w] = {"word": w, "source": SRC_MEME, "tags": it.get("tags", [])}
            n += 1
        print(f"{SRC_MEME}: +{n}")
    else:
        print(f"! 缺少 {p}，跳过梗百科", file=sys.stderr)

    # ---- 4. 分档输出 ----
    buckets = {"title_A": [], "title_B": [], "title_C": []}
    for item in db.values():
        n = cn_len(item["word"])
        if n <= 2:
            buckets["title_A"].append(item)
        elif n <= 4:
            buckets["title_B"].append(item)
        else:
            buckets["title_C"].append(item)

    print()
    for key, items in buckets.items():
        items.sort(key=lambda x: (x["source"], x["word"]))
        out = os.path.join(POOLS, key, "words.json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=1)
        src = Counter(i["source"] for i in items)
        print(f"{key}: {len(items)}  {dict(src)}")

    print("\n总计:", sum(len(v) for v in buckets.values()))
    # 抽样展示
    for key in buckets:
        print(f"\n--- {key} 样本 ---")
        for it in buckets[key][:8]:
            print("   ", it["word"], "|", it["source"], it["tags"])


if __name__ == "__main__":
    main()
