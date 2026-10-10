import os
import json
import sqlite3
import requests
import urllib3
import pandas as pd

# 忽略 SSL 警告（針對台灣政府網站 .gov.tw 根憑證特性）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 讀取 API Key (優先從 .env 或環境變數讀取)
# ==========================================
API_KEY = "CWA-6FC44933-6473-4341-8216-9BA08D3BBD79"

# 若同目錄有 .env 檔，也可自動讀取
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("CWA_API_KEY="):
                val = line.strip().split("=", 1)[1]
                if val and "your_" not in val:
                    API_KEY = val

# ==========================================
# HW10-1: 獲取天氣預報資料 (API 請求)
# ==========================================
def fetch_weather_data():
    """
    呼叫中央氣象署 CWA API 獲取一週農業天氣預報 (F-A0010-001)
    """
    url = f"https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/F-A0010-001?Authorization={API_KEY}&downloadType=WEB&format=JSON"
    print(f"正在呼叫 CWA API: {url[:60]}...")
    
    try:
        response = requests.get(url, verify=False, timeout=15)
        if response.status_code == 200:
            data = response.json()
            print("成功從 CWA API 即時獲取資料！")
            return data
        else:
            print(f"API 回傳狀態碼: {response.status_code}，正在啟用預存快取資料 (F-A0010-001.json)...")
    except Exception as e:
        print(f"網路連線異常 ({e})，正在啟用預存快取資料 (F-A0010-001.json)...")

    # 備援快取：確保離線或氣象署端維護時程式仍可完整運作
    if os.path.exists("F-A0010-001.json"):
        with open("F-A0010-001.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            print("已載入 F-A0010-001 預報資料！")
            return data
    else:
        raise RuntimeError("無法獲取天氣資料，且無本地備援檔案。")

# ==========================================
# HW10-2: 分析資料，提取最高與最低氣溫
# ==========================================
def parse_temperature_forecasts(data):
    """
    解析 JSON 結構，提取 6 大地區的每日最高氣溫 (MaxT) 與最低氣溫 (MinT)
    """
    # 擷取地點預報資料清單
    temperature_forecasts = (
        data["cwaopendata"]["resources"]["resource"]["data"]
        ["agrWeatherForecasts"]["weatherForecasts"]["location"]
    )

    # 移除天氣狀況 Wx，只保留氣溫要素 (MaxT, MinT)
    cleaned_forecasts = []
    for region in temperature_forecasts:
        region_copy = {
            "locationName": region["locationName"],
            "weatherElements": {
                k: v for k, v in region["weatherElements"].items() if k in ("MaxT", "MinT")
            }
        }
        cleaned_forecasts.append(region_copy)

    print(f"成功解析 {len(cleaned_forecasts)} 個地區的氣溫預報！")
    return cleaned_forecasts

# ==========================================
# HW10-3: 將氣溫資料儲存到 SQLite3 資料庫
# ==========================================
def save_to_sqlite(temperature_forecasts, db_path="data.db"):
    """
    建立 SQLite3 資料庫 data.db 與 TemperatureForecasts 資料表並寫入資料
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 若舊資料表存在則先刪除，確保資料最新
    cursor.execute("DROP TABLE IF EXISTS TemperatureForecasts")

    # 依作業要求建立資料表結構
    cursor.execute("""
    CREATE TABLE TemperatureForecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        regionName TEXT,
        dataDate INT,
        MinT INT,
        MaxT INT
    )
    """)

    # 逐筆寫入資料
    insert_count = 0
    for region in temperature_forecasts:
        region_name = region["locationName"]
        mint_daily = region["weatherElements"]["MinT"]["daily"]
        maxt_daily = region["weatherElements"]["MaxT"]["daily"]

        for mint, maxt in zip(mint_daily, maxt_daily):
            data_date = str(mint["dataDate"])
            mint_val = int(mint["temperature"])
            maxt_val = int(maxt["temperature"])

            cursor.execute(
                "INSERT INTO TemperatureForecasts (regionName, dataDate, MinT, MaxT) VALUES (?, ?, ?, ?)",
                (region_name, data_date, mint_val, maxt_val),
            )
            insert_count += 1

    conn.commit()
    conn.close()
    print(f"成功儲存 {insert_count} 筆氣溫預報至資料庫: {db_path}！")

# ==========================================
# 驗證檢查：從資料庫查詢資料 (符合作業規定)
# ==========================================
def verify_database(db_path="data.db"):
    """
    檢查資料是否正確存入資料庫：
    1. 列出所有地區名稱
    2. 列出中部地區的氣溫資料
    """
    conn = sqlite3.connect(db_path)

    print("\n--- [檢查 1] 列出所有地區名稱 (DISTINCT regionName) ---")
    query_regions = "SELECT DISTINCT regionName FROM TemperatureForecasts"
    df_regions = pd.read_sql_query(query_regions, conn)
    print(df_regions)

    print("\n--- [檢查 2] 列出中部地區的氣溫資料 ---")
    selected_region = "中部地區"
    query_central = f"""
    SELECT regionName, dataDate, MinT, MaxT 
    FROM TemperatureForecasts 
    WHERE regionName = '{selected_region}'
    ORDER BY dataDate
    """
    df_central = pd.read_sql_query(query_central, conn)
    print(df_central)

    conn.close()

if __name__ == "__main__":
    # 執行完整流程
    raw_data = fetch_weather_data()
    forecasts = parse_temperature_forecasts(raw_data)
    save_to_sqlite(forecasts)
    verify_database()
