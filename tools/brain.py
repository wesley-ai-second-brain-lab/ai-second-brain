#!/usr/bin/env python3
"""brain — agent-neutral CLI for the AI Second Brain.

Any coding agent with a shell (Claude Code, Codex, Kiro, Devin, Cursor, Gemini CLI…) can run the
whole pipeline with it. Only the Python standard library is needed (plus ffmpeg for `sheets`).

  brain init [--dir DIR]              create the brain folder + brain.config.json
  brain video URL [--start M:SS --end M:SS] [--queue]
                                      download + scene screenshots + transcript (runs now, or --queue for launchd)
  brain sheets INBOX_DIR              contact sheets of all frames (to pick key frames)
  brain ingest NOTE.json              write raw/ sources/ wiki/ index.md assets/ + site data, print where-to-find
  brain site                          build a static website (site/index.html) from all notes
  brain search WORDS…                 find notes/concepts mentioning the words (for Q&A)
  brain where SLUG                    print where a note lives

The brain folder comes from --dir, $AI_BRAIN_DIR, or ~/LLM/AI第二大脑.
Put it inside your Google Drive for desktop folder if you want a cloud copy with zero extra steps.
"""
import argparse, datetime, html, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "template" / "brain"


def brain_dir(arg=None) -> Path:
    return Path(os.path.expanduser(arg or os.environ.get("AI_BRAIN_DIR") or "~/LLM/AI第二大脑")).resolve()


def load_cfg(B: Path) -> dict:
    p = B / "brain.config.json"
    return json.loads(p.read_text()) if p.exists() else {}


def today():
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------- init
def cmd_init(a):
    B = brain_dir(a.dir)
    for d in ["raw", "sources", "wiki", "assets", "inbox/queue", "inbox/logs", "tools", ".brain/library"]:
        (B / d).mkdir(parents=True, exist_ok=True)
    for f in ["README.md", "index.md"]:
        if not (B / f).exists() and (TEMPLATE / f).exists():
            shutil.copy(TEMPLATE / f, B / f)
    cfg = B / "brain.config.json"
    if not cfg.exists():
        c = json.loads((TEMPLATE / "brain.config.example.json").read_text())
        c["local_dir"] = str(B).replace(str(Path.home()), "~", 1)
        cfg.write_text(json.dumps(c, ensure_ascii=False, indent=2))
    for f in ["runner.py", "tts.py"]:
        if (HERE / f).exists():
            shutil.copy(HERE / f, B / "tools" / f)
    print(json.dumps({"brain": str(B), "config": str(cfg)}, ensure_ascii=False))


# ---------------------------------------------------------------- video
def video_id(url):
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", url)
    return m.group(1) if m else re.sub(r"\W+", "_", url)[-40:]


def cmd_video(a):
    B = brain_dir(a.dir)
    vid = video_id(a.url)
    url = f"https://www.youtube.com/watch?v={vid}" if re.fullmatch(r"[\w-]{11}", vid) else a.url
    q = B / "inbox" / "queue"; q.mkdir(parents=True, exist_ok=True)
    extra = " ".join(x for x in [f"--start {a.start}" if a.start else "", f"--end {a.end}" if a.end else ""] if x)
    (q / f"{vid}.url").write_text(url + ("\n" + extra if extra else "") + "\n")
    if a.queue:
        print(json.dumps({"queued": str(q / f"{vid}.url")}, ensure_ascii=False)); return
    py = B / "tools" / ".venv" / "bin" / "python3"
    py = str(py) if py.exists() else sys.executable
    runner = B / "tools" / "runner.py"
    if not runner.exists():
        runner = HERE / "runner.py"
    subprocess.run([py, str(runner)], env={**os.environ, "AI_BRAIN_DIR": str(B)}, check=False)
    st = next((s for s in [".done", ".failed", ".url", ".running"] if (q / f"{vid}{s}").exists()), "?")
    log = (B / "inbox" / "logs" / f"{vid}.log")
    m = re.findall(r"done → (.+)$", log.read_text() if log.exists() else "", re.M)
    out = {"status": st.strip("."), "log": str(log)}
    if m:
        d = Path(m[-1].strip()); out.update(dir=str(d), frames=len(list((d / "frames").glob("*.jpg"))),
                                             transcript=str(d / "transcript.json"))
    print(json.dumps(out, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- sheets
def cmd_sheets(a):
    d = Path(a.inbox_dir).resolve(); (d / "sheets").mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-pattern_type", "glob", "-i", str(d / "frames" / "*.jpg"),
                    "-vf", "scale=320:-1,tile=4x4", str(d / "sheets" / "sheet_%02d.jpg")], check=True)
    frames = sorted(p.name for p in (d / "frames").glob("*.jpg"))
    print(json.dumps({"sheets": sorted(str(p) for p in (d / "sheets").glob("sheet_*.jpg")),
                      "frames_in_order": frames, "note": "each sheet = 16 frames, row by row"}, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- ingest
def secs(t):
    s = 0
    for part in str(t).split(":"):
        s = s * 60 + int(part)
    return s


def tlink(url, t):
    return f"{url}{'&' if '?' in url else '?'}t={secs(t)}s"


def add_bullet(page: Path, bullet: str, slug: str, definition: str, title: str):
    if page.exists():
        t = page.read_text()
        if f"[[{slug}]]" in t:
            return False
        if "## 要点" in t:
            t = re.sub(r"(## 要点\n(?:- .*\n)*)", lambda m: m.group(1) + bullet + "\n", t, count=1)
        else:
            t += f"\n## 要点\n{bullet}\n"
        t = re.sub(r"^updated: .*$", f"updated: {today()}", t, flags=re.M)
    else:
        t = "\n".join(["---", f'title: "{title}"', "type: 概念", f"updated: {today()}", "---", "", f"# {title}", "",
                       definition or f"（待补充定义）", "", "## 要点", bullet, "", "## 相关", "- [[index]]", ""])
    page.write_text(t)
    return True


def rebuild_index(B: Path):
    wiki = sorted(p for p in (B / "wiki").glob("*.md"))
    srcs = sorted((B / "sources").glob("*.md"), reverse=True)
    def first(p):
        for l in p.read_text().split("\n---", 1)[-1].split("\n"):
            if l.strip() and not l.startswith(("#", "---")):
                return l.strip()[:80]
        return ""
    def meta(p):
        t = p.read_text(); ti = re.search(r'^title: "(.*)"$', t, re.M); ty = re.search(r"^type: (.*)$", t, re.M)
        return (ti.group(1) if ti else p.stem), (ty.group(1) if ty else "")
    L = ["# AI 第二大脑 · 总目录", "", "> 回答问题前先读这页，再按链接打开相关页面。新增资料时同步更新本页。", "",
         f"更新：{today()} · 资料 {len(srcs)} 份 · 概念 {len(wiki)} 个", "", "## 概念（wiki/）"]
    L += [f"- [[{p.stem}]] — {first(p)}" for p in wiki]
    L += ["", "## 资料（sources/，新的在前）"]
    L += [f"- [[{p.stem}]] · {meta(p)[1]} · {meta(p)[0]}" for p in srcs]
    (B / "index.md").write_text("\n".join(L) + "\n")


def cmd_ingest(a):
    B = brain_dir(a.dir); n = json.loads(Path(a.note).read_text()); cfg = load_cfg(B)
    slug = n["slug"]; url = n.get("url", ""); typ = n.get("type", "视频"); src = Path(n["source_dir"]) if n.get("source_dir") else None
    A = B / "assets" / slug
    # assets
    frames = []
    for f in n.get("frames", []):
        p = Path(f["file"]); p = p if p.is_absolute() else (src / "frames" / p if src else p)
        if p.exists():
            A.mkdir(parents=True, exist_ok=True); shutil.copy(p, A / p.name)
            frames.append({**f, "file": p.name})
    fmap = {f["file"]: f for f in frames}
    # raw
    raw_name = f"{slug}-raw"
    R = ["---", f'title: "{n["title"]} · 原文"', "type: 原文", f"source: {url}", f"added: {n.get('added', today())}", "---", ""]
    if src and (src / "transcript.json").exists():
        para, st = [], 0
        for s in json.loads((src / "transcript.json").read_text()):
            if not para: st = s["t_start"]
            para.append(s["text"].strip())
            if len(" ".join(para)) > 400:
                R += [f"**[{int(st // 60)}:{int(st % 60):02d}]** " + " ".join(para), ""]; para = []
        if para: R.append(f"**[{int(st // 60)}:{int(st % 60):02d}]** " + " ".join(para))
    elif n.get("raw_text"):
        R.append(n["raw_text"])
    elif n.get("raw_file"):
        R.append(Path(n["raw_file"]).read_text())
    (B / "raw").mkdir(exist_ok=True); (B / "raw" / f"{raw_name}.md").write_text("\n".join(R) + "\n")
    # sources page
    concepts = n.get("concepts", [])[:4]
    L = ["---", f'title: "{n["title"]}"', f"type: {typ}", f"source: {url}", f"author: {n.get('channel', '')}",
         f"published: {n.get('published', '')}", f"added: {n.get('added', today())}", f"concepts: [{', '.join(concepts)}]",
         "---", "", f"# {n['title']}", "", f"> {n.get('channel', '')} · {n.get('duration', '')} · {n.get('guests', '')}", "",
         "## 一句话", n["summary"], "", "## Highlights"] + [f"- {h}" for h in n.get("highlights", [])]
    L += ["", "## 要点"]
    for p in n.get("points", []):
        L.append(f"- [{p['t']}]({tlink(url, p['t'])}) {p['text']}" if p.get("t") else f"- {p['text']}")
        if p.get("frame") and p["frame"] in fmap:
            L.append(f"  ![[assets/{slug}/{p['frame']}]]")
    if frames:
        L += ["", "## 幻灯片截图"]
        for f in frames:
            L += [f"### [{f.get('t', '')}]({tlink(url, f['t']) if f.get('t') else url}) {f.get('caption', '')}", f"![[assets/{slug}/{f['file']}]]", ""]
    if n.get("terms"): L += ["", "## 关键概念"] + [f"- **{t['term']}**：{t['explain']}" for t in n["terms"]]
    L += ["", "## 对我的启发"] + [f"- {t}" for t in n.get("takeaways", [])]
    L += ["", "## 相关概念"] + [f"- [[{c}]]" for c in concepts]
    L += ["", "## 原文", f"- 链接：{url}", f"- 存档：[[raw/{raw_name}]]"]
    sp = B / "sources" / f"{slug}.md"; sp.write_text("\n".join(L) + "\n")
    # wiki
    updated = []
    for c in concepts:
        bullet = f"- {n.get('concept_notes', {}).get(c) or n['summary'].split('。')[0]}（[[{slug}]]）"
        if add_bullet(B / "wiki" / f"{c}.md", bullet, slug, n.get("concept_defs", {}).get(c, ""), c):
            updated.append(c)
    rebuild_index(B)
    # site data
    lib = B / ".brain" / "library"; lib.mkdir(parents=True, exist_ok=True)
    (lib / f"{slug}.json").write_text(json.dumps({**n, "frames": frames, "createdAt": int(time.time() * 1000)}, ensure_ascii=False))
    if src and src.exists():
        (src / ".ingested").write_text(f"{today()} → sources/{slug}.md\n")
    # verify (some editors rewrite an open file)
    ok = sp.exists() and sp.stat().st_size > 200
    print(where_block(B, cfg, slug, n["title"], updated, ok))


def where_block(B, cfg, slug, title, updated=None, ok=True):
    site = B / "site" / "index.html"
    lines = ["📍 在哪里看 / Where to find it"]
    lines.append(f"🌐 网站：{cfg.get('website_url')}  → 「{cfg.get('website_notes_tab', '学习笔记')}」→ 「{title}」" if cfg.get("website_url")
                 else f"🌐 本地网页：{site}（运行 `brain site` 生成/刷新）")
    lines.append(f"💻 Obsidian：{B / 'sources' / (slug + '.md')}" + ("" if ok else "（⚠️ 写入核对失败，请重试）"))
    lines.append(f"   → 左侧 sources → {slug}；或 ⌘/Ctrl+Shift+F 搜标题；截图在 assets/{slug}/")
    gd = cfg.get("drive_folder_url") or ("（brain 文件夹在 Google Drive 同步目录里会自动上云）" if "GoogleDrive" in str(B) or "Google Drive" in str(B) else "未配置")
    lines.append(f"☁️ Google Drive：{gd}")
    if updated is not None:
        lines.append("🧠 概念页：" + ("、".join(f"[[{c}]]" for c in updated) or "无新增") + "；index.md 已更新")
    return "\n".join(lines)


def cmd_where(a):
    B = brain_dir(a.dir); p = B / "sources" / f"{a.slug}.md"
    t = re.search(r'^title: "(.*)"$', p.read_text(), re.M).group(1) if p.exists() else a.slug
    print(where_block(B, load_cfg(B), a.slug, t))


# ---------------------------------------------------------------- search
def cmd_search(a):
    B = brain_dir(a.dir); words = [w.lower() for w in a.words]; hits = []
    for folder in ["wiki", "sources"]:
        for p in (B / folder).glob("*.md"):
            t = p.read_text().lower(); score = sum(t.count(w) for w in words)
            if score and all(w in t for w in words):
                hits.append((score, f"{folder}/{p.name}"))
    for s, h in sorted(hits, reverse=True)[:15]:
        print(f"{s:4d}  {h}")


# ---------------------------------------------------------------- site
def mm_html(node):
    kids = node.get("children") or []
    return f"<li>{html.escape(node.get('text', ''))}" + (f"<ul>{''.join(mm_html(k) for k in kids)}</ul>" if kids else "") + "</li>"


def cmd_site(a):
    B = brain_dir(a.dir); out = B / "site"; out.mkdir(exist_ok=True)
    items = sorted((json.loads(p.read_text()) for p in (B / ".brain" / "library").glob("*.json")), key=lambda x: -x.get("createdAt", 0))
    cards = []
    for n in items:
        e = html.escape; slug = n["slug"]; url = n.get("url", "")
        fr = {f["file"]: f for f in n.get("frames", [])}
        pts = []
        for p in n.get("points", []):
            ts = f'<a class="ts" href="{e(tlink(url, p["t"]))}" target="_blank">{e(p["t"])}</a>' if p.get("t") else ""
            img = f'<img loading="lazy" src="../assets/{e(slug)}/{e(p["frame"])}" alt="">' if p.get("frame") in fr else ""
            pts.append(f"<li>{ts} {e(p['text'])}{img}</li>")
        grid = "".join(f'<figure><img loading="lazy" src="../assets/{e(slug)}/{e(f["file"])}" alt=""><figcaption>{e(f.get("t", ""))} {e(f.get("caption", ""))}</figcaption></figure>' for f in n.get("frames", []))
        mm = f'<details><summary>脑图 Mind map</summary><ul class="mm">{mm_html(n["mindmap"])}</ul></details>' if n.get("mindmap") else ""
        cards.append(f"""<article><h2><a href="{e(url)}" target="_blank">{e(n['title'])}</a></h2>
<div class="meta">{e(n.get('type', ''))} · {e(n.get('channel', ''))} · {e(n.get('duration', ''))}</div>
<p class="sum"><b>一句话</b> {e(n['summary'])}</p>{mm}
<details><summary>完整笔记 Full notes</summary><h3>Highlights</h3><ul>{''.join(f'<li>{e(h)}</li>' for h in n.get('highlights', []))}</ul>
<h3>要点</h3><ol class="pts">{''.join(pts)}</ol>{f'<h3>截图</h3><div class="grid">{grid}</div>' if grid else ''}
<h3>启发</h3><ul>{''.join(f'<li>{e(t)}</li>' for t in n.get('takeaways', []))}</ul></details></article>""")
    page = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 第二大脑 · 学习笔记</title><style>
:root{{--bg:#f6f7fb;--card:#fff;--ink:#1d2433;--mute:#667085;--acc:#e8662a;--line:#e4e7ef}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f1420;--card:#171e2d;--ink:#e8edf7;--mute:#98a3b8;--line:#263045}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 -apple-system,"PingFang SC","Noto Sans CJK SC",sans-serif}}
main{{max-width:980px;margin:0 auto;padding:24px 16px}}h1{{margin:.2em 0}}article{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 22px;margin:16px 0}}
h2{{font-size:20px;margin:.2em 0}}h2 a{{color:inherit;text-decoration:none}}.meta{{color:var(--mute);font-size:13px}}.sum{{background:#e8662a14;border-radius:10px;padding:10px 12px}}
summary{{cursor:pointer;color:var(--acc);font-weight:600;margin:8px 0}}.ts{{font-family:monospace;color:#3b6fd8;margin-right:6px}}
.pts img{{display:block;max-width:520px;width:100%;border-radius:8px;margin:6px 0 10px}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}}
figure{{margin:0}}figure img{{width:100%;border-radius:8px}}figcaption{{font-size:13px;color:var(--mute)}}.mm,.mm ul{{list-style:none;padding-left:18px;border-left:2px solid var(--line)}}
</style></head><body><main><h1>AI 第二大脑 · 学习笔记</h1><p style="color:var(--mute)">{len(items)} 份资料 · 更新 {today()}</p>{''.join(cards)}</main></body></html>"""
    (out / "index.html").write_text(page)
    print(json.dumps({"site": str(out / "index.html"), "notes": len(items)}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(prog="brain", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", help="brain folder (default $AI_BRAIN_DIR or ~/LLM/AI第二大脑)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("init").set_defaults(f=cmd_init)
    v = sp.add_parser("video"); v.add_argument("url"); v.add_argument("--start"); v.add_argument("--end"); v.add_argument("--queue", action="store_true"); v.set_defaults(f=cmd_video)
    s = sp.add_parser("sheets"); s.add_argument("inbox_dir"); s.set_defaults(f=cmd_sheets)
    i = sp.add_parser("ingest"); i.add_argument("note"); i.set_defaults(f=cmd_ingest)
    sp.add_parser("site").set_defaults(f=cmd_site)
    q = sp.add_parser("search"); q.add_argument("words", nargs="+"); q.set_defaults(f=cmd_search)
    w = sp.add_parser("where"); w.add_argument("slug"); w.set_defaults(f=cmd_where)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
