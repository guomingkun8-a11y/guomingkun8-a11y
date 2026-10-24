#!/usr/bin/env python3
"""自动抓取 GMK-blog 最新文章，更新 README 中的博客列表。

在 README 中用以下标记包裹博客列表区域：
    <!-- BLOG-POSTS:START -->
    <!-- BLOG-POSTS:END -->

脚本会读取 GMK-blog 仓库 frontend/src/content/notes/ 下的所有 markdown 文章，
按 frontmatter 的 date 字段排序，取最新 N 篇生成列表。
"""
import os
import re
import sys
import base64
import urllib.request
import json
from datetime import datetime

BLOG_REPO = "guomingkun8-a11y/GMK-blog"
NOTES_PATH = "frontend/src/content/notes"
README_PATH = "README.md"
MAX_POSTS = 5
START_MARK = "<!-- BLOG-POSTS:START -->"
END_MARK = "<!-- BLOG-POSTS:END -->"

GITHUB_TOKEN = os.environ.get("GH_TOKEN", "")
API_BASE = "https://api.github.com"


def api_get(url):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "blog-updater")
    if GITHUB_TOKEN:
        req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_md_files(path):
    """递归列出 NOTES_PATH 下所有 .md 文件路径。"""
    url = f"{API_BASE}/repos/{BLOG_REPO}/git/trees/main?recursive=1"
    tree = api_get(url)["tree"]
    prefix = NOTES_PATH.rstrip("/") + "/"
    return [
        item["path"]
        for item in tree
        if item["path"].startswith(prefix) and item["path"].endswith(".md")
    ]


def fetch_frontmatter(file_path):
    """读取文件并解析 frontmatter 的 title / date / summary / category。"""
    url = f"{API_BASE}/repos/{BLOG_REPO}/contents/{urllib.parse.quote(file_path)}"
    data = api_get(url)
    content = base64.b64decode(data["content"]).decode("utf-8")
    meta = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            front = parts[1]
            for key in ("title", "date", "summary", "category"):
                m = re.search(rf'^{key}:\s*["\']?(.*?)["\']?\s*$', front, re.M)
                if m:
                    meta[key] = m.group(1).strip()
    meta["path"] = file_path
    return meta


def main():
    files = list_md_files(NOTES_PATH)
    if not files:
        print("未找到文章文件", file=sys.stderr)
        return

    posts = []
    for f in files:
        try:
            meta = fetch_frontmatter(f)
            posts.append(meta)
        except Exception as e:
            print(f"跳过 {f}: {e}", file=sys.stderr)

    # 按日期排序，缺日期的排最后
    def sort_key(p):
        d = p.get("date", "")
        try:
            return datetime.strptime(d, "%Y-%m-%d")
        except Exception:
            return datetime.min

    posts.sort(key=sort_key, reverse=True)
    posts = posts[:MAX_POSTS]

    # 生成 markdown 列表
    lines = []
    for p in posts:
        title = p.get("title") or "未命名"
        date = p.get("date", "")
        date_str = f"`{date}` " if date else ""
        category = p.get("category", "")
        cat_str = f" · {category}" if category else ""
        lines.append(f"- {date_str}**{title}**{cat_str}")

    new_block = "\n".join(lines)

    # 读取 README
    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()

    if START_MARK not in readme or END_MARK not in readme:
        print("README 中缺少 BLOG-POSTS 标记", file=sys.stderr)
        return

    pattern = re.compile(
        rf"{re.escape(START_MARK)}.*?{re.escape(END_MARK)}", re.S
    )
    replacement = f"{START_MARK}\n{new_block}\n{END_MARK}"
    new_readme = pattern.sub(replacement, readme)

    if new_readme == readme:
        print("博客列表无变化")
        return

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_readme)
    print(f"已更新 {len(posts)} 篇文章")


if __name__ == "__main__":
    main()
