# WeChat Harness Article Extraction — 2026-05 Session Note

## Context

User asked to evaluate a WeChat/公众号 article for reference value. Initial cloud browser access hit WeChat anti-bot/captcha signals, and an early answer over-interpreted partial text + GitHub repo metadata. User corrected the workflow: first obtain complete source, preferably through the local Mac alias, and avoid triggering interception.

Article URL:

```text
https://mp.weixin.qq.com/s/a3PXFruUYTyD3EhzU30ZhA
```

## Observed Cloud Block

Cloud browser access redirected to a page with:

- `环境异常`
- `当前环境异常，完成验证后即可继续访问。`
- `去验证`
- `wappoc_appmsgcaptcha`
- captcha iframe from `captcha.gtimg.com`

Conclusion: browser DOM contained the challenge page, not article body.

## Local Mac Fetch That Worked

Known user environment: `ssh localmac` reaches the user's Mac. A single conservative local fetch returned full article HTML.

```bash
ssh localmac 'set -e
URL="https://mp.weixin.qq.com/s/a3PXFruUYTyD3EhzU30ZhA"
OUT="$HOME/Downloads/wechat_article_a3PXFruUYTyD3EhzU30ZhA.html"
if [ ! -s "$OUT" ]; then
  /usr/bin/curl -L --compressed --max-time 30 --retry 0 \
    -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36" \
    -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
    -H "Accept-Language: zh-CN,zh;q=0.9,en;q=0.7" \
    "$URL" -o "$OUT"
fi
/usr/bin/python3 - <<PY
from pathlib import Path
p=Path("$OUT")
s=p.read_text(errors="ignore")
print("PATH", p)
print("BYTES", p.stat().st_size)
print("HAS_CAPTCHA", any(x in s for x in ["wappoc_appmsgcaptcha", "环境异常", "验证码"]))
PY'
```

Observed result:

```text
PATH /Users/bytedance/Downloads/wechat_article_a3PXFruUYTyD3EhzU30ZhA.html
BYTES 3014596
HAS_CAPTCHA False
```

## Stdlib Parser Outline

Avoid assuming `bs4` is installed. Use regex + `html` fallback.

```python
from pathlib import Path
import re, html, json, time

src_path = Path.home()/"Downloads/wechat_article_a3PXFruUYTyD3EhzU30ZhA.html"
src = src_path.read_text(errors="ignore")

def first(pats, scope=None):
    s = src if scope is None else scope
    for pat in pats:
        m = re.search(pat, s, re.S|re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""

def js_unescape(v):
    try:
        if "\\x" in v or "\\u" in v:
            return bytes(v, "utf-8").decode("unicode_escape")
    except Exception:
        pass
    return v

meta = {
    "title": first([r"var msg_title = '([^']*)'", r'<meta property="og:title" content="([^"]*)"']),
    "author": first([r"var nickname = '([^']*)'", r'<meta property="og:article:author" content="([^"]*)"']),
    "desc": first([r'<meta property="og:description" content="([^"]*)"', r'var msg_desc = "(.*?)"']),
    "publish_time_raw": first([r"var ct = '([^']*)'", r'id="publish_time"[^>]*>(.*?)</']),
}
meta = {k: js_unescape(v) for k, v in meta.items()}

m = re.search(r'<div[^>]+id="js_content"[^>]*>(.*?)(?:<script nonce|<script type="text/javascript" nonce|<!--\s*本文)', src, re.S|re.I)
block = m.group(1) if m else ""

links=[]
for mm in re.finditer(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S|re.I):
    text = html.unescape(re.sub(r'\s+', ' ', re.sub('<.*?>', '', mm.group(2))).strip())
    links.append((text, html.unescape(mm.group(1))))

imgs=[]
for mm in re.finditer(r'<img\b[^>]*(?:data-src|src)="([^"]+)"[^>]*>', block, re.S|re.I):
    tag = mm.group(0)
    alt = re.search(r'alt="([^"]*)"', tag)
    imgs.append((html.unescape(alt.group(1)) if alt else '', html.unescape(mm.group(1))))

b = block
b = re.sub(r'<br\s*/?>', '\n', b, flags=re.I)
b = re.sub(r'</(p|section|h[1-6]|blockquote|li)>', '\n', b, flags=re.I)
b = re.sub(r'<script.*?</script>|<style.*?</style>', '', b, flags=re.S|re.I)
b = html.unescape(re.sub(r'<[^>]+>', '', b))
lines = [re.sub(r'\s+', ' ', x).strip() for x in b.splitlines()]
text = '\n'.join(x for x in lines if x)

(Path.home()/"Downloads/wechat_article_a3PXFruUYTyD3EhzU30ZhA.txt").write_text(text, encoding="utf-8")
(Path.home()/"Downloads/wechat_article_a3PXFruUYTyD3EhzU30ZhA_meta.json").write_text(
    json.dumps({"meta": meta, "links": links, "image_count": len(imgs), "images": imgs, "chars": len(text)}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
```

## Extracted Facts

- Title: `Harness 工程可视化：在 Vibe Coding 中重建工程可控性`
- Author/account: `Phodal`
- Description: `在最新的 Routa Desktop 中，我们引入了 Harness 工程可视化系统。`
- Extracted text: about 2477 Chinese characters, 29 paragraphs
- Images: 7
- Linked release: `https://github.com/phodal/routa/releases/tag/v0.12.1`

GitHub API context gathered separately:

- repo: `phodal/routa`
- description: `Workspace-first multi-agent coordination platform for AI development, with shared Specs, Kanban orchestration, and MCP/ACP/A2A support across web and desktop.`
- stars observed: 857
- language: TypeScript
- release: `Routa Desktop v0.12.1`

## Image Evidence Summary

The seven images carried important content, not just decoration:

1. Routa specs/source inventory UI: Kiro, Qoder, Bmad/docs; left nav includes instructions, ADR, hooks, review, release, owners, CI/CD, feedback, fitness.
2. Lifecycle UI: requirements, design decisions, coding, local validation, trunk integration, review, gates, release, staging, production, observability.
3. Engineering lifecycle diagram grouped into internal, push, and external feedback loops.
4. Git hook runtime visualization: `pre-commit`, task output, pass gate vs block git action.
5. Fitness radar chart: testability/security/code quality/evolvability/API contract/design system/UI consistency/engineering governance.
6. Harness conceptual diagram: Guides + Sensors feeding a coding agent via feedforward/feedback.
7. Review rules UI: risk, confidence, complexity, routing, human review, pre-push, fallback metrics.

## Analysis Lesson

Do not evaluate reference value from partial body + repo facts. In this session, the correct final analysis only came after:

1. raw full HTML was acquired via local Mac;
2. block markers were checked;
3. body text was extracted;
4. images were downloaded and visually summarized;
5. GitHub repo/release data was used only as external context.

The user specifically wanted a tactful, flexible approach that would not trigger interception. User-facing wording should emphasize "轻量访问 / 避免高频重试 / 不撞风控" rather than adversarial bypass language.
