# -*- coding: utf-8 -*-
"""内容校验测试：章节结构、编辑守则、构建产物与链接完整性。

运行：python3 -m pytest -q
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import build as B  # noqa: E402

CHAPTERS = B.load_chapters()
LINES = B.load_lines()
B.validate(CHAPTERS, LINES)  # 构建级校验不过，测试直接红

DONE = [c for c in CHAPTERS if c["meta"]["status"] == "done"]
PLANNED = [c for c in CHAPTERS if c["meta"]["status"] == "planned"]

SECTION_IDS = ["scene", "framework", "desk", "interview", "drill"]
SECTION_NAMES = ["工作场景", "判断框架", "回到工位", "面试怎么答", "追问链"]

done_ids = [c["meta"]["id"] for c in DONE]
planned_ids = [c["meta"]["id"] for c in PLANNED]


def section(body, sid):
    """截取某个 h2 小节的内容（到下一个 h2 为止）。"""
    m = re.search(r'<h2 id="%s"[^>]*>.*?</h2>(.*?)(?=<h2|\Z)' % sid, body, re.S)
    return m.group(1) if m else None


def strip_tags(text):
    return re.sub(r"<[^>]+>", " ", text)


# ---------- 项目整体形状 ----------

def test_project_shape():
    assert len(LINES) >= 5, "至少五条主线"
    assert len(CHAPTERS) >= 20, "至少规划 20 章"
    assert len(DONE) >= 3, "至少 3 篇全文样板章"
    line_ids = {l["id"] for l in LINES}
    for line in LINES:
        mine = [c for c in CHAPTERS if c["meta"]["line"] == line["id"]]
        assert len(mine) >= 3, "主线 %s 至少 3 章" % line["id"]
    accents = [l["accent"] for l in LINES]
    assert len(set(accents)) == len(accents), "主线强调色不可重复"
    for a in accents:
        assert re.match(r"^#[0-9a-f]{6}$", a), "accent 应为 #rrggbb: %s" % a
    assert line_ids


def test_summary_and_keywords():
    for c in CHAPTERS:
        assert len(c["meta"]["summary"]) <= 90, "%s 摘要超长" % c["meta"]["id"]
        assert c["meta"]["keywords"], "%s 缺关键词" % c["meta"]["id"]


# ---------- 已完成章节：结构与编辑守则 ----------

@pytest.mark.parametrize("ch", DONE, ids=done_ids)
def test_done_section_order(ch):
    body = ch["body"]
    pos = [body.find('<h2 id="%s"' % sid) for sid in SECTION_IDS]
    assert -1 not in pos, "缺少小节：%s" % [n for i, n in zip(pos, SECTION_NAMES) if i == -1]
    assert pos == sorted(pos), "小节顺序必须是：场景→框架→回到工位→面试→追问"
    for name in SECTION_NAMES:
        assert name in body, "缺少小节标题：%s" % name


@pytest.mark.parametrize("ch", DONE, ids=done_ids)
def test_done_editorial_rules(ch):
    body = ch["body"]
    assert "被否决选项的胜场" in body, "编辑守则：被否决的选项必须写清它赢的场景"
    interview = section(body, "interview")
    assert interview, "缺面试小节"
    assert "60 秒示范" in interview, "面试小节必须有 60 秒示范"
    assert "翻车回答" in interview, "面试小节必须有翻车回答"
    assert "AI 破绽" in interview, "面试小节必须有 AI 破绽自查"
    desk = section(body, "desk")
    assert desk and 'class="desk"' in desk, "回到工位必须是可执行动作（desk 框）"


@pytest.mark.parametrize("ch", DONE, ids=done_ids)
def test_done_scenario_bounded(ch):
    scene = section(ch["body"], "scene")
    assert scene, "缺工作场景小节"
    assert len(strip_tags(scene)) <= 700, "工作场景要短（≤700 字符，正文压缩在 200 字内）"


@pytest.mark.parametrize("ch", DONE, ids=done_ids)
def test_done_interview_has_numbers(ch):
    interview = strip_tags(section(ch["body"], "interview"))
    nums = set(re.findall(r"\d+", interview))
    assert len(nums) >= 2, "好答案必须带具体数字（当前只有 %s）" % sorted(nums)


@pytest.mark.parametrize("ch", DONE, ids=done_ids)
def test_done_drill_chain(ch):
    drill = section(ch["body"], "drill")
    assert drill, "缺追问链小节"
    details = re.findall(r"<details", drill)
    assert len(details) >= 3, "追问链至少 3 问"
    for block in re.findall(r"<details.*?</details>", drill, re.S):
        assert "考察意图" in block, "每个追问必须写考察意图"
        assert "过关" in block, "每个追问必须写过关标准"


# ---------- 规划章节 ----------

@pytest.mark.parametrize("ch", PLANNED, ids=planned_ids)
def test_planned_shape(ch):
    body = ch["body"]
    assert "写作中" in body
    assert "这一章要解决的生产问题" in body
    assert body.count("<li") >= 3, "规划章至少给出 3 个判断点"


# ---------- 通用 HTML 卫生 ----------

@pytest.mark.parametrize("ch", CHAPTERS, ids=done_ids + planned_ids)
def test_html_hygiene(ch):
    body = ch["body"]
    assert "<script" not in body, "章节正文不允许脚本"
    for tag in ("div", "details", "table", "ul", "ol", "pre", "blockquote", "summary"):
        assert body.count("<" + tag) == body.count("</" + tag + ">"), \
            "<%s> 标签不配对：%s" % (tag, ch["meta"]["id"])
    for block in re.findall(r'<pre class="mermaid">.*?</pre>', body, re.S):
        assert re.search(r"flowchart|graph |sequenceDiagram", block), "mermaid 图缺少图类型声明"


# ---------- 构建产物与链接完整性 ----------

def test_build_and_links(tmp_path):
    out = tmp_path / "site"
    B.main(["--out", str(out)])

    assert len(list((out / "ch").glob("*.html"))) == len(CHAPTERS)
    for line in LINES:
        assert (out / "line" / (line["id"] + ".html")).exists()
    for name in ("index.html", "method.html", "404.html", "search.json",
                 "assets/style.css", "assets/app.js"):
        assert (out / Path(name)).exists(), "缺产物 %s" % name

    index_html = (out / "index.html").read_text(encoding="utf-8")
    for c in DONE:
        assert c["meta"]["title"] in index_html, "首页缺已完成章节：%s" % c["meta"]["id"]
    assert "入口 A" in index_html and "入口 B" in index_html, "双入口缺失"

    data = json.loads((out / "search.json").read_text(encoding="utf-8"))
    assert {d["id"] for d in data} == {c["meta"]["id"] for c in CHAPTERS}
    for d in data:
        assert d["title"] and d["lineName"] and d["rounds"]

    broken = []
    for html_file in out.rglob("*.html"):
        text = html_file.read_text(encoding="utf-8")
        for attr in re.findall(r'(?:href|src)="([^"]+)"', text):
            if attr.startswith(("http", "mailto:", "data:", "//")):
                continue
            target = attr.split("#")[0]
            if not target:
                continue
            if not (html_file.parent / target).resolve().exists():
                broken.append("%s -> %s" % (html_file.name, attr))
    assert not broken, "存在断链：%s" % broken


def test_prevnext_navigation(tmp_path):
    out = tmp_path / "site"
    B.main(["--out", str(out)])
    for line in LINES:
        mine = B.chapters_of(CHAPTERS, line["id"])
        for i, ch in enumerate(mine):
            page = (out / "ch" / (ch["meta"]["id"] + ".html")).read_text(encoding="utf-8")
            assert ("上一章" in page) and ("下一章" in page)
            if i > 0:
                assert mine[i - 1]["meta"]["id"] + ".html" in page
            if i + 1 < len(mine):
                assert mine[i + 1]["meta"]["id"] + ".html" in page
