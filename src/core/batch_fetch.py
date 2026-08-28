import sqlite3
from news_fetch import fetch_news_rss
from news_db_writer import create_articles_table, insert_articles
from dyad_config import DYAD_KEYWORDS

def run_batch_fetch():
    conn = sqlite3.connect("outputs/relations.db")
    create_articles_table(conn)

    for dyad, lang_settings in DYAD_KEYWORDS.items():
        for lang, setting in lang_settings.items():        
            keyword = setting['keyword']
            country = setting['country']
            articles = fetch_news_rss(keyword=keyword, lang=lang, country=country)
            new_count = insert_articles(conn=conn, articles=articles, dyad=dyad, language=lang)
            print(f"{dyad} / {lang}: 抓到 {len(articles)} 篇，新增 {new_count} 篇")

    conn.close()

if __name__ == "__main__":
    run_batch_fetch()