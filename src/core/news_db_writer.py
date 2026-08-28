"""
db_news_writer.py
============
負責建立 article 資料表，以及把 fetch_news_rss() 抓到的文章寫進 SQLite。
"""

import sqlite3


def create_articles_table(conn):
    """建立 articles 表（若已存在則不重複建立）"""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            article_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            publisher TEXT,
            source_url TEXT UNIQUE,
            published TEXT,
            dyad TEXT,
            language TEXT,
            embedded BOOLEAN DEFAULT 0
        )
    """)
    conn.commit()


def insert_article(conn, article, dyad, language):
    """
    把一篇文章寫進 articles 表。
    article: fetch_news_rss() 回傳的其中一筆 dict，
             包含 title, content, publisher, link, published。
    dyad:     這篇文章對應的雙邊關係代碼，例如 'CHN-JPN'。
    language: 這篇文章是用哪個語言關鍵字抓到的，例如 'zh-TW'。

    用 INSERT OR IGNORE：若 source_url 已存在（UNIQUE 撞到），
    直接跳過這筆，不會報錯中斷整個寫入流程。
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO articles
            (title, content, publisher, source_url, published, dyad, language)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        article["title"],
        article["content"],
        article["publisher"],
        article["link"],
        article["published"],
        dyad,
        language,
    ))
    conn.commit()


def insert_articles(conn, articles, dyad, language):
    """批次寫入多篇文章，回傳實際成功寫入的筆數（重複的不算）"""
    cursor = conn.cursor()
    before = cursor.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    for article in articles:
        insert_article(conn, article, dyad, language)
    after = cursor.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    return after - before


if __name__ == "__main__":
    conn = sqlite3.connect("outputs/relations.db")
    create_articles_table(conn)
    print("articles 表已建立（或已存在）")
    conn.close()