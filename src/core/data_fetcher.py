"""
data_fetcher.py
================
共用的 GDELT 資料抓取函式。
被 bigquery_fetcher.py（訓練用，一次性批次抓取歷史資料）
與 predict_pipeline.py（預測用，抓取最新資料）共同使用，
避免同一段查詢邏輯在兩處重複維護。
"""

from google.cloud import bigquery


def fetch_dyad_events(client, actor1, actor2, start_date, end_date):
    """
    抓取指定 dyad、指定日期範圍的 GDELT 事件資料
    actor1, actor2: 國家代碼字串，例如 'CHN', 'TWN'
    start_date, end_date: 整數，格式 YYYYMMDD，例如 20240101
    """
    query = f"""
    SELECT *
    FROM `gdelt-bq.gdeltv2.events`
    WHERE (
    (Actor1CountryCode = '{actor1}' AND Actor2CountryCode = '{actor2}')
    OR
    (Actor1CountryCode = '{actor2}' AND Actor2CountryCode = '{actor1}')
    )
    AND SQLDATE >= {start_date} AND SQLDATE <= {end_date}
    """
    return client.query(query).to_dataframe()