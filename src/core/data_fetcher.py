"""
data_fetcher.py
================
共用的 GDELT 資料抓取函式。
被 `bigquery_fetcher.py`（訓練用，一次性批次抓取歷史資料）
與 `predict_pipeline.py`（預測用，抓取最新資料）共同使用。

效能備註（2026-08-20）：
原本用迴圈對每組 dyad 各自查詢一次（非分區表 + SELECT *），
單次查詢掃描量 366.6 GB，12 組合計約 4,399 GB，查詢速度慢且花費高。

優化查詢：
1. 改用 GDELT 官方分區版本表 `events_partitioned`，搭配 _PARTITIONTIME
篩選，並只選取必要欄位（而非 SELECT *）
   → 單組查詢掃描量降至 1.65 GB（減少約 222 倍）。
2. 用 IN (...) 一次查詢所有國家的兩兩配對組合，取代逐一迴圈查詢
   → 實測掃描量仍是 1.65 GB，與查單一組完全相同（因為掃描成本主要
   來自「讀取這段時間的分區資料」，篩選條件的複雜度幾乎不影響掃描量）。
   12 次迴圈變 1 次查詢，總掃描量從約 19.8 GB 降到 1.65 GB。

兩者疊加，總掃描量從 4,399 GB 降到 1.65 GB，減少約 2,666 倍。

3. 新增安全網，阻止意外異常高額收費可能

注意：IN (...) 查詢會抓出「所有國家兩兩配對」的組合，
不只是 DYAD_LIST 裡明確列出的那幾組，故仍需手動剔除不要的組合。
"""

from google.cloud import bigquery


def fetch_all_dyads_events(client, countries, start_date, end_date):
    """
    一次查詢，抓取指定國家清單「兩兩配對」必要特徵的所有 GDELT 事件資料。
    回傳的資料包含所有可能的配對組合。

    countries: 國家代碼iso3c，例如:['CHN', 'TWN', 'JPN', ...]
    start_date, end_date: 整數，格式 YYYYMMDD，例如 20240101
    """
    start_str = str(start_date)
    end_str = str(end_date)
    start_ts = f"{start_str[:4]}-{start_str[4:6]}-{start_str[6:]}"
    end_ts = f"{end_str[:4]}-{end_str[4:6]}-{end_str[6:]}"

    country_list_sql = ", ".join(f"'{c}'" for c in countries)

    query = f"""
    SELECT
        MonthYear,
        Actor1CountryCode,
        Actor2CountryCode,
        QuadClass,
        GoldsteinScale,
        NumMentions,
        NumArticles,
        NumSources
    FROM `gdelt-bq.gdeltv2.events_partitioned`
    WHERE
        Actor1CountryCode IN ({country_list_sql})
        AND Actor2CountryCode IN ({country_list_sql})
        AND SQLDATE >= {start_date} AND SQLDATE <= {end_date}
        AND _PARTITIONTIME >= TIMESTAMP("{start_ts}")
        AND _PARTITIONTIME <= TIMESTAMP("{end_ts}")
    """

    # 安全網：單次查詢最多只允許處理 5GB，超過就直接報錯中止，避免因程式錯誤或參數異常導致意外的高額掃描費用。
    job_config = bigquery.QueryJobConfig(maximum_bytes_billed=5 * 1024 ** 3)

    return client.query(query, job_config=job_config).to_dataframe()