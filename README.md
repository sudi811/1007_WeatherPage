# 🌤️ 台灣地區一週氣溫預報系統 (CWA Weather Forecast Web App)

國立中興大學 課後作業 HW4 / HW10 實作專案。

本專案使用中央氣象署 (CWA) OpenData API 獲取全台 6 大地區（北部、中部、南部、東北部、東部、東南部）之一週氣溫預測，將清洗後的資料儲存於 SQLite3 資料庫，並透過 Streamlit 與 Plotly 建立現代化互動式資料視覺化網頁。

---

## 📋 功能特色與作業評分對應

| 階段 | 作業任務 | 評分佔比 | 實作檔案與對應功能 |
| :--- | :--- | :---: | :--- |
| **HW-1** | 獲取天氣預報資料 | **20%** | `fetch_weather.py`：調用 CWA API (`F-A0010-001`) 獲取 JSON 格式資料，並用 `json.dumps` 觀察結構。 |
| **HW-2** | 分析資料與氣溫提取 | **20%** | `fetch_weather.py`：解析 JSON 結構，提取 6 大地區的每日 `MaxT`（最高溫）與 `MinT`（最低溫）。 |
| **HW-3** | 儲存至 SQLite3 資料庫 | **20%** | `fetch_weather.py`：建立 `data.db` 與 `TemperatureForecasts` 資料表，寫入資料並執行 SQL 查詢驗證。 |
| **HW-4** | 實作 Streamlit Web App | **40%** | `app.py`：提供地區下拉選單、SQL 資料查詢、Plotly 折線圖與一週預報數據表格。 |

---

## 🚀 快速開始

### 1. 啟用環境與安裝套件
本專案已備妥虛擬環境：
```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

若需在全新環境安裝套件：
```bash
pip install requests pandas streamlit plotly
```

### 2. 設定 API Key
複製 `.env.example` 為 `.env` 並填入您的 CWA API Key：
```env
CWA_API_KEY=您的_CWA_API_KEY
```

### 3. 抓取資料並建立資料庫 (HW1 ~ HW3)
執行資料抓取與資料庫初始化腳本：
```bash
python fetch_weather.py
```
> 執行後會自動產生 `data.db` 資料庫，並在終端機輸出 SQL 查詢驗證結果。

### 4. 啟動 Streamlit 視覺化網頁 (HW4)
```bash
streamlit run app.py
```
> 瀏覽器會自動開啟 `http://localhost:8501` 查看互動式氣溫預報系統！

---

## 🔒 資安與 GitHub 上傳規範

為避免個人的 CWA API Key 外洩（避免違反資安規範或被氣象署停權）：
- 本專案已配置 `.gitignore`，自動忽略 `.env`、`.venv/` 及快取檔案。
- 上傳 GitHub 時只會上傳程式碼與 `.env.example` 範本，絕對安全！

---

## 📁 檔案結構

```
WeatherPage_1010/
├── app.py                 # Streamlit Web App 前端主程式 (HW4)
├── fetch_weather.py       # API 資料抓取、解析與 SQLite3 寫入 (HW1~HW3)
├── hw4_completed.ipynb    # 完整可執行的 Jupyter Notebook 作業繳交檔
├── data.db                # SQLite3 資料庫 (執行 fetch_weather.py 後產生)
├── F-A0010-001.json       # 離線/備援氣象資料快取
├── .env                   # 本地個人金鑰 (不公開，已被 .gitignore 忽略)
├── .env.example           # 金鑰範本檔
├── .gitignore             # Git 忽略設定
└── README.md              # 專案說明文件
```
