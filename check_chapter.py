#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单章结构自查工具（供写作时用，不影响 pytest）。

用法：python3 check_chapter.py content/chapters/xxx.html [more.html ...]
全部通过输出 ok 并退出码 0，否则列出问题退出码 1。
"""
import json
import re
import sys

META_RE = re.compile(r"<!--\s*chapter-meta\s*(.*?)\s*chapter-meta\s*-->", re.S)
SECTION_IDS = ["scene", "framework", "desk", "interview", "drill"]


def section(body, sid):
    m = re.search(r'<h2 id="%s"[^>]*>.*?</h2>(.*?)(?=<h2|\Z)' % sid, body, re.S)
    return m.group(1) if m else None


def strip_tags(text):
    return re.sub(r"<[^>]+>", " ", text)


def check(path):
    problems = []
    text = open(path, encoding="utf-8").read()
    m = META_RE.search(text)
    if not m:
        return ["缺少 chapter-meta 块"]
    try:
        meta = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        return ["meta JSON 解析失败: %s" % e]
    body = META_RE.sub("", text).strip()

    if meta.get("status") != "done":
        problems.append("status 应为 done")
    if len(meta.get("summary", "")) > 90:
        problems.append("summary 超 90 字（当前 %d）" % len(meta.get("summary", "")))
    if not meta.get("keywords"):
        problems.append("keywords 为空")

    pos = [body.find('<h2 id="%s"' % sid) for sid in SECTION_IDS]
    missing = [sid for sid, p in zip(SECTION_IDS, pos) if p == -1]
    if missing:
        problems.append("缺少小节：%s" % missing)
    elif pos != sorted(pos):
        problems.append("小节顺序错：必须是 scene→framework→desk→interview→drill")

    if "被否决选项的胜场" not in body:
        problems.append("缺 h3：被否决选项的胜场")
    desk = section(body, "desk")
    if not desk or 'class="desk"' not in desk:
        problems.append("回到工位缺少 <div class=\"desk\"> 可执行动作")
    scene = section(body, "scene")
    if scene is not None and len(strip_tags(scene)) > 700:
        problems.append("工作场景超 700 字符（当前 %d）" % len(strip_tags(scene)))

    interview = section(body, "interview") or ""
    for needle in ("60 秒示范", "翻车回答", "AI 破绽"):
        if needle not in interview:
            problems.append("面试小节缺：%s" % needle)
    if len(set(re.findall(r"\d+", strip_tags(interview)))) < 2:
        problems.append("面试小节数字不足 2 个")

    drill = section(body, "drill") or ""
    blocks = re.findall(r"<details.*?</details>", drill, re.S)
    if len(blocks) < 3:
        problems.append("追问链不足 3 问（当前 %d）" % len(blocks))
    for i, b in enumerate(blocks, 1):
        if "考察意图" not in b:
            problems.append("追问%d 缺考察意图" % i)
        if "过关" not in b:
            problems.append("追问%d 缺过关标准" % i)

    if "<script" in body:
        problems.append("正文不允许 <script>")
    for tag in ("div", "details", "table", "ul", "ol", "pre", "blockquote", "summary", "h3"):
        if body.count("<" + tag) != body.count("</" + tag + ">"):
            problems.append("<%s> 标签不配对" % tag)
    for block in re.findall(r'<pre class="mermaid">.*?</pre>', body, re.S):
        if not re.search(r"flowchart|graph |sequenceDiagram", block):
            problems.append("mermaid 缺图类型声明")
    return problems


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    failed = False
    for path in sys.argv[1:]:
        problems = check(path)
        if problems:
            failed = True
            print("FAIL %s" % path)
            for p in problems:
                print("  - %s" % p)
        else:
            print("ok   %s" % path)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
