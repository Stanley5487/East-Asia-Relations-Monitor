"""
app.py
======
東亞情勢監控台 — Streamlit 網站

讀取：
- outputs/latest_predictions.csv    最新一次的模型預測（機率 + 分類標籤）
- outputs/historical_features.csv   真實歷史特徵（用於趨勢圖，非預測值）

執行方式：
    streamlit run src/app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------------------------
# 頁面設定與樣式
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="East Asia Relations Monitor",
    page_icon="compass",
    layout="wide",
)

st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    header[data-testid="stHeader"] {visibility: hidden; height: 0;}
    div[data-testid="stToolbar"] {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

COLORS = {
    "bg": "#0B0F13",
    "panel": "#121820",
    "panel_hover": "#171E27",
    "hairline": "#2A343D",
    "text_hi": "#FFFFFF",
    "text_mid": "#A9B5BE",
    "text_low": "#78838C",
    "cooperation": "#6BB79A",
    "low": "#D4A85C",
    "high": "#CC6960",
}

DYAD_NAMES = {
    "CHN-TWN": ("China", "Taiwan"),
    "CHN-JPN": ("China", "Japan"),
    "CHN-KOR": ("China", "South Korea"),
    "CHN-PRK": ("China", "North Korea"),
    "JPN-KOR": ("Japan", "South Korea"),
    "JPN-PRK": ("Japan", "North Korea"),
    "JPN-TWN": ("Japan", "Taiwan"),
    "KOR-PRK": ("South Korea", "North Korea"),
    "KOR-TWN": ("South Korea", "Taiwan"),
    "CHN-PHL": ("China", "Philippines"),
    "CHN-VNM": ("China", "Vietnam"),
}

LABEL_META = {
    "Cooperation": {"text": "Cooperation", "color": COLORS["cooperation"]},
    "Low_Conflict": {"text": "Low Conflict", "color": COLORS["low"]},
    "High_Conflict": {"text": "High Conflict", "color": COLORS["high"]},
}

THRESHOLDS = {"High_Conflict": 0.225, "Low_Conflict": 0.275}

# 全面覆蓋 Streamlit 預設樣式，確保深色主題下所有文字都清楚可讀
st.markdown(
    f"""
    <style>
    .stApp {{ background-color: {COLORS['bg']}; }}
    .block-container {{ padding-top: 2rem; max-width: 1200px; }}

    h1, h2, h3, h4, h5, h6,
    .stMarkdown, .stMarkdown p, .stMarkdown div, .stMarkdown span,
    label, .stSelectbox label {{
        color: {COLORS['text_hi']} !important;
    }}
    h1, h2, h3 {{ font-family: 'Georgia', serif; }}

    .eyebrow {{
        font-family: 'Courier New', monospace;
        font-size: 11px;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: {COLORS['text_low']} !important;
        margin-bottom: 4px;
    }}

    /* 卡片容器 */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: {COLORS['panel']};
        border: 1px solid {COLORS['hairline']} !important;
        border-radius: 6px;
    }}

    /* 一般按鈕（View detail） */
    .stButton > button {{
        background-color: {COLORS['panel_hover']};
        color: {COLORS['text_hi']} !important;
        border: 1px solid {COLORS['hairline']};
        font-family: 'Courier New', monospace;
        font-size: 12px;
    }}
    .stButton > button:hover {{
        border-color: {COLORS['text_mid']};
        color: {COLORS['text_hi']} !important;
    }}
    .stButton > button p {{
        color: {COLORS['text_hi']} !important;
    }}

    /* selectbox 下拉選單 — 全面覆蓋，含 dialog 內部使用情境 */
    div[data-baseweb="select"] > div,
    div[data-testid="stDialog"] div[data-baseweb="select"] > div {{
        background-color: {COLORS['panel_hover']} !important;
        border-color: {COLORS['hairline']} !important;
    }}
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] div,
    div[data-testid="stDialog"] div[data-baseweb="select"] span,
    div[data-testid="stDialog"] div[data-baseweb="select"] div {{
        color: {COLORS['text_hi']} !important;
        opacity: 1 !important;
    }}
    ul[role="listbox"] {{
        background-color: {COLORS['panel_hover']} !important;
    }}
    ul[role="listbox"] li,
    ul[role="listbox"] li * {{
        color: {COLORS['text_hi']} !important;
        opacity: 1 !important;
    }}

    /* dialog 彈窗 — 全面覆蓋內部所有文字元素，優先度拉到最高 */
    div[data-testid="stDialog"],
    div[data-testid="stDialog"] * {{
        color: {COLORS['text_hi']} !important;
    }}
    /* 只針對 dialog 最外層設定背景，不往內層 div 強制覆蓋，避免蓋住內部元素 */
    div[data-testid="stDialog"] {{
        background-color: {COLORS['panel']} !important;
    }}
    div[data-testid="stDialog"] .eyebrow {{
        color: {COLORS['text_low']} !important;
    }}
    div[data-testid="stDialog"] [data-testid="stCaptionContainer"],
    div[data-testid="stDialog"] [data-testid="stCaptionContainer"] * {{
        color: {COLORS['text_low']} !important;
    }}
    /* dialog 標題(由 st.dialog 標題參數自動產生) */
    div[data-testid="stDialog"] h1,
    div[data-testid="stDialog"] h2,
    div[data-testid="stDialog"] h3 {{
        color: {COLORS['text_hi']} !important;
    }}

    hr {{ border-color: {COLORS['hairline']} !important; }}

    /* caption 文字 */
    .stCaption, [data-testid="stCaptionContainer"] p {{
        color: {COLORS['text_low']} !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# 資料讀取
# ---------------------------------------------------------------------------
@st.cache_data
def load_predictions():
    return pd.read_csv("outputs/latest_predictions.csv")


@st.cache_data
def load_historical_features():
    df = pd.read_csv("outputs/historical_features.csv")
    df["date"] = pd.to_datetime(df["MonthYear"].astype(str), format="%Y%m")
    return df


try:
    predictions = load_predictions()
    history = load_historical_features()
except FileNotFoundError as e:
    st.error(
        f"找不到資料檔案：{e}\n\n"
        "請先執行 src/predict_pipeline.py 產生最新預測，"
        "並確認 src/init_historical_features.py 已執行過一次。"
    )
    st.stop()


# ---------------------------------------------------------------------------
# 詳細面板（彈窗）
# ---------------------------------------------------------------------------
@st.dialog("Dyad detail", width="large")
def show_detail(dyad):
    row = predictions[predictions["dyad"] == dyad].iloc[0]
    a, b = DYAD_NAMES.get(dyad, (dyad, ""))
    forecast_month = row.get("forecast_month", "N/A")

    st.markdown(f'<div class="eyebrow">{dyad} · forecast for {forecast_month}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<h3 style="color:{COLORS['text_hi']} !important; font-family:Georgia,serif;">{a} — {b}</h3>',
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.markdown(
            f'<p style="color:{COLORS['text_hi']} !important; font-weight:600; margin-bottom:8px;"> Probability Prediction </p>',
            unsafe_allow_html=True,
        )
        for label in ["Cooperation", "Low_Conflict", "High_Conflict"]:
            p = row[f"{label}_proba"]
            lmeta = LABEL_META[label]
            st.markdown(
                f"""
                <div style="margin-bottom:10px;">
                    <div style="display:flex; justify-content:space-between; font-size:13px; margin-bottom:3px;">
                        <span style="color:{COLORS['text_mid']};">{lmeta['text']}</span>
                        <span style="font-family:'Courier New',monospace; color:{COLORS['text_hi']} !important;">{p*100:.1f}%</span>
                    </div>
                    <div style="height:6px; background-color:{COLORS['hairline']}; border-radius:3px; overflow:hidden;">
                        <div style="width:{p*100}%; height:100%; background-color:{lmeta['color']};"></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        dyad_hist = history[history["dyad"] == dyad].sort_values("date")
        if len(dyad_hist) > 0:
            latest_feat = dyad_hist.iloc[-1]

            # Goldstein 標準差轉換成文字等級，比原始數字更容易理解
            gstd = latest_feat['goldstein_std']
            if pd.isna(gstd):
                volatility_text = "N/A"
            elif gstd < 3:
                volatility_text = "Low"
            elif gstd < 5:
                volatility_text = "Moderate"
            else:
                volatility_text = "High"

            st.markdown(
                f'<p style="color:{COLORS['text_hi']} !important; font-weight:600; margin-bottom:8px;">What the model saw last month</p>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f"""
                <div style="font-size:13px; color:{COLORS['text_mid']}; line-height:2.1;">
                <span style="color:{COLORS['text_hi']} !important; font-family:'Courier New',monospace;">{latest_feat['event_count']:.0f}</span> reported diplomatic events<br/>
                <span style="color:{COLORS['text_hi']} !important; font-family:'Courier New',monospace;">{volatility_text}</span> volatility in event tone<br/>
                <span style="color:{COLORS['text_hi']} !important; font-family:'Courier New',monospace;">{latest_feat['quad4_pct']*100:.1f}%</span> involved material action, not just rhetoric<br/>
                <span style="color:{COLORS['text_hi']} !important; font-family:'Courier New',monospace;">{latest_feat['num_sources_sum']:.0f}</span> distinct media sources covering it
                </div>
                """,
                unsafe_allow_html=True,
            )

    with col_right:
        st.markdown(
            f'<p style="color:{COLORS['text_hi']} !important; font-weight:600; margin-bottom:8px;">Historical trend (not predictions)</p>',
            unsafe_allow_html=True,
        )
        if len(dyad_hist) > 0:
            view_mode = st.selectbox(
                "View",
                [
                    "High-conflict share only",
                    "Event volume vs. High-conflict share",
                    "Event volume vs. Material conflict share",
                ],
                key=f"view_mode_{dyad}",
                label_visibility="collapsed",
            )

            fig = make_subplots(specs=[[{"secondary_y": True}]])

            if view_mode == "High-conflict share only":
                fig.add_trace(
                    go.Scatter(
                        x=dyad_hist["date"], y=dyad_hist["high_conflict_pct"] * 100,
                        name="High-conflict share (%)", line=dict(color=COLORS["high"], width=1.5),
                        fill="tozeroy", fillcolor="rgba(204,105,96,0.12)",
                    ),
                    secondary_y=False,
                )
                fig.update_yaxes(title_text="High-conflict share (%)", secondary_y=False, gridcolor=COLORS["hairline"], color=COLORS["text_mid"])
                caption_text = "Share of monthly events classified as high-conflict, over time."
            else:
                second_col = "quad4_pct" if "Material" in view_mode else "high_conflict_pct"
                second_name = "Material conflict share (%)" if "Material" in view_mode else "High-conflict share (%)"

                fig.add_trace(
                    go.Scatter(
                        x=dyad_hist["date"], y=dyad_hist["event_count"],
                        name="Event volume", line=dict(color="#7FBFCF", width=1.5),
                    ),
                    secondary_y=False,
                )
                fig.add_trace(
                    go.Scatter(
                        x=dyad_hist["date"], y=dyad_hist[second_col] * 100,
                        name=second_name, line=dict(color=COLORS["high"], width=1.5),
                    ),
                    secondary_y=True,
                )
                fig.update_yaxes(title_text="Event count", secondary_y=False, gridcolor=COLORS["hairline"], color=COLORS["text_mid"])
                fig.update_yaxes(title_text=second_name, secondary_y=True, color=COLORS["text_mid"])
                caption_text = (
                    "Volume and risk moving together suggests genuine escalation. "
                    "Volume rising alone often reflects media attention rather than deteriorating relations."
                )

            fig.update_layout(
                height=320,
                plot_bgcolor=COLORS["panel"],
                paper_bgcolor=COLORS["panel"],
                font=dict(color=COLORS["text_mid"], size=11),
                margin=dict(l=10, r=10, t=30, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color=COLORS["text_hi"])),
                xaxis=dict(gridcolor=COLORS["hairline"], color=COLORS["text_mid"]),
            )
            st.plotly_chart(fig, width='stretch')
            st.caption(caption_text)
        else:
            st.info("No historical data available for this dyad yet.")

    if st.button("Close", width='stretch'):
        st.rerun()


# ---------------------------------------------------------------------------
# 頁首
# ---------------------------------------------------------------------------
run_date = predictions["run_date"].iloc[0] if "run_date" in predictions.columns else "N/A"
forecast_month = predictions["forecast_month"].iloc[0] if "forecast_month" in predictions.columns else "N/A"
based_on = predictions["based_on_month"].iloc[0] if "based_on_month" in predictions.columns else "N/A"

col1, col2 = st.columns([3, 1])
with col1:
    st.markdown('<div class="eyebrow">GDELT-derived forecast · monthly · manual refresh</div>', unsafe_allow_html=True)
    st.title("East Asia Relations Monitor")
with col2:
    st.markdown(
        f"""
        <div style="text-align:right; font-family:'Courier New',monospace; font-size:12px; color:{COLORS['text_mid']}; padding-top: 30px;">
        FORECASTING {forecast_month}<br/>
        BASED ON {based_on}<br/>
        RUN DATE {run_date}
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<hr>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 預警橫幅：特別標示本月需要關注的關係
# ---------------------------------------------------------------------------
watch_list = predictions[
    (predictions["predicted_label"] == "High_Conflict")
    | ((predictions["predicted_label"] == "Low_Conflict") & (predictions["Low_Conflict_proba"] >= 0.40))
].sort_values("High_Conflict_proba", ascending=False)

if len(watch_list) > 0:
    st.markdown(
        f"""
        <div style="border:1px solid {COLORS['high']}; background-color:rgba(204,105,96,0.06);
                    border-radius:6px; padding:18px 20px 12px 20px; margin-bottom:32px;">
            <div style="font-family:'Courier New',monospace; font-size:11px; letter-spacing:0.1em;
                        text-transform:uppercase; color:{COLORS['high']}; margin-bottom:14px;">
                &#9888; This month's watch list — {len(watch_list)} relationship(s) flagged
            </div>
        """,
        unsafe_allow_html=True,
    )
    watch_cols = st.columns(len(watch_list))
    for i, (_, wrow) in enumerate(watch_list.iterrows()):
        wdyad = wrow["dyad"]
        wa, wb = DYAD_NAMES.get(wdyad, (wdyad, ""))
        wmeta = LABEL_META[wrow["predicted_label"]]
        wcoop, wlow, whigh = wrow["Cooperation_proba"], wrow["Low_Conflict_proba"], wrow["High_Conflict_proba"]
        with watch_cols[i]:
            st.markdown(
                f"""
                <div style="background-color:{COLORS['panel']}; border:1px solid {COLORS['hairline']};
                            border-radius:6px; padding:14px; margin-bottom:8px;">
                    <div style="font-family:'Courier New',monospace; font-size:10px; letter-spacing:0.1em;
                                text-transform:uppercase; color:{COLORS['text_low']}; margin-bottom:4px;">
                        {wdyad}
                    </div>
                    <div style="font-family:'Georgia',serif; font-size:14px; color:{COLORS['text_hi']} !important; margin-bottom:8px;">
                        {wa} — {wb}
                    </div>
                    <div style="display:flex; height:5px; border-radius:3px; overflow:hidden; margin-bottom:8px;">
                        <div style="width:{wcoop*100}%; background-color:{COLORS['cooperation']};"></div>
                        <div style="width:{wlow*100}%; background-color:{COLORS['low']};"></div>
                        <div style="width:{whigh*100}%; background-color:{COLORS['high']};"></div>
                    </div>
                    <div style="font-family:'Courier New',monospace; font-size:12px; color:{wmeta['color']};">
                        {wmeta['text']} &middot; {whigh*100:.0f}% HC
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("View", key=f"watch_{wdyad}", width='stretch'):
                show_detail(wdyad)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
else:
    st.markdown(
        f"""
        <div style="border:1px solid {COLORS['cooperation']}; background-color:rgba(107,183,154,0.08);
                    border-radius:6px; padding:14px 20px; margin-bottom:24px;
                    font-family:'Courier New',monospace; font-size:12px; color:{COLORS['cooperation']};">
            No relationships flagged for elevated risk this month.
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# 總覽：狀態統計 + 排序
# ---------------------------------------------------------------------------
counts = predictions["predicted_label"].value_counts()
count_cols = st.columns(4)
for i, label in enumerate(["Cooperation", "Low_Conflict", "High_Conflict"]):
    meta = LABEL_META[label]
    n = counts.get(label, 0)
    with count_cols[i]:
        st.markdown(
            f"""
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="width:8px; height:8px; border-radius:50%; background-color:{meta['color']}; display:inline-block;"></span>
                <span style="font-family:'Courier New',monospace; font-size:16px; color:{COLORS['text_hi']} !important;">{n}</span>
                <span style="color:{COLORS['text_mid']}; font-size:13px;">{meta['text']}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

with count_cols[3]:
    sort_mode = st.selectbox("Sort by", ["Risk (High Conflict %)", "Alphabetical"], label_visibility="collapsed")

if sort_mode == "Risk (High Conflict %)":
    predictions_sorted = predictions.sort_values("High_Conflict_proba", ascending=False)
else:
    predictions_sorted = predictions.sort_values("dyad")

st.markdown("<br/>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Dyad 卡片網格 — 點擊直接彈出詳細視窗，不需往下捲動
# ---------------------------------------------------------------------------
cols = st.columns(3)
for idx, (_, row) in enumerate(predictions_sorted.iterrows()):
    dyad = row["dyad"]
    label = row["predicted_label"]
    meta = LABEL_META[label]
    a, b = DYAD_NAMES.get(dyad, (dyad, ""))
    coop, low, high = row["Cooperation_proba"], row["Low_Conflict_proba"], row["High_Conflict_proba"]

    with cols[idx % 3]:
        with st.container(border=True):
            st.markdown(
                f"""
                <div class="eyebrow">{dyad}</div>
                <div style="font-family:'Georgia',serif; font-size:15px; margin-bottom:8px; color:{COLORS['text_hi']} !important;">{a} — {b}</div>
                <div style="display:flex; height:6px; border-radius:3px; overflow:hidden; margin-bottom:8px;">
                    <div style="width:{coop*100}%; background-color:{COLORS['cooperation']};"></div>
                    <div style="width:{low*100}%; background-color:{COLORS['low']};"></div>
                    <div style="width:{high*100}%; background-color:{COLORS['high']};"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-family:'Courier New',monospace; font-size:12px; margin-bottom:10px;">
                    <span style="color:{meta['color']};">{meta['text']}</span>
                    <span style="color:{COLORS['text_mid']};">{high*100:.0f}% HC</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("View detail", key=f"btn_{dyad}", width='stretch'):
                show_detail(dyad)

# ---------------------------------------------------------------------------
# 頁尾：方法論說明
# ---------------------------------------------------------------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.caption(
    "Model trained and validated on these 11 dyads only (2015–2025 GDELT event data). "
    "Leave-one-dyad-out testing showed reduced reliability on unseen relationships, "
    "so forecasts are not generated for dyads outside this set. Probabilities reflect a "
    "LightGBM classifier's forecast for the next month's dominant relationship category; "
    f"decision thresholds (High Conflict \u2265 {THRESHOLDS['High_Conflict']*100:.1f}%, "
    f"Low Conflict \u2265 {THRESHOLDS['Low_Conflict']*100:.1f}%) were tuned on a held-out test "
    "period, not the default 50% cutoff. Historical trend charts use actual GDELT-derived "
    "features, not model predictions."
)