"""Parse in-corpus article citations in 資通安全管理法 and its subsidiary regulations.

Official article text is never rewritten here. This module only finds spans that
confidently point at an article in the nine-law set and records spans we
recognized but did not link (relative references, other statutes, missing targets).
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Longest-first so「本法施行細則」wins over「本法」and「資通安全管理法」wins over「本法」.
KNOWN_LAWS: Tuple[Tuple[str, str], ...] = (
    ("資通安全事件通報應變及演練辦法", "A0030305"),
    ("資通安全維護計畫實施情形稽核辦法", "A0030306"),
    ("公務機關所屬人員辦理資通安全事項作業辦法", "A0030308"),
    ("危害國家資通安全產品審查辦法", "K0060168"),
    ("資通安全責任等級分級辦法", "A0030304"),
    ("國家資通安全會報設置辦法", "A0010127"),
    ("資通安全管理法施行細則", "A0030303"),
    ("資通安全情資分享辦法", "A0030307"),
    ("資通安全管理法", "A0030297"),
    ("本法施行細則", "A0030303"),
    ("本細則", "SELF"),
    ("本辦法", "SELF"),
    ("本法", "PARENT"),
)

PARENT_PCODE = "A0030297"

NUM = r"(?:[0-9]+|[零〇○一二三四五六七八九十百]+)"
ART_RE = re.compile(
    rf"第\s*(?P<num>{NUM})\s*條(?:\s*之\s*(?P<branch>{NUM}))?"
    rf"(?:\s*第\s*(?P<para>{NUM})\s*項)?"
    rf"(?:\s*第\s*(?P<item>{NUM})\s*款)?"
    rf"(?:\s*第\s*(?P<mu>{NUM})\s*目)?"
    rf"(?P<cont>(?:"
    rf"\s*[、與及]\s*第\s*{NUM}\s*項(?:\s*第\s*{NUM}\s*款)?"
    rf"|\s*[、與及]\s*第\s*{NUM}\s*款"
    rf"|\s*至\s*第\s*{NUM}\s*[款項]"
    rf")*)"
)
RELATIVE_RE = re.compile(
    rf"(?:前|同|本|該)(?:{NUM})?(?:條|項|款|目)"
)
PARA_ONLY_RE = re.compile(rf"第\s*{NUM}\s*(?:項|款|目)")
ALIAS_PAREN_RE = re.compile(r"[（(]以下簡稱[^）)]{1,20}[）)]\s*$")
EXTERNAL_LAW_RE = re.compile(
    r"[\u4e00-\u9fff]{1,40}(?:法|條例|通則|規程|規則|細則|辦法|綱要|標準|準則)$"
)
CONNECTOR_RE = re.compile(r"\s*(?:[、及或與]|至)\s*\Z", re.S)

CN_DIGIT = {
    "零": 0,
    "〇": 0,
    "○": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def cn_to_int(raw: str) -> Optional[int]:
    s = (raw or "").strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if any(ch not in CN_DIGIT and ch not in "十百" for ch in s):
        return None
    if "百" in s:
        left, right = s.split("百", 1)
        if left and left not in CN_DIGIT:
            return None
        hundreds = CN_DIGIT[left] if left else 1
        if not right:
            return hundreds * 100
        if right[0] in "零〇○":
            right = right[1:]
            if len(right) == 1 and right in CN_DIGIT:
                return hundreds * 100 + CN_DIGIT[right]
            return None
        rest = cn_to_int(right)
        if rest is None:
            return None
        return hundreds * 100 + rest
    if "十" in s:
        left, right = s.split("十", 1)
        if left and left not in CN_DIGIT:
            return None
        if right and right not in CN_DIGIT:
            return None
        tens = CN_DIGIT[left] if left else 1
        ones = CN_DIGIT[right] if right else 0
        return tens * 10 + ones
    if len(s) == 1 and s in CN_DIGIT:
        return CN_DIGIT[s]
    return None


def article_id(number: int, branch: Optional[int] = None) -> str:
    if branch:
        return f"{number}-{branch}"
    return str(number)


def _resolve_alias(token: str, current_pcode: str) -> Optional[str]:
    if token == "SELF":
        return current_pcode
    if token == "PARENT":
        return PARENT_PCODE if current_pcode != PARENT_PCODE else current_pcode
    return token


def _law_before(text: str, pos: int, current_pcode: str) -> Optional[str]:
    """Return a pcode, 'EXTERNAL', or None when the article ref is bare."""
    window = text[max(0, pos - 80) : pos].rstrip()
    window = ALIAS_PAREN_RE.sub("", window).rstrip()
    for name, token in KNOWN_LAWS:
        if window.endswith(name):
            return _resolve_alias(token, current_pcode)
    if EXTERNAL_LAW_RE.search(window):
        return "EXTERNAL"
    return None


def _overlaps(spans: Sequence[Tuple[int, int]], start: int, end: int) -> bool:
    return any(start < e and end > s for s, e in spans)


def parse_citations(
    content: str,
    current_pcode: str,
    existing: Dict[str, Iterable[str]],
) -> Tuple[List[dict], List[dict]]:
    """Return (resolved citations, unresolved references) for one article."""
    index = {pcode: set(ids) for pcode, ids in existing.items()}
    citations: List[dict] = []
    unresolved: List[dict] = []
    consumed: List[Tuple[int, int]] = []
    carry: Optional[str] = None
    prev_end = 0

    for match in ART_RE.finditer(content):
        start, end = match.start(), match.end()
        number = cn_to_int(match.group("num"))
        branch = cn_to_int(match.group("branch")) if match.group("branch") else None
        paragraph = cn_to_int(match.group("para")) if match.group("para") else None
        if number is None:
            continue
        target_id = article_id(number, branch)
        explicit = _law_before(content, start, current_pcode)
        gap = content[prev_end:start] if citations or unresolved else content[prev_end:start]
        # Carry only across a pure connector (、及或與至) since the previous ref.
        connected = bool(CONNECTOR_RE.fullmatch(gap)) and carry is not None and prev_end > 0
        if explicit == "EXTERNAL":
            law = "EXTERNAL"
        elif explicit:
            law = explicit
        elif connected:
            law = carry
        else:
            law = current_pcode

        text = content[start:end]
        if law == "EXTERNAL" or law not in index or target_id not in index.get(law, ()):
            kind = "external" if law == "EXTERNAL" else "missing"
            unresolved.append(
                {
                    "kind": kind,
                    "start": start,
                    "end": end,
                    "text": text,
                }
            )
            # Keep an external chain external so the next「或第○條」is not
            # treated as a same-law citation.
            carry = "EXTERNAL" if law == "EXTERNAL" else None
        else:
            citations.append(
                {
                    "start": start,
                    "end": end,
                    "text": text,
                    "targetPcode": law,
                    "targetArticle": target_id,
                    "paragraph": paragraph,
                    "sameLaw": law == current_pcode,
                }
            )
            carry = law
        consumed.append((start, end))
        prev_end = end

    for regex, kind in ((RELATIVE_RE, "relative"), (PARA_ONLY_RE, "paragraph")):
        for match in regex.finditer(content):
            if _overlaps(consumed, match.start(), match.end()):
                continue
            unresolved.append(
                {
                    "kind": kind,
                    "start": match.start(),
                    "end": match.end(),
                    "text": match.group(0),
                }
            )
            consumed.append((match.start(), match.end()))

    citations.sort(key=lambda item: item["start"])
    unresolved.sort(key=lambda item: item["start"])
    return citations, unresolved
