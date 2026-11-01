import { dateLabel, el, kindLabel, loadData, rocFromIsoDate, articleHref } from "./common.js";

const tbody = document.querySelector("#law-rows");
const consulted = document.querySelector("#consulted");

loadData()
  .then((data) => {
    const fetched = rocFromIsoDate(data.fetchedAt);
    consulted.textContent = `名稱與日期取自全國法規資料庫（開放資料更新：${data.source.lawUpdateDate}；本站擷取日：${fetched}）。`;
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
      if (!law.authority.length) {
        auth.textContent = "—";
      } else {
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
  })
  .catch(() => {
    consulted.textContent = "法規資料載入失敗。請重新整理頁面。";
  });
