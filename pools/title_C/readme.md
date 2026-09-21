# 5 字以上题目池

按汉字数分档（C 档）的所有词语。`words.json` 的数据模型同 `title_A`：

```json
[
  { "word": "全自动洗衣机", "source": "文学少女", "tags": [] },
  { "word": "秋天的第一杯奶茶", "source": "梗百科", "tags": ["生活日常"] }
]
```

- `word`：题目文本。
- `source`：词源（文学少女 / 通用词表 / 梗百科），由前端筛选控件呈现。
- `tags`：可选标签。

通用词表来源：清华大学 THUOCL 开放中文词库。
梗百科来源：https://gengbaike.cn（抓取脚本见 `scripts/`）。