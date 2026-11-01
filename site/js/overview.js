import { articleHref, dateLabel, el, kindLabel, loadData, rocFromIsoDate } from "./common.js";

function authorityLine(law) {
  const node = el("p");
  node.append("授權依據：");
  if (!law.authority.length) {
    node.append("—");
    return node;
  }
  law.authority.forEach((item, index) => {
    if (index) node.append("、");
    const link = el("a", null, item.label);
    link.href = articleHref(item.pcode, item.article, item.paragraph);
    node.append(link);
  });
  return node;
}

loadData()
  .then((data) => {
    const root = document.querySelector("#overview-root");
    const fetched = rocFromIsoDate(data.fetchedAt);
    document.querySelector("#consulted").textContent =
      `清單依全國法規資料庫開放資料（更新：${data.source.lawUpdateDate}；本站擷取日：${fetched}）。授權依據取自各子法第 1 條引用的母法條文。`;

    const parent = data.laws.find((law) => law.kind === "parent");
    const banner = el("section", "parent-banner");
    const info = el("div");
    info.append(el("span", "badge badge-parent", "母法"));
    info.append(el("h2", null, parent.name));
    const meta = el("p", "meta");
    const bits = [dateLabel(parent), `${parent.articles.length} 條`, `PCode ${parent.pcode}`];
    if (parent.competentAuthority) bits.splice(1, 0, `主管機關：${parent.competentAuthority}`);
    meta.textContent = bits.join("　");
    info.append(meta);
    const actions = el("div", "actions");
    const open = el("a", "btn btn-primary", "條文查詢");
    open.href = articleHref(parent.pcode, "1");
    const history = el("a", "btn btn-ghost", "條文沿革");
    history.href = `${articleHref(parent.pcode, "1")}#history`;
    actions.append(open, history);
    banner.append(info, actions);
    root.append(banner);

    const grid = el("div", "card-grid");
    for (const law of data.laws.filter((item) => item.kind === "sub")) {
      const card = el("article", "card subcard");
      card.append(el("span", "badge badge-sub", kindLabel(law.kind)));
      card.append(el("h3", null, law.name));
      card.append(authorityLine(law));
      card.append(el("p", null, `${dateLabel(law)}　${law.articles.length} 條`));
      card.append(el("p", null, `PCode ${law.pcode}`));
      const actions = el("div", "actions");
      const link = el("a", "btn btn-primary btn-sm", "條文查詢");
      link.href = articleHref(law.pcode, "1");
      actions.append(link);
      card.append(actions);
      grid.append(card);
    }
    root.append(grid);

    const tableCard = el("div", "table-wrap");
    tableCard.style.marginTop = "18px";
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const hr = document.createElement("tr");
    ["#", "類型", "法規名稱", "授權依據（母法條文）", "最新修正／發布", "PCode"].forEach((label, index) => {
      hr.append(el("th", index === 0 ? "num" : null, label));
    });
    thead.append(hr);
    const tbody = document.createElement("tbody");
    data.laws.forEach((law, index) => {
      const tr = document.createElement("tr");
      tr.append(el("td", "num", String(index + 1)));
      const kind = el("td");
      kind.append(el("span", law.kind === "parent" ? "badge badge-parent" : "badge badge-sub", kindLabel(law.kind)));
      tr.append(kind);
      const name = el("td");
      const link = el("a", "name-link", law.name);
      link.href = articleHref(law.pcode, "1");
      name.append(link);
      tr.append(name);
      const auth = el("td");
      if (!law.authority.length) auth.textContent = "—";
      else {
        law.authority.forEach((item, itemIndex) => {
          if (itemIndex) auth.append("、");
          const a = el("a", null, item.label);
          a.href = articleHref(item.pcode, item.article, item.paragraph);
          const piece = el("span", "nowrap");
          piece.append(a);
          auth.append(piece);
        });
      }
      tr.append(auth);
      tr.append(el("td", "nowrap", dateLabel(law)));
      const code = el("td", "nowrap");
      code.append(el("code", "pcode", law.pcode));
      tr.append(code);
      tbody.append(tr);
    });
    table.append(thead, tbody);
    tableCard.append(table);
    root.append(el("h2", null, "九部法規一覽"));
    root.append(tableCard);
    const note = el("p", "callout", "各部會依母法授權訂定的作業辦法尚未收錄。本版僅含母法與 8 部子法。");
    root.append(note);
  })
  .catch(() => {
    document.querySelector("#overview-root").textContent = "法規資料載入失敗。請重新整理頁面。";
  });
