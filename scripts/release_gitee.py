#!/usr/bin/env python3
# 在 Gitee 上创建 Release 并上传安装包 + sha256（标准库 urllib 实现，无第三方依赖）。
#
# 用法：
#   GITEE_TOKEN=xxxx python scripts/release_gitee.py
#
# 说明：
#   - 默认把仓库根目录下的 release/ 作为产物目录；可用环境变量 REL_DIR 覆盖。
#   - 仓库与 tag 在文件顶部 OWNER / REPO / TAG 常量中修改。
#   - 若 tag 已存在（重复运行），会自动复用已有 Release 并补传缺漏的附件。
import os, sys, json, mimetypes
import urllib.request, urllib.error

OWNER = "siwpan"
REPO = "santi-teleprompter"
API = "https://gitee.com/api/v5"
TAG = "v1.1.0"

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)  # scripts/ -> 仓库根
REL_DIR = os.environ.get("REL_DIR") or os.path.join(REPO_ROOT, "release")

ASSETS = [
    "SantiTeleprompter-Setup-1.1.0.exe",
    "SantiTeleprompter-1.1.0-portable.exe",
    "SantiTeleprompter-1.1.0-portable-win-x64.7z",
    "SantiTeleprompter-1.1.0.sha256.txt",
]


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
    notes_path = os.path.join(REPO_ROOT, "release", "RELEASE_NOTES_v1.1.0.md")
    notes = open(notes_path, encoding="utf-8").read() if os.path.exists(notes_path) \
        else open(os.path.join(REL_DIR, "RELEASE_NOTES_v1.1.0.md"), encoding="utf-8").read()
    body = {
        "tag_name": TAG,
        "name": "v1.1.0 多来源词库（7880 词）与词源筛选",
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
