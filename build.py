#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《Java 高级判断力：从能写到敢做决定》静态站点构建脚本。

仅依赖标准库。用法：
    python3 build.py [--out site]

输入：
    content/lines.json          五条主线元信息
    content/chapters/*.html     章节（<!--chapter-meta {...} chapter-meta--> + 正文片段）
    template/                   页面模板与静态资源

输出（默认 site/，可直接托管到 GitHub Pages）：
    index.html / method.html / 404.html / line/<id>.html / ch/<id>.html
    assets/style.css assets/app.js search.json
"""
import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
TEMPLATE = ROOT / "template"

META_RE = re.compile(r"<!--\s*chapter-meta\s*(.*?)\s*chapter-meta\s*-->", re.S)

REQUIRED_FIELDS = [
    "id", "line", "title", "order", "rounds", "signal", "signal_note",
    "company", "trigger", "updated", "status", "summary", "keywords",
]
VALID_ROUNDS = ["一面", "二面", "系统设计面"]
VALID_SIGNAL = ["高", "中"]
VALID_STATUS = ["done", "planned"]
SITE_UPDATED = "2026-11"


def die(msg):
    print("build error: %s" % msg, file=sys.stderr)
    sys.exit(1)


def esc(value):
    return html.escape(str(value), quote=True)


def fill(tpl, mapping):
    out = tpl
    for key, value in mapping.items():
        out = out.replace("{{" + key + "}}", value)
    return out


def parse_chapter(path):
    text = path.read_text(encoding="utf-8")
    match = META_RE.search(text)
    if not match:
        die("%s: 缺少 chapter-meta 块" % path.name)
    try:
        meta = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        die("%s: chapter-meta JSON 解析失败: %s" % (path.name, exc))
    body = META_RE.sub("", text).strip()
    return {"meta": meta, "body": body, "file": path.stem}


def load_chapters():
    files = sorted((CONTENT / "chapters").glob("*.html"))
    if not files:
        die("content/chapters 下没有任何章节文件")
    return [parse_chapter(p) for p in files]


def load_lines():
    lines = json.loads((CONTENT / "lines.json").read_text(encoding="utf-8"))
    for line in lines:
        for key in ("id", "name", "short", "tagline", "accent", "versions"):
            if not line.get(key):
                die("lines.json: 主线缺少字段 %s" % key)
    return lines


def validate(chapters, lines):
    line_ids = {line["id"] for line in lines}
    seen_ids = set()
    for ch in chapters:
        meta, stem = ch["meta"], ch["file"]
        missing = [k for k in REQUIRED_FIELDS
                   if k not in meta or meta[k] in ("", [], None)]
        if missing:
            die("%s: meta 缺少字段 %s" % (stem, missing))
        if meta["id"] != stem:
            die("%s: 文件名与 meta.id (%s) 不一致" % (stem, meta["id"]))
        if meta["id"] in seen_ids:
            die("章节 id 重复: %s" % meta["id"])
        seen_ids.add(meta["id"])
        if meta["line"] not in line_ids:
            die("%s: 未知主线 %s" % (stem, meta["line"]))
        if not set(meta["rounds"]) <= set(VALID_ROUNDS):
            die("%s: rounds 含非法值 %s" % (stem, meta["rounds"]))
        if meta["signal"] not in VALID_SIGNAL:
            die("%s: signal 必须是 高/中" % stem)
        if meta["status"] not in VALID_STATUS:
            die("%s: status 必须是 done/planned" % stem)
        if not re.match(r"^\d{4}-\d{2}$", str(meta["updated"])):
            die("%s: updated 应为 YYYY-MM" % stem)
        if not isinstance(meta["keywords"], list):
            die("%s: keywords 应为数组" % stem)
        if meta["status"] == "done" and not ch["body"].strip():
            die("%s: 已完成章节正文为空" % stem)
    for line in lines:
        orders = [c["meta"]["order"] for c in chapters
                  if c["meta"]["line"] == line["id"]]
        if len(set(orders)) != len(orders):
            die("主线 %s 内 order 冲突" % line["id"])
    return True


def chapters_of(chapters, line_id):
    return sorted(
        [c for c in chapters if c["meta"]["line"] == line_id],
        key=lambda c: c["meta"]["order"],
    )


def chip(text, extra_class=""):
    cls = "chip %s" % extra_class if extra_class else "chip"
    return '<span class="%s">%s</span>' % (cls, esc(text))


def meta_bar(meta, line):
    parts = [chip(line["short"], "chip-line")]
    parts += [chip(r) for r in meta["rounds"]]
    parts.append(chip("面试信号强度 · %s" % meta["signal"], "chip-signal"))
    for c in meta["company"]:
        parts.append(chip(c))
    parts.append(chip("整理于 %s" % meta["updated"]))
    if meta["status"] == "planned":
        parts.append(chip("写作中", "chip-planned"))
    trigger = '<p class="trigger">工作触发：%s</p>' % esc(meta["trigger"])
    note = '<p class="signal-note">信号说明：%s</p>' % esc(meta["signal_note"])
    return '<div class="meta-bar">%s</div>%s%s' % (
        "".join(parts), trigger, note)


def chapter_card(meta):
    if meta["status"] == "done":
        title = '<a class="card-title" href="../ch/%s.html">%s</a>' % (
            esc(meta["id"]), esc(meta["title"]))
        tail = chip(meta["signal"], "chip-signal")
    else:
        title = '<span class="card-title planned">%s</span>' % esc(meta["title"])
        tail = chip("写作中", "chip-planned")
    chips = tail + chip("/".join(meta["rounds"]))
    cls = "card card-planned" if meta["status"] == "planned" else "card"
    return ('<article class="%s"><div class="card-head">%s<div class="card-chips">%s</div></div>'
            '<p class="card-sum">%s</p></article>'
            % (cls, title, chips, esc(meta["summary"])))


def link_chapter(meta):
    href = "ch/%s.html" % esc(meta["id"])
    if meta["status"] == "done":
        return ('<li class="entry-item"><a href="%s">%s</a>'
                '<span class="entry-meta">信号 %s · %s</span></li>'
                % (href, esc(meta["title"]), esc(meta["signal"]),
                   esc("/".join(meta["rounds"]))))
    return ('<li class="entry-item dim"><span class="item-planned">%s</span>'
            '<span class="entry-meta">写作中 · %s</span></li>'
            % (esc(meta["title"]), esc("/".join(meta["rounds"]))))


def build(out_dir):
    chapters = load_chapters()
    lines = load_lines()
    validate(chapters, lines)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "line").mkdir(parents=True)
    (out_dir / "ch").mkdir(parents=True)

    header_raw = (TEMPLATE / "header.html").read_text(encoding="utf-8")
    footer_raw = (TEMPLATE / "footer.html").read_text(encoding="utf-8")

    def partials(prefix):
        return {
            "HEADER": fill(header_raw, {
                "ASSET_PREFIX": prefix, "INDEX_PREFIX": prefix}),
            "FOOTER": fill(footer_raw, {
                "ASSET_PREFIX": prefix, "INDEX_PREFIX": prefix,
                "UPDATED": SITE_UPDATED}),
        }

    done_total = sum(1 for c in chapters if c["meta"]["status"] == "done")

    # ---- 章节页（ch/<id>.html，相对前缀 ../）----
    ch_tpl = (TEMPLATE / "ch.html").read_text(encoding="utf-8")
    base_sub = partials("../")
    for line in lines:
        mine = chapters_of(chapters, line["id"])
        for idx, ch in enumerate(mine):
            meta = ch["meta"]

            def nav(other, label):
                if other is None:
                    return '<span class="pn dim">%s：无</span>' % label
                return '<a class="pn" href="%s.html">%s：%s</a>' % (
                    other["meta"]["id"], label, esc(other["meta"]["title"]))

            prev_c = mine[idx - 1] if idx > 0 else None
            next_c = mine[idx + 1] if idx + 1 < len(mine) else None
            breadcrumb = ('<a href="../index.html">首页</a> › '
                          '<a href="../line/%s.html">%s</a> › 正文'
                          % (esc(line["id"]), esc(line["short"])))
            page = fill(ch_tpl, dict(
                base_sub,
                TITLE=esc(meta["title"]),
                ACCENT=esc(line["accent"]),
                BREADCRUMB=breadcrumb,
                META_BAR=meta_bar(meta, line),
                BODY=ch["body"],
                PREVNEXT='<div class="prevnext">%s%s</div>' % (
                    nav(prev_c, "上一章"), nav(next_c, "下一章")),
            ))
            (out_dir / "ch" / ("%s.html" % meta["id"])).write_text(
                page, encoding="utf-8")

    # ---- 主线页（line/<id>.html）----
    line_tpl = (TEMPLATE / "line.html").read_text(encoding="utf-8")
    for line in lines:
        mine = chapters_of(chapters, line["id"])
        done = sum(1 for c in mine if c["meta"]["status"] == "done")
        cards = "".join(chapter_card(c["meta"]) for c in mine)
        page = fill(line_tpl, dict(
            partials("../"),
            TITLE=esc(line["name"]),
            ACCENT=esc(line["accent"]),
            TAGLINE=esc(line["tagline"]),
            VERSIONS=esc(line["versions"]),
            CARDS=cards,
            COUNT="%d 章已规划 · %d 篇已完成" % (len(mine), done),
        ))
        (out_dir / "line" / ("%s.html" % line["id"])).write_text(
            page, encoding="utf-8")

    # ---- 首页（双入口）----
    index_tpl = (TEMPLATE / "index.html").read_text(encoding="utf-8")
    line_rank = {l["id"]: i for i, l in enumerate(lines)}
    round_blocks = []
    for rnd in VALID_ROUNDS:
        items = [link_chapter(c["meta"]) for c in sorted(
            chapters,
            key=lambda c: (line_rank[c["meta"]["line"]], c["meta"]["order"]))
            if rnd in c["meta"]["rounds"]]
        round_blocks.append(
            '<section class="entry"><h3>%s</h3><ul class="entry-list">%s</ul></section>'
            % (esc(rnd), "".join(items)))
    line_cards = []
    for line in lines:
        mine = chapters_of(chapters, line["id"])
        done = sum(1 for c in mine if c["meta"]["status"] == "done")
        line_cards.append(
            '<a class="line-card" href="line/%s.html" style="--accent:%s">'
            '<div class="lc-name">%s</div><div class="lc-tag">%s</div>'
            '<div class="lc-count">%d / %d 篇完成</div></a>'
            % (esc(line["id"]), esc(line["accent"]), esc(line["name"]),
               esc(line["tagline"]), done, len(mine)))
    page = fill(index_tpl, dict(
        partials(""),
        TITLE="Java 高级判断力：从能写到敢做决定",
        ACCENT="#2f6fed",
        ROUNDS="".join(round_blocks),
        LINES="".join(line_cards),
        TOTAL="%d 篇样板章全文 · %d 章已纳入规划" % (done_total, len(chapters)),
        UPDATED=SITE_UPDATED,
    ))
    (out_dir / "index.html").write_text(page, encoding="utf-8")

    # ---- 方法论页 / 404 ----
    for name, title in (("method.html", "五步判断法"), ("404.html", "页面不存在")):
        tpl = (TEMPLATE / name).read_text(encoding="utf-8")
        (out_dir / name).write_text(
            fill(tpl, dict(partials(""), TITLE=title)), encoding="utf-8")

    # ---- 搜索索引 ----
    line_name = {l["id"]: l["short"] for l in lines}
    index_data = [{
        "id": c["meta"]["id"],
        "title": c["meta"]["title"],
        "summary": c["meta"]["summary"],
        "keywords": c["meta"]["keywords"],
        "lineName": line_name[c["meta"]["line"]],
        "rounds": c["meta"]["rounds"],
        "signal": c["meta"]["signal"],
        "status": c["meta"]["status"],
    } for c in chapters]
    (out_dir / "search.json").write_text(
        json.dumps(index_data, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 静态资源 ----
    shutil.copytree(TEMPLATE / "assets", out_dir / "assets")

    print("build ok: %d 章（%d 篇已完成）, %d 条主线 -> %s"
          % (len(chapters), done_total, len(lines), out_dir))


def main(argv=None):
    parser = argparse.ArgumentParser(description="构建静态站点")
    parser.add_argument("--out", default=str(ROOT / "site"))
    args = parser.parse_args(argv)
    build(Path(args.out).resolve())


if __name__ == "__main__":
    main()
