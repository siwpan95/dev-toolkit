# 1-2 字题目池

按汉字数分档（A 档）的所有词语。`words.json` 的数据模型：

```json
[
  { "word": "云",   "source": "文学少女", "tags": [] },
  { "word": "奶茶", "source": "通用词表", "tags": ["食物"] }
]
```

- `word`：题目文本。
- `source`：词源（文学少女 / 通用词表 / 梗百科），由前端筛选控件呈现。
- `tags`：可选标签，前端暂不展示，预留做主题筛选。

通用词表来源：清华大学 THUOCL 开放中文词库（thunlp/THUOCL，经 funNLP 镜像）。
梗百科来源：https://gengbaike.cn（抓取脚本见 `scripts/`）。