#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字体爬虫工具 v2.1 — 免费公版字体下载器
=============================================
参考 webcopier v5.4 架构重构：
  - BrowserIdentityManager：从 identities.json 加载身份池，支持 curl_cffi TLS 指纹
  - RateLimiter：线程安全限速，感知 robots.txt Crawl-delay
  - FontHTTPClient：双后端（requests + curl_cffi）、自适应重试、身份轮换
  - FontCrawlEngine：通用爬虫 + 各站点专属解析器
  - GoogleFontsEngine：修复双重请求 bug
  - 站点支持：猫啃网、字体天下、100font、Fontesk、ZeoSeven、字库星球、字体库(zitiku)、
               Open Foundry、DaFont、GitHub Releases

可爬取字体站点（免登/免费/公版）汇总见 BUILTIN_SITES 常量。

作者: 全哥
版本: 2.1
"""

import json
import os
import re
import sys
import threading
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, unquote
from urllib.robotparser import RobotFileParser
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import requests
from bs4 import BeautifulSoup

# ============================================================
#  可选依赖
# ============================================================
try:
    from curl_cffi import requests as curl_requests
    _HAS_CURL_CFFI = True
except ImportError:
    _HAS_CURL_CFFI = False

# ============================================================
#  常量定义
# ============================================================

FONT_EXTENSIONS = ('.ttf', '.otf', '.woff', '.woff2', '.zip', '.7z', '.rar')
FONT_MIME_TYPES = {
    'font/ttf', 'font/otf', 'font/woff', 'font/woff2',
    'application/x-font-ttf', 'application/x-font-otf',
    'application/font-ttf', 'application/font-otf',
    'application/x-font-woff', 'application/font-woff',
    'application/octet-stream',
    'application/zip', 'application/x-zip-compressed',
    'application/x-7z-compressed', 'application/x-rar-compressed',
}
ANTICRAWL_CODES = {403, 429, 503, 418, 502, 999}

# ============================================================
#  浏览器身份管理器（参考 webcopier identity_manager）
# ============================================================

_FALLBACK_IDENTITIES = [
    {
        "id": "chrome-win-130",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "curl_impersonate": "chrome120",
        "headers": {
            "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        },
    },
    {
        "id": "firefox-win-133",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
        "curl_impersonate": "firefox116",
        "headers": {},
    },
    {
        "id": "safari-mac-18",
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
        "curl_impersonate": "safari17_0",
        "headers": {},
    },
    {
        "id": "edge-win-130",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
        "curl_impersonate": "edge101",
        "headers": {
            "sec-ch-ua": '"Chromium";v="130", "Microsoft Edge";v="130", "Not?A_Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        },
    },
    {
        "id": "chrome-mac-130",
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "curl_impersonate": "chrome120",
        "headers": {
            "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
        },
    },
    {
        "id": "chrome-linux-130",
        "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "curl_impersonate": "chrome120",
        "headers": {
            "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Linux"',
        },
    },
    {
        "id": "chrome-android-130",
        "ua": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
        "curl_impersonate": "chrome120",
        "headers": {
            "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
        },
    },
]

_DEFAULT_HEADERS_BASE = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}


class BrowserIdentityManager:
    """浏览器身份池管理器（对齐 webcopier identity_manager v5.2）"""

    def __init__(self, identities_path=None):
        # 优先从同目录下 font_identities.json 加载
        if identities_path is None:
            identities_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "font_identities.json"
            )
        self._path = identities_path
        self._identities = []
        self._load()

    def _load(self):
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            loaded = data.get("identities", [])
            if loaded:
                self._identities = loaded
                return
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        self._identities = list(_FALLBACK_IDENTITIES)

    @property
    def count(self):
        return len(self._identities)

    def get_identity(self, index: int) -> dict:
        return self._identities[index % len(self._identities)]

    def get_random_identity(self) -> dict:
        return random.choice(self._identities)

    def build_headers(self, identity: dict, referer=None) -> dict:
        headers = dict(_DEFAULT_HEADERS_BASE)
        headers["User-Agent"] = identity.get("ua", _DEFAULT_HEADERS_BASE.get("User-Agent", ""))
        id_headers = identity.get("headers", {})
        for key in ("sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform"):
            if key in id_headers:
                headers[key] = id_headers[key]
            else:
                headers.pop(key, None)
        if referer:
            headers["Referer"] = referer
        # curl_cffi 指纹透传（FontHTTPClient 内部会 pop 掉）
        headers["_curl_impersonate"] = identity.get("curl_impersonate", "chrome120")
        return headers


# 模块级单例
_identity_mgr = None


def get_identity_manager() -> BrowserIdentityManager:
    global _identity_mgr
    if _identity_mgr is None:
        _identity_mgr = BrowserIdentityManager()
    return _identity_mgr


# ============================================================
#  速率控制器（参考 webcopier engine.RateLimiter v5.4）
# ============================================================

class RateLimiter:
    """线程安全并发限速器，支持 robots.txt Crawl-delay"""

    def __init__(self, delay: float = 1.0, concurrency: int = 1,
                 crawl_delay: float = 0.0):
        self._delay = max(delay, crawl_delay)
        self._concurrency = max(1, concurrency)
        self._period = max(self._delay / self._concurrency, 0.1)
        self._lock = threading.Lock()
        self._last_time = 0.0

    @property
    def effective_delay(self):
        return self._delay

    def wait(self):
        with self._lock:
            now = time.time()
            wait_for = self._period - (now - self._last_time)
            self._last_time = max(now, self._last_time + self._period)
        if wait_for > 0:
            time.sleep(wait_for)

    def __enter__(self):
        self.wait()
        return self

    def __exit__(self, *args):
        pass


# ============================================================
#  HTTP 客户端层（对齐 webcopier http_client v5.1）
# ============================================================

class FontHTTPClient:
    """字体下载专用 HTTP 客户端

    特性：
    - 双后端：requests（默认）+ curl_cffi（TLS指纹，可选）
    - 身份池轮换（由 BrowserIdentityManager 管理）
    - 自适应重试（身份数 = 最大尝试次数）
    - 随机延迟（可选）
    - 流式下载、Content-Disposition 文件名解析
    """

    def __init__(self, log_callback=None, use_curl_cffi=False,
                 random_delay=False, identity_mgr=None):
        self._log = log_callback or (lambda msg: None)
        self._use_curl = use_curl_cffi and _HAS_CURL_CFFI
        self._random_delay = random_delay
        self._identity_mgr = identity_mgr or get_identity_manager()

        # requests Session（连接池复用）
        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10, pool_maxsize=20, max_retries=0
        )
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def _auto_referer(self, url: str) -> str:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}/"

    def _do_get(self, url, headers, timeout, stream=False):
        """底层 GET，根据后端选择执行"""
        curl_imp = headers.pop("_curl_impersonate", "chrome120")
        if self._use_curl:
            resp = curl_requests.get(
                url, headers=headers, timeout=timeout,
                stream=stream, allow_redirects=True,
                impersonate=curl_imp,
            )
        else:
            resp = self._session.get(
                url, headers=headers, timeout=timeout,
                stream=stream, allow_redirects=True,
            )
        return resp

    def get(self, url, referer=None, timeout=30, stream=False,
            start_identity_index=0):
        """GET 请求，内建身份轮换式重试

        start_identity_index: 起始身份索引（批量下载时可分散负载）
        """
        max_attempts = self._identity_mgr.count
        last_error = None

        for attempt in range(max_attempts):
            if self._random_delay and attempt == 0:
                time.sleep(random.uniform(0.3, 1.5))

            identity = self._identity_mgr.get_identity(
                (start_identity_index + attempt) % max_attempts
            )
            headers = self._identity_mgr.build_headers(
                identity,
                referer=referer or self._auto_referer(url)
            )

            try:
                resp = self._do_get(url, headers, timeout, stream=stream)

                if resp.status_code in ANTICRAWL_CODES:
                    wait = 10 * (attempt + 1)
                    self._log(f"  ⚠️ HTTP {resp.status_code}，切换身份等待 {wait}s...")
                    time.sleep(wait)
                    continue

                if resp.status_code == 200:
                    if not stream:
                        if resp.encoding is None or resp.encoding.lower() in (
                                "iso-8859-1", "latin-1"):
                            resp.encoding = resp.apparent_encoding or "utf-8"
                    return resp

                resp.raise_for_status()

            except requests.RequestException as e:
                last_error = e
                if attempt < max_attempts - 1:
                    backoff = min(2 ** attempt, 60)
                    self._log(f"  ⚠️ [{identity['id']}] 请求失败: {e}，{backoff}s 后重试...")
                    time.sleep(backoff)
            except Exception as e:
                last_error = e
                if attempt < max_attempts - 1:
                    self._log(f"  ⚠️ [{identity['id']}] 异常: {e}，重试...")

        raise last_error or RuntimeError(f"请求失败（已耗尽全部 {max_attempts} 个身份）: {url}")

    def post(self, url, data=None, referer=None, timeout=30,
             start_identity_index=0):
        """POST 请求，内建身份轮换式重试（与 get() 对齐）"""
        max_attempts = self._identity_mgr.count
        last_error = None

        for attempt in range(max_attempts):
            if self._random_delay and attempt == 0:
                time.sleep(random.uniform(0.3, 1.5))

            identity = self._identity_mgr.get_identity(
                (start_identity_index + attempt) % max_attempts
            )
            headers = self._identity_mgr.build_headers(
                identity,
                referer=referer or self._auto_referer(url)
            )

            try:
                if self._use_curl:
                    resp = curl_requests.post(
                        url, data=data, headers=headers,
                        timeout=timeout, allow_redirects=True,
                        impersonate=identity.get("curl_impersonate", "chrome120"),
                    )
                else:
                    resp = self._session.post(
                        url, data=data, headers=headers,
                        timeout=timeout, allow_redirects=True,
                    )

                if resp.status_code in ANTICRAWL_CODES:
                    wait = 10 * (attempt + 1)
                    self._log(f"  ⚠️ HTTP {resp.status_code}，切换身份等待 {wait}s...")
                    time.sleep(wait)
                    continue

                if resp.status_code == 200:
                    if not hasattr(resp, 'apparent_encoding'):
                        if resp.encoding is None or resp.encoding.lower() in (
                                "iso-8859-1", "latin-1"):
                            resp.encoding = resp.apparent_encoding or "utf-8"
                    return resp

                resp.raise_for_status()

            except Exception as e:
                last_error = e
                if attempt < max_attempts - 1:
                    backoff = min(2 ** attempt, 60)
                    self._log(f"  ⚠️ [{identity['id']}] POST 失败: {e}，{backoff}s 后重试...")
                    time.sleep(backoff)

        raise last_error or RuntimeError(f"POST 请求失败（已耗尽全部 {max_attempts} 个身份）: {url}")

    def get_filename_from_response(self, response, url: str) -> str | None:
        """从响应头或 URL 提取文件名（参考 webcopier writer.url_to_filename）"""
        cd = response.headers.get("Content-Disposition", "")
        if cd:
            # filename*=UTF-8''xxx
            m = re.search(r"filename\*=(?:UTF-8''|utf-8'')(.+?)(?:;|$)", cd, re.I)
            if m:
                return unquote(m.group(1).strip())
            # filename="xxx"
            m = re.search(r'filename="?(.+?)"?(?:;|$)', cd, re.I)
            if m:
                return m.group(1).strip().strip('"')
        parsed = urlparse(url)
        fname = os.path.basename(parsed.path).split("?")[0]
        if fname and "." in fname:
            return fname
        return None

    def download_file(self, url, save_path, referer=None, timeout=60):
        """流式下载到文件，返回 (success, bytes_written)"""
        resp = self.get(url, referer=referer, timeout=timeout, stream=True)
        downloaded = 0
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
        return True, downloaded


# ============================================================
#  robots.txt 工具
# ============================================================

def fetch_robots(base_url: str, user_agent: str, log=None):
    """读取 robots.txt，返回 (RobotFileParser | None, crawl_delay: float)"""
    _log = log or (lambda x: None)
    robot = RobotFileParser()
    crawl_delay = 0.0
    try:
        robots_url = urljoin(base_url, "/robots.txt")
        robot.set_url(robots_url)
        robot.read()
        try:
            crawl_delay = robot.crawl_delay(user_agent) or 0.0
        except Exception:
            pass
        _log(f"   ✅ robots.txt: {robots_url} (crawl-delay={crawl_delay}s)")
        return robot, crawl_delay
    except Exception as e:
        _log(f"   ⚠️ robots.txt 无法获取: {e}")
        return None, 0.0


# ============================================================
#  内置字体站点配置（联网调研更新 2026-06）
# ============================================================

BUILTIN_SITES = {
    # -------- 中文字体站 --------
    "猫啃网（817款中文免费商用）": {
        "url": "https://www.maoken.com/all-fonts",
        "home": "https://www.maoken.com",
        "desc": (
            "全部可免费商用，OFL/IPA/GPL/MIT/作者声明等协议。\n"
            "列表页跳转详情页后获取网盘/直链下载。\n"
            "推荐「深层」模式爬取，延迟建议 1.5s+。"
        ),
        "type": "list",
        "mode_hint": "deep",
        "delay_hint": 1.5,
    },
    "字体天下（商用免费分区）": {
        "url": "https://www.fonts.net.cn/commercial-free/fonts-zh-1.html",
        "home": "https://www.fonts.net.cn",
        "desc": (
            "商用免费中文字体分区，直链下载，无需登录。\n"
            "使用专属解析器：列表页 → 详情页 → POST 获取 CDN 临时链接。\n"
            "下载链接含 auth_key 时效令牌，获取后立即下载。"
        ),
        "type": "fontsnet",
        "mode_hint": "fontsnet",
        "delay_hint": 1.0,
    },
    "100font（免费商用大全）": {
        "url": "https://www.100font.com/",
        "home": "https://www.100font.com",
        "desc": (
            "论坛帖子架构，OFL/GPL/作者声明。\n"
            "需进入详情帖获取下载链接（多为百度网盘）。\n"
            "推荐「深层」模式。"
        ),
        "type": "forum",
        "mode_hint": "deep",
        "delay_hint": 1.5,
    },
    "ZeoSeven Fonts（开源中英文）": {
        "url": "https://fonts.zeoseven.com/browse/",
        "home": "https://fonts.zeoseven.com",
        "desc": (
            "1000+ 款 OFL/IPA/作者声明开源字体，含大量优质中文字体（霞鹜系列、思源、朱雀等）。\n"
            "直链下载，无需登录。URL格式：/items/{id}/，使用专属解析器自动提取下载链接。\n"
            "FontsAPI 支持 CDN 嵌入（fontsapi.zeoseven.com）。"
        ),
        "type": "zeoseven",
        "mode_hint": "zeoseven",
        "delay_hint": 1.0,
    },
    "字库星球（国内免费商用）": {
        "url": "https://www.zikuxq.com/",
        "home": "https://www.zikuxq.com",
        "desc": (
            "国内免费可商用字体平台，授权经核对确认。\n"
            "列表页→详情页→直链下载，无需登录。"
        ),
        "type": "list",
        "mode_hint": "deep",
        "delay_hint": 1.5,
    },
    "字体库 zitiku.org": {
        "url": "https://zitiku.org/",
        "home": "https://zitiku.org",
        "desc": (
            "1000+ 中英文免费商用字体，无需注册登录，直接下载。\n"
            "浅层爬取即可获取大量直链。"
        ),
        "type": "direct",
        "mode_hint": "paginate",
        "delay_hint": 1.0,
    },
    "免费字体网 mianfeiziti": {
        "url": "https://www.mianfeiziti.com/",
        "home": "https://www.mianfeiziti.com",
        "desc": "国内老牌免费字体站，含中英文，部分直链。",
        "type": "direct",
        "mode_hint": "paginate",
        "delay_hint": 1.5,
    },
    # -------- 英文/国际字体站 --------
    "Fontesk（英文为主）": {
        "url": "https://fontesk.com/fonts/",
        "home": "https://fontesk.com",
        "desc": (
            "13000+ 字体，OFL/免费商用为主，列表页含直接下载链接。\n"
            "浅层翻页模式可批量获取。"
        ),
        "type": "direct",
        "mode_hint": "paginate",
        "delay_hint": 1.0,
    },
    "Open Foundry（精选开源）": {
        "url": "https://open-foundry.com/fonts",
        "home": "https://open-foundry.com",
        "desc": (
            "精选 OFL 开源字体，均为高质量西文字体。\n"
            "列表页直接提供下载链接，无需登录。"
        ),
        "type": "direct",
        "mode_hint": "shallow",
        "delay_hint": 1.0,
    },
    "GitHub Releases（直链下载）": {
        "url": "GITHUB_RELEASES",
        "home": "https://github.com",
        "desc": (
            "霞鹜文楷、思源黑体/宋体、朱雀仿宋、得意黑等顶级开源字体均在 GitHub 发布。\n"
            "在「GitHub Releases」标签页输入仓库地址（如 lxgw/LxgwWenKai）直接下载。"
        ),
        "type": "github",
        "mode_hint": None,
    },
    "Google Fonts（API直链）": {
        "url": "GOOGLE_FONTS_API",
        "home": "https://fonts.google.com",
        "desc": (
            "1600+ OFL 开源字体，API 直接返回 .ttf 下载链接（需 API Key）。\n"
            "获取方式：https://console.cloud.google.com/apis/credentials"
        ),
        "type": "api",
        "mode_hint": None,
    },
}

# 知名开源字体 GitHub 仓库快查表
GITHUB_FONT_REPOS = {
    "霞鹜文楷 (LXGW WenKai)": "lxgw/LxgwWenKai",
    "霞鹜文楷 GB (Screen)": "lxgw/LxgwWenKaiGB",
    "霞鹜新晰黑 (LXGW Neo XiHei)": "lxgw/LXGWNeoXiHei",
    "思源黑体 (Source Han Sans)": "adobe-fonts/source-han-sans",
    "思源宋体 (Source Han Serif)": "adobe-fonts/source-han-serif",
    "朱雀仿宋 (Zhuque Fangsong)": "TrionesType/zhuque-fangsong",
    "得意黑 (Smiley Sans)": "atelier-anchor/smiley-sans",
    "汇文明朝 (HuiWen Mincho)": "takushiiisaka/MinchoPunk",
    "Maple Mono NF-CN": "subframe7536/maple-font",
    "未来荧黑 (Fusion Pixel)": "TakWolf/fusion-pixel-font",
    "京华老宋体": "takushiiisaka/JingHuaLaoSongTi",
}


# ============================================================
#  字体爬取引擎
# ============================================================

class FontCrawlEngine:
    """通用字体爬虫引擎 + 各站点专属解析器"""

    def __init__(self, log_callback=None, progress_callback=None,
                 stop_flag=None, use_curl_cffi=False,
                 random_delay=False, respect_robots=True):
        self._log = log_callback or (lambda msg: None)
        self._progress = progress_callback or (lambda c, t, m: None)
        self._stop = stop_flag or (lambda: False)
        self._respect_robots = respect_robots
        self._http = FontHTTPClient(
            log_callback=log_callback,
            use_curl_cffi=use_curl_cffi,
            random_delay=random_delay,
        )
        self._limiter = RateLimiter(delay=1.0)
        self._robots_cache = {}  # domain -> (robot, crawl_delay)

    def set_delay(self, seconds: float, concurrency: int = 1):
        self._limiter = RateLimiter(
            delay=max(0.1, seconds), concurrency=concurrency
        )

    def _get_robots(self, url: str):
        """获取（缓存）robots.txt"""
        if not self._respect_robots:
            return None, 0.0
        domain = urlparse(url).netloc
        if domain not in self._robots_cache:
            robot, cd = fetch_robots(url, "FontDownloader/2.1", self._log)
            # 更新实际限速
            if cd > 0 and cd > self._limiter.effective_delay:
                self._limiter = RateLimiter(
                    delay=cd, concurrency=1
                )
                self._log(f"   ℹ️ robots.txt Crawl-delay={cd}s 已生效")
            self._robots_cache[domain] = (robot, cd)
        return self._robots_cache[domain]

    def _robots_ok(self, url: str) -> bool:
        robot, _ = self._get_robots(url)
        if robot is None:
            return True
        return robot.can_fetch("FontDownloader/2.1", url)

    # ----------------------------------------------------------
    #  统一调度（自动识别站点，优先使用专属解析器）
    # ----------------------------------------------------------

    def discover(self, url: str, mode: str = "auto",
                max_pages: int = 1, max_detail: int = 30,
                max_fonts: int = 50) -> list:
        """自动识别站点并调用对应解析器

        mode 值：
          - "auto"    ：自动识别（默认）
          - "shallow"  ：仅当前页
          - "paginate"：翻页
          - "deep"    ：深层（列表→详情→下载）
          - "zeoseven"：ZeoSeven 专属
          - "fontsnet" ：字体天下专属
        """
        host = urlparse(url).netloc.lower()

        # 站点专属解析器（最高优先级）
        if "fonts.net.cn" in host or mode == "fontsnet":
            self._log("🔗 自动识别：字体天下 (fonts.net.cn)，使用专属解析器")
            return self.discover_fontsnet(url, max_fonts=max_fonts)

        if "zeoseven" in host or mode == "zeoseven":
            self._log("🔗 自动识别：ZeoSeven Fonts，使用专属解析器")
            return self.discover_zeoseven(max_fonts=max_fonts)

        if "zitiku" in host:
            self._log("🔗 自动识别：字体库 (zitiku.org)")
            engine = ZitikuEngine(url, self._http, self._limiter)
            return engine.discover()

        # 自动模式：根据 URL 特征选择策略
        if mode == "auto":
            # 含 /browse 或 /items → 可能是列表+详情结构
            if any(k in url.lower() for k in ["/browse", "/items", "/font-", "/detail"]):
                self._log("🔗 自动选择：深层模式（检测到列表→详情结构）")
                return self.discover_deep(url, max_detail_pages=max_detail)
            else:
                self._log("🔗 自动选择：浅层+翻页模式")
                return self.discover_font_links(url, max_pages=max_pages)

        # 手动指定模式
        if mode == "deep":
            return self.discover_deep(url, max_detail_pages=max_detail)
        elif mode in ("shallow", "paginate"):
            return self.discover_font_links(url, max_pages=max_pages)
        else:
            self._log(f"⚠️ 未知模式：{mode}，使用自动模式")
            return self.discover(url, mode="auto",
                             max_pages=max_pages, max_detail=max_detail,
                             max_fonts=max_fonts)

    # ----------------------------------------------------------
    #  通用链接提取
    # ----------------------------------------------------------

    def _extract_font_urls(self, soup: BeautifulSoup, base_url: str) -> set:
        """从 soup 中提取字体文件 URL（多策略）"""
        urls = set()

        # 策略1: <a href> 以字体扩展名结尾
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            lower = href.lower()
            if re.search(r"\.(ttf|otf|woff|woff2|zip|7z|rar)(\?|$)", lower, re.I):
                urls.add(urljoin(base_url, href))

        # 策略2: href 含 download/font 关键词且路径含字体扩展名
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            lower = href.lower()
            if any(kw in lower for kw in ["download", "/font", "typeface", "ttf", "otf"]):
                if not lower.endswith((".html", ".htm", ".php", ".asp", ".jsp")):
                    full = urljoin(base_url, href)
                    path = urlparse(full).path.lower()
                    if re.search(r"\.(ttf|otf|woff|woff2)", path):
                        urls.add(full)

        # 策略3: 页面文本中裸露的字体 URL
        text = soup.get_text()
        for m in re.finditer(
                r"https?://[^\s<>\"']+?\.(?:ttf|otf|woff|woff2|zip)", text, re.I):
            urls.add(m.group(0))

        # 策略4: <source>/<link> 标签（字体预加载）
        for tag in soup.find_all(["source", "link"], href=True):
            href = tag.get("href", "")
            if re.search(r"\.(ttf|otf|woff|woff2)", href.lower()):
                urls.add(urljoin(base_url, href))

        return urls

    def _find_next_page(self, soup: BeautifulSoup, base_url: str) -> str | None:
        """发现下一页链接（参考 webcopier link_finder）"""
        selectors = [
            ("a", {"rel": "next"}),
            ("a", {"class": re.compile(r"next", re.I)}),
            ("a", {"string": re.compile(r"下一页|下一頁|Next|»|›", re.I)}),
            ("link", {"rel": "next"}),
        ]
        for tag_name, attrs in selectors:
            el = soup.find(tag_name, attrs)
            if el:
                href = el.get("href", "")
                if href:
                    return urljoin(base_url, href)
        # 备用：查找 <a> 中文字匹配
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            if re.match(r"下一[页頁]|Next|›|»", text):
                return urljoin(base_url, a["href"])
        return None

    # ----------------------------------------------------------
    #  爬取模式
    # ----------------------------------------------------------

    def discover_font_links(self, url: str, max_pages: int = 1) -> list:
        """浅层/翻页模式：当前页（及后续翻页）中提取字体链接"""
        all_links = set()
        visited = set()
        queue = [url]
        page_count = 0

        while queue and page_count < max_pages and not self._stop():
            current = queue.pop(0)
            if current in visited:
                continue
            if not self._robots_ok(current):
                self._log(f"   ⛔ robots.txt 不允许: {current}")
                continue
            visited.add(current)
            page_count += 1

            with self._limiter:
                try:
                    self._log(f"🔍 [{page_count}/{max_pages}] 分析页面：{current}")
                    resp = self._http.get(current, timeout=20)
                    soup = BeautifulSoup(resp.text, "lxml")

                    found = self._extract_font_urls(soup, current)
                    all_links.update(found)
                    if found:
                        self._log(f"   发现 {len(found)} 个字体链接")

                    if max_pages > 1:
                        nxt = self._find_next_page(soup, current)
                        if nxt and nxt not in visited:
                            queue.append(nxt)
                            self._log(f"   ➡️ 下一页：{nxt}")

                except Exception as e:
                    self._log(f"   ❌ 页面分析失败：{e}")

        self._log(f"\n📦 共发现 {len(all_links)} 个字体链接")
        return list(all_links)

    def discover_deep(self, list_url: str, max_detail_pages: int = 30) -> list:
        """深层模式：列表页 → 详情页 → 下载链接"""
        all_links = set()

        # Step1: 读列表页
        with self._limiter:
            try:
                self._log(f"🔍 读取列表页：{list_url}")
                if not self._robots_ok(list_url):
                    self._log("   ⛔ robots.txt 不允许")
                    return []
                resp = self._http.get(list_url, timeout=20)
                soup = BeautifulSoup(resp.text, "lxml")
            except Exception as e:
                self._log(f"❌ 列表页请求失败：{e}")
                return []

        # 先检查列表页本身有没有直链
        direct = self._extract_font_urls(soup, list_url)
        all_links.update(direct)
        if direct:
            self._log(f"   列表页直链：{len(direct)} 个")

        # Step2: 收集详情页链接
        base_domain = urlparse(list_url).netloc
        detail_urls = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            lower = href.lower()
            if lower.endswith((".css", ".js", ".png", ".jpg", ".ico", ".svg")):
                continue
            full = urljoin(list_url, href)
            if urlparse(full).netloc != base_domain:
                continue
            if full in seen or full == list_url:
                continue
            seen.add(full)
            text = a.get_text(strip=True)
            detail_urls.append((full, text))

        self._log(f"📋 候选详情页：{len(detail_urls)} 个")

        # Step3: 逐个详情页提取
        crawled = 0
        for detail_url, name in detail_urls:
            if self._stop():
                break
            if crawled >= max_detail_pages:
                break
            if not self._robots_ok(detail_url):
                continue

            with self._limiter:
                try:
                    crawled += 1
                    short = (name[:30] if name else detail_url[:60])
                    self._log(f"  [{crawled}/{max_detail_pages}] {short}")
                    resp = self._http.get(detail_url, timeout=15)
                    soup2 = BeautifulSoup(resp.text, "lxml")
                    found = self._extract_font_urls(soup2, detail_url)
                    all_links.update(found)
                    if found:
                        self._log(f"     ✅ {len(found)} 个下载链接")
                except Exception as e:
                    self._log(f"     ⚠️ 失败：{e}")

        self._log(f"\n📦 深层爬取完成：共发现 {len(all_links)} 个字体链接")
        return list(all_links)

    def discover_zeoseven(self, max_fonts: int = 50) -> list:
        """ZeoSeven Fonts 专属解析器

        说明：
          ZeoSeven 是 Next.js 静态导出站点，字体列表通过客户端 JS 渲染，
          静态 HTML 中无法直接获取 /items/ 链接。
          本解析器提取详情页中的 GitHub 仓库链接，并返回 GitHub Releases
          下载链接（需配合 GitHubReleasesEngine 使用）。

        备选方案：
          直接使用「GitHub Releases」标签页，输入字体仓库名（如 lxgw/LxgwWenKai）
          直接下载，无需通过 ZeoSeven 跳转。
        """
        all_links = set()
        base = "https://fonts.zeoseven.com"
        self._log("🌟 ZeoSeven Fonts 解析器启动（提取 GitHub 链接）")

        # ZeoSeven 的字体 ID 范围是 1~约 1500
        # 直接遍历前 N 个详情页，提取 GitHub 链接
        visited = 0
        for font_id in range(1, max_fonts + 50):
            if self._stop() or len(all_links) >= max_fonts:
                break

            item_url = f"{base}/items/{font_id}/"
            with self._limiter:
                try:
                    resp = self._http.get(item_url, referer=base + "/", timeout=15)
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "lxml")

                    # 提取 GitHub 仓库链接
                    for a in soup.find_all("a", href=True):
                        href = a["href"].strip()
                        if "github.com" in href and re.match(
                            r"https://github\.com/[^/]+/[^/]+/?", href
                        ):
                            # 转换为 Releases 下载链接格式
                            repo = href.rstrip("/").replace("https://github.com/", "")
                            if repo.count("/") == 1:
                                all_links.add(f"github:{repo}")
                                visited += 1
                                self._log(f"     ✅ {repo}")
                                break

                except Exception:
                    continue

        self._log(f"\n📦 ZeoSeven 完成：{len(all_links)} 个 GitHub 仓库链接")
        self._log("💡 提示：这些链接需通过 GitHub Releases 引擎下载")
        return list(all_links)

    # ----------------------------------------------------------
    #  fonts.net.cn 专属解析器
    # ----------------------------------------------------------

    def discover_fontsnet(self, list_url: str, max_fonts: int = 50) -> list:
        """字体天下 (fonts.net.cn) 专属解析器

        规律：
        - 列表页：https://www.fonts.net.cn/commercial-free/fonts-zh-N.html
        - 详情页：https://www.fonts.net.cn/font-XXXXXXXXXXX.html
        - 下载按钮触发 POST /font-download.html?id=font_id
        - 返回 JSON：{"success":true,"data":{"url":"//fileres.fonts.net.cn/...zip?auth_key=..."}}
        - 下载链接含时效 auth_key，需立即使用
        """
        all_links = []
        base = "https://www.fonts.net.cn"
        page = 1
        collected = 0

        self._log("🔗 字体天下 (fonts.net.cn) 专属解析器启动")

        while collected < max_fonts and not self._stop():
            # fonts.net.cn 分页格式：/commercial-free/fonts-zh-N.html
            # N 直接在路径中，不是 ?page=N 参数
            if page == 1:
                paged_url = list_url
            else:
                # 尝试替换路径中的数字（fonts-zh-1 → fonts-zh-N）
                if re.search(r"fonts-zh-(\d+)", list_url):
                    paged_url = re.sub(r"fonts-zh-\d+", f"fonts-zh-{page}", list_url)
                elif re.search(r"fonts-\w+-\d+\.html", list_url):
                    paged_url = re.sub(r"fonts-\w+-\d+\.html",
                                       lambda m: re.sub(r"\d+", str(page), m.group(0), count=1),
                                       list_url)
                else:
                    # 通用 fallback：路径末尾 -数字.html
                    paged_url = re.sub(r"-(\d+)\.html$", f"-{page}.html", list_url)

            with self._limiter:
                try:
                    self._log(f"  📄 列表页 p{page}：{paged_url[:80]}")
                    resp = self._http.get(paged_url, timeout=20)
                    soup = BeautifulSoup(resp.text, "lxml")
                except Exception as e:
                    self._log(f"   ❌ 列表页失败 p{page}: {e}")
                    break

            # 提取详情页链接（匹配 /font-数字.html）
            detail_items = []  # [(detail_url, font_id)]
            seen_ids = set()
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                m = re.match(r"^/font-(\d+)\.html$", href)
                if m:
                    font_id = m.group(1)
                    if font_id in seen_ids:
                        continue
                    seen_ids.add(font_id)
                    detail_items.append((urljoin(base, href), font_id))

            if not detail_items:
                self._log(f"   ℹ️ 第 {page} 页无字体条目，停止翻页")
                break

            self._log(f"   第 {page} 页：{len(detail_items)} 款字体")

            # 逐个 POST 获取下载链接
            for detail_url, font_id in detail_items:
                if self._stop() or collected >= max_fonts:
                    break

                with self._limiter:
                    try:
                        api_url = urljoin(base, "/font-download.html")
                        # 使用 _http.post() 统一身份轮换 + curl_cffi 支持
                        post_resp = self._http.post(
                            api_url,
                            data=f"id={font_id}",
                            referer=detail_url,
                            timeout=15,
                        )

                        try:
                            js = post_resp.json()
                        except Exception:
                            self._log(f"     ⚠️ {font_id}: 响应非 JSON")
                            continue

                        if js.get("success"):
                            # 拼接下载 URL（返回的 url 以 // 开头）
                            raw_url = js["data"]["url"]
                            # 去掉转义反斜杠
                            raw_url = raw_url.replace("\\", "")
                            if raw_url.startswith("//"):
                                dl_url = "https:" + raw_url
                            elif raw_url.startswith("/"):
                                dl_url = base + raw_url
                            else:
                                dl_url = raw_url
                            all_links.append(dl_url)
                            collected += 1
                            fname = js["data"].get("filename", font_id)
                            self._log(f"     ✅ {fname}: {dl_url[:70]}...")
                        else:
                            reason = js.get("error", "未知")
                            self._log(f"     ⚠️ {font_id}: API 失败 - {reason}")

                    except Exception as e:
                        self._log(f"     ⚠️ {font_id}: {e}")

            page += 1

        self._log(f"\n📦 字体天下完成：{len(all_links)} 个下载链接")
        return all_links

    # ----------------------------------------------------------
    #  下载
    # ----------------------------------------------------------

    def download_fonts(self, links: list, save_dir: str,
                       concurrency: int = 3) -> tuple:
        """并发下载字体文件，支持断点续传

        支持链接格式：
          - 普通 HTTP/HTTPS 直链
          - github:owner/repo 格式（自动跳转 GitHub Releases 下载）
        """
        if not links:
            self._log("⚠️ 没有可下载的链接")
            return 0, 0

        # 分离 github: 链接和普通链接
        github_links = [l for l in links if l.startswith("github:")]
        normal_links = [l for l in links if not l.startswith("github:")]

        success = fail = 0

        # 先处理 GitHub 链接
        if github_links:
            self._log(f"🔗 发现 {len(github_links)} 个 GitHub 仓库链接，使用 GitHub Releases 引擎下载")
            github_success = 0
            for gl in github_links:
                repo = gl.replace("github:", "").strip()
                self._log(f"  📦 {repo}")
                try:
                    gh_engine = GitHubReleasesEngine(
                        log_callback=self._log,
                        stop_flag=self._stop,
                    )
                    s, f = gh_engine.download(repo, save_dir, concurrency=concurrency)
                    github_success += s
                    fail += f
                except Exception as e:
                    self._log(f"     ❌ {repo}: {e}")
                    fail += 1
            success += github_success
            self._log(f"✅ GitHub 仓库下载完成：{github_success} 个")

        # 再处理普通链接
        if not normal_links:
            return success, fail

        os.makedirs(save_dir, exist_ok=True)

        # 断点续传
        checkpoint_file = os.path.join(save_dir, ".font_checkpoint.json")
        downloaded_set = set()
        if os.path.exists(checkpoint_file):
            try:
                with open(checkpoint_file, "r", encoding="utf-8") as f:
                    downloaded_set = set(json.load(f).get("downloaded", []))
                self._log(f"📌 断点恢复：已完成 {len(downloaded_set)} 个")
            except Exception:
                pass

        pending = [l for l in normal_links if l not in downloaded_set]
        if not pending:
            self._log("✅ 全部文件已下载完毕")
            return success + len(downloaded_set), fail

        self._log(f"⬇️ 下载 {len(pending)} 个文件（并发={concurrency}）...")
        success = fail = 0
        lock = threading.Lock()

        def _one(args):
            idx, link = args
            if self._stop():
                return idx, link, False, "已取消"

            # 生成文件名
            parsed = urlparse(link)
            fname = os.path.basename(parsed.path).split("?")[0]
            if not fname or "." not in fname:
                ext = next((e.lstrip(".") for e in FONT_EXTENSIONS
                            if link.lower().endswith(e)), "ttf")
                fname = f"font_{idx}.{ext}"
            fname = re.sub(r'[\\/*?:"<>|]', "_", fname)
            save_path = os.path.join(save_dir, fname)

            if os.path.exists(save_path):
                return idx, link, True, "已存在"

            try:
                resp = self._http.get(link, timeout=60, stream=True,
                                      start_identity_index=idx)

                # Content-Type 校验
                ct = resp.headers.get("Content-Type", "").lower()
                is_font = any(mt in ct for mt in FONT_MIME_TYPES)
                if not is_font and not any(
                        link.lower().endswith(e) for e in FONT_EXTENSIONS):
                    return idx, link, True, f"跳过（非字体: {ct[:40]}）"

                # 更好的文件名
                better = self._http.get_filename_from_response(resp, link)
                if better:
                    better = re.sub(r'[\\/*?:"<>|]', "_", better)
                    save_path = os.path.join(save_dir, better)

                # 大小检查
                total_size = int(resp.headers.get("content-length", 0))
                if total_size and total_size < 1024:
                    return idx, link, False, f"文件太小({total_size}B)"

                # 流式写入
                downloaded = 0
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if self._stop():
                            try:
                                f.close()
                                os.remove(save_path)
                            except Exception:
                                pass
                            return idx, link, False, "下载取消"
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                size_kb = os.path.getsize(save_path) // 1024
                return idx, link, True, f"{size_kb} KB"

            except Exception as e:
                return idx, link, False, str(e)

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(_one, (i + 1, link)): link
                for i, link in enumerate(pending)
            }
            for future in as_completed(futures):
                idx, link, ok, msg = future.result()
                with lock:
                    if ok:
                        success += 1
                        downloaded_set.add(link)
                        self._log(f"  ✅ [{idx}/{len(pending)}] "
                                  f"{os.path.basename(link)[:45]} ({msg})")
                    else:
                        fail += 1
                        self._log(f"  ❌ [{idx}/{len(pending)}] {msg}")

                    # 每完成一个就保存断点
                    try:
                        with open(checkpoint_file, "w", encoding="utf-8") as f:
                            json.dump({"downloaded": list(downloaded_set)}, f)
                    except Exception:
                        pass

                    self._progress(
                        success + fail, len(pending),
                        f"下载中... {success} 成功 / {fail} 失败"
                    )

        # 完成清理断点
        if not self._stop() and os.path.exists(checkpoint_file):
            os.remove(checkpoint_file)

        self._log(f"\n🎉 下载完成！成功：{success}，失败：{fail}")
        return success, fail


# ============================================================
#  Google Fonts API 引擎（修复双重请求 bug）
# ============================================================

class GoogleFontsEngine:
    """Google Fonts API 字体下载引擎

    API Key 获取：
    1. https://console.cloud.google.com/apis/credentials
    2. 创建 API 密钥 → 启用 Google Fonts Developer API
    """

    API_URL = "https://www.googleapis.com/webfonts/v1/webfonts"

    def __init__(self, log_callback=None, stop_flag=None, use_curl_cffi=False):
        self._log = log_callback or (lambda msg: None)
        self._stop = stop_flag or (lambda: False)
        self._http = FontHTTPClient(
            log_callback=log_callback,
            use_curl_cffi=use_curl_cffi,
        )
        self._api_key = ""

    def set_api_key(self, key: str):
        self._api_key = key.strip()

    def list_fonts(self, sort_by="popularity", category=None, subset=None) -> list:
        """获取字体列表，返回 [(family, category, variants, files), ...]"""
        if not self._api_key:
            self._log("❌ 请先设置 Google API Key")
            return []

        params = [f"key={self._api_key}", f"sort={sort_by}"]
        if category:
            params.append(f"category={category}")
        if subset:
            params.append(f"subset={subset}")
        url = self.API_URL + "?" + "&".join(params)

        try:
            resp = self._http.get(url, timeout=15)
            data = resp.json()
        except Exception as e:
            self._log(f"❌ Google Fonts API 请求失败：{e}")
            return []

        fonts = []
        for item in data.get("items", []):
            fonts.append((
                item["family"],
                item.get("category", ""),
                item.get("variants", []),
                item.get("files", {}),
            ))
        return fonts

    def download_fonts(self, families: list, save_dir: str,
                       variants=None, concurrency: int = 3) -> tuple:
        """下载指定字体系列"""
        if not self._api_key:
            self._log("❌ 请先设置 Google API Key")
            return 0, 0

        os.makedirs(save_dir, exist_ok=True)
        all_tasks = []

        for family_name in families:
            if self._stop():
                break
            try:
                url = (f"{self.API_URL}?key={self._api_key}"
                       f"&family={family_name.replace(' ', '+')}")
                resp = self._http.get(url, timeout=15)
                data = resp.json()
                items = data.get("items", [])
                if not items:
                    self._log(f"  ⚠️ 未找到字体：{family_name}")
                    continue

                files = items[0].get("files", {})
                for variant, dl_url in files.items():
                    if variants and variant not in variants:
                        continue
                    # 强制 HTTPS
                    dl_url = dl_url.replace("http://", "https://", 1)
                    ext = ".woff2" if "woff2" in variant.lower() else ".ttf"
                    fname = re.sub(
                        r'[\\/*?:"<>|]', "_",
                        f"{family_name.replace(' ', '_')}_{variant}{ext}"
                    )
                    all_tasks.append((fname, dl_url))

                self._log(f"  ✅ {family_name}: {len(files)} 个变体")

            except Exception as e:
                self._log(f"  ❌ {family_name} 查询失败：{e}")

        if not all_tasks:
            self._log("⚠️ 没有可下载的字体")
            return 0, 0

        self._log(f"\n⬇️ 共 {len(all_tasks)} 个文件，开始下载...")
        success = fail = 0
        lock = threading.Lock()

        def _dl(task):
            fname, url = task
            save_path = os.path.join(save_dir, fname)
            if os.path.exists(save_path):
                return fname, True, "已存在"
            try:
                resp = self._http.get(url, timeout=60, stream=True)
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if self._stop():
                            f.close()
                            os.remove(save_path)
                            return fname, False, "取消"
                        if chunk:
                            f.write(chunk)
                size_kb = os.path.getsize(save_path) // 1024
                return fname, True, f"{size_kb} KB"
            except Exception as e:
                return fname, False, str(e)

        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = [ex.submit(_dl, t) for t in all_tasks]
            for fut in as_completed(futures):
                fname, ok, msg = fut.result()
                with lock:
                    if ok:
                        success += 1
                        self._log(f"  ✅ {fname} ({msg})")
                    else:
                        fail += 1
                        self._log(f"  ❌ {fname}: {msg}")

        self._log(f"\n🎉 完成！成功：{success}，失败：{fail}")
        return success, fail


# ============================================================
#  GitHub Releases 下载引擎
# ============================================================

class GitHubReleasesEngine:
    """从 GitHub Releases 页面提取并下载字体文件

    支持格式：
      - 仓库名：lxgw/LxgwWenKai
      - 完整URL：https://github.com/lxgw/LxgwWenKai/releases/latest
    """

    GITHUB_API = "https://api.github.com/repos/{repo}/releases/latest"

    def __init__(self, log_callback=None, stop_flag=None):
        self._log = log_callback or (lambda msg: None)
        self._stop = stop_flag or (lambda: False)
        self._http = FontHTTPClient(log_callback=log_callback)

    def _parse_repo(self, repo_or_url: str) -> str:
        """从输入提取 owner/repo 格式"""
        repo_or_url = repo_or_url.strip()
        # 完整 URL
        m = re.search(r"github\.com/([^/]+/[^/\s]+)", repo_or_url)
        if m:
            return m.group(1).rstrip("/")
        # 直接 owner/repo
        if "/" in repo_or_url and not repo_or_url.startswith("http"):
            return repo_or_url
        return repo_or_url

    def get_release_assets(self, repo_input: str) -> list:
        """获取最新 Release 的字体资源列表，返回 [(filename, download_url), ...]"""
        repo = self._parse_repo(repo_input)
        api_url = self.GITHUB_API.format(repo=repo)

        self._log(f"🔍 查询 GitHub Release: {repo}")
        try:
            resp = self._http.get(api_url, timeout=20)
            data = resp.json()
        except Exception as e:
            self._log(f"❌ GitHub API 请求失败：{e}（提示：API 有限速，可稍后重试）")
            return []

        if "message" in data:
            self._log(f"❌ GitHub 返回错误：{data['message']}")
            return []

        tag = data.get("tag_name", "unknown")
        assets = data.get("assets", [])
        self._log(f"   Release: {tag}，共 {len(assets)} 个资源")

        font_assets = []
        for a in assets:
            name = a["name"]
            if any(name.lower().endswith(ext) for ext in FONT_EXTENSIONS):
                font_assets.append((name, a["browser_download_url"]))
                self._log(f"   📎 {name}")

        if not font_assets:
            self._log("   ⚠️ 该 Release 未发现字体文件（.ttf/.otf/.zip等）")

        return font_assets

    def download(self, repo_input: str, save_dir: str,
                 concurrency: int = 3) -> tuple:
        """下载仓库最新 Release 的全部字体"""
        assets = self.get_release_assets(repo_input)
        if not assets:
            return 0, 0

        os.makedirs(save_dir, exist_ok=True)
        success = fail = 0

        def _dl(item):
            fname, url = item
            save_path = os.path.join(save_dir, fname)
            if os.path.exists(save_path):
                return fname, True, "已存在"
            try:
                resp = self._http.get(url, timeout=120, stream=True)
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if self._stop():
                            f.close()
                            os.remove(save_path)
                            return fname, False, "取消"
                        if chunk:
                            f.write(chunk)
                size_kb = os.path.getsize(save_path) // 1024
                return fname, True, f"{size_kb} KB"
            except Exception as e:
                return fname, False, str(e)

        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            for fname, ok, msg in map(lambda f: f.result(),
                                       [ex.submit(_dl, a) for a in assets]):
                if ok:
                    success += 1
                    self._log(f"  ✅ {fname} ({msg})")
                else:
                    fail += 1
                    self._log(f"  ❌ {fname}: {msg}")

        self._log(f"\n🎉 完成！成功：{success}，失败：{fail}")
        return success, fail


# ============================================================
#  GUI 界面
# ============================================================

class FontSpiderGUI:
    """增强版字体爬虫 GUI v2.1"""

    def __init__(self, root):
        self.root = root
        root.title("字体爬虫工具 v2.1 — 免费公版字体下载器")
        root.geometry("820x720")
        root.resizable(True, True)

        # 变量
        self.save_dir_var = tk.StringVar()
        self.url_var = tk.StringVar()
        self.concurrency_var = tk.IntVar(value=3)
        self.delay_var = tk.DoubleVar(value=1.0)
        self.max_pages_var = tk.IntVar(value=5)
        self.google_api_key_var = tk.StringVar()
        self.google_families_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="shallow")
        self.use_curl_var = tk.BooleanVar(value=False)
        self.random_delay_var = tk.BooleanVar(value=False)
        self.respect_robots_var = tk.BooleanVar(value=True)
        # GitHub
        self.github_repo_var = tk.StringVar()

        # 控制信号
        self.stop_flag = False
        self.work_thread = None

        # 配置路径
        self._config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            ".font_downloader_config.json"
        )
        self._load_config()

        # 构建界面
        self._create_widgets()

        # 默认保存目录
        default_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "download_fonts")
        os.makedirs(default_dir, exist_ok=True)
        if not self.save_dir_var.get():
            self.save_dir_var.set(default_dir)

    # ---------- 配置持久化 ----------

    def _load_config(self):
        try:
            if os.path.exists(self._config_path):
                with open(self._config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self.save_dir_var.set(cfg.get("save_dir", ""))
                self.concurrency_var.set(cfg.get("concurrency", 3))
                self.delay_var.set(cfg.get("delay", 1.0))
                self.max_pages_var.set(cfg.get("max_pages", 5))
                self.google_api_key_var.set(cfg.get("google_api_key", ""))
                self.use_curl_var.set(cfg.get("use_curl", False))
                self.respect_robots_var.set(cfg.get("respect_robots", True))
        except Exception:
            pass

    def _save_config(self):
        try:
            cfg = {
                "save_dir": self.save_dir_var.get(),
                "concurrency": self.concurrency_var.get(),
                "delay": self.delay_var.get(),
                "max_pages": self.max_pages_var.get(),
                "google_api_key": self.google_api_key_var.get(),
                "use_curl": self.use_curl_var.get(),
                "respect_robots": self.respect_robots_var.get(),
            }
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------- GUI 构建 ----------

    def _create_widgets(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 标签页
        tab_general = ttk.Frame(self.notebook)
        self.notebook.add(tab_general, text="通用爬虫")
        self._build_general_tab(tab_general)

        tab_google = ttk.Frame(self.notebook)
        self.notebook.add(tab_google, text="Google Fonts")
        self._build_google_tab(tab_google)

        tab_github = ttk.Frame(self.notebook)
        self.notebook.add(tab_github, text="GitHub Releases")
        self._build_github_tab(tab_github)

        tab_builtin = ttk.Frame(self.notebook)
        self.notebook.add(tab_builtin, text="📚 推荐站点")
        self._build_builtin_tab(tab_builtin)

        # 底部共用区域
        bottom = tk.Frame(self.root)
        bottom.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        log_frame = tk.LabelFrame(bottom, text="运行日志")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, height=11, font=("Consolas", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 进度
        self.progress_var = tk.StringVar(value="就绪")
        self.progress_bar = ttk.Progressbar(bottom, mode="determinate")
        self.progress_bar.pack(fill=tk.X, padx=5, pady=(2, 0))
        tk.Label(bottom, textvariable=self.progress_var, anchor="w",
                 font=("", 8)).pack(fill=tk.X, padx=5)

        # 按钮
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.start_btn = tk.Button(
            btn_frame, text="▶ 开始", command=self._start, width=12,
            bg="#4CAF50", fg="white", font=("", 10, "bold")
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(
            btn_frame, text="■ 停止", command=self._stop_task, width=10,
            bg="#f44336", fg="white", state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="清空日志",
                  command=self._clear_log, width=10).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame, text="打开目录",
            command=lambda: os.startfile(self.save_dir_var.get()),
            width=10
        ).pack(side=tk.RIGHT, padx=5)

    def _build_general_tab(self, parent):
        # URL
        f1 = tk.Frame(parent)
        f1.pack(pady=(10, 5), padx=10, fill=tk.X)
        tk.Label(f1, text="目标网址：").pack(side=tk.LEFT)
        tk.Entry(f1, textvariable=self.url_var, width=52).pack(
            side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        # 保存目录
        f2 = tk.Frame(parent)
        f2.pack(pady=5, padx=10, fill=tk.X)
        tk.Label(f2, text="保存目录：").pack(side=tk.LEFT)
        tk.Label(f2, textvariable=self.save_dir_var, relief=tk.SUNKEN,
                 width=47, anchor="w").pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        tk.Button(f2, text="浏览", command=self._select_dir).pack(side=tk.LEFT)

        # 爬取模式
        f3 = tk.Frame(parent)
        f3.pack(pady=5, padx=10, fill=tk.X)
        tk.Label(f3, text="爬取模式：").pack(side=tk.LEFT)
        for val, label in [("shallow", "浅层"), ("paginate", "翻页"),
                            ("deep", "深层"), ("zeoseven", "ZeoSeven"),
                            ("fontsnet", "字体天下"), ("auto", "自动识别")]:
            ttk.Radiobutton(f3, text=label, variable=self.mode_var,
                            value=val).pack(side=tk.LEFT, padx=(5, 8))

        # 参数
        f4 = tk.Frame(parent)
        f4.pack(pady=5, padx=10, fill=tk.X)
        for label, var, kw in [
            ("最大页数/详情页：", self.max_pages_var, {"from_": 1, "to": 200, "width": 5}),
            ("并发：", self.concurrency_var, {"from_": 1, "to": 10, "width": 4}),
            ("延迟(s)：", self.delay_var, {"from_": 0.1, "to": 15.0,
                                            "increment": 0.5, "width": 4}),
        ]:
            tk.Label(f4, text=label).pack(side=tk.LEFT)
            tk.Spinbox(f4, textvariable=var, **kw).pack(side=tk.LEFT, padx=(2, 12))

        # 高级选项
        f5 = tk.Frame(parent)
        f5.pack(pady=5, padx=10, fill=tk.X)
        curl_text = "curl_cffi TLS指纹" + ("" if _HAS_CURL_CFFI else "（未安装）")
        ttk.Checkbutton(f5, text=curl_text, variable=self.use_curl_var,
                        state=tk.NORMAL if _HAS_CURL_CFFI else tk.DISABLED
                        ).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Checkbutton(f5, text="随机延迟",
                        variable=self.random_delay_var).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Checkbutton(f5, text="遵守 robots.txt",
                        variable=self.respect_robots_var).pack(side=tk.LEFT)

        # 提示
        tk.Label(
            parent,
            text="💡 浅层=仅当前页 | 翻页=自动翻页 | 深层=列表→详情→下载 | ZeoSeven=专属解析",
            justify=tk.LEFT, fg="#666", font=("", 8),
        ).pack(anchor="w", padx=10)

    def _build_google_tab(self, parent):
        f1 = tk.Frame(parent)
        f1.pack(pady=(10, 5), padx=10, fill=tk.X)
        tk.Label(f1, text="API Key：").pack(side=tk.LEFT)
        self._api_key_entry = tk.Entry(
            f1, textvariable=self.google_api_key_var, width=47, show="*")
        self._api_key_entry.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        tk.Button(f1, text="👁", width=3,
                  command=self._toggle_key_vis).pack(side=tk.LEFT)
        self._key_vis = False

        f2 = tk.Frame(parent)
        f2.pack(pady=5, padx=10, fill=tk.X)
        tk.Label(f2, text="字体名称：").pack(side=tk.LEFT)
        tk.Entry(f2, textvariable=self.google_families_var, width=52
                 ).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        f3 = tk.Frame(parent)
        f3.pack(pady=5, padx=10, fill=tk.X)
        tk.Label(f3, text="保存目录：").pack(side=tk.LEFT)
        tk.Label(f3, textvariable=self.save_dir_var, relief=tk.SUNKEN,
                 width=47, anchor="w").pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        tk.Button(f3, text="浏览", command=self._select_dir).pack(side=tk.LEFT)

        f4 = tk.Frame(parent)
        f4.pack(pady=10, padx=10, fill=tk.X)
        tk.Button(f4, text="🔍 搜索字体列表",
                  command=self._search_google, width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(f4, text="⬇️ 下载指定字体",
                  command=self._download_google, width=15,
                  bg="#4CAF50", fg="white").pack(side=tk.LEFT, padx=5)

        tk.Label(
            parent,
            text=(
                "📖 说明：\n"
                "1. 获取 API Key：https://console.cloud.google.com/apis/credentials\n"
                "2. 字体名称填英文原名，多个用逗号分隔，例：Noto Sans SC, LXGW WenKai\n"
                "3. 所有字体均为 OFL 协议，可免费商用"
            ),
            justify=tk.LEFT, fg="#666", font=("", 8),
        ).pack(anchor="w", padx=10, pady=5)

    def _build_github_tab(self, parent):
        f1 = tk.Frame(parent)
        f1.pack(pady=(10, 5), padx=10, fill=tk.X)
        tk.Label(f1, text="仓库地址：").pack(side=tk.LEFT)
        tk.Entry(f1, textvariable=self.github_repo_var, width=52
                 ).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        f2 = tk.Frame(parent)
        f2.pack(pady=5, padx=10, fill=tk.X)
        tk.Label(f2, text="保存目录：").pack(side=tk.LEFT)
        tk.Label(f2, textvariable=self.save_dir_var, relief=tk.SUNKEN,
                 width=47, anchor="w").pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        tk.Button(f2, text="浏览", command=self._select_dir).pack(side=tk.LEFT)

        f3 = tk.Frame(parent)
        f3.pack(pady=5, padx=10, fill=tk.X)
        tk.Label(f3, text="快速选择：").pack(side=tk.LEFT)
        self._repo_combo = ttk.Combobox(
            f3, width=45,
            values=[f"{name}  ({repo})"
                    for name, repo in GITHUB_FONT_REPOS.items()]
        )
        self._repo_combo.pack(side=tk.LEFT, padx=5)
        self._repo_combo.bind("<<ComboboxSelected>>", self._on_repo_select)

        tk.Label(
            parent,
            text=(
                "📎 支持格式：\n"
                "  - 仓库名：lxgw/LxgwWenKai\n"
                "  - 完整 URL：https://github.com/lxgw/LxgwWenKai\n"
                "  注：GitHub API 每小时限速 60 次（未认证）"
            ),
            justify=tk.LEFT, fg="#666", font=("", 8),
        ).pack(anchor="w", padx=10, pady=10)

    def _build_builtin_tab(self, parent):
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5), pady=10)

        tk.Label(
            scroll_frame,
            text="📚 已调研：免登 / 免费 / 公版字体站（联网调研 2026-06）",
            font=("", 11, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        type_label_map = {
            "list": "列表页 → 详情页 → 下载",
            "forum": "论坛架构 → 详情帖 → 下载",
            "direct": "列表页直接下载",
            "zeoseven": "ZeoSeven 专属解析",
            "fontsnet": "字体天下专属解析（POST API）",
            "github": "GitHub Releases 直链",
            "api": "API 接口直链",
        }

        for name, info in BUILTIN_SITES.items():
            frame = tk.LabelFrame(scroll_frame, text=name, padx=10, pady=6)
            frame.pack(fill=tk.X, pady=4, padx=5)

            type_text = type_label_map.get(info.get("type", ""), info.get("type", ""))
            hint = info.get("mode_hint", "")
            delay = info.get("delay_hint", 1.0)
            meta = f"🔗 模式：{type_text}"
            if hint:
                meta += f"  |  建议：{hint}  延迟≥{delay}s"

            tk.Label(frame, text=meta + "\n📝 " + info["desc"].replace("\n", "\n   "),
                     justify=tk.LEFT, fg="#333",
                     wraplength=680).pack(anchor="w", pady=(0, 4))

            site_type = info.get("type", "")
            if site_type in ("api", "github"):
                continue  # 这两个有专属标签页

            btn_frame = tk.Frame(frame)
            btn_frame.pack(anchor="w")

            if site_type == "zeoseven":
                tk.Button(
                    btn_frame, text="🌟 ZeoSeven专属爬取",
                    command=lambda u=info["url"]: self._use_zeoseven(),
                    width=16
                ).pack(side=tk.LEFT, padx=(0, 5))
            elif site_type == "fontsnet":
                tk.Button(
                    btn_frame, text="🔤 字体天下专属爬取",
                    command=lambda u=info["url"]: self._use_fontsnet(u),
                    width=16
                ).pack(side=tk.LEFT, padx=(0, 5))
            else:
                def _make_fill(u):
                    return lambda: self._use_builtin_site(u)
                def _make_deep(u, hint, d):
                    return lambda: self._use_builtin_deep(u, hint, d)

                tk.Button(btn_frame, text="📋 填入网址",
                          command=_make_fill(info["url"]),
                          width=12).pack(side=tk.LEFT, padx=(0, 5))

                if site_type in ("list", "forum"):
                    tk.Button(btn_frame, text="🔍 深层爬取",
                              command=_make_deep(info["url"], hint, delay),
                              width=12).pack(side=tk.LEFT)

    # ---------- 辅助 ----------

    def log(self, msg):
        self.root.after(0, lambda: self.log_text.insert(tk.END, msg + "\n"))
        self.root.after(0, lambda: self.log_text.see(tk.END))

    def update_progress(self, completed, total, message=""):
        self.root.after(0, lambda: self.progress_bar.configure(
            maximum=max(total, 1), value=completed))
        self.root.after(0, lambda: self.progress_var.set(
            f"{completed}/{total}  {message}" if message else f"{completed}/{total}"))

    def _clear_log(self):
        self.log_text.delete(1.0, tk.END)

    def _select_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.save_dir_var.set(d)

    def _toggle_key_vis(self):
        self._key_vis = not self._key_vis
        self._api_key_entry.configure(show="" if self._key_vis else "*")

    def _on_repo_select(self, event):
        val = self._repo_combo.get()
        # 提取括号内的 owner/repo
        m = re.search(r"\(([^)]+)\)\s*$", val)
        if m:
            self.github_repo_var.set(m.group(1).strip())

    def _use_builtin_site(self, url):
        self.url_var.set(url)
        self.notebook.select(0)
        self.log(f"📋 已填入：{url}")

    def _use_builtin_deep(self, url, hint, delay):
        self.url_var.set(url)
        self.mode_var.set("deep")
        self.max_pages_var.set(30)
        self.delay_var.set(max(self.delay_var.get(), delay))
        self.notebook.select(0)
        self.log(f"📋 深层爬取：{url}")
        self._start()

    def _use_zeoseven(self):
        self.url_var.set("https://fonts.zeoseven.com/browse/")
        self.mode_var.set("zeoseven")
        self.notebook.select(0)
        self.log("🌟 ZeoSeven 专属模式已设置")
        self._start()

    def _use_fontsnet(self, url):
        self.url_var.set(url)
        self.mode_var.set("fontsnet")
        self.max_pages_var.set(50)
        self.delay_var.set(max(self.delay_var.get(), 1.0))
        self.notebook.select(0)
        self.log("🔤 字体天下专属模式已设置")
        self._start()

    def _set_buttons(self, running):
        self.root.after(0, lambda: self.start_btn.config(
            state=tk.DISABLED if running else tk.NORMAL))
        self.root.after(0, lambda: self.stop_btn.config(
            state=tk.NORMAL if running else tk.DISABLED))

    # ---------- 启动/停止 ----------

    def _start(self):
        tab = self.notebook.index(self.notebook.select())
        save_dir = self.save_dir_var.get()
        os.makedirs(save_dir, exist_ok=True)
        self._save_config()
        self._set_buttons(True)
        self.stop_flag = False

        if tab == 1:  # Google Fonts
            self.work_thread = threading.Thread(
                target=self._run_google, args=(save_dir,), daemon=True)
        elif tab == 2:  # GitHub Releases
            repo = self.github_repo_var.get().strip()
            if not repo:
                messagebox.showerror("错误", "请输入仓库地址")
                self._set_buttons(False)
                return
            self.work_thread = threading.Thread(
                target=self._run_github, args=(repo, save_dir), daemon=True)
        else:  # 通用爬虫
            url = self.url_var.get().strip()
            if not url:
                messagebox.showerror("错误", "请输入目标网址")
                self._set_buttons(False)
                return
            self.work_thread = threading.Thread(
                target=self._run_crawl, args=(url, save_dir), daemon=True)

        self.work_thread.start()

    def _stop_task(self):
        self.stop_flag = True
        self.log("🛑 请求停止，等待当前操作完成...")

    def _make_engine(self):
        engine = FontCrawlEngine(
            log_callback=self.log,
            progress_callback=self.update_progress,
            stop_flag=lambda: self.stop_flag,
            use_curl_cffi=self.use_curl_var.get(),
            random_delay=self.random_delay_var.get(),
            respect_robots=self.respect_robots_var.get(),
        )
        engine.set_delay(self.delay_var.get(), self.concurrency_var.get())
        return engine

    # ---------- 任务 ----------

    def _run_crawl(self, url, save_dir):
        engine = self._make_engine()
        try:
            mode = self.mode_var.get()
            max_p = self.max_pages_var.get()

            # 统一使用 discover() 调度（含自动识别 + 所有专属解析器）
            links = engine.discover(
                url, mode=mode,
                max_pages=max_p, max_detail=max_p, max_fonts=max_p,
            )

            if links:
                s, f = engine.download_fonts(links, save_dir,
                                             concurrency=self.concurrency_var.get())
                self.log(f"\n✅ 任务完成！成功 {s} / 失败 {f}")
            else:
                self.log("⚠️ 未发现字体文件。\n提示：部分网站使用网盘链接，需手动下载。")

        except Exception as e:
            self.log(f"❌ 任务异常：{e}")
            import traceback; traceback.print_exc()
        finally:
            self._set_buttons(False)

    def _run_google(self, save_dir):
        api_key = self.google_api_key_var.get().strip()
        families_str = self.google_families_var.get().strip()
        families = [f.strip() for f in families_str.split(",") if f.strip()]

        if not families:
            self.log("❌ 请输入字体名称")
            self._set_buttons(False)
            return

        engine = GoogleFontsEngine(
            log_callback=self.log,
            stop_flag=lambda: self.stop_flag,
            use_curl_cffi=self.use_curl_var.get(),
        )
        engine.set_api_key(api_key)
        try:
            engine.download_fonts(families, save_dir,
                                  concurrency=self.concurrency_var.get())
        except Exception as e:
            self.log(f"❌ 下载异常：{e}")
        finally:
            self._set_buttons(False)

    def _search_google(self):
        api_key = self.google_api_key_var.get().strip()
        if not api_key:
            messagebox.showerror("错误", "请先输入 Google API Key")
            return

        def _run():
            self._set_buttons(True)
            engine = GoogleFontsEngine(log_callback=self.log,
                                       stop_flag=lambda: self.stop_flag)
            engine.set_api_key(api_key)
            self.log("🔍 获取 Google Fonts 列表...")
            fonts = engine.list_fonts()
            if fonts:
                self.log(f"\n📋 前 50 个热门字体（共 {len(fonts)} 个）：")
                self.log("-" * 60)
                for i, (fam, cat, variants, _) in enumerate(fonts[:50], 1):
                    vs = ", ".join(variants[:5])
                    if len(variants) > 5:
                        vs += f" (+{len(variants)-5})"
                    self.log(f"{i:3d}. {fam}  [{cat}]  {vs}")
                self.log("-" * 60)
                self.log("💡 将字体名称填入上方输入框即可下载。")
            self._set_buttons(False)

        threading.Thread(target=_run, daemon=True).start()

    def _download_google(self):
        if not self.google_api_key_var.get().strip():
            messagebox.showerror("错误", "请先输入 Google API Key")
            return
        if not self.google_families_var.get().strip():
            messagebox.showerror("错误", "请输入要下载的字体名称")
            return
        save_dir = self.save_dir_var.get()
        os.makedirs(save_dir, exist_ok=True)
        self._save_config()
        self._set_buttons(True)
        self.stop_flag = False
        self.work_thread = threading.Thread(
            target=self._run_google, args=(save_dir,), daemon=True)
        self.work_thread.start()

    def _run_github(self, repo, save_dir):
        engine = GitHubReleasesEngine(
            log_callback=self.log,
            stop_flag=lambda: self.stop_flag,
        )
        try:
            engine.download(repo, save_dir,
                            concurrency=self.concurrency_var.get())
        except Exception as e:
            self.log(f"❌ 下载异常：{e}")
        finally:
            self._set_buttons(False)


# ============================================================
#  入口
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = FontSpiderGUI(root)
    root.mainloop()
