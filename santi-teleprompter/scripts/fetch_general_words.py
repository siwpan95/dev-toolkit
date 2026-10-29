"""获取公开可自由使用的中文词表，按字数分档导出。

数据源
------
THUOCL（清华大学开放中文词库，THUOCL: Tsinghua Open Chinese Lexicon）
  https://github.com/thunlp/THUOCL  ——  面向中文信息处理的开源词表，许可宽松。
  经 funNLP 仓库（fighting41love/funNLP）镜像分发。

采用的具体词表：
  THUOCL_animal.txt    动物
  THUOCL_food.txt      食物
  THUOCL_poem.txt      诗词高频词
  THUOCL_chengyu.txt   成语
  professions.txt      职业

为什么不用《现代汉语词典》《辞海》
  二者正文均受版权保护，词条全集不可再分发。此处改用公开可自由使用的
  开源词表；来源标注为「通用词表」，不冒充词典。

输出: data/general_words_raw.json
  {"sources": [...], "words": [{"word": ..., "tag": ...}, ...]}
"""
import json
import os
import sys
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"

RAW_BASE = "https://raw.githubusercontent.com/fighting41love/funNLP/master/data/"
MIRRORS = [
    "https://gh-proxy.com/{u}",
    "https://ghfast.top/{u}",
    "{u}",
]

# (相对路径, 分类标签)
FILES = [
    ("动物词库/THUOCL_animal.txt", "动物"),
    ("食物词库/THUOCL_food.txt", "食物"),
    ("诗词短句词库/THUOCL_poem.txt", "诗词"),
    ("成语词库/THUOCL_chengyu.txt", "成语"),
    ("职业词库/professions.txt", "职业"),
]


def enc(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (p.scheme, p.netloc, urllib.parse.quote(p.path), p.query, p.fragment))


def fetch(url, tries=3, timeout=90):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            # 404 / 错误页是小型 HTML
            if len(data) < 4096 and data.lstrip()[:1] in (b"<", b"{"):
                continue
            return data
        except Exception as e:  # noqa: BLE001
            print(f"    fail[{i}] {type(e).__name__}", file=sys.stderr)
    return None


def decode(data: bytes) -> str:
    """THUOCL / funNLP 的文件有 UTF-8 也有 GBK，逐个尝试。"""
    for cs in ("utf-8", "gb18030", "utf-16"):
        try:
            t = data.decode(cs)
            # 出现大量替换字符则视为解码失败
            if t.count("\ufffd") < len(t) * 0.01:
                return t
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def get_file(rel):
    """先对路径做百分号编码，再套镜像前缀。

    坑：GitHub 返回的 download_url 里中文是未编码的，直接交给 urllib 会抛
    UnicodeEncodeError('ascii' codec can't encode ...)。因此必须自己 quote。
    另外镜像站（gh-proxy / ghfast）要求传入的仍是**已编码**的 URL，不能再编码一次，
    否则 %E5%8A%A8 会被二次转义成 %25E5%258A%25A8 → 404。
    """
    url = enc(RAW_BASE + rel)
    # 镜像站容易过载，原生 raw 最可靠，放最前
    attempts = [url] + [tpl.format(u=url) for tpl in MIRRORS]
    for u in attempts:
        d = fetch(u, tries=2)
        if d:
            print(f"    OK {rel}  ({len(d)}B)  via {u.split('/')[2]}")
            return d
    print(f"    FAIL {rel}", file=sys.stderr)
    return None


def main():
    os.makedirs(DATA, exist_ok=True)
    out = {}
    # 记录每个词的词频（同一词在多表出现取最大值），用于后续按常用度排序
    freq = {}
    ok_sources = []
    for rel, tag in FILES:
        print(f"[抓取] {tag} <- {rel}")
        d = get_file(rel)
        if not d:
            continue
        text = decode(d)
        n = 0
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t") if "\t" in line else line.split(" ")
            w = parts[0].strip()
            f = 0
            if len(parts) > 1:
                try:
                    f = int(parts[1])
                except ValueError:
                    f = 0
            if not w or len(w) > 12:
                continue
            if w in out:
                freq[w] = max(freq.get(w, 0), f)
                continue
            out[w] = tag
            freq[w] = f
            n += 1
        ok_sources.append(f"{tag}({n})")

    # 按词频降序排列输出，供 build_pools 截取高频段
    words = [{"word": w, "tag": t, "freq": freq.get(w, 0)}
             for w, t in sorted(out.items(), key=lambda kv: -freq.get(kv[0], 0))]
    payload = {"sources": ["THUOCL 清华大学开放中文词库"], "words": words}
    p = os.path.join(DATA, "general_words_raw.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"\n合计 {len(words)} 词（去重后）")
    print("来源:", ", ".join(ok_sources))
    print("->", p)
    print("\n高频前 40:", [w["word"] for w in words[:40]])
    print("词频中位段样本:", [w["word"] for w in words[len(words)//2:len(words)//2+25]])


if __name__ == "__main__":
    main()
