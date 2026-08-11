"""
測試 BigQuery 連線與認證是否成功
"""
from google.cloud import bigquery

PROJECT_ID = "gdelt-east-asia-forecast"


def main():
    print("正在連線 BigQuery...")
    client = bigquery.Client(project=PROJECT_ID)

    query = """
    SELECT COUNT(*) AS total_events
    FROM `gdelt-bq.gdeltv2.events`
    WHERE SQLDATE = 20240101
    """

    print("正在執行測試查詢(只掃描一天的資料)...")
    result = client.query(query).to_dataframe()

    print("\n連線成功！查詢結果：")
    print(result)

if __name__ == "__main__":
    main()