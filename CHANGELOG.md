# Changelog

本项目所有值得注意的变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.1.0] - 2026-08-28

### Changed

- 候选词频升级：接入 rime-ice 词库真实词频（词/成语候选按真实使用频率排序，此前为按词典顺序的启发式值）；未收录的罕见词回退原启发式垫底。
- 词库扩充：并入 rime-ice 中 print 词库之外的常用词约 30 万条（`build_rime_freq.py` 生成产物，权重 ≥100 截断）。
- 缓存 v2：词/成语索引缓存重建（`word_index_v2.pkl` / `idiom_index_v2.pkl`）；`cache/` 不再入库。

### Added

- `build_rime_freq.py`：构建 rime-ice 词频产物（`dictionary/rime_ice/rime_freq.pkl` + `rime_words.pkl` + `SOURCE.txt` 来源注记）；产物不入版本库，随安装包 datas 分发。

### 数据来源注记

- 词频数据源自 [rime-ice](https://github.com/iDvel/rime-ice)（GPLv3）cn_dicts 的 `base.dict.yaml` / `ext.dict.yaml`（组成词库：华宇野风词库、THUOCL、现代汉语常用词表、腾讯词向量；上游多源合并去重调频）。本程序本体 MIT；词频数据沿用 rime-ice 口径，随包 `dictionary/rime_ice/SOURCE.txt` 供溯源。

## [1.0.0] - 2026-08-27

### Added

- 首个发行版：Windows 单文件可执行程序（PyInstaller，Python 3.14）。
- 发布面：gitee [siwpan/print](https://gitee.com/siwpan/print) release `v1.0.0`（中文拼音输入法 v1.0.0）。