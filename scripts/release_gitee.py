#!/usr/bin/env python3
# 在 Gitee 上创建 Release 并上传安装包 + sha256（标准库 urllib 实现，无第三方依赖）。
#
# 用法：
#   GITEE_TOKEN=xxxx [REL_VERSION=1.2.0] [REL_DIR=...] [RELEASE_NAME="..."] [RELEASE_NOTES=...] \
#       python scripts/release_gitee.py
#
# 说明：
#   - 版本由 REL_VERSION 控制（默认 1.1.0，可带或不带前导 "v"）；TAG 自动取 "v" + 版本号。
#   - 附件名按固定命名规则由版本号推导（与 electron-builder + 7z 脚本 + sha256 生成保持一致）：
#       SantiTeleprompter-Setup-{v}.exe
#       SantiTeleprompter-{v}-portable.exe
#       SantiTeleprompter-{v}-portable-win-x64.7z
#       SantiTeleprompter-{v}.sha256.txt
#   - 发布说明默认读 REL_DIR/RELEASE_NOTES_{TAG}.md；可用 RELEASE_NOTES 环境变量指定其它路径。
#   - REL_DIR 默认 仓库根/release，可用环境变量覆盖。
#   - OWNER / REPO 常量需按实际仓库修改。
#   - 若 tag 已存在（重复运行），会自动复用已有 Release 并补传缺漏的附件（幂等）。
import os, sys, json, mimetypes
import urllib.request, urllib.error

OWNER = "siwpan"
REPO = "santi-teleprompter"
API = "https://gitee.com/api/v5"

# ---- 版本相关（全部可由环境变量覆盖，实现「任意版本一键发版」）----
# VERSION 为干净版本号（不含前导 v），用于文件名；TAG 统一补 "v" 前缀。
VERSION = (os.environ.get("REL_VERSION") or "1.1.0").lstrip("v")
TAG = "v" + VERSION                     # 容错：REL_VERSION 带不带 "v" 都行

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)       # scripts/ -> 仓库根
REL_DIR = os.environ.get("REL_DIR") or os.path.join(REPO_ROOT, "release")

# 附件名由版本号推导（与构建产物的命名保持一致）
ASSETS = [
    f"SantiTeleprompter-Setup-{VERSION}.exe",
    f"SantiTeleprompter-{VERSION}-portable.exe",
    f"SantiTeleprompter-{VERSION}-portable-win-x64.7z",
    f"SantiTeleprompter-{VERSION}.sha256.txt",
]


def _notes_path():
    # 允许用环境变量显式指定发布说明文件；否则按 TAG 在 REL_DIR 下查找
    env = os.environ.get("RELEASE_NOTES")
    if env:
        return env
    return os.path.join(REL_DIR, f"RELEASE_NOTES_{TAG}.md")


def http(method, url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def get_release_by_tag(token):
    url = f"{API}/repos/{OWNER}/{REPO}/releases/tags/{TAG}?access_token={token}"
    status, text = http("GET", url)
    if status == 200:
        return json.loads(text)["id"]
    raise SystemExit("按 tag 取 release 失败: %s %s" % (status, text[:200]))


def create_release(token):
    url = f"{API}/repos/{OWNER}/{REPO}/releases?access_token={token}"
    np_ = _notes_path()
    if not os.path.exists(np_):
        raise SystemExit("发布说明缺失: %s（可用 RELEASE_NOTES 环境变量指定）" % np_)
    notes = open(np_, encoding="utf-8").read()
    name = os.environ.get("RELEASE_NAME") or f"v{VERSION}"
    body = {
        "tag_name": TAG,
        "name": name,
        "body": notes,
        "target_commitish": "master",
        "prerelease": False,
    }
    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json;charset=UTF-8"}
    status, text = http("POST", url, data=data, headers=headers)
    print("create_release ->", status, text[:200])
    if status in (200, 201):
        return json.loads(text)["id"]
    if status in (400, 409):  # tag/发行版已存在：复用
        print("release 已存在，按 tag 获取 id ...")
        return get_release_by_tag(token)
    raise SystemExit("创建 Release 失败")


def upload_asset(token, release_id, filepath):
    url = f"{API}/repos/{OWNER}/{REPO}/releases/{release_id}/attach_files?access_token={token}"
    boundary = "----wbrel%d" % os.getpid()
    fname = os.path.basename(filepath)
    ctype = mimetypes.guess_type(fname)[0] or "application/octet-stream"
    with open(filepath, "rb") as f:
        content = f.read()
    parts = []
    for name, val in (("access_token", token), ("release_id", str(release_id))):
        parts += [b"--" + boundary.encode(),
                  f'Content-Disposition: form-data; name="{name}"'.encode(),
                  b"", val.encode()]
    parts += [b"--" + boundary.encode(),
              f'Content-Disposition: form-data; name="file"; filename="{fname}"'.encode(),
              f"Content-Type: {ctype}".encode(), b"", content,
              b"--" + boundary.encode() + b"--", b""]
    body = b"\r\n".join(parts)
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    status, text = http("POST", url, data=body, headers=headers)
    print("upload", fname, "(%d bytes) ->" % len(content), status, text[:160])
    return status


def main():
    token = os.environ.get("GITEE_TOKEN")
    if not token:
        raise SystemExit("请先设置环境变量 GITEE_TOKEN（Gitee 私人令牌，需仓库权限）")
    print("发版参数: TAG=%s  REL_DIR=%s" % (TAG, REL_DIR))
    rid = create_release(token)
    print("release id =", rid)
    for fn in ASSETS:
        p = os.path.join(REL_DIR, fn)
        if os.path.exists(p):
            upload_asset(token, rid, p)
        else:
            print("跳过（缺失）:", p)
    print("完成 ->", f"https://gitee.com/{OWNER}/{REPO}/releases/tag/{TAG}")


if __name__ == "__main__":
    main()
