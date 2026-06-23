# 📈 台灣股市法人籌碼與連買連賣網頁看板 (Taiwan Stock Institutional Trades & Streaks Web Dashboard)

這是一個專為台灣股市設計的**無伺服器 (Serverless) 網頁看板**。利用 **GitHub Actions** 作為每日定時排程的自動爬蟲，抓取證交所、櫃買中心與期交所盤後數據，並將計算結果編譯為靜態 JSON 資料庫，最後託管於 **GitHub Pages** 免費靜態網站上。

### 🌟 系統優點
1. **完全免費**：完全使用 GitHub 提供的免費靜態網站代管 (Pages) 與自動化容器 (Actions)。
2. **無 Google Drive 依賴**：改為「Repo-as-Database」架構，歷史快取自動存於 Git 倉庫中，分享給其他人使用時，**不會 mount 或佔用任何人的 Google Drive 空間**。
3. **即時載入**：瀏覽器端僅讀取預先編譯好的靜態 JSON 檔案，網頁開啟僅需數毫秒。
4. **全平台響應式與雙主題**：支援手機與電腦瀏覽，提供精美現代感的亮色卡片佈局，並能一鍵切換深色模式。
5. **個股即時檢索**：可搜尋任意上市櫃代碼，立刻顯示今日收盤價、漲跌幅、開盤、最高、最低、成交張數，以及外資、投信、自營商、三大法人合計之連買連賣天數與買賣超張數。
---

### 手動觸發第一次爬網以啟動網頁
由於網頁預設是去讀取 `data/` 資料夾下的 JSON。剛上傳時還沒有資料，您可以手動執行第一次 Actions 爬蟲來生成資料：
1. 在 GitHub 倉庫網頁，點選上方選單的 **`Actions`**。
2. 在左側選擇 **`Scrape Daily Taiwan Stock Data`** 工作流。
3. 點選右側的 **`Run workflow`** 下拉選單。
4. 點選綠色的 **`Run workflow`** 按鈕。
5. 稍等約 1 分鐘，工作流執行完畢（綠色勾勾）後，它會自動將當日盤後資料寫入您的倉庫中，這時您的 GitHub Pages 網頁就全部運作正常囉！
6. 之後的每個交易日**下午 15:45 (台北時間)**，GitHub Actions 都會自動執行這個腳本，完全不需要人工手動操作。

---

## 📂 專案檔案結構說明
* `.github/workflows/scrape.yml`：GitHub Actions 的自動排程工作流設定檔。
* `build_static_data.py`：Python 爬蟲與資料編譯主程式（專為 Actions 容器優化）。
* `index.html`：前端網頁結構，採用 HTML5 語意化標籤。
* `styles.css`：前端排版樣式，支援 Slate 亮色卡片與深色模式。
* `app.js`：前端 JavaScript 邏輯，負責處理資料載入、表格渲染、籌碼面分析以及個股即時搜尋。
* `data/`：存放編譯完成之資料與 matplotlib 疊圖（自動生成）。
  * `data/cache/`：存放抓取過的歷史法人資料快取，防止重複發送 API 請求造成封鎖。
