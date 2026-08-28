"""
rag_embed.py
============
把 SQLite 裡尚未 embedding 的文章，轉成向量存進 Chroma，並把 SQLite 的 embedded 欄位標記為已處理。
embedding 的模型先選用免費的multilingual-e5-base，若效果不佳在考慮付費版模型
"""

import sqlite3
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

def get_unembedded_articles(conn):
    """從SQLite撈出還沒embedding的文章"""
    cursor = conn.cursor()
    cursor.execute("""
            SELECT article_id, title, content, publisher, source_url, published, dyad, language
            FROM articles
            WHERE embedded = 0
        """)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    return [dict(zip(columns, row)) for row in rows]


def mark_as_embedded(conn, article_ids):
    """將完成的文章標記改為已完成的embedding"""
    cursor = conn.cursor()
    for article_id in article_ids:
        cursor.execute("""
            UPDATE articles
            SET embedded = 1
            WHERE article_id = ?
        """, (article_id,))
    conn.commit()


def build_documents(articles):
    """把撈出來的文章，轉成LangChain的Document物件"""
    documents = []
    for article in articles:
        doc = Document(
           page_content = article['content'],
           metadata = {"dyad": article['dyad'], 
                       "title": article['title'],
                       "publisher": article['publisher'],
                       "published": article['published'],
                       'source':article['source_url']
            }
        )
        documents.append(doc)
    return documents

if __name__ == "__main__":
    conn = sqlite3.connect("outputs/relations.db")
    articles = get_unembedded_articles(conn)
    print(f"共有 {len(articles)} 篇文章未embedding") 
    if articles:
        documents = build_documents(articles)

        # embedding 
        embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-base")
        vectorstore = Chroma(
            collection_name = "news_articles",
            embedding_function=embeddings,
            persist_directory="outputs/chroma_db"
        )
        vectorstore.add_documents(documents)
        print("embedding完成，已存入Chroma")

        # 更新資料庫embedded狀態
        article_ids = [a["article_id"] for a in articles]
        mark_as_embedded(conn, article_ids)
        print(f"已將 {len(article_ids)} 篇文章標記為 embedded=1")

    else:
        print("沒有新文章需要處理")

    conn.close()