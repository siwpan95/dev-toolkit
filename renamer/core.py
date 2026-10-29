"""renamer 核心逻辑：基于正则表达式的批量重命名。

本模块为「纯逻辑」层，仅依赖 Python 标准库（re / os / uuid），
不依赖任何第三方包，也不依赖 GUI。这样可以在无显示器环境下
直接导入并测试纯函数。

主要接口：
    preview_renames(folder, pattern, repl, recursive=False)
        -> list[dict]，每个元素含 old / new / status / path
    apply_renames(preview, only_status='ok')
        -> (done, skipped)

status 取值：
    'ok'        正常，可重命名
    'conflict'  多个文件映射到同一新名（冲突，必定阻止）
    'empty'     替换后新名为空（阻止）
    'invalid'   新名含非法字符 / 保留名（阻止）
    'overwrite' 新名会被已存在且不会被腾空的条目占用（阻止）
"""

from __future__ import annotations

import os
import re
import uuid

# Windows 文件名非法字符
_ILLEGAL_CHARS = set('\\/:*?"<>|')

# Windows 保留设备名（不区分大小写）
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def has_illegal_chars(name: str) -> bool:
    """判断文件名是否非法（含非法字符、保留设备名、首尾空格/点）。

    参数:
        name: 待检查的文件名（不含路径）
    返回:
        bool: 含非法内容返回 True
    """
    if name == "":
        return True
    if any(ch in _ILLEGAL_CHARS for ch in name):
        return True
    # 保留设备名检查（取主名，去掉扩展名）
    stem = name.split(".", 1)[0].upper()
    if stem in _RESERVED_NAMES:
        return True
    # 文件名不能以空格或点结尾
    if name.endswith(".") or name.endswith(" "):
        return True
    return False


def _collect_entries(folder: str, recursive: bool):
    """收集待处理的「文件」条目，以及每个目录下的「全部名称」。

    重命名不跨目录，因此冲突 / 覆盖判定都以「同一目录内」为单位。
    返回: dict[dirpath] -> {
        'files':  list[(old_basename, fullpath)],   # 仅文件，会被重命名
        'all_names': set[str],                       # 该目录下文件+目录名，用于覆盖判定
    }
    """
    groups: dict[str, dict] = {}
    if recursive:
        for root, dirs, files in os.walk(folder):
            rec = groups.setdefault(root, {"files": [], "all_names": set()})
            rec["all_names"].update(dirs)
            rec["all_names"].update(files)
            for name in files:
                rec["files"].append((name, os.path.join(root, name)))
    else:
        rec = groups.setdefault(folder, {"files": [], "all_names": set()})
        for name in os.listdir(folder):
            full = os.path.join(folder, name)
            rec["all_names"].add(name)
            if os.path.isfile(full):
                rec["files"].append((name, full))
    return groups


def preview_renames(folder: str, pattern: str, repl: str, recursive: bool = False):
    """预览正则重命名结果，不做任何实际改动（dry-run）。

    参数:
        folder:    目标文件夹路径
        pattern:   正则表达式字符串（re 语法）
        repl:      替换模板字符串（支持 \\1 等分组引用，即 re.sub 语法）
        recursive: 是否递归处理子目录中的文件（默认 False）

    返回:
        list[dict]，每个元素形如:
            {
                'old':   str,   # 原文件名（basename）
                'new':   str,   # 正则替换后的新文件名
                'status':str,   # 'ok'|'conflict'|'empty'|'overwrite'|'invalid'
                'path':  str,   # 原文件完整路径（供 apply 使用）
            }

    异常:
        re.error: pattern 不是合法正则时抛出，由调用方（GUI）捕获并提示。

    说明:
        - 仅对「文件」做正则替换预览；目录不在重命名之列。
        - 判定顺序：空名 -> 非法字符 -> 无变化(no-op) -> 同目录重复新名(conflict)
          -> 覆盖已存在且不会被腾空的条目(overwrite) -> ok。
        - 链/环式重命名（a->b, b->c 或 a<->b）在预览中标记为 ok，
          实际执行时由 apply_renames 通过临时分级重命名保证安全。
    """
    regex = re.compile(pattern)

    groups = _collect_entries(folder, recursive)
    result: list[dict] = []

    for root, rec in groups.items():
        files = rec["files"]
        all_names = rec["all_names"]

        computed: list[dict] = []
        for old, full in files:
            new = regex.sub(repl, old)
            computed.append({"old": old, "new": new, "path": full})

        # 同目录新名计数（用于冲突检测）
        new_counts: dict[str, int] = {}
        for c in computed:
            new_counts[c["new"]] = new_counts.get(c["new"], 0) + 1

        # 会被「腾空」的旧名集合：old==X 且 new!=X 的文件
        vacated = {c["old"] for c in computed if c["new"] != c["old"]}

        for c in computed:
            new = c["new"]
            if new == "":
                c["status"] = "empty"
            elif has_illegal_chars(new):
                c["status"] = "invalid"
            elif new == c["old"]:
                # 正则未改变文件名，属于无操作
                c["status"] = "ok"
            elif new_counts[new] > 1:
                # 同一目录下多个文件映射到同一新名
                c["status"] = "conflict"
            elif new in all_names and new not in vacated:
                # 目标名已被一个「不会移动走」的现存条目占用
                c["status"] = "overwrite"
            else:
                c["status"] = "ok"
            result.append(c)

    return result


def _stage_rename(old_path: str, new_path: str) -> None:
    """安全地重命名一个文件，使用临时文件分级避免批内相互覆盖。

    策略：先把 old_path 重命名为一个唯一临时名（同目录，保证同文件系统），
    随后再将该临时名重命名为最终 new_path。由于所有临时名全局唯一，
    因此即便存在链式（a->b, b->c）或环式（a<->b）重命名，也不会在
    中间步骤互相覆盖。

    异常:
        任何 OSError（含文件被占用 PermissionError / 目标已存在等）
        都会向上抛出，由调用方捕获并跳过该条目。
    """
    tmp_path = old_path + ".renamer_tmp_" + uuid.uuid4().hex
    os.rename(old_path, tmp_path)      # 阶段一：腾空原槽位
    try:
        os.rename(tmp_path, new_path)  # 阶段二：落入最终槽位
    except OSError:
        # 阶段二失败：尽量把临时文件还原，避免文件「丢失」
        try:
            if not os.path.exists(old_path):
                os.rename(tmp_path, old_path)
        except OSError:
            pass
        raise


def apply_renames(preview: list[dict], only_status: str = "ok") -> tuple[int, int]:
    """根据预览结果执行实际重命名。

    参数:
        preview:      preview_renames 的返回值
        only_status:  只执行状态等于该值的条目（默认 'ok'）；
                      非该状态的条目（conflict/empty/overwrite/invalid）
                      一律跳过并计入 skipped。

    返回:
        (done, skipped):
            done    : 成功重命名的文件数量
            skipped : 被跳过（状态不符 / 无变化 / 出错）的文件数量

    安全策略:
        - 只处理指定状态的条目，风险条目天然被阻止。
        - new == old 的无操作条目直接跳过（计入 skipped）。
        - 执行前再次确认目标不存在，存在则跳过（双保险）。
        - 使用临时分级重命名，避免批内覆盖。
        - 文件被占用 / 无权限等错误被捕获并跳过，不影响其余文件。
    """
    done = 0
    skipped = 0
    for item in preview:
        if item.get("status") != only_status:
            skipped += 1
            continue
        old = item["old"]
        new = item["new"]
        if new == old:
            # 无变化，跳过
            skipped += 1
            continue
        old_path = item["path"]
        new_path = os.path.join(os.path.dirname(old_path), new)
        # 双保险：执行时若目标已存在，跳过（理论上 preview 已拦截）
        if os.path.exists(new_path):
            skipped += 1
            continue
        try:
            _stage_rename(old_path, new_path)
            done += 1
        except OSError:
            # 文件被占用 / 权限不足 / 其他错误：跳过并继续
            skipped += 1
    return done, skipped
