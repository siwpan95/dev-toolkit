# -*- coding: utf-8 -*-
"""
拼音音节表
包含所有合法拼音音节（无声调），用于输入法拼写分割
"""

# 完整拼音音节列表（无调号，约410个音节）
# 按声母分组：空声母(零声母), b, p, m, f, d, t, n, l, g, k, h,
#              j, q, x, zh, ch, sh, r, z, c, s, y, w

PINYIN_SYLLABLES = frozenset([
    # 零声母
    "a", "ai", "an", "ang", "ao",
    "e", "ei", "en", "eng", "er",
    "o", "ou",
    # b
    "ba", "bai", "ban", "bang", "bao", "bei", "ben", "beng", "bi",
    "bian", "biao", "bie", "bin", "bing", "bo", "bu",
    # p
    "pa", "pai", "pan", "pang", "pao", "pei", "pen", "peng", "pi",
    "pian", "piao", "pie", "pin", "ping", "po", "pou", "pu",
    # m
    "ma", "mai", "man", "mang", "mao", "me", "mei", "men", "meng",
    "mi", "mian", "miao", "mie", "min", "ming", "miu", "mo", "mou", "mu",
    # f
    "fa", "fan", "fang", "fei", "fen", "feng", "fo", "fou", "fu",
    # d
    "da", "dai", "dan", "dang", "dao", "de", "dei", "den", "deng",
    "di", "dian", "diao", "die", "ding", "diu", "dong", "dou", "du",
    "duan", "dui", "dun", "duo",
    # t
    "ta", "tai", "tan", "tang", "tao", "te", "teng", "ti", "tian",
    "tiao", "tie", "ting", "tong", "tou", "tu", "tuan", "tui", "tun", "tuo",
    # n
    "na", "nai", "nan", "nang", "nao", "ne", "nei", "nen", "neng",
    "ni", "nian", "niang", "niao", "nie", "nin", "ning", "niu",
    "nong", "nou", "nu", "nuan", "nü", "nue", "nuo", "nv",
    # l
    "la", "lai", "lan", "lang", "lao", "le", "lei", "leng", "li",
    "lia", "lian", "liang", "liao", "lie", "lin", "ling", "liu",
    "long", "lou", "lu", "luan", "lun", "luo", "lü", "lve", "lüe", "lv",
    # g
    "ga", "gai", "gan", "gang", "gao", "ge", "gei", "gen", "geng",
    "gong", "gou", "gu", "gua", "guai", "guan", "guang", "gui", "gun", "guo",
    # k
    "ka", "kai", "kan", "kang", "kao", "ke", "ken", "keng", "kong",
    "kou", "ku", "kua", "kuai", "kuan", "kuang", "kui", "kun", "kuo",
    # h
    "ha", "hai", "han", "hang", "hao", "he", "hei", "hen", "heng",
    "hong", "hou", "hu", "hua", "huai", "huan", "huang", "hui", "hun", "huo",
    # j
    "ji", "jia", "jian", "jiang", "jiao", "jie", "jin", "jing",
    "jiong", "jiu", "ju", "juan", "jue", "jun",
    # q
    "qi", "qia", "qian", "qiang", "qiao", "qie", "qin", "qing",
    "qiong", "qiu", "qu", "quan", "que", "qun",
    # x
    "xi", "xia", "xian", "xiang", "xiao", "xie", "xin", "xing",
    "xiong", "xiu", "xu", "xuan", "xue", "xun",
    # zh
    "zha", "zhai", "zhan", "zhang", "zhao", "zhe", "zhen", "zheng",
    "zhi", "zhong", "zhou", "zhu", "zhua", "zhuai", "zhuan",
    "zhuang", "zhui", "zhun", "zhuo",
    # ch
    "cha", "chai", "chan", "chang", "chao", "che", "chen", "cheng",
    "chi", "chong", "chou", "chu", "chua", "chuai", "chuan",
    "chuang", "chui", "chun", "chuo",
    # sh
    "sha", "shai", "shan", "shang", "shao", "she", "shei", "shen",
    "sheng", "shi", "shou", "shu", "shua", "shuai", "shuan",
    "shuang", "shui", "shun", "shuo",
    # r
    "ran", "rang", "rao", "re", "ren", "reng", "ri", "rong",
    "rou", "ru", "rua", "ruan", "rui", "run", "ruo",
    # z
    "za", "zai", "zan", "zang", "zao", "ze", "zei", "zen", "zeng",
    "zi", "zong", "zou", "zu", "zuan", "zui", "zun", "zuo",
    # c
    "ca", "cai", "can", "cang", "cao", "ce", "cen", "ceng",
    "ci", "cong", "cou", "cu", "cuan", "cui", "cun", "cuo",
    # s
    "sa", "sai", "san", "sang", "sao", "se", "sen", "seng",
    "si", "song", "sou", "su", "suan", "sui", "sun", "suo",
    # y (i/u 行零声母)
    "ya", "yai", "yan", "yang", "yao", "ye", "yi", "yin",
    "ying", "yo", "yong", "you", "yu", "yuan", "yue", "yun",
    # w (u 行零声母)
    "wa", "wai", "wan", "wang", "wei", "wen", "weng", "wo", "wu",
    # 特殊 / 方言 / 语气
    "ng", "hng", "m", "n", "hm",
    # 其他变体 (ü的替代写法)
    "nve", "nue", "lve", "lue", "jve", "jue", "qve", "que", "xve", "xue",
    "yve", "yue",
])

# 声母集合（用于智能分割）
INITIALS = frozenset([
    "b", "p", "m", "f", "d", "t", "n", "l",
    "g", "k", "h", "j", "q", "x",
    "zh", "ch", "sh", "r", "z", "c", "s",
    "y", "w",
])

# 韵母集合
FINALS = frozenset([
    "a", "o", "e", "i", "u", "ü", "v",
    "ai", "ei", "ao", "ou",
    "an", "en", "ang", "eng", "ong",
    "ia", "ie", "iao", "iu", "iou",
    "ian", "in", "iang", "ing", "iong",
    "ua", "uo", "uai", "ui", "uei",
    "uan", "un", "uen", "uang", "ueng",
    "üe", "ve", "üan", "van", "ün", "vn",
    "er",
])


def is_valid_syllable(s: str) -> bool:
    """检查是否为合法拼音音节"""
    return s.lower() in PINYIN_SYLLABLES
