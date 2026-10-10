import os
import sqlite3
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go

# ==========================================
# 頁面配置
# ==========================================
st.set_page_config(
    page_title="台灣地區一週氣溫預報系統",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自訂 CSS 美化
st.markdown("""
<style>
    .main-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.0rem;
        color: #64748B;
        margin-bottom: 1.2rem;
    }
    .metric-box {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 12px 16px;
        text-align: center;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #64748B;
    }
    .legend-badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 600;
        color: white;
        margin-right: 6px;
    }
</style>
""", unsafe_allow_html=True)

# 標題區
st.markdown('<div class="main-title">🌤️ 台灣地區一週氣溫預報系統 (CWA Forecast App)</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">資料來源：中央氣象署 (CWA) 農業天氣預報 ｜ 後端儲存：SQLite3 (data.db) & weather_data.csv</div>', unsafe_allow_html=True)

# ==========================================
# 6 大地區概略經緯度座標 (Approximate Coordinates)
# ==========================================
REGION_COORDS = {
    "北部地區": [25.04, 121.55],
    "中部地區": [24.15, 120.67],
    "南部地區": [23.00, 120.22],
    "東北部地區": [24.75, 121.75],
    "東部地區": [23.98, 121.60],
    "東南部地區": [22.76, 121.14]
}

# ==========================================
# 溫度著色規則 (Instruction Prompt 指定)
# blue <20°C, green 20-25°C, yellow 25-30°C, red >30°C
# ==========================================
def get_temp_color(temp):
    if temp < 20:
        return "#2563EB"  # 藍色 (blue)
    elif 20 <= temp <= 25:
        return "#16A34A"  # 綠色 (green)
    elif 25 < temp <= 30:
        return "#EAB308"  # 黃色 (yellow)
    else:
        return "#DC2626"  # 紅色 (red)

def get_temp_label(temp):
    if temp < 20:
        return "涼冷 (<20°C)"
    elif 20 <= temp <= 25:
        return "舒適 (20-25°C)"
    elif 25 < temp <= 30:
        return "溫暖 (25-30°C)"
    else:
        return "炎熱 (>30°C)"

# ==========================================
# 資料庫查詢與即時載入函式 (無過期快取)
# ==========================================
DB_PATH = "data.db"

def load_all_weather_data(force_refresh=False):
    # 若資料庫不存在、或要求強制更新、或資料庫中日期為舊資料(小於2026)，自動自 CWA 重新抓取
    need_fetch = force_refresh or (not os.path.exists(DB_PATH))
    if not need_fetch and os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            check_df = pd.read_sql_query("SELECT MAX(dataDate) as max_d FROM TemperatureForecasts", conn)
            conn.close()
            if check_df.empty or check_df["max_d"].iloc[0] is None or check_df["max_d"].iloc[0] < "2026":
                need_fetch = True
        except Exception:
            need_fetch = True

    if need_fetch and os.path.exists("fetch_weather.py"):
        try:
            import fetch_weather
            payload = fetch_weather.fetch_weather_data()
            records = fetch_weather.parse_temperature_forecasts(payload)
            fetch_weather.save_to_sqlite(records)
        except Exception as e:
            st.warning(f"自動同步最新氣象資料時發生連線警告: {e}")

    conn = sqlite3.connect(DB_PATH)
    query = "SELECT id, regionName, dataDate, MinT, MaxT FROM TemperatureForecasts ORDER BY dataDate, id"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # 計算平均溫度 AvgT
    df["AvgT"] = ((df["MinT"] + df["MaxT"]) / 2.0).round(1)
    return df

# 側邊欄重新同步按鈕
if st.sidebar.button("🔄 重新連線 CWA 同步即時預報"):
    st.cache_data.clear()
    df_all = load_all_weather_data(force_refresh=True)
    st.rerun()
else:
    df_all = load_all_weather_data()

if df_all.empty:
    st.error("⚠️ 資料庫中尚無資料，請點擊上方按鈕重新抓取資料！")
    st.stop()

# 取得所有可用日期與地區
available_dates = sorted(df_all["dataDate"].unique().tolist())
available_regions = df_all["regionName"].unique().tolist()

# ==========================================
# 側邊欄控制面板 (動態日期篩選器)
# ==========================================
st.sidebar.header("📅 預報日期切換 (Date Selector)")
selected_date = st.sidebar.selectbox(
    "選擇要檢視的預報日期：",
    available_dates,
    index=0
)

# 篩選所選日期的 6 區數據
df_selected_date = df_all[df_all["dataDate"] == selected_date].copy()

st.sidebar.markdown("---")
st.sidebar.markdown("**🎨 氣溫圖例 (Color Legend):**")
st.sidebar.markdown("""
<div style="line-height: 1.8;">
    <span class="legend-badge" style="background-color: #2563EB;">藍色</span> &lt; 20°C (涼冷)<br>
    <span class="legend-badge" style="background-color: #16A34A;">綠色</span> 20 - 25°C (舒適)<br>
    <span class="legend-badge" style="background-color: #EAB308;">黃色</span> 25 - 30°C (溫暖)<br>
    <span class="legend-badge" style="background-color: #DC2626;">紅色</span> &gt; 30°C (炎熱)
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.caption("國立中興大學 課後作業 ｜ CWA 氣象資料視覺化")

# ==========================================
# 核心版面：左右分欄佈局 (Left-Right Layout)
# 左側：Folium 台灣互動地圖
# 右側：該日期全區氣溫資料表
# ==========================================
st.subheader(f"📍 {selected_date} 全台 6 大地區氣溫預報分佈")

col_left, col_right = st.columns([1.15, 0.85], gap="large")

# ----------------- 左側：Folium 地圖 -----------------
with col_left:
    st.markdown("##### 🗺️ 台灣氣溫互動地圖 (依平均溫著色)")
    
    # 建立 Folium 地圖物件，中心鎖定台灣 (使用免金鑰的標準 OpenStreetMap)
    m = folium.Map(
        location=[23.70, 120.95],
        zoom_start=7,
        tiles="OpenStreetMap",
        control_scale=True
    )

    # 繪製各地區標記圓圈
    for _, row in df_selected_date.iterrows():
        region = row["regionName"]
        mint = row["MinT"]
        maxt = row["MaxT"]
        avgt = row["AvgT"]
        coords = REGION_COORDS.get(region, [23.7, 121.0])
        color = get_temp_color(avgt)
        label = get_temp_label(avgt)

        # Popup 詳細資訊內容 (以 IFrame 封裝確保排版與點擊觸發)
        popup_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Arial, "Microsoft JhengHei", sans-serif;
                    margin: 0;
                    padding: 4px;
                    font-size: 13px;
                    line-height: 1.5;
                    color: #1E293B;
                }}
                h4 {{
                    margin: 0 0 6px 0;
                    font-size: 15px;
                    color: #0F172A;
                    border-bottom: 2px solid {color};
                    padding-bottom: 4px;
                }}
                .item {{ margin: 3px 0; }}
            </style>
        </head>
        <body>
            <h4>{region}</h4>
            <div class="item"><b>預報日期：</b>{selected_date}</div>
            <div class="item"><b>最高氣溫：</b><span style="color:#DC2626; font-weight:bold;">{maxt}°C</span></div>
            <div class="item"><b>最低氣溫：</b><span style="color:#2563EB; font-weight:bold;">{mint}°C</span></div>
            <div class="item"><b>平均氣溫：</b><b>{avgt}°C</b></div>
            <div class="item"><b>體感狀態：</b><span style="color:{color}; font-weight:bold;">{label}</span></div>
        </body>
        </html>
        """
        iframe = folium.IFrame(html=popup_html, width=170, height=140)
        popup = folium.Popup(iframe, max_width=200)

        # 圓形標記 CircleMarker
        folium.CircleMarker(
            location=coords,
            radius=18,
            color="#FFFFFF",
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.88,
            popup=popup,
            tooltip=f"{region}：平均 {avgt}°C (點擊查看詳情)"
        ).add_to(m)

        # 在地圖圓圈內標記平均溫度文字 (pointer-events: none 確保不阻擋圓圈點擊事件)
        folium.Marker(
            location=coords,
            icon=folium.DivIcon(
                icon_size=(36, 36),
                icon_anchor=(18, 12),
                html=f'<div style="font-size: 11px; font-weight: bold; color: white; text-align: center; text-shadow: 1px 1px 2px #333; pointer-events: none; user-select: none;">{int(round(avgt))}°</div>'
            )
        ).add_to(m)

    # 在 Streamlit 中渲染地圖 (returned_objects=[] 避免點擊觸發全頁 Rerun 而關閉彈出視窗)
    st_folium(m, height=480, width=None, returned_objects=[])

# ----------------- 右側：資料表格與指標 -----------------
with col_right:
    st.markdown("##### 📋 各地區氣溫詳細數據表")
    
    # 頂部小統計卡片
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        st.markdown(f'<div class="metric-box"><div class="metric-label">當日最高溫</div><div class="metric-value" style="color:#DC2626;">{df_selected_date["MaxT"].max()}°C</div></div>', unsafe_allow_html=True)
    with col_s2:
        st.markdown(f'<div class="metric-box"><div class="metric-label">當日最低溫</div><div class="metric-value" style="color:#2563EB;">{df_selected_date["MinT"].min()}°C</div></div>', unsafe_allow_html=True)
    with col_s3:
        st.markdown(f'<div class="metric-box"><div class="metric-label">全台均溫</div><div class="metric-value" style="color:#16A34A;">{round(df_selected_date["AvgT"].mean(), 1)}°C</div></div>', unsafe_allow_html=True)
    
    st.write("")

    # 整理表格顯示
    table_df = df_selected_date[["regionName", "MinT", "MaxT", "AvgT"]].copy()
    table_df["溫差 (°C)"] = table_df["MaxT"] - table_df["MinT"]
    table_df["狀態"] = table_df["AvgT"].apply(get_temp_label)
    table_df.columns = ["地區名稱", "最低溫 (°C)", "最高溫 (°C)", "平均溫 (°C)", "溫差 (°C)", "氣溫狀態"]

    st.dataframe(
        table_df,
        hide_index=True,
        height=320
    )

    st.caption("💡 提示：點擊地圖上的各區圓點，可彈出詳細預報視窗！")

# ==========================================
# 延伸分析：各區一週走勢折線圖 (完整保留 HW4-4 評分項目)
# ==========================================
st.markdown("---")
st.subheader("📈 單一地區一週氣溫趨勢分析 (SQL 查詢折線圖)")

col_sel, col_chart = st.columns([0.3, 0.7])
with col_sel:
    region_choice = st.selectbox(
        "選擇要分析趨勢的地區：",
        available_regions,
        index=1 if "中部地區" in available_regions else 0
    )
    df_reg = df_all[df_all["regionName"] == region_choice].sort_values("dataDate")
    
    st.markdown(f"""
    **{region_choice} 一週概要：**
    - 預報天數：{len(df_reg)} 天
    - 一週最高：{df_reg['MaxT'].max()}°C
    - 一週最低：{df_reg['MinT'].min()}°C
    - 平均溫差：{round((df_reg['MaxT'] - df_reg['MinT']).mean(), 1)}°C
    """)

with col_chart:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_reg["dataDate"],
        y=df_reg["MaxT"],
        mode="lines+markers+text",
        name="最高氣溫 (MaxT)",
        line=dict(color="#EF4444", width=3),
        marker=dict(size=8, color="#DC2626"),
        text=df_reg["MaxT"].astype(str) + "°C",
        textposition="top center"
    ))
    fig.add_trace(go.Scatter(
        x=df_reg["dataDate"],
        y=df_reg["MinT"],
        mode="lines+markers+text",
        name="最低氣溫 (MinT)",
        line=dict(color="#3B82F6", width=3),
        marker=dict(size=8, color="#2563EB"),
        text=df_reg["MinT"].astype(str) + "°C",
        textposition="bottom center"
    ))
    fig.update_layout(
        title=f"{region_choice} 未來 7 天氣溫走勢圖",
        xaxis_title="預報日期",
        yaxis_title="氣溫 (°C)",
        template="plotly_white",
        margin=dict(l=20, r=20, t=40, b=20),
        height=320,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig)
