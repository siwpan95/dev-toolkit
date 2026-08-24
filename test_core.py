"""renamer 冒烟测试：纯逻辑验证，无需 GUI / 显示器。

运行：python test_core.py
"""
import os
import tempfile

# Windows 控制台编码修复：测试输出含 ✅/✓ 等符号，GBK 代码页无法编码
import sys
if sys.stdout and getattr(sys.stdout, "encoding", "").lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


import core


def main() -> None:
    # 用临时目录造数据，测完自动清理
    with tempfile.TemporaryDirectory() as tmp:
        names = ["a_1.txt", "a_2.txt"]
        for n in names:
            with open(os.path.join(tmp, n), "w", encoding="utf-8") as f:
                f.write("x")

        pattern = r"a_(\d+)"
        repl = r"b_\1"

        # 1) 仅预览，不改动磁盘
        preview = core.preview_renames(tmp, pattern, repl, recursive=False)
        print("预览结果：")
        for p in preview:
            print(f"  {p['old']} -> {p['new']}  [{p['status']}]")

        # 断言：新名正确且状态 ok
        mapping = {p["old"]: p["new"] for p in preview}
        assert mapping.get("a_1.txt") == "b_1.txt", mapping
        assert mapping.get("a_2.txt") == "b_2.txt", mapping
        assert all(p["status"] == "ok" for p in preview), "状态应全为 ok"

        # 断言：dry-run 路径——只 preview 不 apply，文件不动
        after_preview = sorted(os.listdir(tmp))
        assert after_preview == sorted(names), f"预览不应改动文件: {after_preview}"

        # 2) 真正执行
        done, skipped = core.apply_renames(preview, only_status="ok")
        print(f"\napply_renames -> done={done}, skipped={skipped}")
        assert done == 2 and skipped == 0, (done, skipped)

        final = sorted(os.listdir(tmp))
        assert final == ["b_1.txt", "b_2.txt"], f"重命名结果错误: {final}"
        print("\n最终文件：", final)

        # 3) 风险检测：制造冲突（两个文件映射到同一新名）
        with tempfile.TemporaryDirectory() as tmp2:
            for n in ["c_1.txt", "c_2.txt"]:
                with open(os.path.join(tmp2, n), "w", encoding="utf-8") as f:
                    f.write("x")
            # pattern 去掉数字差异 -> 都变成 d.txt
            pv = core.preview_renames(tmp2, r"c_(\d+)", r"d", recursive=False)
            conflict_cnt = sum(1 for p in pv if p["status"] == "conflict")
            print("\n冲突用例预览状态：", [p["status"] for p in pv])
            assert conflict_cnt == 2, "应检测到 2 个冲突"
            done2, skipped2 = core.apply_renames(pv, only_status="ok")
            assert done2 == 0, "冲突项不应被执行"
            assert sorted(os.listdir(tmp2)) == ["c_1.txt", "c_2.txt"], "冲突时不该改动"

    print("\n✅ 全部冒烟测试通过")


if __name__ == "__main__":
    main()
