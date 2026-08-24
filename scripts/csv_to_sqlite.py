# 改寫資料存放方式，變成關聯式資料
import pandas  as pd
import sqlite3
df_latest_predictions = pd.read_csv('outputs/latest_predictions.csv')
df_historical_features = pd.read_csv('outputs/historical_features.csv')

conn = sqlite3.connect('outputs/relations.db')
df_latest_predictions.to_sql('predictions', conn, if_exists="replace", index=False)
df_historical_features.to_sql('historical_features', conn, if_exists='replace', index=False)

print('資料創建成功')
conn.close()
