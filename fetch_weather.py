import os
import json
import sqlite3
import requests
import urllib3
import pandas as pd
from collections import defaultdict

# 忽略 SSL 警告（針對台灣政府網站 .gov.tw 根憑證特性）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 讀取 API Key (優先從 .env 讀取)
# ==========================================
API_KEY = "CWA-6FC44933-6473-4341-8216-9BA08D3BBD79"

if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("CWA_API_KEY="):
                val = line.strip().split("=", 1)[1]
                if val and "your_" not in val:
                    API_KEY = val

# 台灣 22 縣市對應至 6 大作業預報區域
COUNTY_TO_REGION = {
    # 北部地區
    "基隆市": "北部地區", "臺北市": "北部地區", "新北市": "北部地區",
    "桃園市": "北部地區", "新竹市": "北部地區", "新竹縣": "北部地區", "苗栗縣": "北部地區",
    # 中部地區
    "臺中市": "中部地區", "彰化縣": "中部地區", "南投縣": "中部地區", "雲林縣": "中部地區",
    # 南部地區
    "嘉義市": "南部地區", "嘉義縣": "南部地區", "臺南市": "南部地區", "高雄市": "南部地區", "屏東縣": "南部地區",
    # 東北部地區
    "宜蘭縣": "東北部地區",
    # 東部地區
    "花蓮縣": "東部地區",
    # 東南部地區
    "臺東縣": "東南部地區"
}

REGIONS_ORDER = ["北部地區", "中部地區", "南部地區", "東北部地區", "東部地區", "東南部地區"]

# ==========================================
# HW10-1: 獲取天氣預報資料 (API 請求)
# 優先採用 CWA 最新實時一週預報 API (F-D0047-091)
# ==========================================
def fetch_weather_data():
    """
    呼叫中央氣象署 CWA API 獲取今日起未來一週的天氣預報
    """
    realtime_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-D0047-091?Authorization={API_KEY}"
    print(f"正在呼叫 CWA 實時一週氣象預報 API (F-D0047-091)...")

    try:
        response = requests.get(realtime_url, verify=False, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if "records" in data and "Locations" in data["records"]:
                print("成功自 CWA API 取得今日最新實時氣候資料！")
                return {"type": "realtime", "data": data}
    except Exception as e:
        print(f"實時 API 連線異常: {e}")

    # 備援快取：若連線異常則載入預存檔案
    print("正在啟用備援快取資料 (F-A0010-001.json)...")
    if os.path.exists("F-A0010-001.json"):
        with open("F-A0010-001.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return {"type": "cache", "data": data}
    else:
        raise RuntimeError("無法獲取天氣資料，且無本地備援檔案。")

# ==========================================
# HW10-2: 分析資料，提取 6 大地區最高與最低氣溫
# ==========================================
def parse_temperature_forecasts(payload):
    """
    解析 JSON 結構，輸出 6 大地區之每日最高氣溫 (MaxT) 與最低氣溫 (MinT)
    """
    data_type = payload["type"]
    data = payload["data"]

    results = []

    if data_type == "realtime":
        locations = data["records"]["Locations"][0]["Location"]
        
        region_daily_min = defaultdict(lambda: defaultdict(list))
        region_daily_max = defaultdict(lambda: defaultdict(list))

        for loc in locations:
            county = loc["LocationName"]
            if county not in COUNTY_TO_REGION:
                continue
            region = COUNTY_TO_REGION[county]

            for we in loc["WeatherElement"]:
                elem_name = we["ElementName"]
                if elem_name == "最高溫度":
                    for t in we["Time"]:
                        date = t["StartTime"].split("T")[0]
                        val = int(t["ElementValue"][0]["MaxTemperature"])
                        region_daily_max[region][date].append(val)
                elif elem_name == "最低溫度":
                    for t in we["Time"]:
                        date = t["StartTime"].split("T")[0]
                        val = int(t["ElementValue"][0]["MinTemperature"])
                        region_daily_min[region][date].append(val)

        # 取得未來 7 天日期
        all_dates = sorted(list(next(iter(region_daily_max.values())).keys()))[:7]

        for reg in REGIONS_ORDER:
            for d in all_dates:
                mins = region_daily_min[reg][d]
                maxs = region_daily_max[reg][d]
                min_v = int(round(sum(mins) / len(mins))) if mins else 20
                max_v = int(round(sum(maxs) / len(maxs))) if maxs else 26
                results.append({
                    "regionName": reg,
                    "dataDate": d,
                    "MinT": min_v,
                    "MaxT": max_v,
                    "AvgT": round((min_v + max_v) / 2.0, 1)
                })

    else:
        # 解析 F-A0010-001 快取格式
        locations = (
            data["cwaopendata"]["resources"]["resource"]["data"]
            ["agrWeatherForecasts"]["weatherForecasts"]["location"]
        )
        for region in locations:
            region_name = region["locationName"]
            mint_daily = region["weatherElements"]["MinT"]["daily"]
            maxt_daily = region["weatherElements"]["MaxT"]["daily"]
            for mint, maxt in zip(mint_daily, maxt_daily):
                d = str(mint["dataDate"])
                min_v = int(mint["temperature"])
                max_v = int(maxt["temperature"])
                results.append({
                    "regionName": region_name,
                    "dataDate": d,
                    "MinT": min_v,
                    "MaxT": max_v,
                    "AvgT": round((min_v + max_v) / 2.0, 1)
                })

    print(f"成功解析 {len(results)} 筆氣溫預測資料！")
    return results

# ==========================================
# HW10-3: 將氣溫資料儲存到 SQLite3 資料庫與 CSV
# ==========================================
def save_to_sqlite(records, db_path="data.db"):
    """
    建立 SQLite3 資料庫 data.db 與 TemperatureForecasts 資料表並寫入資料
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS TemperatureForecasts")
    cursor.execute("""
    CREATE TABLE TemperatureForecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        regionName TEXT,
        dataDate TEXT,
        MinT INT,
        MaxT INT
    )
    """)

    for row in records:
        cursor.execute(
            "INSERT INTO TemperatureForecasts (regionName, dataDate, MinT, MaxT) VALUES (?, ?, ?, ?)",
            (row["regionName"], row["dataDate"], row["MinT"], row["MaxT"])
        )

    conn.commit()
    conn.close()
    print(f"成功儲存 {len(records)} 筆氣溫預報至資料庫: {db_path}！")

    # 同步匯出 weather_data.csv (依作業 Prompt 要求)
    df = pd.DataFrame(records)
    df.insert(0, "id", range(1, len(df) + 1))
    df.to_csv("weather_data.csv", index=False, encoding="utf-8-sig")
    print("成功匯出實時資料至 weather_data.csv！")

# ==========================================
# 驗證檢查：從資料庫查詢資料 (符合作業規定)
# ==========================================
def verify_database(db_path="data.db"):
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
    payload = fetch_weather_data()
    records = parse_temperature_forecasts(payload)
    save_to_sqlite(records)
    verify_database()
