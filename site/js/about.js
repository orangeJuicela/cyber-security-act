import { loadData } from "./common.js";

loadData()
  .then((data) => {
    const node = document.querySelector("#cite-stats");
    const kinds = data.stats.unresolvedByKind || {};
    node.textContent =
      `目前已連結的條文引用 ${data.stats.resolved} 處；` +
      `暫不連結 ${data.stats.unresolved} 處` +
      `（相對指稱 ${kinds.relative || 0}、僅標項款 ${kinds.paragraph || 0}、九法以外的法規 ${kinds.external || 0}）。`;
    document.querySelector("#source-updated").textContent = data.source.lawUpdateDate;
  })
  .catch(() => {
    document.querySelector("#cite-stats").textContent = "引用統計暫時無法載入。";
  });
