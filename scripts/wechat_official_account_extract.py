#!/usr/bin/env python3
"""Fetch and extract WeChat Official Account articles for Hermes ingestion.

This is intentionally dependency-light and evidence-oriented. It accepts either raw
message text (as received from Weixin/Feishu) or explicit URLs, extracts
mp.weixin.qq.com article URLs, fetches each page, parses title/account/time/body,
and writes durable JSON + text evidence.

Fetch strategy:
1. Try the user's local Mac via SSH alias `localmac`/`mac` with a mobile Safari UA.
2. Fall back to direct cloud fetch with the same UA.

No cookies/tokens are used or printed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
    "Mobile/15E148 Safari/604.1"
)

URL_RE = re.compile(r"https?://(?:mp\.weixin\.qq\.com|mp\.weixin\.qq\.com\.cn)/[^\s\]）)>'\"]+", re.I)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def clean_url(url: str) -> str:
    url = html.unescape(url.strip())
    # Chat clients often append punctuation; preserve query params but strip sentence marks.
    return url.rstrip(".,，。；;、)）]】>'\"")


def extract_urls_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in URL_RE.finditer(text or ""):
        u = clean_url(m.group(0))
        if u and u not in seen:
            out.append(u)
            seen.add(u)
    return out


def fetch_direct(url: str, timeout: int = 25) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": MOBILE_UA,
            "Referer": "https://mp.weixin.qq.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    started = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - explicit user-provided public article URL
        data = r.read()
        return {
            "ok": True,
            "method": "direct",
            "status": getattr(r, "status", None),
            "final_url": getattr(r, "url", url),
            "bytes": len(data),
            "duration_seconds": round(time.time() - started, 3),
            "html": data.decode("utf-8", "replace"),
        }


def fetch_via_ssh(alias: str, url: str, timeout: int = 35) -> dict[str, Any]:
    # Pass URL via argv to avoid shell interpolation. The heredoc body is constant.
    code = r'''
import json, sys, time, urllib.request
url=sys.argv[1]
ua=sys.argv[2]
started=time.time()
try:
    req=urllib.request.Request(url, headers={
        'User-Agent': ua,
        'Referer': 'https://mp.weixin.qq.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    })
    with urllib.request.urlopen(req, timeout=25) as r:
        data=r.read()
    print(json.dumps({
        'ok': True,
        'status': getattr(r, 'status', None),
        'final_url': getattr(r, 'url', url),
        'bytes': len(data),
        'duration_seconds': round(time.time()-started, 3),
        'html': data.decode('utf-8', 'replace'),
    }, ensure_ascii=False))
except Exception as e:
    print(json.dumps({'ok': False, 'error': str(e), 'duration_seconds': round(time.time()-started, 3)}, ensure_ascii=False))
    sys.exit(2)
'''
    remote_cmd = " ".join([
        "python3",
        "-c",
        shlex.quote(code),
        shlex.quote(url),
        shlex.quote(MOBILE_UA),
    ])
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", alias, remote_cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        return {"ok": False, "method": f"ssh:{alias}", "error": (proc.stderr or proc.stdout).strip()[-1000:]}
    try:
        payload = json.loads(proc.stdout)
    except Exception as exc:
        return {"ok": False, "method": f"ssh:{alias}", "error": f"invalid ssh json: {exc}", "stdout_tail": proc.stdout[-1000:]}
    payload["method"] = f"ssh:{alias}"
    return payload


def fetch_article(url: str, prefer_localmac: bool = True) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    if prefer_localmac:
        for alias in ("localmac", "mac"):
            attempt = fetch_via_ssh(alias, url)
            attempts.append({k: v for k, v in attempt.items() if k != "html"})
            if attempt.get("ok") and attempt.get("html"):
                attempt["attempts"] = attempts
                return attempt
    try:
        attempt = fetch_direct(url)
    except Exception as exc:
        attempt = {"ok": False, "method": "direct", "error": str(exc)}
    attempts.append({k: v for k, v in attempt.items() if k != "html"})
    attempt["attempts"] = attempts
    return attempt


def clean_html_fragment(fragment: str) -> str:
    s = fragment or ""
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</(?:p|section|h\d|li|div|blockquote|span|strong)>", "\n", s, flags=re.I)
    s = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>|<svg[\s\S]*?</svg>", "", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = s.replace("\r", "")
    s = re.sub(r"[ \t\u00a0]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def first_match(patterns: list[str], text: str, *, clean: bool = True) -> str:
    for pat in patterns:
        m = re.search(pat, text, flags=re.S | re.I)
        if m:
            value = m.group(1)
            return clean_html_fragment(value) if clean else html.unescape(value.strip())
    return ""


def parse_article(page_html: str) -> dict[str, Any]:
    title = first_match([
        r'<h1[^>]*id=["\']activity-name["\'][^>]*>([\s\S]*?)</h1>',
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'var\s+msg_title\s*=\s*["\']([\s\S]*?)["\'];',
        r'"title"\s*:\s*"([^"]+)"',
    ], page_html)
    account = first_match([
        r'<span[^>]*id=["\']js_name["\'][^>]*>([\s\S]*?)</span>',
        r'var\s+nickname\s*=\s*["\']([\s\S]*?)["\'];',
        r'"nickname"\s*:\s*"([^"]+)"',
    ], page_html)
    publish_time = first_match([
        r'id=["\']publish_time["\'][^>]*>([\s\S]*?)</span>',
        r'var\s+publish_time\s*=\s*["\']([\s\S]*?)["\'];',
        r'"publish_time"\s*:\s*"([^"]+)"',
    ], page_html)
    content_match = re.search(r'<div[^>]*id=["\']js_content["\'][^>]*>([\s\S]*?)</div>\s*<(?:script|div)', page_html, flags=re.S | re.I)
    if not content_match:
        content_match = re.search(r'<div[^>]*id=["\']js_content["\'][^>]*>([\s\S]*?)</div>', page_html, flags=re.S | re.I)
    content = clean_html_fragment(content_match.group(1)) if content_match else ""
    block_signals = []
    visible = clean_html_fragment(page_html[:20000])
    for token in ("环境异常", "完成验证", "captcha.gtimg.com", "访问过于频繁", "该内容已被发布者删除"):
        if token in page_html or token in visible:
            block_signals.append(token)
    return {
        "title": title,
        "account": account,
        "publish_time": publish_time,
        "content": content,
        "content_chars": len(content),
        "content_lines": content.count("\n") + (1 if content else 0),
        "block_signals": block_signals,
        "complete_enough": bool(title and len(content) >= 300 and not block_signals),
    }


def safe_slug(value: str, fallback: str) -> str:
    value = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "-", value or "").strip("-._")
    return (value[:80] or fallback)


def write_outputs(out_dir: Path, article: dict[str, Any], html_text: str) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    idx = article.get("index", 1)
    slug = safe_slug(article.get("title") or urllib.parse.urlparse(article.get("url", "")).path.strip("/") or "article", f"article-{idx}")
    base = f"{idx:02d}-{slug}"
    html_path = out_dir / f"{base}.html"
    txt_path = out_dir / f"{base}.txt"
    json_path = out_dir / f"{base}.json"
    html_path.write_text(html_text, encoding="utf-8")
    text_doc = "\n".join([
        f"标题：{article.get('title','')}",
        f"公众号：{article.get('account','')}",
        f"时间：{article.get('publish_time','')}",
        f"URL：{article.get('url','')}",
        f"抽取方式：{article.get('fetch_method','')}",
        "",
        article.get("content", ""),
    ]).strip() + "\n"
    txt_path.write_text(text_doc, encoding="utf-8")
    json_path.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"html": str(html_path), "text": str(txt_path), "json": str(json_path)}


def build_landing_suggestions(article: dict[str, Any]) -> list[str]:
    title = article.get("title") or "公众号文章"
    return [
        f"生成《{title}》的高密度摘要与可执行行动项。",
        "把文章结论映射到现有灵感收集箱：新想法建主表记录，补充已有想法则写更新记录。",
        "若文章能推进工程/自动化项目，创建 Feishu Doc 作为长文产出物，并在主表记录关联云文档。",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract WeChat Official Account article text with evidence.")
    parser.add_argument("--url", action="append", default=[], help="mp.weixin.qq.com article URL; may repeat")
    parser.add_argument("--message", default="", help="raw inbound chat message text containing article URLs")
    parser.add_argument("--message-file", help="file containing raw inbound chat message text")
    parser.add_argument("--sample-file", help="newline-delimited URLs/messages for smoke verification")
    parser.add_argument("--out-dir", default="reports/wechat-official-account-extraction/artifacts")
    parser.add_argument("--summary-json", default="reports/wechat-official-account-extraction/wechat-official-account-extraction-smoke.json")
    parser.add_argument("--no-localmac", action="store_true", help="skip ssh localmac/mac and fetch directly")
    parser.add_argument("--min-chars", type=int, default=300)
    args = parser.parse_args()

    raw_texts: list[str] = []
    if args.message:
        raw_texts.append(args.message)
    if args.message_file:
        raw_texts.append(Path(args.message_file).read_text(encoding="utf-8"))
    if args.sample_file:
        sample = Path(args.sample_file).read_text(encoding="utf-8")
        raw_texts.append(sample)
    urls = [clean_url(u) for u in args.url]
    for text in raw_texts:
        urls.extend(extract_urls_from_text(text))
    # Preserve order, remove dupes.
    urls = list(dict.fromkeys(u for u in urls if u))

    report: dict[str, Any] = {
        "ok": False,
        "generated_at": now_iso(),
        "input": {"url_count": len(urls), "has_message": bool(raw_texts)},
        "articles": [],
        "errors": [],
    }
    out_dir = Path(args.out_dir)
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    if not urls:
        report["errors"].append("no mp.weixin.qq.com URL found in input")
        summary_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    for i, url in enumerate(urls, 1):
        fetched = fetch_article(url, prefer_localmac=not args.no_localmac)
        article: dict[str, Any] = {
            "index": i,
            "url": url,
            "fetch_ok": bool(fetched.get("ok")),
            "fetch_method": fetched.get("method"),
            "status": fetched.get("status"),
            "final_url": fetched.get("final_url"),
            "html_bytes": fetched.get("bytes", 0),
            "attempts": fetched.get("attempts", []),
        }
        html_text = fetched.get("html") or ""
        if not fetched.get("ok") or not html_text:
            article["error"] = fetched.get("error") or "empty html"
            report["articles"].append(article)
            continue
        parsed = parse_article(html_text)
        article.update(parsed)
        article["complete_enough"] = bool(parsed.get("complete_enough") and parsed.get("content_chars", 0) >= args.min_chars)
        article["landing_suggestions"] = build_landing_suggestions(article)
        article["paths"] = write_outputs(out_dir, article, html_text)
        report["articles"].append({k: v for k, v in article.items() if k != "content"})

    ok_articles = [a for a in report["articles"] if a.get("complete_enough")]
    report["ok"] = len(ok_articles) == len(urls)
    report["summary"] = {
        "total": len(urls),
        "complete": len(ok_articles),
        "failed": len(urls) - len(ok_articles),
        "titles": [a.get("title") for a in report["articles"] if a.get("title")],
    }
    summary_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
