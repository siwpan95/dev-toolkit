#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cordis 表格应用 —— Python 侧 OpenPyXL 工作者（JSON-RPC over stdio）

协议纪律（见 cordis-host-python-bridge 技能）：
  - stdout 只走一行一对象的 JSON-RPC 2.0，所有日志/异常栈走 stderr；
  - 被调库若直接 print 会污染协议通道，故处理器执行期间重定向 stdout->stderr；
  - 每个方法 try/except 兜住，返回 JSON-RPC error（-32601 未知方法 / -32000 执行异常），
    保证子进程不死。

编码纪律：宿主 Node 一律以 UTF-8 写管道，故启动时强制把 stdio 转成 UTF-8（见 _force_utf8_stdio）。
Windows 中文环境里 Python 默认按区域编码 gbk/cp936 解 stdin，UTF-8 中文会被解成乱码；
解不动的字节还会退化成本不该出现的**孤立代理字符**（如 U+DCBC），
这种字符串能一路存活到 openpyxl 落盘那一刻，才由 lxml 以
"UnicodeEncodeError: surrogates not allowed" 报出来 —— 现场离病根很远，
故在唯一的协议入口一次性掐掉。

工作簿以 path 为键缓存在内存，save 时落盘；close 时保存并移出缓存。
"""

import sys
import os
import io
import json
import base64
import decimal
import datetime
import traceback
import contextlib

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


WORKBOOKS = {}  # path -> Workbook


def _json_default(o):
    """把 openpyxl 单元格里的非 JSON 原生类型转成 JSON 安全表示。

    read_sheet 直接吐单元格原始值，而 Excel 里的日期是 datetime/date/time 对象、
    时间差是 timedelta、高精度数字可能是 Decimal、二进制是 bytes —— json.dumps 一个都不认。
    这里统一成 ISO 8601 字符串 / 数字，宿主拿到的就是"确定能过 JSON"的东西。
    （踩过：一个日期单元格就能让 json.dumps 抛 TypeError；那时序列化还在 try 之外，
      整个 worker 进程被带走，表格能力当场全废。）
    """
    if isinstance(o, (datetime.datetime, datetime.date, datetime.time)):
        return o.isoformat()
    if isinstance(o, datetime.timedelta):
        return o.total_seconds()
    if isinstance(o, decimal.Decimal):
        return float(o)
    if isinstance(o, (bytes, bytearray)):
        return base64.b64encode(bytes(o)).decode("ascii")
    return str(o)


def _coerce(val, ctype):
    """按列声明的类型，把宿主传来的值还原成 Excel 原生类型。

    宿主与 worker 之间只有 JSON，日期必然是字符串；要让 Excel 里的日期能排序/筛选/做日期计算，
    就得在这里变回 datetime。只做"能确定"的转换：解析失败原样写入，绝不为了类型好看丢数据。
    """
    if val is None or val == "" or not ctype:
        return val
    if ctype in ("datetime", "date", "time"):
        if not isinstance(val, str):
            return val
        try:
            dt = datetime.datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            return val
        if ctype == "date":
            return dt.date()
        if ctype == "time":
            return dt.time()
        return dt
    if ctype == "number":
        if isinstance(val, (int, float)):
            return val
        try:
            text = str(val).strip()
            return float(text) if ("." in text or "e" in text.lower()) else int(text)
        except (TypeError, ValueError):
            return val
    if ctype == "text":
        return str(val)
    return val


def _get_wb(path):
    if path in WORKBOOKS:
        return WORKBOOKS[path]
    if os.path.exists(path):
        wb = load_workbook(path)
    else:
        wb = Workbook()
    WORKBOOKS[path] = wb
    return wb


def _sheet(wb, name):
    if name:
        if name in wb.sheetnames:
            return wb[name]
        return wb.create_sheet(title=name)
    return wb.active


def handle(method, params):
    p = params or {}
    path = p.get("path")

    if method == "ping":
        import openpyxl
        return {
            "python": sys.version.split()[0],
            "openpyxl": openpyxl.__version__,
        }

    if method == "create_workbook":
        wb = Workbook()
        if p.get("sheet"):
            wb.active.title = p["sheet"]
        WORKBOOKS[path] = wb
        return {"ok": True, "sheets": wb.sheetnames}

    if method == "add_sheet":
        wb = _get_wb(path)
        ws = wb.create_sheet(title=p.get("name", "Sheet"))
        return {"ok": True, "sheets": wb.sheetnames}

    if method == "write_rows":
        wb = _get_wb(path)
        ws = _sheet(wb, p.get("sheet"))
        start_row = int(p.get("start_row", 1))
        start_col = int(p.get("start_col", 1))
        rows = p.get("rows", [])
        col_types = p.get("col_types") or []
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                ctype = col_types[j] if j < len(col_types) else None
                # openpyxl 不接受 None 以外的"空"；None 即空单元格
                ws.cell(row=start_row + i, column=start_col + j, value=_coerce(val, ctype))
        return {"ok": True, "rows": len(rows)}

    if method == "write_cell":
        wb = _get_wb(path)
        ws = _sheet(wb, p.get("sheet"))
        ws.cell(row=int(p["row"]), column=int(p["col"]), value=p.get("value"))
        return {"ok": True}

    if method == "style_header":
        wb = _get_wb(path)
        ws = _sheet(wb, p.get("sheet"))
        row = int(p.get("row", 1))
        ncols = int(p.get("ncols", 1))
        fill_hex = p.get("fill", "FF4472C4")
        font_color = p.get("font_color", "FFFFFFFF")
        fill = PatternFill(start_color=fill_hex, end_color=fill_hex, fill_type="solid")
        font = Font(bold=True, color=font_color)
        thin = Side(style="thin", color="FFB0B0B0")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        for c in range(1, ncols + 1):
            cell = ws.cell(row=row, column=c)
            cell.font = font
            cell.fill = fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border
        return {"ok": True}

    if method == "set_column_width":
        wb = _get_wb(path)
        ws = _sheet(wb, p.get("sheet"))
        col = int(p["col"])
        ws.column_dimensions[get_column_letter(col)].width = float(p.get("width", 15))
        return {"ok": True}

    # 数字格式：一次调用可带多段区域，避免宿主为"日期列 / 时长列"来回几十次往返
    # items: [{ "range": "A2:A8", "format": "yyyy-mm-dd" }, ...]
    if method == "set_number_format":
        wb = _get_wb(path)
        ws = _sheet(wb, p.get("sheet"))
        items = p.get("items") or []
        applied = 0
        for it in items:
            rng = it.get("range")
            if not rng:
                continue
            fmt = it.get("format") or "General"
            # ws["B2"] 给单个 Cell，ws["A2:A8"] 给 tuple of tuple —— 前者不可迭代，先归一成列表
            target = ws[rng]
            if isinstance(target, tuple):
                cells = [c for row in target for c in (row if isinstance(row, tuple) else (row,))]
            else:
                cells = [target]
            for cell in cells:
                cell.number_format = fmt
            applied += 1
        return {"ok": True, "applied": applied}

    # 冻结窗格（表头常驻）：cell 形如 "A2" 表示冻结首行
    if method == "freeze_panes":
        wb = _get_wb(path)
        ws = _sheet(wb, p.get("sheet"))
        ws.freeze_panes = p.get("cell") or None
        return {"ok": True, "freeze_panes": ws.freeze_panes}

    # 工作表元信息：给宿主/测试一个"能验证文件真实形态"的读口
    # （日期到底是真日期还是文本、表头冻没冻、单元格是什么格式 —— 光看 read_sheet 分不清）
    if method == "sheet_meta":
        wb = _get_wb(path)
        ws = _sheet(wb, p.get("sheet"))
        row = int(p.get("row", 2))
        cols = range(1, ws.max_column + 1)
        return {
            "title": ws.title,
            "sheets": list(wb.sheetnames),
            "max_row": ws.max_row,
            "max_col": ws.max_column,
            "freeze_panes": ws.freeze_panes,
            "number_formats": [ws.cell(row=row, column=c).number_format for c in cols],
            "value_types": [type(ws.cell(row=row, column=c).value).__name__ for c in cols],
        }

    if method == "read_sheet":
        wb = _get_wb(path)
        ws = _sheet(wb, p.get("sheet"))
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        return {"rows": rows, "max_row": ws.max_row, "max_col": ws.max_column}

    if method == "save":
        wb = WORKBOOKS.get(path)
        if not wb:
            return {"ok": False, "error": "workbook not opened"}
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        wb.save(path)
        return {"ok": True, "path": path}

    if method == "close":
        wb = WORKBOOKS.pop(path, None)
        if wb:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            wb.save(path)
        return {"ok": True}

    raise ValueError("unknown method: " + str(method))


def _force_utf8_stdio():
    """把三个标准流钉死成 UTF-8（Windows 区域编码下的必要动作）。

    - stdin/stdout 是 JSON-RPC 协议通道，两端都必须是 UTF-8，一个字节都不能猜；
      Node 的 child.stdin.write(str) 就是 UTF-8，所以 Python 侧也必须是 UTF-8。
    - stdin 用 errors="replace"：真收到坏字节时退化成 U+FFFD，让 json.loads 失败后
      按约定跳过这一行，而不是抛 UnicodeDecodeError 把整个循环掀翻。
    - stdout 用 errors="strict"：宁可在这里明确报错，也不要往协议里写坏数据。
    - stderr 用 errors="backslashreplace"：日志是排障通道，任何怪字符都不该让日志本身崩掉。

    非 TextIOWrapper（例如已被重定向成别的对象）时静默跳过。
    """
    for stream, errors in (
        (sys.stdin, "replace"),
        (sys.stdout, "strict"),
        (sys.stderr, "backslashreplace"),
    ):
        try:
            stream.reconfigure(encoding="utf-8", errors=errors)
        except Exception:
            pass


def main():
    _force_utf8_stdio()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        msgid = req.get("id")
        method = req.get("method")
        params = req.get("params")
        # 序列化也必须在 try 里：json.dumps 会因为单元格里的 datetime/Decimal 抛 TypeError，
        # 一旦漏在 try 外，异常会掀翻整个 for 循环并带走进程 ——
        # 一个坏单元格 = 表格能力全废（宿主后续所有调用都变成 "python worker exited"）。
        try:
            with contextlib.redirect_stdout(sys.stderr):
                result = handle(method, params)
            resp = {"jsonrpc": "2.0", "id": msgid, "result": result}
            payload = json.dumps(resp, ensure_ascii=False, default=_json_default)
        except Exception as e:
            resp = {
                "jsonrpc": "2.0",
                "id": msgid,
                "error": {"code": -32000, "message": str(e), "data": traceback.format_exc()},
            }
            # 到这里再炸就真没办法了（连错误都编不成 JSON），但也不能静默丢响应
            payload = json.dumps(resp, ensure_ascii=False, default=_json_default)
        sys.stdout.write(payload + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
