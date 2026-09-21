# 词语池（pools）

三个分档文件夹，每个档对应一个 `words.json`：

| 档 | 路径 | 汉字数 |
|---|---|---|
| A | `title_A/words.json` | 1–2 |
| B | `title_B/words.json` | 3–4 |
| C | `title_C/words.json` | 5 字以上 |

## 数据模型

每条词条是**对象**，不再是裸字符串：

```json
[
  { "word": "云",   "source": "文学少女", "tags": [] },
  { "word": "奶茶", "source": "通用词表", "tags": ["食物"] }
]
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `word` | string | 题目文本 |
| `source` | string | 词源标识：`文学少女` / `通用词表` / `梗百科` |
| `tags` | string[] | 主题标签（前端暂未启用，预留给主题筛选） |

> **兼容性**：后端 `topics.js` 的 `normalizeEntry` 兼容纯字符串与对象两种写法，
> 因此旧版的 `words.json = ["云", "雪"]` 仍可工作（会被识别为 source=`文学少女`）。

## 词源说明

- **文学少女**（101 条）：原作《文学少女》「三题故事」题目的人工整理集，
  这是项目最初的词库，全部由用户与最初的作品细节提供，作为题目风格基线保留。
- **通用词表**（≈6200 条）：清华大学 THUOCL 开放中文词库（thunlp/THUOCL），
  包含动物 / 食物 / 诗词 / 成语 / 职业 等常用词子集；脚本仅保留词频前 12% 的常用词，
  并按字数自动归入三档。本词库替代了「《现代汉语词典》《辞海》全集」的角色：
  这两部词典正文受版权保护不可分发，而 THUOCL 是同类型、许可更宽松的开源替代。
- **梗百科**（≈1620 条）：来自 [gengbaike.cn](https://gengbaike.cn)（梗百科）的精选网络流行语。
  已过滤掉：涉政 / 涉性 / 饭圈 / 真人 / 品牌 / 一次性事件名 / 纯数字英文缩写 等。
  详见 `scripts/filter_gengbaike.py` 的过滤规则。

## 出题规则

`src/topics.js` 的 `randomThree()` 从三档各抽 1 条组成「三题」，可选 `sources` 参数
过滤词源：缺省 = 全部词源；显式传入 = 仅从这些词源里抽。前端在工具栏下方提供
「词源」勾选控件。

## 抓取与重建

```bash
# 1) 抓取梗百科 + 通用词表（结果写入 scripts/data/）
python scripts/scrape_gengbaike.py
python scripts/fetch_general_words.py

# 2) 过滤梗百科词条
python scripts/filter_gengbaike.py

# 3) 重建三档 words.json（合并 文学少女 + 通用词表 + 梗百科）
python scripts/build_pools.py
```

构建脚本运行前会读 `scripts/data/pools_backup/` 作为「原作」词库，
确保重新构建不会丢原作词。