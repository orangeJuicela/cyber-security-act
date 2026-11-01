import {
  appendRich,
  articleHref,
  bindPopover,
  byPcode,
  copyText,
  dateLabel,
  el,
  findArticle,
  kindLabel,
  loadData,
  parseArticleQuery,
  snippet,
  termPattern,
  textHasTerms,
} from "./common.js";

const app = document.querySelector("#app");

function readState() {
  const params = new URLSearchParams(location.search);
  const scope = params.get("scope");
  return {
    pcode: params.get("pcode") || "",
    article: params.get("a") || "",
    q: (params.get("q") || "").trim(),
    scope: scope === "parent" || scope === "sub" ? scope : "all",
  };
}

function scopedLaws(data, scope) {
  if (scope === "parent") return data.laws.filter((law) => law.kind === "parent");
  if (scope === "sub") return data.laws.filter((law) => law.kind === "sub");
  return data.laws;
}

function termsOf(query) {
  return query.split(/\s+/).filter(Boolean);
}

function search(data, state) {
  const laws = scopedLaws(data, state.scope);
  const parsed = parseArticleQuery(state.q);
  const hits = [];
  if (parsed) {
    for (const law of laws) {
      const article = law.articles.find((item) => item.number === parsed.number && !item.branch);
      if (article) hits.push({ law, article, paragraph: parsed.paragraph });
    }
    return hits;
  }
  const terms = termsOf(state.q);
  for (const law of laws) {
    for (const article of law.articles) {
      if (textHasTerms(article.content, terms)) hits.push({ law, article, paragraph: null });
    }
  }
  return hits;
}

function scopeHref(scope, state) {
  const params = new URLSearchParams();
  if (state.pcode) params.set("pcode", state.pcode);
  if (state.article) params.set("a", state.article);
  if (state.q) params.set("q", state.q);
  if (scope !== "all") params.set("scope", scope);
  const qs = params.toString();
  return qs ? `law.html?${qs}` : "law.html";
}

function renderChrome(data, state) {
  const tools = el("div", "law-tools");
  const form = document.createElement("form");
  form.className = "tool-row";
  form.action = "law.html";
  form.method = "get";
  form.setAttribute("role", "search");

  const select = document.createElement("select");
  select.name = "pcode";
  select.setAttribute("aria-label", "法規切換");
  for (const law of data.laws) {
    const option = document.createElement("option");
    option.value = law.pcode;
    option.textContent = law.kind === "parent" ? `${law.name}（母法）` : law.name;
    if (law.pcode === state.pcode) option.selected = true;
    select.append(option);
  }
  select.addEventListener("change", () => {
    location.href = articleHref(select.value, "1");
  });

  const input = document.createElement("input");
  input.type = "search";
  input.name = "q";
  input.value = state.q;
  input.placeholder = "輸入關鍵字或條號，例如「通報 應變」「第17條」";
  input.setAttribute("aria-label", "搜尋條文");

  if (state.scope !== "all") {
    const hidden = document.createElement("input");
    hidden.type = "hidden";
    hidden.name = "scope";
    hidden.value = state.scope;
    form.append(hidden);
  }
  const submit = el("button", "btn btn-primary", "搜尋");
  submit.type = "submit";
  form.append(select, input, submit);

  const scope = el("div", "scope");
  scope.setAttribute("role", "group");
  scope.setAttribute("aria-label", "搜尋範圍");
  for (const [value, label] of [
    ["all", "全部法規"],
    ["parent", "只搜母法"],
    ["sub", "只搜子法"],
  ]) {
    const link = el("a", value === state.scope ? "is-active" : null, label);
    link.href = scopeHref(value, state);
    if (value === state.scope) link.setAttribute("aria-current", "true");
    scope.append(link);
  }
  tools.append(form, scope);

  const tabs = el("nav", "law-tabs");
  tabs.setAttribute("aria-label", "法規");
  for (const law of data.laws) {
    const link = el("a", law.pcode === state.pcode ? "is-active" : null, law.shortName === "母法" ? "資通安全管理法（母法）" : law.shortName);
    link.href = articleHref(law.pcode, "1");
    if (law.pcode === state.pcode) link.setAttribute("aria-current", "page");
    tabs.append(link);
  }
  tools.append(tabs);
  return tools;
}

function hintOf(article) {
  const lead = article.paragraphs[0]?.lead || article.content;
  const flat = lead.replace(/\s+/g, "");
  return flat.length > 18 ? `${flat.slice(0, 18)}…` : flat;
}

function renderChapters(law, articleId, termsQuery) {
  const aside = el("aside", "panel chapters");
  aside.append(el("h2", null, "章節"));
  for (const chapter of law.chapters) {
    const block = el("div", "chapter-block");
    if (chapter.title !== "全文") block.append(el("h3", null, chapter.title));
    for (const id of chapter.articleIds) {
      const article = findArticle(law, id);
      if (!article) continue;
      const link = document.createElement("a");
      const params = new URLSearchParams(location.search);
      params.set("pcode", law.pcode);
      params.set("a", id);
      params.delete("view");
      const qs = params.toString();
      link.href = `law.html?${qs}`;
      if (id === articleId) {
        link.className = "is-active";
        link.setAttribute("aria-current", "page");
      }
      link.append(article.no);
      const small = el("small", null, hintOf(article));
      link.append(small);
      if (termsQuery && textHasTerms(article.content, termsOf(termsQuery))) {
        small.append(" · 含關鍵字");
      }
      block.append(link);
    }
    aside.append(block);
  }
  return aside;
}

function renderParagraph(paragraph, terms) {
  const section = el("section", "para");
  section.id = `p-${paragraph.n}`;
  section.append(el("h3", "para-label", `第 ${paragraph.n} 項`));
  if (paragraph.lead) {
    const p = el("p", "para-text");
    appendRich(p, paragraph.lead, paragraph.citations, terms);
    section.append(p);
  }
  if (paragraph.items.length) {
    const list = el("ul", "kuan-list");
    for (const item of paragraph.items) {
      const li = document.createElement("li");
      if (item.text) appendRich(li, item.text, item.citations, terms);
      if (item.subs?.length) {
        const subs = el("ul", "mu-list");
        for (const sub of item.subs) {
          const subLi = document.createElement("li");
          appendRich(subLi, sub.text, sub.citations, terms);
          subs.append(subLi);
        }
        li.append(subs);
      }
      list.append(li);
    }
    section.append(list);
  }
  return section;
}

function whereLine(mentions) {
  const nums = [...new Set(mentions.map((item) => item.sourceParagraph).filter(Boolean))];
  if (!nums.length) return "";
  return `出現在${nums.map((n) => `第 ${n} 項`).join("、")}`;
}

function renderRefs(article, data) {
  const aside = el("aside", "panel refs");
  aside.append(el("h2", null, "引用關係"));

  const outgoing = el("div", "ref-block");
  outgoing.append(el("h3", null, `本條引用　${article.outgoing.length} 筆`));
  if (!article.outgoing.length) outgoing.append(el("p", "ref-empty", "本條沒有解析到可連結的條文引用。"));
  for (const group of article.outgoing) {
    const law = byPcode(data, group.pcode);
    const card = document.createElement("a");
    card.className = "ref-card";
    const paragraph = singleParagraph(group.mentions);
    card.href = articleHref(group.pcode, group.article, paragraph);
    const badge = el("span", law.kind === "parent" ? "badge badge-parent" : "badge badge-sub", kindLabel(law.kind));
    card.append(badge);
    const target = findArticle(law, group.article);
    card.append(el("strong", null, `${law.name} ${target ? target.no : ""}`));
    const bits = [group.mentions.map((item) => item.text).join("、")];
    const where = whereLine(group.mentions);
    if (where) bits.push(where);
    card.append(el("span", null, bits.join(" · ")));
    outgoing.append(card);
  }
  aside.append(outgoing);

  const incoming = el("div", "ref-block");
  incoming.append(el("h3", null, `被引用於　${article.incoming.length} 筆`));
  if (!article.incoming.length) incoming.append(el("p", "ref-empty", "其他八部法規的條文沒有引用本條。"));
  for (const row of article.incoming) {
    const law = byPcode(data, row.pcode);
    const card = document.createElement("a");
    card.className = "ref-card";
    card.href = articleHref(row.pcode, row.article);
    if (row.authorizing) card.append(el("span", "badge badge-auth", "授權依據"));
    card.append(el("span", law.kind === "parent" ? "badge badge-parent" : "badge badge-sub", kindLabel(law.kind)));
    const source = findArticle(law, row.article);
    card.append(el("strong", null, `${law.name} ${source ? source.no : ""}`));
    card.append(el("span", null, row.mentions.map((item) => item.text).join("、")));
    incoming.append(card);
  }
  aside.append(incoming);

  const legend = el("p", "legend");
  legend.append("線上顏色：");
  legend.append(el("i", "swatch-same", "同法引用"));
  legend.append("、");
  legend.append(el("i", "swatch-cross", "跨法引用"));
  legend.append("。前條、前項、同條與九法以外的法規維持純文字。");
  aside.append(legend);
  return aside;
}

function singleParagraph(mentions) {
  const values = [...new Set(mentions.map((item) => item.targetParagraph).filter(Boolean))];
  return values.length === 1 ? values[0] : null;
}

function renderArticle(data, law, article, state) {
  const main = el("article", "panel article");
  const terms = state.q && !parseArticleQuery(state.q) ? termsOf(state.q) : [];
  if (state.q) {
    const banner = el("div", "search-banner");
    const back = document.createElement("a");
    const params = new URLSearchParams();
    params.set("q", state.q);
    if (state.scope !== "all") params.set("scope", state.scope);
    back.href = `law.html?${params.toString()}`;
    back.textContent = "返回搜尋結果";
    banner.append(`關鍵字「${state.q}」。`);
    banner.append(document.createTextNode(" "));
    banner.append(back);
    main.append(banner);
  }

  const kicker = el("div", "article-kicker");
  kicker.append(el("span", law.kind === "parent" ? "badge badge-parent" : "badge badge-sub", kindLabel(law.kind)));
  kicker.append(el("span", "chip", dateLabel(law)));
  if (article.chapter) kicker.append(el("span", "chip", article.chapter));
  kicker.append(el("span", "chip", law.pcode));
  main.append(kicker);
  main.append(el("h1", null, `${law.name}　${article.no}`));

  const tools = el("div", "article-tools");
  const source = el("a", null, "全國法規資料庫原文");
  source.href = law.sourceUrl;
  source.target = "_blank";
  source.rel = "noopener noreferrer";
  const copy = el("button", "btn btn-ghost btn-sm", "複製條文");
  copy.type = "button";
  copy.addEventListener("click", async () => {
    const ok = await copyText(article.content);
    copy.textContent = ok ? "已複製" : "複製失敗";
    window.setTimeout(() => {
      copy.textContent = "複製條文";
    }, 1600);
  });
  tools.append(source, copy);
  main.append(tools);

  const origin = el("section", "origin-block");
  const head = el("div", "origin-head");
  head.append(el("h2", null, "法條原文"));
  origin.append(head);
  for (const paragraph of article.paragraphs) origin.append(renderParagraph(paragraph, terms));
  main.append(origin);

  if (law.attachments.length && article.id === "1") {
    const box = el("div", "callout");
    box.append("本法規另有附表，請見全國法規資料庫：");
    const list = el("ul", "attach-list");
    for (const file of law.attachments) {
      const li = document.createElement("li");
      const a = el("a", null, file.fileName);
      a.href = file.fileUrl;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      li.append(a);
      list.append(li);
    }
    box.append(list);
    main.append(box);
  }

  const plain = el("section", "plain");
  const header = document.createElement("header");
  header.append(el("h2", null, "白話解說"));
  header.append(el("span", null, "本站整理，僅供學習參考"));
  plain.append(header, el("p", "plain-status", "白話解說撰寫中"));
  main.append(plain);

  const index = law.articles.findIndex((item) => item.id === article.id);
  const pager = el("nav", "pager");
  pager.setAttribute("aria-label", "上一條與下一條");
  const prev = law.articles[index - 1];
  const next = law.articles[index + 1];
  if (prev) {
    const link = el("a", null, `〈 ${prev.no}`);
    link.href = keepQuery(articleHref(law.pcode, prev.id), state);
    pager.append(link);
  } else pager.append(el("span"));
  if (next) {
    const link = el("a", null, `${next.no} 〉`);
    link.href = keepQuery(articleHref(law.pcode, next.id), state);
    pager.append(link);
  }
  main.append(pager);

  const history = el("details", "history");
  history.id = "history";
  if (location.hash === "#history") history.open = true;
  history.append(el("summary", null, "沿革"));
  history.append(el("pre", null, law.histories || "（來源未提供沿革）"));
  if (law.effectiveRoc) history.append(el("p", null, `施行日期：${law.effectiveRoc}`));
  if (law.effectiveNote) history.append(el("p", null, law.effectiveNote));
  main.append(history);
  return main;
}

function keepQuery(href, state) {
  if (!state.q) return href;
  const url = new URL(href, location.href);
  url.searchParams.set("q", state.q);
  if (state.scope !== "all") url.searchParams.set("scope", state.scope);
  return `law.html${url.search}${url.hash}`;
}

function renderResults(data, state, hits) {
  const main = el("section", "panel article");
  main.append(el("h1", null, "搜尋結果"));
  const scopeName = state.scope === "parent" ? "只搜母法" : state.scope === "sub" ? "只搜子法" : "全部法規";
  main.append(el("p", null, `「${state.q}」・${scopeName}・${hits.length} 筆`));
  if (!hits.length) {
    main.append(el("p", "ref-empty", "找不到符合的條文。可以改搜全部法規，或換一個關鍵字。"));
    return main;
  }
  const list = el("ul", "results");
  const shown = hits.slice(0, 80);
  const terms = parseArticleQuery(state.q) ? [] : termsOf(state.q);
  for (const hit of shown) {
    const li = document.createElement("li");
    const link = document.createElement("a");
    const params = new URLSearchParams();
    params.set("pcode", hit.law.pcode);
    params.set("a", hit.article.id);
    params.set("q", state.q);
    if (state.scope !== "all") params.set("scope", state.scope);
    const hash = hit.paragraph ? `#p-${hit.paragraph}` : "";
    link.href = `law.html?${params.toString()}${hash}`;
    const meta = el("div", "hit-meta");
    meta.append(el("span", hit.law.kind === "parent" ? "badge badge-parent" : "badge badge-sub", kindLabel(hit.law.kind)));
    meta.append(` ${hit.law.name}`);
    link.append(meta);
    link.append(el("strong", null, hit.article.no));
    const text = el("p");
    const piece = snippet(hit.article.content, terms.length ? terms : [hit.article.no]);
    appendRich(text, piece, [], terms);
    link.append(text);
    li.append(link);
    list.append(li);
  }
  main.append(list);
  if (hits.length > shown.length) main.append(el("p", null, `另有 ${hits.length - shown.length} 筆未顯示。請縮小關鍵字。`));
  return main;
}

function render(data) {
  const state = readState();
  if (!state.pcode) state.pcode = data.laws[0].pcode;
  const law = byPcode(data, state.pcode) || data.laws[0];
  state.pcode = law.pcode;
  const showResults = Boolean(state.q) && !state.article;
  app.textContent = "";
  const crumb = el("p", "crumb");
  crumb.append(linkNode("index.html", "首頁"), " / ", linkNode("law.html", "條文查詢"));
  app.append(crumb, renderChrome(data, state));

  const layout = el("div", "law-layout");
  let article = findArticle(law, state.article);
  if (!showResults && !article) {
    article = law.articles[0];
    state.article = article.id;
  }
  layout.append(renderChapters(law, showResults ? "" : state.article, state.q));
  if (showResults) {
    const hits = search(data, state);
    layout.append(renderResults(data, state, hits));
    const placeholder = el("aside", "panel refs");
    placeholder.append(el("h2", null, "引用關係"));
    placeholder.append(el("p", "ref-empty", "打開一條條文後，這裡會列出它引用的條文，以及其他條文引用它的地方。"));
    layout.append(placeholder);
    document.title = `搜尋「${state.q}」｜資安法白話通`;
  } else {
    layout.append(renderArticle(data, law, article, state));
    layout.append(renderRefs(article, data));
    document.title = `${article.no}｜${law.name}｜資安法白話通`;
  }
  app.append(layout);
  const current = document.querySelector(".chapter-block a.is-active");
  if (current) {
    const scroller = current.closest(".chapters");
    if (scroller) {
      const delta = current.getBoundingClientRect().top - scroller.getBoundingClientRect().top;
      scroller.scrollTop += delta - 36;
    }
  }
  const hash = location.hash.replace("#", "");
  if (hash) {
    const target = document.getElementById(hash);
    if (target) {
      target.classList.add("is-target");
      target.scrollIntoView({ block: "center" });
    }
  }
  if (state.q && !showResults && termPattern(termsOf(state.q))) {
    /* highlights are applied while rendering */
  }
}

function linkNode(href, text) {
  const a = el("a", null, text);
  a.href = href;
  return a;
}

loadData()
  .then((data) => {
    bindPopover(data);
    render(data);
    window.addEventListener("popstate", () => render(data));
  })
  .catch(() => {
    app.textContent = "";
    app.append(el("p", "error", "法規資料載入失敗。請重新整理頁面。"));
  });
