"""抓取 gengbaike.cn（梗百科）词条标题，过滤后输出为 JSON。

用法:
    python scrape_gengbaike.py            # 抓取并写出 data/gengbaike_raw.json
    python scrape_gengbaike.py --limit 3000

抓取面:
    * list-recentchange-N   最近更新（分页，字母小写形式）
    * list-letter-<X>-N     字母/数字索引（X = 0-9, A-Z, a-z）
    * list-focus-N          热门/精彩/推荐词条
    * list-popularity       人气指数
    * list-weekuserlist / list-allcredit  贡献榜（抓词条）
"""
import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://gengbaike.cn/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "data")


def fetch(url, tries=3, pause=0.35):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45, context=CTX) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(pause * (i + 1))
    print(f"  ! FAIL {url}: {last}", file=sys.stderr)
    return None


def parse_entries(html):
    """从列表页抽出 (id, title) 对。"""
    out = re.findall(r'doc-view-(\d+)\.html"[^>]*>([^<]{1,80})</a>', html)
    res = []
    for did, title in out:
        t = title.strip()
        if not t or t.startswith("["):
            continue
        res.append((did, t))
    return res


def max_page(html, list_name):
    """该列表页的最大页码（同列表的内部链接）。"""
    nums = [int(m) for m in re.findall(rf"{re.escape(list_name)}-(\d+)\.html", html)]
    return max(nums) if nums else 1


def scrape_list(list_name, start_url, page_limit=60):
    """从 start_url 起，逐页抓取 list_name 列表。"""
    url = start_url
    seen_pages = set()
    got = {}
    page = 0
    while url and page < page_limit:
        if url in seen_pages:
            break
        seen_pages.add(url)
        page += 1
        html = fetch(url)
        if html is None:
            break
        entries = parse_entries(html)
        for did, t in entries:
            got.setdefault(t, did)
        total = max_page(html, list_name)
        if page == 1:
            print(f"  {list_name}: {total} pages, {len(entries)} per page")
        if page >= total:
            break
        url = f"{BASE}{list_name}-{page + 1}.html"
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="每列表抓取上限（页），0=全部")
    args = ap.parse_args()
    page_limit = args.limit if args.limit else 60

    all_entries = {}

    print("[1/3] 最近更新 list-recentchange")
    all_entries.update(scrape_list("list-recentchange", f"{BASE}list-recentchange-1.html", page_limit))

    print("[2/3] 字母/数字索引 list-letter-*")
    keys = [str(i) for i in range(10)] + [chr(c) for c in range(ord("A"), ord("Z") + 1)] \
        + [chr(c) for c in range(ord("a"), ord("z") + 1)]
    for k in keys:
        got = scrape_list(f"list-letter-{k}", f"{BASE}list-letter-{k}-1.html", page_limit)
        if got:
            print(f"    {k}: +{len(got)}")
        all_entries.update(got)

    print("[3/3] 热门 / 精彩 / 推荐 / 人气")
    for ln, first in [("list-focus", 1), ("list-focus", 2), ("list-focus", 3),
                      ("list-popularity", 1), ("list-weekuserlist", 1),
                      ("list-allcredit", 1)]:
        url = f"{BASE}{ln}-{first}.html"
        html = fetch(url)
        if html is None:
            continue
        got = parse_entries(html)
        total = max_page(html, ln)
        # 这几个列表一般只有 1 页，但若多页也抓完
        for p in range(2, min(total, page_limit) + 1):
            h2 = fetch(f"{BASE}{ln}-{p}.html")
            if h2:
                got += parse_entries(h2)
        print(f"    {ln}-{first}: {len(got)}")
        for did, t in got:
            all_entries.setdefault(t, did)

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "gengbaike_raw.json")
    payload = [{"word": w, "id": i} for w, i in sorted(all_entries.items())]
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"\n总计 {len(payload)} 条 -> {out}")


if __name__ == "__main__":
    main()
