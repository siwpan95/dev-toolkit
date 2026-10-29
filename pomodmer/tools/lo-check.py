# lo-check.py —— 用 LibreOffice 自己（UNO API）打开 xlsx 并汇报结构
#
# 为什么值得做：openpyxl 读回来"没问题"不等于 Excel/WPS/LibreOffice 打开没问题 ——
# 它们是不同的实现。这里让**另一个实现**（LibreOffice Calc 的导入过滤器）真的打开文件，
# 报出工作表、图表数量、隐藏属性、抽样单元格；需要修复的文件会在这条路上暴露成异常或结构缺失。
#
# 必须用 LibreOffice 自带的 python（它带 uno 模块）：
#   Windows: F:\Libre\program\python.exe lo-check.py <xlsx> <端口> <输出 json 路径> [--pdf <pdf>] [--resave <xlsx>]
#   Linux:   /usr/lib/libreoffice/program/python 或系统 python3（需 python3-uno）
#
# --resave：让 LibreOffice 用它**自己的 xlsx 导出过滤器**重存一份，供调用方用 openpyxl 再读 ——
# 跨实现往返能查出"只有 openpyxl 自己看得懂"的东西。
#
# 结果**写文件**而不是打印：Windows 控制台编码会把中文表名变乱码，写 UTF-8 文件两边都干净。
import json
import sys

import uno
from com.sun.star.beans import PropertyValue


def connect(port):
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local)
    return resolver.resolve(
        f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")


def prop(name, value):
    p = PropertyValue()
    p.Name = name
    p.Value = value
    return p


def main():
    path, port, out_path = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    pdf_path = None
    resave_path = None
    if "--pdf" in sys.argv:
        pdf_path = sys.argv[sys.argv.index("--pdf") + 1]
    if "--resave" in sys.argv:
        resave_path = sys.argv[sys.argv.index("--resave") + 1]

    ctx = connect(port)
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    # 不加 ReadOnly：下面要用 LO 自己的 xlsx 导出过滤器重存一份（只读文档存不了）
    doc = desktop.loadComponentFromURL(
        uno.systemPathToFileUrl(path), "_blank", 0,
        (prop("Hidden", True), prop("UpdateDocMode", 0)))

    out = {
        "sheet_count": doc.Sheets.Count,
        # 仅作参考：LibreOffice 会因良性原因把文档标记为已修改，不能拿它当"需要修复"的判据
        "modified_after_load": bool(doc.isModified),
        "sheets": [],
        "pdf": None,
        "resaved": None,
    }
    for i in range(doc.Sheets.Count):
        sh = doc.Sheets.getByIndex(i)
        row = {
            "name": sh.Name,
            "visible": bool(sh.IsVisible),
            "charts": sh.Charts.Count if hasattr(sh, "Charts") else 0,
            "a1": sh.getCellByPosition(0, 0).getString() if sh.Rows.Count and sh.Columns.Count else None,
            "b2_type": sh.getCellByPosition(1, 1).getType().value if sh.Rows.Count > 1 and sh.Columns.Count > 1 else None,
            "b2_value": sh.getCellByPosition(1, 1).getValue() if sh.Rows.Count > 1 and sh.Columns.Count > 1 else None,
            "b2_text": sh.getCellByPosition(1, 1).getString() if sh.Rows.Count > 1 and sh.Columns.Count > 1 else None,
        }
        out["sheets"].append(row)

    if pdf_path:
        # 存一份 PDF：既是"能正常渲染"的证据，也给人肉眼看一眼图表长什么样
        doc.storeToURL(uno.systemPathToFileUrl(pdf_path),
                       (prop("FilterName", "calc_pdf_Export"),))
        out["pdf"] = pdf_path

    if resave_path:
        # 让 **LibreOffice 自己**把文档重存成 xlsx（等价于"另一个实现读完又写回"），
        # 之后调用方会用 openpyxl 再读这份文件 —— 跨实现往返能查出"只有 openpyxl 自己看得懂"的东西。
        doc.storeToURL(uno.systemPathToFileUrl(resave_path),
                       (prop("FilterName", "Calc MS Excel 2007 XML"),))
        out["resaved"] = resave_path

    doc.close(False)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


main()
