#!/usr/bin/env python3
"""Turn a vet-this report.md into a styled, self-contained report.html (no dependencies).

Usage:
  python3 md_to_html.py report.md [report.html]

Handles the markdown the report template uses: headings, paragraphs, lists, tables,
code blocks, blockquotes, images, bold, italics, inline code and links.
"""
import html
import re
import sys

CSS = """
html{font-size:18px}
body{margin:0;background:#fafaf8;color:#1d1d1b;font:1rem/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Helvetica,Arial,sans-serif}
main{max-width:980px;margin:0 auto;padding:3rem 2rem 5rem}
h1{font-size:2.1rem;line-height:1.2;margin:0 0 .4rem}
h2{font-size:1.4rem;margin:2.6rem 0 .8rem;padding-top:1rem;border-top:1px solid #e4e2dc}
h3{font-size:1.1rem;margin:1.8rem 0 .5rem}
p,li{font-size:.95rem}
a{color:#1f5fbf}
code{font:.85rem/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;background:#efede7;padding:.1rem .3rem}
pre{background:#f1efe9;border:1px solid #e4e2dc;padding:1rem;overflow:auto}
pre code{background:none;padding:0}
table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.9rem;background:#fff}
th,td{border:1px solid #e4e2dc;padding:.55rem .7rem;text-align:left;vertical-align:top}
th{background:#f3f1ec;font-size:.8rem;text-transform:uppercase;letter-spacing:.03em;color:#55534d}
blockquote{margin:1.2rem 0;padding:.9rem 1.2rem;background:#fff;border:1px solid #e4e2dc;border-left:5px solid #8a8780;border-radius:0}
blockquote.good{border-left-color:#2e8b57}
blockquote.warn{border-left-color:#d08a1c}
blockquote.bad{border-left-color:#c0392b}
blockquote p{margin:.3rem 0}
img{max-width:100%;border:1px solid #e4e2dc}
.frames{display:flex;flex-wrap:wrap;gap:.6rem}
.frames img{width:23%;min-width:160px}
.meta{color:#6b6962;font-size:.8rem}
"""

GOOD = re.compile(r"\b(safe|holds|lives up|yes|good fit|install)\b", re.I)
BAD = re.compile(r"\b(don't install|do not install|unsafe|doesn't hold|no fit|skip|avoid|fails)\b", re.I)
WARN = re.compile(r"\b(caveat|partly|mixed|can't verify|unverified|maybe|wait)\b", re.I)


def inline(t):
    t = html.escape(t, quote=False)
    codes = []
    t = re.sub(r"`([^`]+)`", lambda m: codes.append(m.group(1)) or f"\x00{len(codes)-1}\x00", t)
    t = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img alt="\1" src="\2">', t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r'(?<!["(>])\b(https?://[^\s<)]+[^\s<).,;])', r'<a href="\1">\1</a>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\w)", r"<em>\1</em>", t)
    t = re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{codes[int(m.group(1))]}</code>", t)
    return t


def convert(md):
    lines = md.splitlines()
    out, i = [], 0
    title = "vet-this report"
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            buf, i = [], i + 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(html.escape(lines[i]))
                i += 1
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", ln)
        if m:
            lvl = len(m.group(1))
            if lvl == 1:
                title = m.group(2)
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            hdr = [c.strip() for c in ln.strip().strip("|").split("|")]
            rows, i = [], i + 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            t = "<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in hdr) + "</tr></thead><tbody>"
            t += "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(t + "</tbody></table>")
            continue
        if ln.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i][1:].strip())
                i += 1
            text = " ".join(buf)
            cls = "bad" if BAD.search(text) else "warn" if WARN.search(text) else "good" if GOOD.search(text) else ""
            body = "".join(f"<p>{inline(b)}</p>" for b in buf if b)
            out.append(f'<blockquote class="{cls}">{body}</blockquote>')
            continue
        if re.match(r"^\s*([-*]|\d+\.)\s+", ln):
            ordered = bool(re.match(r"^\s*\d+\.", ln))
            tag = "ol" if ordered else "ul"
            items = []
            while i < len(lines) and (re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]) or (lines[i].startswith("  ") and items)):
                if re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                    items.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i]))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        m = re.match(r'^<p class="meta">(.*)</p>\s*$', ln.strip())
        if m:
            out.append(f'<p class="meta">{inline(m.group(1))}</p>')
            i += 1
            continue
        if ln.strip().startswith('<div class="frames">'):
            buf = []
            while i < len(lines):
                buf.append(lines[i])
                if "</div>" in lines[i]:
                    break
                i += 1
            out.append("\n".join(buf))
            i += 1
            continue
        if ln.strip():
            buf = []
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#|>|\||```|\s*([-*]|\d+\.)\s)", lines[i]):
                buf.append(lines[i].strip())
                i += 1
            out.append(f"<p>{inline(' '.join(buf))}</p>")
            continue
        i += 1
    return title, "\n".join(out)


def main():
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else re.sub(r"\.md$", "", src) + ".html"
    title, body = convert(open(src, encoding="utf-8").read())
    page = (f"<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
            f"<body><main>{body}</main></body></html>")
    open(dst, "w", encoding="utf-8").write(page)
    print(dst)


if __name__ == "__main__":
    main()
