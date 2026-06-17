# 📈 台灣股市法人籌碼與連買連賣網頁看板 (Taiwan Stock Institutional Trades & Streaks Web Dashboard)

這是一個專為台灣股市設計的**無伺服器 (Serverless) 網頁看板**。利用 **GitHub Actions** 作為每日定時排程的自動爬蟲，抓取證交所、櫃買中心與期交所盤後數據，並將計算結果編譯為靜態 JSON 資料庫，最後託管於 **GitHub Pages** 免費靜態網站上。

### 🌟 系統優點
1. **完全免費**：完全使用 GitHub 提供的免費靜態網站代管 (Pages) 與自動化容器 (Actions)。
2. **無 Google Drive 依賴**：改為「Repo-as-Database」架構，歷史快取自動存於 Git 倉庫中，分享給其他人使用時，**不會 mount 或佔用任何人的 Google Drive 空間**。
3. **即時載入**：瀏覽器端僅讀取預先編譯好的靜態 JSON 檔案，網頁開啟僅需數毫秒。
4. **全平台響應式與雙主題**：支援手機與電腦瀏覽，提供精美現代感的亮色卡片佈局，並能一鍵切換深色模式。
5. **個股即時檢索**：可搜尋任意上市櫃代碼，立刻顯示今日收盤價、漲跌幅、開盤、最高、最低、成交張數，以及外資、投信、自營商、三大法人合計之連買連賣天數與買賣超張數。

---

## 🛠️ 快速部屬指南 (Deployment Steps)

請跟著以下簡單的步驟，即可在 5 分鐘內將此系統部署到您個人的 GitHub Pages 上：

### 第一步：在 GitHub 上建立新倉庫
1. 登入您的 GitHub 帳號。
2. 點擊右上角 **`+`** 選擇 **`New repository`**。
3. 輸入倉庫名稱（例如：`taiwan-stock-dashboard`）。
4. 設定為 **`Public`** (公開)，不要勾選 Initialize with README。
5. 點擊 **`Create repository`**。

### 第二步：上傳程式碼至 GitHub
在您的本機電腦上（已經有此專案目錄下），開啟終端機或命令提示字元 (cmd)，執行以下指令：
```bash
# 切換到本機的專案目錄
cd C:\Users\P170\.gemini\antigravity\scratch\stock_scraper

# 初始化 git 倉庫
git init

# 將所有程式碼加入暫存區
git add .

# 提交第一次 commit
git commit -m "Initial commit for stock web dashboard"

# 連結遠端 GitHub 倉庫 (請將下方的 URL 換成您在第一步建立的倉庫 URL)
git branch -M main
git remote add origin https://github.com/您的帳號/taiwan-stock-dashboard.git

# 推送程式碼至 GitHub
git push -u origin main -f
```

### 第三步：開啟 GitHub Actions 的寫入權限 (重要 ⚠️)
因為 GitHub Actions 爬蟲在每日下午跑完後，必須將新的快取 JSON 與走勢圖 commit 回您的 GitHub 倉庫，所以必須開啟寫入權限：
1. 進入您的 GitHub 倉庫網頁。
2. 點選上方選單的 **`Settings`** (設定)。
3. 在左側選單點選 **`Actions`** > **`General`**。
4. 拉到最下方找到 **`Workflow permissions`**。
5. 勾選 **`Read and write permissions`** (讀取與寫入權限)。
6. 點擊 **`Save`**。

### 第四步：啟用 GitHub Pages 網頁代管
1. 在同一個 **`Settings`** (設定) 頁面，點選左側選單的 **`Pages`**。
2. 在 **Build and deployment** 下的 **Source** 選擇 **`Deploy from a branch`**。
3. 在 **Branch** 選項中，選擇 **`main`**，後面資料夾選擇 **`/ (root)`**。
4. 點擊 **`Save`**。
5. 稍等 1-2 分鐘，頁面最上方會出現網址（例如：`https://<您的帳號>.github.io/taiwan-stock-dashboard/`）。

### 第五步：手動觸發第一次爬網以啟動網頁
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
