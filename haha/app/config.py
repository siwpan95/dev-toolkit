"""配置层 — 全局共享的常量与路径解析。

原 haha.py 中的 LANGUAGE_MAP 与 helloworld 目录定位逻辑统一移到此处，
供 Model / View / Controller 共用，避免散落在各模块中重复定义。

增强（联网检索补充）：
- LANGUAGES: 每种语言的增强元数据（显示名、标准扩展名、范式、诞生年、
  设计者、一句话简介）。范式/年份/设计者经维基百科、各语言官网及
  Rosetta Code / learnxbyexample 等公开资料交叉核对。
- LANGUAGE_MAP: 由 LANGUAGES 派生，保持与原接口兼容（key -> 显示名）。
"""

import os


# 增强元数据表
# 字段: name 显示名 | ext 标准扩展名 | paradigm 范式 | year 诞生年
#       designer 设计者 | blurb 一句话简介
LANGUAGES = {
    "ada":       {"name": "Ada",       "ext": ".adb",  "paradigm": "多范式；强类型、并发、OO",        "year": 1983, "designer": "Jean Ichbiah 等 (CII Honeywell Bull)", "blurb": "高可靠嵌入式与航天系统"},
    "agda":      {"name": "Agda",      "ext": ".agda", "paradigm": "依赖类型、纯函数式",              "year": 2007, "designer": "Ulf Norell",                        "blurb": "依赖类型证明助手"},
    "algol68":   {"name": "ALGOL 68",  "ext": ".a68",  "paradigm": "过程式、多范式",                  "year": 1968, "designer": "IFIP WG 2.1",                      "blurb": "ALGOL 系的现代演进"},
    "asm":       {"name": "Assembly",  "ext": ".asm",  "paradigm": "低级；面向指令集",                "year": 1949, "designer": "Kathleen Booth 等",                "blurb": "直接对应机器指令"},
    "bash":      {"name": "Bash",      "ext": ".sh",   "paradigm": "脚本、Shell",                     "year": 1989, "designer": "Brian Fox",                        "blurb": "Unix Shell 脚本"},
    "basic":     {"name": "BASIC",     "ext": ".bas",  "paradigm": "过程式、教学",                    "year": 1964, "designer": "J. Kemeny & T. Kurtz",            "blurb": "入门教学语言"},
    "bcpl":      {"name": "BCPL",      "ext": ".bcpl", "paradigm": "过程式、系统",                    "year": 1966, "designer": "Martin Richards",                   "blurb": "C 语言的前身之一"},
    "befunge":   {"name": "Befunge",   "ext": ".b98",  "paradigm": "esolang、二维栈",                  "year": 1993, "designer": "Chris Pressey",                    "blurb": "二维网格指令 esolang"},
    "brainfuck": {"name": "Brainfuck", "ext": ".b",    "paradigm": "esolang、极简图灵完备",            "year": 1993, "designer": "Urban Müller",                     "blurb": "8 条指令的极简 esolang"},
    "c":         {"name": "C",         "ext": ".c",    "paradigm": "过程式、系统",                    "year": 1972, "designer": "Dennis Ritchie",                   "blurb": "系统/操作系统基石"},
    "clean":     {"name": "Clean",     "ext": ".icl",  "paradigm": "纯函数式",                        "year": 1987, "designer": "Rinus Plasmeijer 等 (奈梅亨大学)",  "blurb": "纯函数式 + uniqueness 类型"},
    "clojure":   {"name": "Clojure",   "ext": ".clj",  "paradigm": "Lisp、函数式 (JVM)",              "year": 2007, "designer": "Rich Hickey",                      "blurb": "JVM 上的 Lisp"},
    "cobol":     {"name": "COBOL",     "ext": ".cbl",  "paradigm": "过程式、商业",                    "year": 1959, "designer": "Grace Hopper 等 (CODASYL)",        "blurb": "企业/金融遗留系统"},
    "cpp":       {"name": "C++",       "ext": ".cpp",  "paradigm": "多范式；OOP/泛型",                "year": 1985, "designer": "Bjarne Stroustrup",                "blurb": "C 的超集；系统与应用"},
    "crystal":   {"name": "Crystal",   "ext": ".cr",   "paradigm": "静态、Ruby 风",                   "year": 2014, "designer": "Ary Borenszweig 等",               "blurb": "类 Ruby 的静态编译"},
    "csharp":    {"name": "C#",        "ext": ".cs",   "paradigm": "多范式；OO/组件 (.NET)",          "year": 2000, "designer": "Anders Hejlsberg 等 (Microsoft)", "blurb": ".NET 生态主力"},
    "curry":     {"name": "Curry",     "ext": ".curry","paradigm": "函数式逻辑",                      "year": 1990, "designer": "Michael Hanus 等",                 "blurb": "函数式逻辑编程"},
    "dart":      {"name": "Dart",      "ext": ".dart", "paradigm": "面向对象、JIT/AOT",               "year": 2011, "designer": "Lars Bak & Kasper Lund (Google)",  "blurb": "Flutter 前端语言"},
    "elixir":    {"name": "Elixir",    "ext": ".ex",   "paradigm": "函数式 (BEAM)",                   "year": 2011, "designer": "José Valim",                       "blurb": "基于 Erlang VM 的现代语言"},
    "erlang":    {"name": "Erlang",    "ext": ".erl",  "paradigm": "函数式、并发、容错",              "year": 1986, "designer": "Joe Armstrong 等 (Ericsson)",      "blurb": "电信/分布式容错"},
    "forth":     {"name": "Forth",     "ext": ".fth",  "paradigm": "栈式、拼接",                      "year": 1970, "designer": "Charles H. Moore",                 "blurb": "极简栈式/嵌入式"},
    "fortran":   {"name": "Fortran",   "ext": ".f90",  "paradigm": "过程式、数值",                    "year": 1957, "designer": "John Backus 等 (IBM)",             "blurb": "科学计算元老"},
    "fsharp":    {"name": "F#",        "ext": ".fs",   "paradigm": "函数式 (.NET)",                   "year": 2005, "designer": "Don Syme (Microsoft)",              "blurb": ".NET 上的函数式"},
    "go":        {"name": "Go",        "ext": ".go",   "paradigm": "并发、系统",                      "year": 2009, "designer": "Pike, Griesemer, Thompson (Google)","blurb": "云原生/并发简洁"},
    "groovy":    {"name": "Groovy",    "ext": ".groovy","paradigm": "动态、JVM",                      "year": 2003, "designer": "James Strachan",                   "blurb": "JVM 动态脚本"},
    "hare":      {"name": "Hare",      "ext": ".ha",   "paradigm": "系统级、过程式",                  "year": 2021, "designer": "Drew DeVault",                     "blurb": "现代 C 替代；强调简洁"},
    "haskell":   {"name": "Haskell",   "ext": ".hs",   "paradigm": "纯函数式、惰性",                  "year": 1990, "designer": "Haskell 委员会 (SPJ 等)",          "blurb": "纯函数式标杆"},
    "idris":     {"name": "Idris",     "ext": ".idr",  "paradigm": "纯函数式、依赖类型",              "year": 2009, "designer": "Edwin Brady",                      "blurb": "依赖类型/证明级类型"},
    "intercal":  {"name": "INTERCAL",  "ext": ".i",    "paradigm": "esolang、恶搞",                   "year": 1972, "designer": "Don Woods & James Lyon",           "blurb": "故意反直觉的 esolang"},
    "java":      {"name": "Java",      "ext": ".java", "paradigm": "面向对象、JVM",                   "year": 1995, "designer": "James Gosling (Sun)",              "blurb": "跨平台企业级"},
    "javascript": {"name": "JavaScript", "ext": ".js", "paradigm": "原型 OO、事件",                   "year": 1995, "designer": "Brendan Eich (Netscape)",          "blurb": "Web 前端脚本"},
    "kotlin":    {"name": "Kotlin",    "ext": ".kt",   "paradigm": "多范式 (JVM/OO)",                 "year": 2011, "designer": "JetBrains",                        "blurb": "JVM 现代；Android 首选"},
    "logo":      {"name": "Logo",      "ext": ".logo", "paradigm": "多范式；教育、Turtle",            "year": 1967, "designer": "Feurzeig, Papert 等",              "blurb": "儿童编程/海龟绘图"},
    "lolcode":   {"name": "LOLCODE",   "ext": ".lol",  "paradigm": "esolang、类英语",                 "year": 2007, "designer": "Adam Lindsay",                     "blurb": "网络迷因风格 esolang"},
    "lua":       {"name": "Lua",       "ext": ".lua",  "paradigm": "脚本、可嵌入",                    "year": 1993, "designer": "Ierusalimschy 等 (PUC-Rio)",       "blurb": "轻量可嵌入脚本"},
    "malbolge":  {"name": "Malbolge",  "ext": ".mal",  "paradigm": "esolang、极难",                   "year": 1998, "designer": "Ben Olmstead",                     "blurb": "以但丁地狱命名的 esolang"},
    "mercury":   {"name": "Mercury",   "ext": ".m",    "paradigm": "逻辑函数式、强类型",              "year": 1995, "designer": "Zoltan Somogyi 等 (墨尔本大学)",    "blurb": "强类型逻辑编程"},
    "mumps":     {"name": "MUMPS",     "ext": ".mps",  "paradigm": "多范式；数据库",                  "year": 1966, "designer": "John Lazarus (麻省总医院)",         "blurb": "医疗/事务数据库"},
    "nim":       {"name": "Nim",       "ext": ".nim",  "paradigm": "多范式、元编程",                  "year": 2008, "designer": "Andreas Rumpf",                    "blurb": "Python 风语法 + 编译"},
    "ocaml":     {"name": "OCaml",     "ext": ".ml",   "paradigm": "函数式、强类型",                  "year": 1996, "designer": "Xavier Leroy 等 (INRIA)",          "blurb": "工业级 ML"},
    "odin":      {"name": "Odin",      "ext": ".odin", "paradigm": "系统级、多范式",                  "year": 2016, "designer": "Ginger Bill",                       "blurb": "面向数据/游戏的系统语言"},
    "ook":       {"name": "Ook!",      "ext": ".ook",  "paradigm": "esolang (Brainfuck 变体)",        "year": 2009, "designer": "David Morgan-Mar",                 "blurb": "仅用 Ook. Ook? Ook! 的 esolang"},
    "pascal":    {"name": "Pascal",    "ext": ".pas",  "paradigm": "过程式、教学",                    "year": 1970, "designer": "Niklaus Wirth",                    "blurb": "结构化教学语言"},
    "perl":      {"name": "Perl",      "ext": ".pl",   "paradigm": "多范式、文本处理",                "year": 1987, "designer": "Larry Wall",                       "blurb": "胶水/正则之王"},
    "php":       {"name": "PHP",       "ext": ".php",  "paradigm": "服务端脚本",                      "year": 1995, "designer": "Rasmus Lerdorf",                   "blurb": "Web 后端主力"},
    "pli":       {"name": "PL/I",      "ext": ".pl1",  "paradigm": "多范式；科学+商业",               "year": 1964, "designer": "IBM (George Radin)",               "blurb": "大型机科学商业通用"},
    "postscript": {"name": "PostScript","ext": ".ps",   "paradigm": "堆栈式、声明式",                  "year": 1982, "designer": "Warnock & Geschke (Adobe)",         "blurb": "页面描述/打印"},
    "powershell":{"name": "PowerShell", "ext": ".ps1", "paradigm": "脚本、管道对象",                  "year": 2006, "designer": "Jeffrey Snover (Microsoft)",        "blurb": "Windows 对象管道 Shell"},
    "prolog":    {"name": "Prolog",    "ext": ".pro",  "paradigm": "逻辑编程",                        "year": 1972, "designer": "Alain Colmerauer 等",              "blurb": "规则/回溯逻辑"},
    "python":    {"name": "Python",    "ext": ".py",   "paradigm": "多范式；OO/脚本",                 "year": 1991, "designer": "Guido van Rossum",                 "blurb": "易读通用脚本"},
    "r":         {"name": "R",         "ext": ".r",    "paradigm": "数值、统计、向量",                "year": 1993, "designer": "Ross Ihaka & R. Gentleman",         "blurb": "统计计算"},
    "ruby":      {"name": "Ruby",      "ext": ".rb",   "paradigm": "面向对象、脚本",                  "year": 1995, "designer": "Yukihiro Matsumoto",               "blurb": "以人为本的脚本"},
    "rust":      {"name": "Rust",      "ext": ".rs",   "paradigm": "系统、内存安全",                  "year": 2010, "designer": "Graydon Hoare (Mozilla)",           "blurb": "无 GC 的内存安全"},
    "scala":     {"name": "Scala",     "ext": ".scala","paradigm": "函数式+OO (JVM)",                "year": 2004, "designer": "Martin Odersky",                    "blurb": "JVM 上的函数式"},
    "scheme":    {"name": "Scheme",    "ext": ".scm",  "paradigm": "最小 Lisp、函数式",               "year": 1975, "designer": "Steele & Sussman",                 "blurb": "Scheme Lisp 方言"},
    "shakespeare":{"name": "Shakespeare", "ext": ".spl","paradigm": "esolang、戏剧脚本",              "year": 2001, "designer": "Åslund & Johansson",               "blurb": "用戏剧对白写程序的 esolang"},
    "simula":    {"name": "Simula",    "ext": ".sim",  "paradigm": "面向对象、仿真",                  "year": 1967, "designer": "Dahl & Nygaard",                    "blurb": "OOP 与仿真的起源"},
    "solidity":  {"name": "Solidity",  "ext": ".sol",  "paradigm": "合约、静态",                      "year": 2014, "designer": "Gavin Wood (Ethereum)",             "blurb": "以太坊智能合约"},
    "sql":       {"name": "SQL",       "ext": ".sql",  "paradigm": "声明式（集合）",                  "year": 1974, "designer": "Chamberlin & Boyce (IBM)",          "blurb": "关系数据库查询"},
    "swift":     {"name": "Swift",     "ext": ".swift","paradigm": "多范式、安全",                    "year": 2014, "designer": "Chris Lattner 等 (Apple)",          "blurb": "Apple 平台现代语言"},
    "tcl":       {"name": "Tcl",       "ext": ".tcl",  "paradigm": "脚本、可嵌入",                    "year": 1988, "designer": "John Ousterhout",                   "blurb": "可嵌入工具脚本"},
    "typescript":{"name": "TypeScript","ext": ".ts",   "paradigm": "静态类型 (JS 超集)",             "year": 2012, "designer": "Anders Hejlsberg (Microsoft)",      "blurb": "JavaScript 的类型层"},
    "vala":      {"name": "Vala",      "ext": ".vala", "paradigm": "面向对象（类 C#）",              "year": 2006, "designer": "Billeter & Sandrini (GNOME)",       "blurb": "GNOME 原生；编译为 C"},
    "xml":       {"name": "XML",       "ext": ".xml",  "paradigm": "标记语言",                        "year": 1998, "designer": "W3C (Tim Bray 等)",                "blurb": "可扩展标记/数据交换"},
    "zig":       {"name": "Zig",       "ext": ".zig",  "paradigm": "系统级、过程式",                  "year": 2016, "designer": "Andrew Kelley",                    "blurb": "现代系统语言；替代 C"},
    # ---- 联网检索新增的缺失语言 ----
    "julia":     {"name": "Julia",     "ext": ".jl",   "paradigm": "多范式；多重分派、JIT",           "year": 2012, "designer": "Bezanson, Karpinski, Shah, Edelman","blurb": "科学计算高性能"},
    "d":         {"name": "D",         "ext": ".d",    "paradigm": "系统级多范式",                    "year": 2001, "designer": "Walter Bright (Digital Mars)",      "blurb": "C/C++ 性能 + 高级抽象"},
    "matlab":    {"name": "MATLAB",    "ext": ".m",    "paradigm": "数值/矩阵、专有",                 "year": 1984, "designer": "Cleve Moler (MathWorks)",           "blurb": "数值与工程仿真"},
    "raku":      {"name": "Raku",      "ext": ".raku", "paradigm": "多范式；渐进类型",                "year": 2000, "designer": "Larry Wall (2019 更名 Raku)",      "blurb": "Perl 的现代继任"},
    "elm":       {"name": "Elm",       "ext": ".elm",  "paradigm": "纯函数式、响应式",                "year": 2012, "designer": "Evan Czaplicki",                    "blurb": "可靠的前端 Web"},
    "gdscript":  {"name": "GDScript",  "ext": ".gd",   "paradigm": "面向对象（类 Python）",           "year": 2014, "designer": "Godot 社区 (Linietsky 等)",         "blurb": "Godot 游戏引擎专用"},
    "hack":      {"name": "Hack",      "ext": ".hack", "paradigm": "PHP 方言（渐进类型）",            "year": 2014, "designer": "Facebook (Verlaguet 等)",           "blurb": "HHVM 上的静态类型 PHP"},
    "objectivec":{"name": "Objective-C","ext": ".m",   "paradigm": "面向对象（C 超集、消息）",        "year": 1984, "designer": "Brad Cox & Tom Love",               "blurb": "Apple/NeXT 生态"},
    # ---- 联网检索补充的更多标志性缺失语言 ----
    "smalltalk": {"name": "Smalltalk", "ext": ".st",  "paradigm": "纯面向对象、消息传递",            "year": 1972, "designer": "Alan Kay 等 (Xerox PARC)",          "blurb": "面向对象范式诞生地"},
    "lisp":      {"name": "Common Lisp", "ext": ".lisp", "paradigm": "Lisp、多范式、动态",          "year": 1984, "designer": "Guy Steele & Scott Fahlman 等 (ANSI)","blurb": "工业级 Lisp；宏系统强大"},
    "vb":        {"name": "Visual Basic", "ext": ".vb", "paradigm": "面向对象、.NET",               "year": 1991, "designer": "Alan Cooper 等 (Microsoft)",        "blurb": "易学易用的 .NET 语言"},
}

# 与原接口兼容：key -> 显示名
LANGUAGE_MAP = {key: info["name"] for key, info in LANGUAGES.items()}

# 项目根目录：app/ 的父目录（即 G:/haha）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Hello World 源码数据目录（与 main.py 同级）
HELLOWORLD_DIR = os.path.join(BASE_DIR, "helloworld")
