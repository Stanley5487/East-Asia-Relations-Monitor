from google.cloud import bigquery
import pandas as pd
PROJECT_ID = "gdelt-east-asia-forecast"

# 測試一下結果
def fetch_dyad_events(client, actor1, actor2, start_date, end_date):
    """
    抓取指定 dyad、指定日期範圍的 GDELT 事件資料 actor1, actor2: 國家代碼字串，例如 'CHN', 'TWN'
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


def main():
    print('正在連線 BigQuery')
    client = bigquery.Client(project=PROJECT_ID)
    print('正在查詢資料')
    dyad_list = [
        ('CHN', 'TWN'), ('CHN', 'JPN'), ('CHN', 'KOR'), ('CHN', 'PRK'),
        ('JPN', 'KOR'), ('JPN', 'PRK'), ('JPN', 'TWN'),
        ('KOR', 'PRK'), ('KOR', 'TWN'),
        ('PRK', 'TWN'),
        ('CHN', 'PHL'), ('CHN', 'VNM'),
    ]

    for actor1, actor2 in dyad_list:
        print(f'正在搜尋{actor1}、{actor2}')
        df = fetch_dyad_events(client, actor1, actor2, 20150101, 20251231)
        df.to_csv(f'data/raw/{actor1}_{actor2}2015_2025.csv')
        print(f"抓到 {len(df)} 筆資料")


if __name__ == "__main__":
    main()