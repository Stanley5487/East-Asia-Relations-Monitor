"""
init_historical_features.py
=============================
一次性初始化腳本，只需執行一次。

用途：
把 2015-2025 訓練期完整的「真實」月度特徵資料，
建立為 outputs/historical_features.csv 的起點。
之後 predict_pipeline.py 每月執行時，會自動把最新一個月的
真實特徵追加進這份檔案，讓歷史趨勢持續往後延伸。

注意：
此檔案存放的是「真實發生過」的歷史資料，不是模型的預測值，因此不含 regime_diff、不含 lag 欄位、不含 monthly_label

執行前提：
- data/processed/gdelt_dyad.csv 存在（12 組 dyad 合併後的逐筆事件原始資料）
- src/features.py 內含 build_feature()
"""

import pandas as pd
from features import build_feature

RAW_DATA_PATH = 'data/processed/gdelt_dyad.csv'
OUTPUT_PATH = 'outputs/historical_features.csv'

EXCLUDED_DYADS = ['PRK-TWN']

KEEP_COLS = [
    'dyad', 'MonthYear', 'event_count', 'goldstein_std', 'goldstein_min',
    'num_mentions_sum', 'num_articles_sum', 'num_sources_sum',
    'high_conflict_count', 'low_conflict_count', 'quad4_count',
    'high_conflict_pct', 'low_conflict_pct', 'quad4_pct',
]


def main():
    print(f'讀取原始逐筆事件資料：{RAW_DATA_PATH}')
    needed_cols = [
        'dyad', 'MonthYear', 'GoldsteinScale', 'QuadClass',
        'NumMentions', 'NumArticles', 'NumSources',
    ]
    from features import classify_event

    partial_aggs = []
    chunk_size = 20_000
    total = 0
    for i, chunk in enumerate(pd.read_csv(RAW_DATA_PATH, usecols=needed_cols, chunksize=chunk_size)):
        chunk = classify_event(chunk)

        agg = chunk.groupby(['dyad', 'MonthYear']).agg(
            event_count=('GoldsteinScale', 'size'),
            goldstein_sum=('GoldsteinScale', 'sum'),
            goldstein_sqsum=('GoldsteinScale', lambda x: (x ** 2).sum()),
            goldstein_min=('GoldsteinScale', 'min'),
            num_mentions_sum=('NumMentions', 'sum'),
            num_articles_sum=('NumArticles', 'sum'),
            num_sources_sum=('NumSources', 'sum'),
        ).reset_index()

        rel_counts = chunk.groupby(['dyad', 'MonthYear'])['relation'].value_counts().unstack(fill_value=0).reset_index()
        for col in ['High_Conflict', 'Low_Conflict', 'Cooperation']:
            if col not in rel_counts.columns:
                rel_counts[col] = 0
        agg = agg.merge(rel_counts[['dyad', 'MonthYear', 'High_Conflict', 'Low_Conflict']], on=['dyad', 'MonthYear'])
        agg = agg.rename(columns={'High_Conflict': 'high_conflict_count', 'Low_Conflict': 'low_conflict_count'})

        quad4 = chunk[chunk['QuadClass'] == 4].groupby(['dyad', 'MonthYear']).size().reset_index(name='quad4_count')
        agg = agg.merge(quad4, on=['dyad', 'MonthYear'], how='left')
        agg['quad4_count'] = agg['quad4_count'].fillna(0)

        partial_aggs.append(agg)
        total += len(chunk)
        print(f'  已處理第 {i + 1} 批，累計 {total} 筆')
        del chunk

    print('合併各批彙總結果...')
    combined = pd.concat(partial_aggs, ignore_index=True)
    del partial_aggs
    final = combined.groupby(['dyad', 'MonthYear']).agg(
        event_count=('event_count', 'sum'),
        goldstein_sum=('goldstein_sum', 'sum'),
        goldstein_sqsum=('goldstein_sqsum', 'sum'),
        goldstein_min=('goldstein_min', 'min'),
        num_mentions_sum=('num_mentions_sum', 'sum'),
        num_articles_sum=('num_articles_sum', 'sum'),
        num_sources_sum=('num_sources_sum', 'sum'),
        high_conflict_count=('high_conflict_count', 'sum'),
        low_conflict_count=('low_conflict_count', 'sum'),
        quad4_count=('quad4_count', 'sum'),
    ).reset_index()
    n = final['event_count']
    mean = final['goldstein_sum'] / n
    variance = (final['goldstein_sqsum'] - n * mean ** 2) / (n - 1).clip(lower=1)
    final['goldstein_std'] = variance.clip(lower=0) ** 0.5
    final.loc[n <= 1, 'goldstein_std'] = float('nan')  # 樣本數不足1筆時，標準差無意義

    final['high_conflict_pct'] = final['high_conflict_count'] / final['event_count']
    final['low_conflict_pct'] = final['low_conflict_count'] / final['event_count']
    final['quad4_pct'] = final['quad4_count'] / final['event_count']

    features_clean = final[KEEP_COLS]
    features_clean = features_clean[~features_clean['dyad'].isin(EXCLUDED_DYADS)]
    features_clean = features_clean.sort_values(['dyad', 'MonthYear']).reset_index(drop=True)
    features_clean.to_csv(OUTPUT_PATH, index=False)

    print(f'初始化完成：{OUTPUT_PATH}')
    print(f'共 {len(features_clean)} 筆歷史真實特徵紀錄')
    print(f'涵蓋 dyad：{sorted(features_clean["dyad"].unique())}')
    print(f'時間範圍：{features_clean["MonthYear"].min()} ~ {features_clean["MonthYear"].max()}')


if __name__ == '__main__':
    main()