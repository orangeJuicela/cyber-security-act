# 資安法白話通

資通安全管理法與 8 部子法的非官方條文查詢站。條文來自全國法規資料庫，只供學習參考，不構成法律意見。

預設網站位址（需先在儲存庫啟用 GitHub Pages，見下方）：<https://orangejuicela.github.io/cyber-security-act/>

## 本版有什麼

- 母法與 8 部子法全文（章、條、項、款）
- 首頁搜尋（全部法規／只搜母法／只搜子法）
- 法規總覽：日期、PCode、各子法第 1 條的授權依據
- 條文查詢：法規切換、章節、前後條、關鍵字標示
- 條文引用連結與「本條引用／被引用於」
- 白話解說區塊目前只顯示「白話解說撰寫中」

尚未收錄：各部會作業辦法、白話解說正文、互動練習、關係圖。

## 更新法規

```bash
python3 scripts/fetch_laws.py
python3 scripts/test_citations.py
```

`scripts/fetch_laws.py` 會下載：

- <https://law.moj.gov.tw/api/ch/law/json>
- <https://law.moj.gov.tw/api/ch/order/json>

只留下這九個 PCode，寫入 `site/data/laws.json`。抓不到的法規會直接失敗，不會補上自編條文。全國法規資料庫若修正條文，重新執行後請一併更新 `scripts/test_citations.py` 裡鎖定的日期與引用統計。

## 本機預覽

在 `site/` 開一個靜態伺服器（不要用 `file://`，瀏覽器會擋住 JSON）：

```bash
python3 -m http.server 4173 --directory site
```

然後打開 <http://127.0.0.1:4173/>。

## GitHub Pages

這個儲存庫用 GitHub Actions 部署 `site/`（`.github/workflows/pages.yml`）。

若網站還沒有上線，請由儲存庫擁有者到 **Settings → Pages → Build and deployment**，把 **Source** 改成 **GitHub Actions**（不要選 Deploy from a branch）。合併到 `main` 之後，Actions 會執行「Deploy GitHub Pages」。
