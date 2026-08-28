import sqlite3
from news_fetch import fetch_news_rss
from news_db_writer import create_articles_table, insert_articles

if __name__ == "__main__":
    conn = sqlite3.connect("outputs/relations.db")
    create_articles_table(conn)

    # 用中日關係當測試
    articles = fetch_news_rss("中日關係", lang="zh-TW", country="TW", days=7)
    new_count = insert_articles(conn, articles, dyad="CHN-JPN", language="zh-TW")

    print(f"這次抓到 {len(articles)} 篇文章，新增了 {new_count} 篇（重複的被跳過）")

    conn.close()