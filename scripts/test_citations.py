#!/usr/bin/env python3
"""Checks the committed statute snapshot and citation graph. No network."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from citations import cn_to_int, parse_citations  # noqa: E402

DATA = ROOT / "site" / "data" / "laws.json"

EXPECTED = {
    "A0030297": ("資通安全管理法", "parent", "114-09-24", "修正", 35, []),
    "A0030303": ("資通安全管理法施行細則", "sub", "115-01-05", "修正", 15, ["第 34 條"]),
    "A0030304": ("資通安全責任等級分級辦法", "sub", "115-01-07", "修正", 12, ["第 7 條第 3 項"]),
    "A0030305": ("資通安全事件通報應變及演練辦法", "sub", "115-01-05", "修正", 20, ["第 10 條第 4 項", "第 17 條第 4 項", "第 24 條第 4 項"]),
    "A0030306": ("資通安全維護計畫實施情形稽核辦法", "sub", "115-01-05", "修正", 14, ["第 8 條第 4 項", "第 16 條第 3 項"]),
    "A0030307": ("資通安全情資分享辦法", "sub", "115-01-05", "修正", 13, ["第 9 條第 2 項"]),
    "A0030308": ("公務機關所屬人員辦理資通安全事項作業辦法", "sub", "115-01-13", "修正", 24, ["第 18 條第 3 項", "第 19 條第 6 項", "第 28 條第 2 項"]),
    "K0060168": ("危害國家資通安全產品審查辦法", "sub", "114-12-19", "發布", 11, ["第 11 條第 3 項"]),
    "A0010127": ("國家資通安全會報設置辦法", "sub", "115-03-02", "發布", 11, ["第 5 條第 4 項"]),
}


def fail(message: str) -> None:
    print("FAIL:", message)
    raise SystemExit(1)


def walk_pieces(article: dict):
    for para in article["paragraphs"]:
        yield para["lead"], para["citations"], para["n"]
        for item in para["items"]:
            yield item["text"], item["citations"], para["n"]
            for sub in item.get("subs") or []:
                yield sub["text"], sub["citations"], para["n"]


def rebuild(article: dict) -> str:
    parts = []
    for para in article["paragraphs"]:
        if para["lead"]:
            parts.append(para["lead"])
        for item in para["items"]:
            if item["text"]:
                parts.append(item["text"])
            for sub in item.get("subs") or []:
                parts.append(sub["text"])
    return "\n".join(parts)


def targets(article: dict):
    return [(group["pcode"], group["article"]) for group in article["outgoing"]]


def main() -> int:
    assert cn_to_int("十七") == 17
    assert cn_to_int("三十四") == 34
    assert cn_to_int("十") == 10
    assert cn_to_int("二十一") == 21
    assert cn_to_int("17") == 17

    sample_index = {code: {str(n) for n in range(1, 41)} for code in EXPECTED}
    text = "各機關依資通安全責任等級分級辦法第四條第一款至第五款或第五條第一款至第五款涉及之業務"
    cites, unresolved = parse_citations(text, "A0030303", sample_index)
    got = [(c["targetPcode"], c["targetArticle"], c["text"]) for c in cites]
    if got != [
        ("A0030304", "4", "第四條第一款至第五款"),
        ("A0030304", "5", "第五條第一款至第五款"),
    ]:
        fail(f"carry/range parse unexpected: {got}")
    if any(item["kind"] == "missing" for item in unresolved):
        fail(f"range parse marked missing: {unresolved}")

    external = "符合財團法人法第二條第二項、第三項或第六十三條規定"
    cites, unresolved = parse_citations(external, "A0030297", sample_index)
    if cites:
        fail(f"external statute was linked: {cites}")
    if not any(item["kind"] == "external" for item in unresolved):
        fail("external statute was not recorded as unresolved")

    relative = "應向前項受通報機關提出。前三項通報由主管機關定之。"
    cites, unresolved = parse_citations(relative, "A0030297", sample_index)
    if cites:
        fail(f"relative reference was linked: {cites}")
    kinds = {item["text"] for item in unresolved}
    if "前項" not in kinds or "前三項" not in kinds:
        fail(f"relative references missing: {unresolved}")

    data = json.loads(DATA.read_text(encoding="utf-8"))
    laws = data["laws"]
    if [law["pcode"] for law in laws] != list(EXPECTED):
        fail("law order or PCode set changed")

    by_code = {law["pcode"]: law for law in laws}
    for code, (name, kind, roc, action, count, authority) in EXPECTED.items():
        law = by_code[code]
        if law["name"] != name or law["kind"] != kind:
            fail(f"{code} name/kind {law['name']} {law['kind']}")
        if law["modifiedRoc"] != roc or law["dateAction"] != action:
            fail(f"{code} date {law['modifiedRoc']} {law['dateAction']}")
        if len(law["articles"]) != count:
            fail(f"{code} article count {len(law['articles'])}")
        labels = [item["label"] for item in law["authority"]]
        if labels != authority:
            fail(f"{code} authority {labels}")
        if "pcode=" + code not in law["sourceUrl"]:
            fail(f"{code} source url {law['sourceUrl']}")
        for article in law["articles"]:
            if rebuild(article) != article["content"]:
                fail(f"{code} {article['id']} did not round-trip")
            mention_count = 0
            for group in article["outgoing"]:
                mention_count += len(group["mentions"])
                if group["sameLaw"] != (group["pcode"] == code):
                    fail(f"sameLaw flag wrong {code} {article['id']}")
            span_count = 0
            for piece, citations, _para in walk_pieces(article):
                for cite in citations:
                    span_count += 1
                    if piece[cite["start"] : cite["end"]] != cite["text"]:
                        fail(f"span mismatch {code} {article['id']} {cite}")
            if span_count != mention_count:
                fail(f"span/outgoing mismatch {code} {article['id']} {span_count} {mention_count}")

    parent = by_code["A0030297"]
    art17 = next(article for article in parent["articles"] if article["id"] == "17")
    if "應向第十四條規定收受其實施情形之機關" not in art17["content"]:
        fail("parent article 17 text missing")
    if ("A0030297", "14") not in targets(art17):
        fail("parent art 17 should cite art 14")
    incoming = {(row["pcode"], row["article"]) for row in art17["incoming"]}
    if ("A0030305", "1") not in incoming:
        fail("通報應變辦法第1條 should cite 母法第17條")
    notice = by_code["A0030305"]
    notice1 = next(article for article in notice["articles"] if article["id"] == "1")
    if "第十條第四項、第十七條第四項及第二十四條第四項" not in notice1["content"]:
        fail("notice art 1 official text missing")
    notice_targets = targets(notice1)
    for article_id in ("10", "17", "24"):
        if ("A0030297", article_id) not in notice_targets:
            fail(f"notice art 1 missing parent art {article_id}")

    rules = by_code["A0030303"]
    art10 = next(article for article in rules["articles"] if article["id"] == "10")
    if ("A0030304", "4") not in targets(art10) or ("A0030304", "5") not in targets(art10):
        fail("施行細則 art 10 should cite the grading regulation")
    art13 = next(article for article in rules["articles"] if article["id"] == "13")
    if ("A0030305", "2") not in targets(art13):
        fail("施行細則 art 13 should cite 通報辦法第2條")

    art3 = next(article for article in parent["articles"] if article["id"] == "3")
    if targets(art3):
        fail(f"parent art 3 should not link external statutes: {targets(art3)}")
    if not art3["content"].startswith("本法用詞，定義如下："):
        fail("parent art 3 text changed")

    if parent["competentAuthority"] != "數位發展部":
        fail(f"competent authority {parent['competentAuthority']}")

    stats = data["stats"]
    if stats["resolved"] != 109 or stats["unresolved"] != 172:
        fail(f"citation stats drifted: {stats}")
    if stats["unresolvedByKind"].get("external") != 7:
        fail(f"external count drifted: {stats['unresolvedByKind']}")

    # UI constraints: no right-aligned table text, no analytics, placeholder explanation only.
    css = (ROOT / "site" / "css" / "style.css").read_text(encoding="utf-8")
    if "text-align: right" in css or "text-align:right" in css:
        fail("stylesheet right-aligns text")
    law_js = (ROOT / "site" / "js" / "law.js").read_text(encoding="utf-8")
    if "白話解說撰寫中" not in law_js:
        fail("plain-language placeholder missing")
    blob = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "site").rglob("*") if path.suffix in {".html", ".js", ".css"})
    for banned in ("gtag", "google-analytics", "googletagmanager", "plausible"):
        if banned in blob:
            fail(f"tracking snippet found: {banned}")
    for page in ("index.html", "overview.html", "law.html", "about.html"):
        html = (ROOT / "site" / page).read_text(encoding="utf-8")
        if "不構成法律意見" not in html:
            fail(f"{page} missing disclaimer")

    print(
        f"ok laws=9 resolved={stats['resolved']} unresolved={stats['unresolved']} "
        f"kinds={stats['unresolvedByKind']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
