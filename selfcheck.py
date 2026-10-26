#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renamer（正则批量重命名）无头自检。

只导入 core（纯逻辑层，仅标准库），不导入 main（Tkinter GUI）。

验证点：
  1. 预览风险判定：ok / conflict（同目录撞名）/ empty（空名）/ invalid（非法字符）/
     overwrite（目标名被不会腾空的现存条目占用）/ 无变化 no-op；
  2. dry-run 语义：preview_renames 不改动磁盘（文件名与内容保持不变）；
  3. 状态推进 + 数据往返：apply_renames 真正改名，改名前后文件内容一致，
     未匹配文件保持原样，返回的 (done, skipped) 计数正确；
  4. has_illegal_chars 的 Windows 保留名 / 非法字符判定。

全部操作在系统临时目录中进行，不触碰项目目录与仓库文件。
"""
import os
import shutil
import sys
import tempfile
import time
import traceback


def _setup_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def _write(folder, name, text):
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _names(folder):
    return sorted(os.listdir(folder))


def run_checks():
    from core import apply_renames, has_illegal_chars, preview_renames

    checks = []

    # --- 1. 非法名判定 -------------------------------------------------------
    if has_illegal_chars("ok.txt") or has_illegal_chars("重命名.txt"):
        raise AssertionError("合法文件名被误判为非法")
    for bad in ("CON", "aux.txt", "a:b.txt", "x?.txt", "trail. ", ""):
        if not has_illegal_chars(bad):
            raise AssertionError(f"非法文件名未被识别: {bad!r}")
    checks.append("非法名判定：保留设备名/非法字符/空名均被拦截")

    tmpdir = tempfile.mkdtemp(prefix="renamer_selfcheck_")
    try:
        # --- 2. 预览状态判定 + dry-run --------------------------------------
        case = os.path.join(tmpdir, "preview")
        os.makedirs(case)
        _write(case, "a_1.txt", "one")
        _write(case, "a_2.txt", "two")
        _write(case, "note.md", "keep")
        before = _names(case)

        preview = preview_renames(case, r"a_(\d+)", r"b_\1")
        by_old = {item["old"]: item for item in preview}
        if set(by_old) != {"a_1.txt", "a_2.txt", "note.md"}:
            raise AssertionError(f"预览条目集合错误: {sorted(by_old)}")
        if by_old["a_1.txt"]["new"] != "b_1.txt" or by_old["a_1.txt"]["status"] != "ok":
            raise AssertionError(f"分组引用替换错误: {by_old['a_1.txt']}")
        if by_old["note.md"]["status"] != "ok" or by_old["note.md"]["new"] != "note.md":
            raise AssertionError("未匹配文件应原样保留（no-op）")
        if _names(case) != before:
            raise AssertionError("preview_renames 改动了磁盘（dry-run 被破坏）")

        # 冲突：多个文件映射到同一新名
        conflict_dir = os.path.join(tmpdir, "conflict")
        os.makedirs(conflict_dir)
        _write(conflict_dir, "x1.txt", "1")
        _write(conflict_dir, "x2.txt", "2")
        conflict = {i["old"]: i["status"] for i in preview_renames(conflict_dir, r"x\d", "y")}
        if set(conflict.values()) != {"conflict"}:
            raise AssertionError(f"冲突未识别: {conflict}")

        # 空名
        empty_dir = os.path.join(tmpdir, "empty")
        os.makedirs(empty_dir)
        _write(empty_dir, "drop.txt", "d")
        empty = preview_renames(empty_dir, r".*", "")
        if empty[0]["status"] != "empty":
            raise AssertionError(f"空名未识别: {empty[0]['status']}")

        # 非法字符
        invalid_dir = os.path.join(tmpdir, "invalid")
        os.makedirs(invalid_dir)
        _write(invalid_dir, "v1.txt", "v")
        invalid = preview_renames(invalid_dir, r"v1", "a/b")
        if invalid[0]["status"] != "invalid":
            raise AssertionError(f"非法字符未识别: {invalid[0]['status']}")

        # 覆盖：目标名被一个不会腾空的现存条目占用（同名子目录占位）
        overwrite_dir = os.path.join(tmpdir, "overwrite")
        os.makedirs(os.path.join(overwrite_dir, "b_1.txt"))
        _write(overwrite_dir, "a_1.txt", "src")
        overwrite = {i["old"]: i["status"] for i in preview_renames(overwrite_dir, r"a_(\d+)", r"b_\1")}
        if overwrite.get("a_1.txt") != "overwrite":
            raise AssertionError(f"覆盖未识别: {overwrite}")
        checks.append("预览风险判定：conflict/empty/invalid/overwrite 与 no-op 均正确且不改动磁盘")

        # --- 3. 状态推进：实际改名 + 内容往返 --------------------------------
        apply_dir = os.path.join(tmpdir, "apply")
        os.makedirs(apply_dir)
        for idx in range(3):
            _write(apply_dir, f"img_{idx}.txt", f"payload-{idx}")
        _write(apply_dir, "keep.md", "untouched")

        apply_preview = preview_renames(apply_dir, r"img_(\d+)", r"pic_\1")
        if any(i["status"] != "ok" for i in apply_preview):
            raise AssertionError(f"可执行用例出现风险状态: {apply_preview}")
        done, skipped = apply_renames(apply_preview)
        if (done, skipped) != (3, 1):
            raise AssertionError(f"apply_renames 计数错误: done={done} skipped={skipped}")

        expected = ["keep.md", "pic_0.txt", "pic_1.txt", "pic_2.txt"]
        if _names(apply_dir) != expected:
            raise AssertionError(f"改名后目录内容错误: {_names(apply_dir)}")
        for idx in range(3):
            if _read(os.path.join(apply_dir, f"pic_{idx}.txt")) != f"payload-{idx}":
                raise AssertionError(f"改名后内容丢失: pic_{idx}.txt")
        if _read(os.path.join(apply_dir, "keep.md")) != "untouched":
            raise AssertionError("未匹配文件内容被改动")

        # 风险条目一律跳过：冲突目录执行后文件不变
        conflict_apply = preview_renames(conflict_dir, r"x\d", "y")
        done2, skipped2 = apply_renames(conflict_apply)
        if (done2, skipped2) != (0, 2) or _names(conflict_dir) != ["x1.txt", "x2.txt"]:
            raise AssertionError(f"风险条目未阻止: done={done2} skipped={skipped2} {_names(conflict_dir)}")
        checks.append("执行重命名：3 个文件改名成功且内容逐字节一致，冲突全部跳过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return checks


def main() -> int:
    _setup_stdout()
    started = time.time()
    try:
        checks = run_checks()
    except Exception as exc:
        print(f"selfcheck FAIL: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1

    print(f"selfcheck ok: renamer 无头核心逻辑（{'; '.join(checks)}）"
          f" [{time.time() - started:.2f}s]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
