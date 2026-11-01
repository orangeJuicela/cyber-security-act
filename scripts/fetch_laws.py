#!/usr/bin/env python3
"""Download 資通安全管理法 and eight subsidiary regulations from 全國法規資料庫.

Source (official open data, ZIP of JSON):
  https://law.moj.gov.tw/api/ch/law/json
  https://law.moj.gov.tw/api/ch/order/json

Each statute's human-readable page is LawAll.aspx?pcode=<PCode>.
The script writes site/data/laws.json and site/data/citation-stats.json.
It refuses to invent text: if a PCode is missing, it exits without replacing
the previous JSON.
"""

from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from citations import (  # noqa: E402
    PARENT_PCODE,
    article_id,
    cn_to_int,
    parse_citations,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "site" / "data" / "laws.json"
STATS_PATH = ROOT / "site" / "data" / "citation-stats.json"

LAW_API = "https://law.moj.gov.tw/api/ch/law/json"
ORDER_API = "https://law.moj.gov.tw/api/ch/order/json"
USER_AGENT = (
    "cyber-security-act-fetch/1.0 "
    "(educational; +https://github.com/orangeJuicela/cyber-security-act)"
)

# Stable display order. shortName is a UI label, not a substitute for LawName.
CATALOG: Tuple[Tuple[str, str, str], ...] = (
    ("A0030297", "parent", "母法"),
    ("A0030303", "sub", "施行細則"),
    ("A0030304", "sub", "責任等級"),
    ("A0030305", "sub", "通報應變"),
    ("A0030306", "sub", "稽核"),
    ("A0030307", "sub", "情資分享"),
    ("A0030308", "sub", "所屬人員"),
    ("K0060168", "sub", "產品審查"),
    ("A0010127", "sub", "會報設置"),
)

KUAN_RE = re.compile(r"^[一二三四五六七八九十百零]+、")
MU_RE = re.compile(r"^（[一二三四五六七八九十百零]+）")
HEADING_RE = re.compile(r"(第[一二三四五六七八九十百]+[編章節])(.*)")


def download(url: str, timeout: int = 180) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/zip, application/json"})
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    if data[:2] != b"PK":
        raise RuntimeError(f"{url} did not return a ZIP (starts with {data[:4]!r})")
    return data


def load_laws(zip_bytes: bytes) -> Tuple[str, List[dict]]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".json")]
        if len(names) != 1:
            raise RuntimeError(f"expected one JSON in zip, got {names}")
        payload = json.loads(zf.read(names[0]).decode("utf-8-sig"))
    return payload.get("UpdateDate") or "", payload.get("Laws") or []


def pcode_of(law: dict) -> Optional[str]:
    url = law.get("LawURL") or ""
    match = re.search(r"pcode=([A-Za-z0-9]+)", url)
    return match.group(1) if match else None


def roc_date(yyyymmdd: str) -> str:
    if not yyyymmdd or len(yyyymmdd) < 8 or not yyyymmdd[:8].isdigit():
        return ""
    year = int(yyyymmdd[:4]) - 1911
    return f"{year}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def date_action(histories: str) -> str:
    text = (histories or "").replace("\r\n", "\n").replace("\r", "\n")
    parts = re.split(r"\n(?=\d+\.)", text.strip())
    last = parts[-1] if parts else text
    head = last.split("公告")[0]
    return "修正" if "修正" in head else "發布"


def normalize_newlines(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n")


def normalize_heading(raw: str) -> str:
    compact = re.sub(r"\s+", "", raw or "")
    match = HEADING_RE.match(compact)
    if not match:
        return compact
    rest = match.group(2)
    return f"{match.group(1)} {rest}" if rest else match.group(1)


def parse_article_no(raw: str) -> Tuple[str, int, Optional[int]]:
    text = re.sub(r"\s+", "", raw or "")
    match = re.match(r"第([0-9一二三四五六七八九十百]+)條(?:之([0-9一二三四五六七八九十]+))?$", text)
    if not match:
        raise ValueError(f"unrecognized article number: {raw!r}")
    number = cn_to_int(match.group(1))
    branch = cn_to_int(match.group(2)) if match.group(2) else None
    if number is None:
        raise ValueError(f"unrecognized article number: {raw!r}")
    return article_id(number, branch), number, branch


def split_structure(content: str) -> List[dict]:
    """Group official lines into 項, with 款 and 目 nested underneath.

    Line text is copied verbatim. Reconstruction joins pieces with newlines.
    """
    paragraphs: List[dict] = []
    current: Optional[dict] = None
    pos = 0
    lines = content.split("\n") if content else []
    for index, line in enumerate(lines):
        start = pos
        end = pos + len(line)
        stripped = line.strip()
        if MU_RE.match(stripped):
            if current is None:
                current = {"n": 1, "lead": "", "leadStart": start, "items": []}
                paragraphs.append(current)
            sub = {"text": line, "start": start, "end": end, "citations": []}
            if current["items"]:
                current["items"][-1].setdefault("subs", []).append(sub)
            else:
                current["items"].append({"text": "", "start": start, "end": start, "citations": [], "subs": [sub]})
        elif KUAN_RE.match(stripped):
            if current is None:
                current = {"n": len(paragraphs) + 1, "lead": "", "leadStart": start, "items": []}
                paragraphs.append(current)
            current["items"].append({"text": line, "start": start, "end": end, "citations": [], "subs": []})
        else:
            current = {
                "n": len(paragraphs) + 1,
                "lead": line,
                "leadStart": start,
                "leadEnd": end,
                "citations": [],
                "items": [],
            }
            paragraphs.append(current)
        pos = end + (1 if index < len(lines) - 1 else 0)
    return paragraphs


def reconstruct(paragraphs: List[dict]) -> str:
    parts: List[str] = []
    for para in paragraphs:
        if para.get("lead"):
            parts.append(para["lead"])
        for item in para["items"]:
            if item.get("text"):
                parts.append(item["text"])
            for sub in item.get("subs") or []:
                parts.append(sub["text"])
    return "\n".join(parts)


def paragraph_at(paragraphs: List[dict], offset: int) -> Optional[int]:
    for para in paragraphs:
        if para.get("lead") and para["leadStart"] <= offset < para.get("leadEnd", para["leadStart"]):
            return para["n"]
        for item in para["items"]:
            if item.get("text") and item["start"] <= offset < item["end"]:
                return para["n"]
            for sub in item.get("subs") or []:
                if sub["start"] <= offset < sub["end"]:
                    return para["n"]
    if paragraphs:
        return paragraphs[-1]["n"]
    return None


def attach_citations(paragraphs: List[dict], citations: List[dict]) -> None:
    pieces: List[Tuple[int, int, dict]] = []
    for para in paragraphs:
        if para.get("lead"):
            pieces.append((para["leadStart"], para["leadEnd"], para))
        for item in para["items"]:
            if item.get("text"):
                pieces.append((item["start"], item["end"], item))
            for sub in item.get("subs") or []:
                pieces.append((sub["start"], sub["end"], sub))
    for cite in citations:
        host = None
        for start, end, obj in pieces:
            if start <= cite["start"] < end:
                host = (start, end, obj)
                break
        if host is None:
            raise RuntimeError(f"citation offset {cite['start']} not in any line: {cite['text']}")
        start, end, obj = host
        if cite["end"] > end:
            raise RuntimeError(f"citation crosses a line break: {cite['text']}")
        rel = dict(cite)
        rel["start"] = cite["start"] - start
        rel["end"] = cite["end"] - start
        obj.setdefault("citations", []).append(rel)


def authority_from(citations: List[dict]) -> List[dict]:
    seen = set()
    rows = []
    for cite in citations:
        if cite["targetPcode"] != PARENT_PCODE:
            continue
        key = (cite["targetArticle"], cite.get("paragraph"))
        if key in seen:
            continue
        seen.add(key)
        label = f"第 {cite['targetArticle'].split('-')[0]} 條"
        if "-" in cite["targetArticle"]:
            label += f"之 {cite['targetArticle'].split('-')[1]}"
        if cite.get("paragraph"):
            label += f"第 {cite['paragraph']} 項"
        rows.append(
            {
                "pcode": cite["targetPcode"],
                "article": cite["targetArticle"],
                "paragraph": cite.get("paragraph"),
                "label": label,
            }
        )
    return rows


def group_outgoing(citations: List[dict]) -> List[dict]:
    grouped: List[dict] = []
    index: Dict[Tuple[str, str], dict] = {}
    for cite in citations:
        key = (cite["targetPcode"], cite["targetArticle"])
        row = index.get(key)
        if row is None:
            row = {
                "pcode": cite["targetPcode"],
                "article": cite["targetArticle"],
                "sameLaw": cite["sameLaw"],
                "mentions": [],
            }
            index[key] = row
            grouped.append(row)
        row["mentions"].append(
            {
                "text": cite["text"],
                "sourceParagraph": cite.get("sourceParagraph"),
                "targetParagraph": cite.get("paragraph"),
            }
        )
    return grouped


def build_law(raw: dict, kind: str, short_name: str, existing: Dict[str, set]) -> dict:
    pcode = pcode_of(raw)
    if not pcode:
        raise RuntimeError(f"missing pcode for {raw.get('LawName')}")
    chapters: List[dict] = []
    articles: List[dict] = []
    heading: List[str] = []
    unresolved_all: List[dict] = []

    for node in raw.get("LawArticles") or []:
        atype = node.get("ArticleType") or ""
        if atype == "C":
            title = normalize_heading(node.get("ArticleContent") or "")
            if not title:
                continue
            if "章" in title or "編" in title:
                heading = [title]
            elif "節" in title:
                heading = [heading[0], title] if heading else [title]
            else:
                heading = (heading + [title])[-3:]
            if not chapters or chapters[-1]["title"] != " / ".join(heading):
                chapters.append({"title": " / ".join(heading), "articleIds": []})
            continue
        if atype != "A":
            continue
        art_id, number, branch = parse_article_no(node.get("ArticleNo") or "")
        content = normalize_newlines(node.get("ArticleContent") or "")
        paragraphs = split_structure(content)
        rebuilt = reconstruct(paragraphs)
        if rebuilt != content:
            raise RuntimeError(f"{pcode} {art_id} structure did not round-trip")
        citations, unresolved = parse_citations(content, pcode, existing)
        for cite in citations:
            cite["sourceParagraph"] = paragraph_at(paragraphs, cite["start"])
        attach_citations(paragraphs, citations)
        chapter_title = " / ".join(heading) if heading else ""
        if not chapters:
            chapters.append({"title": "全文", "articleIds": []})
        chapters[-1]["articleIds"].append(art_id)
        articles.append(
            {
                "id": art_id,
                "no": re.sub(r"\s+", " ", (node.get("ArticleNo") or "").strip()),
                "number": number,
                "branch": branch,
                "chapter": chapter_title,
                "content": content,
                "paragraphs": _public_paragraphs(paragraphs),
                "outgoing": group_outgoing(citations),
            }
        )
        for item in unresolved:
            unresolved_all.append({"article": art_id, **item})

    authority = []
    if kind == "sub" and articles:
        # Article 1 states the authorizing parent-law provisions.
        first = next((a for a in articles if a["id"] == "1"), articles[0])
        flat = []
        for group in first["outgoing"]:
            if group["pcode"] != PARENT_PCODE:
                continue
            for mention in group["mentions"]:
                flat.append(
                    {
                        "targetPcode": group["pcode"],
                        "targetArticle": group["article"],
                        "paragraph": mention.get("targetParagraph"),
                        "text": mention["text"],
                    }
                )
        authority = authority_from(flat)

    histories = normalize_newlines(raw.get("LawHistories") or "")
    modified = raw.get("LawModifiedDate") or ""
    competent = None
    if pcode == PARENT_PCODE:
        art2 = next((a for a in articles if a["id"] == "2"), None)
        if art2:
            found = re.search(r"主管機關為([^。\n]+)", art2["content"])
            if found:
                competent = found.group(1).strip()

    return {
        "pcode": pcode,
        "name": raw.get("LawName") or "",
        "shortName": short_name,
        "kind": kind,
        "level": raw.get("LawLevel") or "",
        "category": raw.get("LawCategory") or "",
        "sourceUrl": raw.get("LawURL") or f"https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode={pcode}",
        "modifiedDate": modified,
        "modifiedRoc": roc_date(modified),
        "dateAction": date_action(histories),
        "effectiveDate": raw.get("LawEffectiveDate") or "",
        "effectiveRoc": roc_date(raw.get("LawEffectiveDate") or ""),
        "effectiveNote": normalize_newlines(raw.get("LawEffectiveNote") or ""),
        "competentAuthority": competent,
        "histories": histories,
        "attachments": [
            {"fileName": item.get("FileName") or "", "fileUrl": item.get("FileURL") or ""}
            for item in (raw.get("LawAttachements") or raw.get("LawAttachments") or [])
            if item.get("FileURL")
        ],
        "authority": authority,
        "chapters": chapters,
        "articles": articles,
        "_unresolved": unresolved_all,
    }


def _public_paragraphs(paragraphs: List[dict]) -> List[dict]:
    public = []
    for para in paragraphs:
        public.append(
            {
                "n": para["n"],
                "lead": para.get("lead") or "",
                "citations": para.get("citations") or [],
                "items": [
                    {
                        "text": item.get("text") or "",
                        "citations": item.get("citations") or [],
                        "subs": [
                            {
                                "text": sub["text"],
                                "citations": sub.get("citations") or [],
                            }
                            for sub in (item.get("subs") or [])
                        ],
                    }
                    for item in para["items"]
                ],
            }
        )
    return public


def add_incoming(laws: List[dict]) -> None:
    buckets: Dict[Tuple[str, str], List[dict]] = {}
    order = {law["pcode"]: index for index, law in enumerate(laws)}
    for law in laws:
        for article in law["articles"]:
            for group in article["outgoing"]:
                key = (group["pcode"], group["article"])
                buckets.setdefault(key, []).append(
                    {
                        "pcode": law["pcode"],
                        "article": article["id"],
                        "sameLaw": group["sameLaw"],
                        "mentions": group["mentions"],
                        "authorizing": law["kind"] == "sub"
                        and article["id"] == "1"
                        and group["pcode"] == PARENT_PCODE,
                    }
                )
    for law in laws:
        for article in law["articles"]:
            rows = buckets.get((law["pcode"], article["id"]), [])
            rows.sort(key=lambda row: (order.get(row["pcode"], 99), _art_sort(row["article"])))
            article["incoming"] = rows


def _art_sort(art_id: str) -> Tuple[int, int]:
    if "-" in art_id:
        left, right = art_id.split("-", 1)
        return int(left), int(right)
    return int(art_id), 0


def collect_stats(laws: List[dict]) -> dict:
    resolved = 0
    unresolved = 0
    by_kind: Dict[str, int] = {}
    samples: List[dict] = []
    for law in laws:
        for article in law["articles"]:
            for group in article["outgoing"]:
                resolved += len(group["mentions"])
        for item in law["_unresolved"]:
            unresolved += 1
            by_kind[item["kind"]] = by_kind.get(item["kind"], 0) + 1
            if len(samples) < 80:
                samples.append(
                    {
                        "pcode": law["pcode"],
                        "law": law["name"],
                        "article": item["article"],
                        "kind": item["kind"],
                        "text": item["text"],
                    }
                )
    return {
        "resolved": resolved,
        "unresolved": unresolved,
        "unresolvedByKind": by_kind,
        "samples": samples,
    }


def main() -> int:
    print("downloading", LAW_API)
    law_zip = download(LAW_API)
    print("downloading", ORDER_API)
    order_zip = download(ORDER_API)
    law_updated, law_rows = load_laws(law_zip)
    order_updated, order_rows = load_laws(order_zip)
    by_pcode: Dict[str, dict] = {}
    for row in law_rows + order_rows:
        code = pcode_of(row)
        if code:
            by_pcode[code] = row

    missing = [code for code, _, _ in CATALOG if code not in by_pcode]
    if missing:
        print("ERROR: these PCodes were not in the official open data:", ", ".join(missing))
        return 1

    # Existence index is built from official article numbers before citation parsing.
    existing: Dict[str, set] = {}
    for code, _, _ in CATALOG:
        ids = set()
        for node in by_pcode[code].get("LawArticles") or []:
            if (node.get("ArticleType") or "") != "A":
                continue
            art_id, _, _ = parse_article_no(node.get("ArticleNo") or "")
            ids.add(art_id)
        existing[code] = ids

    laws = [build_law(by_pcode[code], kind, short, existing) for code, kind, short in CATALOG]
    add_incoming(laws)
    stats = collect_stats(laws)
    for law in laws:
        law.pop("_unresolved", None)

    now = datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds")
    payload = {
        "fetchedAt": now,
        "source": {
            "lawApi": LAW_API,
            "orderApi": ORDER_API,
            "lawUpdateDate": law_updated,
            "orderUpdateDate": order_updated,
            "pagePattern": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode={pcode}",
        },
        "stats": {
            "resolved": stats["resolved"],
            "unresolved": stats["unresolved"],
            "unresolvedByKind": stats["unresolvedByKind"],
        },
        "laws": laws,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(OUT_PATH)
    STATS_PATH.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {OUT_PATH}")
    print(
        f"citations resolved={stats['resolved']} unresolved={stats['unresolved']} "
        f"byKind={stats['unresolvedByKind']}"
    )
    for law in laws:
        n = len(law["articles"])
        auth = "、".join(item["label"] for item in law["authority"]) or "—"
        print(
            f"  {law['pcode']} {law['name']} articles={n} "
            f"{law['modifiedRoc']} {law['dateAction']} 授權={auth}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
