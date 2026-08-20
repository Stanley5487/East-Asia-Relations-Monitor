"""
predict_pipeline.py
====================
用途：對固定的11組已訓練過的東亞dyad，抓取最新GDELT資料，
套用訓練好的模型，產出下一期的關係類別機率預測與分類標籤(end-to-end 腳本)。

注意：本檔案的所有檔案路徑，皆以 PROJECT_ROOT（本檔案所在位置往上一層）
為基準組成絕對路徑，不依賴執行當下的工作目錄，避免在不同環境（本機 / GitHub Actions）下因工作目錄不同而找不到檔案。

效能備註（2026-08-20）：改用一次查詢涵蓋所有國家配對（見 core/data_fetcher.py），
取代原本迴圈查詢的方式，BigQuery 掃描量從約 19.8 GB 降至 1.65 GB。
"""

import json
import joblib
import pandas as pd
from pathlib import Path
from google.cloud import bigquery
from datetime import datetime, timedelta

from core.features import build_feature
from core.data_fetcher import fetch_all_dyads_events

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ID = "gdelt-east-asia-forecast"

# 不包含PRK-TWN
DYAD_LIST = [
    ('CHN', 'TWN'), ('CHN', 'JPN'), ('CHN', 'KOR'), ('CHN', 'PRK'),
    ('JPN', 'KOR'), ('JPN', 'PRK'), ('JPN', 'TWN'),
    ('KOR', 'PRK'), ('KOR', 'TWN'),
    ('CHN', 'PHL'), ('CHN', 'VNM'),
]

# 查詢時實際涉及的國家
COUNTRIES = sorted({country for pair in DYAD_LIST for country in pair})


def get_last_complete_month_end(reference_date=None):
    if reference_date is None:
        reference_date = datetime.today()
    first_day_of_this_month = reference_date.replace(day=1)
    return first_day_of_this_month - timedelta(days=1)


def merge_regime_diff(features, vdem_dyad):
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


def save_historical_features(features, path=None):
    if path is None:
        path = PROJECT_ROOT / 'outputs' / 'historical_features.csv'
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


def filter_to_valid_dyads(raw_df, dyad_list):
    """
    一次性查詢會抓回「所有國家兩兩配對」的組合，
    這裡依照 dyad_list 篩選出真正需要的配對，
    並統一標記為固定方向的 dyad 名稱（例如 CHN-TWN，而非 TWN-CHN）。
    """
    filtered_frames = []
    for actor1, actor2 in dyad_list:
        mask = (
            ((raw_df['Actor1CountryCode'] == actor1) & (raw_df['Actor2CountryCode'] == actor2))
            | ((raw_df['Actor1CountryCode'] == actor2) & (raw_df['Actor2CountryCode'] == actor1))
        )
        subset = raw_df[mask].copy()
        subset['dyad'] = f'{actor1}-{actor2}'
        filtered_frames.append(subset)

    return pd.concat(filtered_frames, ignore_index=True)


def run_prediction_pipeline(start_date, end_date):
    """
    完整預測流程：抓資料 -> 特徵工程 -> 合併政體差異 -> 套用模型 -> 產出結果
    """
    print('正在連線 BigQuery')
    client = bigquery.Client(project=PROJECT_ID)

    print(f'一次查詢涵蓋國家：{COUNTRIES}')
    raw_df = fetch_all_dyads_events(client, COUNTRIES, start_date, end_date)
    print(f'共抓取 {len(raw_df)} 筆事件資料（含所有國家配對，尚未篩選）')

    raw_df = filter_to_valid_dyads(raw_df, DYAD_LIST)
    print(f'篩選出目標 dyad 後，剩餘 {len(raw_df)} 筆事件資料')

    features = build_feature(raw_df)

    features['year'] = features['MonthYear'] // 100
    vdem_path = PROJECT_ROOT / 'data' / 'processed' / 'vdem_dyad.csv'
    vdem_dyad = pd.read_csv(vdem_path)
    features = merge_regime_diff(features, vdem_dyad)

    save_historical_features(features)

    latest_data = features.sort_values('MonthYear').groupby('dyad').tail(1).reset_index(drop=True)

    model_path = PROJECT_ROOT / 'outputs' / 'models' / 'mod_lgb.pkl'
    config_path = PROJECT_ROOT / 'outputs' / 'models' / 'model_config.json'
    model = joblib.load(model_path)
    with open(config_path) as f:
        config = json.load(f)

    feature_cols = config['features']
    thresholds = config['thresholds']

    missing = latest_data[feature_cols].isna().sum()
    if missing.sum() > 0:
        print('警告：以下特徵存在缺值：')
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
    print(f'PROJECT_ROOT: {PROJECT_ROOT}')

    last_complete_month_end = get_last_complete_month_end()
    end_date = int(last_complete_month_end.strftime('%Y%m%d'))
    start_date = int((last_complete_month_end - timedelta(days=180)).strftime('%Y%m%d'))

    print(f'今天日期: {datetime.today().strftime("%Y-%m-%d")}')
    print(f'抓取範圍: {start_date} ~ {end_date}')

    results = run_prediction_pipeline(start_date=start_date, end_date=end_date)
    results['run_date'] = datetime.today().strftime('%Y-%m-%d')
    print(results)

    history_path = PROJECT_ROOT / 'outputs' / 'prediction_history.csv'
    combined = append_or_replace(results, history_path, key_cols=['dyad', 'forecast_month'])
    print(f'已存檔至 {history_path}（共 {len(combined)} 筆）')

    latest_path = PROJECT_ROOT / 'outputs' / 'latest_predictions.csv'
    results.to_csv(latest_path, index=False)
    print(f'已存檔至 {latest_path}')