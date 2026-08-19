"""
predict_pipeline.py
====================
用途：對固定的11組已訓練過的東亞dyad，抓取最新GDELT資料，
套用訓練好的模型，產出下一期的關係類別機率預測與分類標籤。

執行邏輯：
只使用「已完整結束的月份」做預測，自動排除當前尚未過完的月份。
例如今天是 2026-08-18，最近一個完整結束的月份是 2026-07，
系統會用 7 月的完整特徵，預測「8 月」的關係走向。

使用前準備:
- 模型已訓練並存於 outputs/models/mod_lgb.pkl
- 特徵欄位清單、門檻設定存於 outputs/models/model_config.json
- V-Dem政體差異資料已處理並存於 data/processed/vdem_dyad.csv
"""

import json
import joblib
import pandas as pd
from google.cloud import bigquery
from datetime import datetime, timedelta

from core.features import build_feature
from core.data_fetcher import fetch_dyad_events

PROJECT_ID = "gdelt-east-asia-forecast"
DYAD_LIST = [
    ('CHN', 'TWN'), ('CHN', 'JPN'), ('CHN', 'KOR'), ('CHN', 'PRK'),
    ('JPN', 'KOR'), ('JPN', 'PRK'), ('JPN', 'TWN'),
    ('KOR', 'PRK'), ('KOR', 'TWN'),
    ('CHN', 'PHL'), ('CHN', 'VNM'),
]


def get_last_complete_month_end(reference_date=None):
    """
    找出「已完整結束的最近一個月」的最後一天。
    例如 reference_date = 2026-08-18 -> 回傳 2026-07-31
        reference_date = 2026-01-05 -> 回傳 2025-12-31（跨年處理）
    """
    if reference_date is None:
        reference_date = datetime.today()
    first_day_of_this_month = reference_date.replace(day=1)
    return first_day_of_this_month - timedelta(days=1)


def merge_regime_diff(features, vdem_dyad):
    """
    合併政體差異特徵，若目標年份無資料（如尚未發布的年份），
    則沿用該 dyad 在 vdem_dyad 中最近一個「小於等於目標年份」的數值（LOCF 邏輯）。
    """
    features_sorted = features.sort_values('year').copy()
    vdem_sorted = vdem_dyad.sort_values('year').copy()
    return pd.merge_asof(
        features_sorted,
        vdem_sorted[['dyad', 'year', 'regime_diff']],
        on='year',
        by='dyad',
        direction='backward',
    )


def next_month(monthyear):
    y, m = monthyear // 100, monthyear % 100
    if m == 12:
        return (y + 1) * 100 + 1
    return y * 100 + m + 1


def append_or_replace(new_rows, path, key_cols):
    """
    通用的「累加存檔」邏輯：若 key_cols 組合已存在於舊紀錄，
    以本次結果覆蓋，其餘保留，最後合併寫回同一個 csv。
    被 save_historical_features()（真實特徵）與主流程（預測紀錄）共用。
    """
    try:
        existing = pd.read_csv(path)
        existing = existing[
            ~existing.set_index(key_cols).index.isin(new_rows.set_index(key_cols).index)
        ]
        combined = pd.concat([existing, new_rows], ignore_index=True)
    except FileNotFoundError:
        combined = new_rows

    combined = combined.sort_values(key_cols).reset_index(drop=True)
    combined.to_csv(path, index=False)
    return combined


def save_historical_features(features, path='outputs/historical_features.csv'):
    """
    將這次算出的「真實」特徵（非預測值）累加進歷史紀錄檔案，供趨勢圖使用。
    首次使用前，須先執行 init_historical_features.py 建立 2015-2025 的完整起點。
    """
    keep_cols = [
        'dyad', 'MonthYear', 'event_count', 'goldstein_std', 'goldstein_min',
        'num_mentions_sum', 'num_articles_sum', 'num_sources_sum',
        'high_conflict_count', 'low_conflict_count', 'quad4_count',
        'high_conflict_pct', 'low_conflict_pct', 'quad4_pct',
    ]
    new_rows = features[keep_cols].dropna(subset=['event_count'])
    combined = append_or_replace(new_rows, path, key_cols=['dyad', 'MonthYear'])
    print(f'已更新歷史真實特徵紀錄：{path}（共 {len(combined)} 筆）')


def assign_label(row, thresholds):
    if row['High_Conflict_proba'] >= thresholds['High_Conflict']:
        return 'High_Conflict'
    elif row['Low_Conflict_proba'] >= thresholds['Low_Conflict']:
        return 'Low_Conflict'
    return 'Cooperation'


def run_prediction_pipeline(start_date, end_date):
    """
    完整預測流程：抓資料 -> 特徵工程 -> 合併政體差異 -> 套用模型 -> 產出結果

    end_date 必須是「已完整結束的月份」的月底，不能是尚未過完的當月，否則該月的特徵會因資料不完整而失真。
    """
    print('正在連線 BigQuery')
    client = bigquery.Client(project=PROJECT_ID)

    all_dyad_data = []
    for actor1, actor2 in DYAD_LIST:
        print(f'正在抓取 {actor1}-{actor2}')
        df = fetch_dyad_events(client, actor1, actor2, start_date, end_date)
        df['dyad'] = f'{actor1}-{actor2}'
        all_dyad_data.append(df)

    raw_df = pd.concat(all_dyad_data, ignore_index=True)
    print(f'共抓取 {len(raw_df)} 筆事件資料')

    features = build_feature(raw_df)

    features['year'] = features['MonthYear'] // 100
    vdem_dyad = pd.read_csv('data/processed/vdem_dyad.csv')
    features = merge_regime_diff(features, vdem_dyad)

    save_historical_features(features)

    latest_data = features.sort_values('MonthYear').groupby('dyad').tail(1).reset_index(drop=True)

    model = joblib.load('outputs/models/mod_lgb.pkl')
    with open('outputs/models/model_config.json') as f:
        config = json.load(f)

    feature_cols = config['features']
    thresholds = config['thresholds']

    missing = latest_data[feature_cols].isna().sum()
    if missing.sum() > 0:
        print('警告：以下特徵存在缺值，可能是抓取的時間範圍不夠長，lag特徵無法計算：')
        print(missing[missing > 0])

    X_latest = latest_data[feature_cols]
    proba = model.predict_proba(X_latest)
    classes = list(model.classes_)

    results = latest_data[['dyad', 'MonthYear']].copy()
    results = results.rename(columns={'MonthYear': 'based_on_month'})
    for i, cls in enumerate(classes):
        results[f'{cls}_proba'] = proba[:, i]

    results['predicted_label'] = results.apply(lambda row: assign_label(row, thresholds), axis=1)
    results['forecast_month'] = results['based_on_month'].apply(next_month)

    return results


if __name__ == '__main__':
    last_complete_month_end = get_last_complete_month_end()
    end_date = int(last_complete_month_end.strftime('%Y%m%d'))
    start_date = int((last_complete_month_end - timedelta(days=180)).strftime('%Y%m%d'))

    print(f'今天日期: {datetime.today().strftime("%Y-%m-%d")}')
    print(f'抓取範圍: {start_date} ~ {end_date}（僅使用已完整結束的月份）')

    results = run_prediction_pipeline(start_date=start_date, end_date=end_date)
    results['run_date'] = datetime.today().strftime('%Y-%m-%d')
    print(results)

    combined = append_or_replace(results, 'outputs/prediction_history.csv', key_cols=['dyad', 'forecast_month'])
    print(f'已存檔至 outputs/prediction_history.csv（累積歷史紀錄，共 {len(combined)} 筆）')

    results.to_csv('outputs/latest_predictions.csv', index=False)
    print('已存檔至 outputs/latest_predictions.csv（本次最新結果）')