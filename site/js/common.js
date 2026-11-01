const CN = { "零": 0, "〇": 0, "○": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9 };

export function cnToInt(raw) {
  const s = String(raw || "").trim();
  if (!s) return null;
  if (/^\d+$/.test(s)) return Number(s);
  if ([...s].some((ch) => !(ch in CN) && ch !== "十" && ch !== "百")) return null;
  if (s.includes("百")) {
    const [left, right] = s.split("百");
    const hundreds = left ? CN[left] : 1;
    if (!right) return hundreds * 100;
    if (right[0] === "零" || right[0] === "〇" || right[0] === "○") {
      return hundreds * 100 + (CN[right.slice(1)] ?? NaN);
    }
    return hundreds * 100 + cnToInt(right);
  }
  if (s.includes("十")) {
    const [left, right] = s.split("十");
    const tens = left ? CN[left] : 1;
    const ones = right ? CN[right] : 0;
    return tens * 10 + ones;
  }
  return s.length === 1 ? CN[s] : null;
}

let cache;
export function loadData() {
  if (!cache) {
    cache = fetch("data/laws.json").then((res) => {
      if (!res.ok) throw new Error("無法載入法規資料");
      return res.json();
    });
  }
  return cache;
}

export function rocFromIsoDate(iso) {
  const day = String(iso || "").slice(0, 10);
  const [y, m, d] = day.split("-");
  if (!y) return "";
  return `${Number(y) - 1911}-${m}-${d}`;
}

export function dateLabel(law) {
  if (!law.modifiedRoc) return "";
  return `民國 ${law.modifiedRoc} ${law.dateAction || ""}`.trim();
}

export function byPcode(data, pcode) {
  return data.laws.find((law) => law.pcode === pcode) || null;
}

export function findArticle(law, id) {
  if (!law) return null;
  return law.articles.find((article) => article.id === id) || null;
}

export function articleHref(pcode, id, paragraph) {
  const params = new URLSearchParams();
  params.set("pcode", pcode);
  params.set("a", id);
  const hash = paragraph ? `#p-${paragraph}` : "";
  return `law.html?${params.toString()}${hash}`;
}

export function kindLabel(kind) {
  return kind === "parent" ? "母法" : "子法";
}

export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

export function parseArticleQuery(query) {
  const match = String(query || "")
    .trim()
    .match(/^第?\s*([0-9]+|[零〇○一二三四五六七八九十百]+)\s*條(?:\s*第?\s*([0-9]+|[零〇○一二三四五六七八九十百]+)\s*項)?$/);
  if (!match) return null;
  const number = cnToInt(match[1]);
  if (!number) return null;
  const paragraph = match[2] ? cnToInt(match[2]) : null;
  return { number, paragraph };
}

function flexSource(term) {
  return [...term]
    .map((ch) => ch.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("\\s*");
}

export function termPattern(terms) {
  const usable = terms.filter(Boolean);
  if (!usable.length) return null;
  return new RegExp(usable.map(flexSource).join("|"), "g");
}

export function textHasTerms(text, terms) {
  return terms.every((term) => new RegExp(flexSource(term)).test(text));
}

export function appendHighlighted(parent, text, terms) {
  const pattern = termPattern(terms);
  if (!pattern || !text) {
    if (text) parent.append(text);
    return;
  }
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > last) parent.append(text.slice(last, match.index));
    const mark = document.createElement("mark");
    mark.textContent = match[0];
    parent.append(mark);
    last = match.index + match[0].length;
  }
  if (last < text.length) parent.append(text.slice(last));
}

export function snippet(text, terms) {
  const clean = text.replace(/\s+/g, " ").trim();
  if (!terms.length) return clean.slice(0, 90);
  const pattern = new RegExp(flexSource(terms[0]));
  const match = pattern.exec(clean);
  if (!match) return clean.slice(0, 90);
  const start = Math.max(0, match.index - 28);
  const end = Math.min(clean.length, match.index + match[0].length + 56);
  const slice = clean.slice(start, end);
  return `${start ? "…" : ""}${slice}${end < clean.length ? "…" : ""}`;
}

let pop;
let pinned = false;
let hideTimer = 0;
let dataRef = null;

function previewText(law, article, paragraph) {
  if (paragraph) {
    const block = article.paragraphs.find((item) => item.n === Number(paragraph));
    if (block) {
      const parts = [block.lead];
      for (const item of block.items) {
        if (item.text) parts.push(item.text);
        for (const sub of item.subs || []) parts.push(sub.text);
      }
      const joined = parts.filter(Boolean).join("\n");
      if (joined) return clip(joined);
    }
  }
  return clip(article.content);
}

function clip(text) {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > 180 ? `${flat.slice(0, 180)}…` : flat;
}

function fillPopover(anchor) {
  if (!dataRef) return;
  const pcode = anchor.dataset.pcode;
  const articleId = anchor.dataset.article;
  const paragraph = anchor.dataset.paragraph || "";
  const law = byPcode(dataRef, pcode);
  const article = findArticle(law, articleId);
  if (!law || !article) return;
  const same = anchor.classList.contains("cite-same");
  pop.querySelector(".popover-kicker").textContent = same ? "引用預覽・同一部法規" : "引用預覽・跨法規";
  const title = pop.querySelector(".popover-title");
  title.textContent = "";
  title.append(`${law.name} ${article.no} `);
  const badge = el("span", law.kind === "parent" ? "badge badge-parent" : "badge badge-sub", kindLabel(law.kind));
  title.append(badge);
  pop.querySelector(".popover-body").textContent = previewText(law, article, paragraph);
  pop.querySelector(".popover-date").textContent = `現行版本 ${dateLabel(law)}`;
  const go = pop.querySelector(".popover-go");
  go.href = anchor.getAttribute("href");
}

function anchorRect(anchor, event) {
  const rects = [...anchor.getClientRects()];
  if (!rects.length) return anchor.getBoundingClientRect();
  if (event && Number.isFinite(event.clientX)) {
    const hit = rects.find((rect) => (
      event.clientX >= rect.left - 4
      && event.clientX <= rect.right + 4
      && event.clientY >= rect.top - 4
      && event.clientY <= rect.bottom + 4
    ));
    if (hit) return hit;
  }
  return rects[0];
}

function place(anchor, event) {
  const rect = anchorRect(anchor, event);
  pop.hidden = false;
  const width = pop.offsetWidth;
  const height = pop.offsetHeight;
  let left = rect.left;
  let top = rect.bottom + 8;
  if (left + width > window.innerWidth - 8) left = window.innerWidth - width - 8;
  if (top + height > window.innerHeight - 8) top = Math.max(8, rect.top - height - 8);
  if (left < 8) left = 8;
  pop.style.left = `${left}px`;
  pop.style.top = `${top}px`;
}

function hide() {
  pinned = false;
  if (pop) pop.hidden = true;
}

function scheduleHide() {
  clearTimeout(hideTimer);
  hideTimer = window.setTimeout(() => {
    if (!pinned) hide();
  }, 220);
}

export function bindPopover(data) {
  dataRef = data;
  pop = document.getElementById("cite-popover");
  if (!pop || pop.dataset.bound) return;
  pop.dataset.bound = "1";
  document.addEventListener("mouseover", (event) => {
    const anchor = event.target.closest?.("a.cite");
    if (!anchor || pinned) return;
    clearTimeout(hideTimer);
    fillPopover(anchor);
    place(anchor, event);
  });
  document.addEventListener("mouseout", (event) => {
    const anchor = event.target.closest?.("a.cite");
    if (!anchor || pinned) return;
    if (event.relatedTarget && anchor.contains(event.relatedTarget)) return;
    scheduleHide();
  });
  document.addEventListener("focusin", (event) => {
    const anchor = event.target.closest?.("a.cite");
    if (!anchor || pinned) return;
    fillPopover(anchor);
    place(anchor, event);
  });
  document.addEventListener("click", (event) => {
    const anchor = event.target.closest?.("a.cite");
    if (anchor) {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
      if (event.detail === 0) return;
      event.preventDefault();
      pinned = true;
      clearTimeout(hideTimer);
      fillPopover(anchor);
      place(anchor, event);
      return;
    }
    if (pinned && pop && !pop.contains(event.target)) hide();
  });
  pop.addEventListener("mouseenter", () => clearTimeout(hideTimer));
  pop.addEventListener("mouseleave", () => {
    if (!pinned) scheduleHide();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") hide();
  });
  window.addEventListener("scroll", () => {
    if (pinned) hide();
  }, true);
  window.addEventListener("resize", () => {
    if (!pop.hidden) hide();
  });
}

export function appendRich(parent, text, citations, terms) {
  const cites = (citations || []).slice().sort((a, b) => a.start - b.start);
  let cursor = 0;
  const paint = (node, slice) => appendHighlighted(node, slice, terms);
  for (const cite of cites) {
    if (cite.start < cursor || cite.end > text.length) continue;
    if (cite.start > cursor) paint(parent, text.slice(cursor, cite.start));
    const anchor = document.createElement("a");
    anchor.className = `cite ${cite.sameLaw ? "cite-same" : "cite-cross"}`;
    anchor.href = articleHref(cite.targetPcode, cite.targetArticle, cite.paragraph);
    anchor.dataset.pcode = cite.targetPcode;
    anchor.dataset.article = cite.targetArticle;
    if (cite.paragraph) anchor.dataset.paragraph = String(cite.paragraph);
    anchor.setAttribute("aria-haspopup", "dialog");
    paint(anchor, text.slice(cite.start, cite.end));
    parent.append(anchor);
    cursor = cite.end;
  }
  if (cursor < text.length) paint(parent, text.slice(cursor));
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.left = "-9999px";
    document.body.append(area);
    area.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch {
      ok = false;
    }
    area.remove();
    return ok;
  }
}
