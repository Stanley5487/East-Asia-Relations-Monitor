"""
features.py
============
特徵工程核心函式，供訓練 notebook 與 predict_pipeline.py 共用，
確保訓練時與預測時使用完全相同的特徵計算邏輯。

包含：
- classify_event(df)：逐筆事件依 GoldsteinScale 分類為 合作/低度衝突/高度衝突
- build_feature(df)：以 dyad + 月份彙總，產出模型 A 的 12 個核心特徵
  （含 lag1 位移，並補齊 dyad x 月份完整骨架避免斷月造成 lag 錯位）
- build_monthly_label(df)：產出 y 標籤（僅訓練階段使用）
"""

import numpy as np
import pandas as pd


def classify_event(df):
    """
    依碩論方法（Goldstein <= -8 為高度衝突）將每筆事件分類。
    """
    df_copy = df.copy()
    goldstein = df_copy['GoldsteinScale']
    bins = [-float('inf'), -8, 0, float('inf')]
    group_names = ['High_Conflict', 'Low_Conflict', 'Cooperation']
    df_copy['relation'] = pd.cut(goldstein, bins, labels=group_names)
    return df_copy


def build_feature(df):
    """
    將逐筆事件資料，彙總成 dyad-月份為單位的特徵表，
    並統一位移為 lag1（上月）版本，避免資料洩漏。
    """
    df_copy = df.copy()
    df_copy = classify_event(df_copy)

    features = df_copy.groupby(['dyad', 'MonthYear']).agg(
        event_count=('GoldsteinScale', 'size'),
        goldstein_std=('GoldsteinScale', 'std'),
        goldstein_min=('GoldsteinScale', 'min'),
        num_mentions_sum=('NumMentions', 'sum'),
        num_articles_sum=('NumArticles', 'sum'),
        num_sources_sum=('NumSources', 'sum'),
    )

    relation_counts = df_copy.groupby(['dyad', 'MonthYear'])['relation'].value_counts().unstack(fill_value=0)
    features['high_conflict_count'] = relation_counts['High_Conflict']
    features['low_conflict_count'] = relation_counts['Low_Conflict']

    quad4_count = df_copy[df_copy['QuadClass'] == 4].groupby(['dyad', 'MonthYear']).size()
    features['quad4_count'] = quad4_count
    features['quad4_count'] = features['quad4_count'].fillna(0)

    # ---- 補齊完整的 dyad x 月份骨架，避免斷月造成 lag 錯位 ----
    # 骨架範圍取「資料實際涵蓋的第一個月」到「資料實際涵蓋的最後一個月」，
    # 而非整年補齊，避免預測情境下補出尚未發生的未來月份
    # （例如資料只到 2026-08，不應補出 2026-09~2026-12 這種不存在的月份）。
    all_dyads = features.index.get_level_values('dyad').unique()
    monthyear_min = features.index.get_level_values('MonthYear').min()
    monthyear_max = features.index.get_level_values('MonthYear').max()

    all_months = []
    y, m = monthyear_min // 100, monthyear_min % 100
    while (y, m) <= (monthyear_max // 100, monthyear_max % 100):
        all_months.append(int(f'{y}{m:02d}'))
        m += 1
        if m > 12:
            m = 1
            y += 1

    full_index = pd.MultiIndex.from_product([all_dyads, all_months], names=['dyad', 'MonthYear'])

    features = features.reindex(full_index)

    # 計數類欄位：缺月份代表「當月無事件」，補 0
    count_cols = [
        'event_count', 'num_mentions_sum', 'num_articles_sum', 'num_sources_sum',
        'high_conflict_count', 'low_conflict_count', 'quad4_count'
    ]
    features[count_cols] = features[count_cols].fillna(0)

    # 佔比、統計量類欄位：分母為 0 或無事件時，維持 NaN（不可計算，不等於 0）
    features['high_conflict_pct'] = features['high_conflict_count'] / features['event_count']
    features['low_conflict_pct'] = features['low_conflict_count'] / features['event_count']
    features['quad4_pct'] = features['quad4_count'] / features['event_count']
    # goldstein_std、goldstein_min 補齊後，缺月份自然是 NaN，不用額外處理

    # ---- 統一做 lag（此時骨架已完整連續，位移才會對齊到真正的上個月）----
    feature_cols = features.columns.tolist()
    for col in feature_cols:
        features[f'{col}_lag1'] = features.groupby('dyad')[col].shift(1)

    features = features.reset_index()
    return features


def build_monthly_label(df, high_threshold_quantile=0.9, low_threshold_quantile=0.75):
    """
    產出 y 標籤：將逐筆事件彙總為 dyad-月份的關係類別。
    僅於訓練階段使用，predict_pipeline.py 不需要呼叫此函式
    （預測階段不需要知道「正確答案」，只需計算 X 特徵）。
    """
    df_copy = df.copy()
    df_copy = classify_event(df_copy)
    counts = df_copy.groupby(['dyad', 'MonthYear'])['relation'].value_counts().unstack(fill_value=0)
    counts['total'] = counts['Cooperation'] + counts['Low_Conflict'] + counts['High_Conflict']
    counts['high_conflict_pct'] = counts['High_Conflict'] / counts['total']
    counts['low_conflict_pct'] = counts['Low_Conflict'] / counts['total']

    high_threshold = counts['high_conflict_pct'].quantile(high_threshold_quantile)
    low_threshold = counts['low_conflict_pct'].quantile(low_threshold_quantile)

    counts['monthly_label'] = np.where(
        counts['high_conflict_pct'] >= high_threshold,
        'High_Conflict',
        np.where(
            counts['low_conflict_pct'] >= low_threshold,
            'Low_Conflict',
            'Cooperation'
        )
    )

    counts = counts.reset_index()
    return counts