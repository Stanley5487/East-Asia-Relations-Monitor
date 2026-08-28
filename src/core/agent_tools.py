import os
from dotenv import load_dotenv
from langchain.tools import tool
import sqlite3
import sqlite3
from langchain.tools import tool
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

load_dotenv()

_embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-base")
_vectorstore = Chroma(
    collection_name="news_articles",
    embedding_function=_embeddings,
    persist_directory="outputs/chroma_db"
)
_last_sources = {} 


@tool
def query_prediction(dyad: str) -> str:
    """
    查詢指定雙邊關係(dyad)目前的預測結果，包含合作/低度衝突/高度衝突的機率。
    dyad格式範例：'CHN-JPN', 'CHN-TWN', 'KOR-TWN' 等。
    當使用者詢問「現在」、「目前」、「最新預測」等趨勢性問題時使用這個工具。
    """
    conn = sqlite3.connect("outputs/relations.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT predicted_label, Cooperation_proba, Low_Conflict_proba, High_Conflict_proba, forecast_month
        FROM predictions
        WHERE dyad = ?
    """, (dyad,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return f"找不到 {dyad} 這組關係的預測資料。"

    label, coop, low, high, month = row
    return (
        f"{dyad} 在 {month} 的預測結果為「{label}」，"
        f"合作機率 {coop*100:.1f}%，低度衝突機率 {low*100:.1f}%，高度衝突機率 {high*100:.1f}%。"
    )

@tool
def query_news(question: str, dyad: str) -> str:
    """
    根據問題，在指定雙邊關係(dyad)的新聞資料庫裡做語意檢索，
    回傳最相關的幾篇新聞內容，並用[新聞1]、[新聞2]等代號標記。
    回答時請直接引用這些代號（例如：日本議員團訪華[新聞1]），
    不需要自己生成或複製網址，系統會自動在回答最後補上正確的參考來源。
    當使用者詢問「為什麼」、「原因」、「發生什麼事」等需要背景解釋的問題時使用這個工具。
    dyad格式範例：'CHN-JPN', 'CHN-TWN', 'KOR-TWN' 等。
    """
    global _last_sources
    _last_sources.clear()

    results = _vectorstore.similarity_search(question, k=5, filter={"dyad": dyad})
    context_parts = []
    for i, doc in enumerate(results, start=1):
        tag = f"[新聞{i}]"
        published = doc.metadata.get("published", "日期不詳")
        title = doc.metadata.get("title", "")
        publisher = doc.metadata.get("publisher", "來源不詳")
        source = doc.metadata.get("source", "")
        content = doc.page_content[:500]

        _last_sources[tag] = {
            "title": title,
            "publisher": publisher,
            "published": published,
            "url": source,
        }

        part = f"{tag} 【發布日期：{published}】【媒體：{publisher}】【標題：{title}】\n{content}"
        context_parts.append(part)

    context = "\n\n---\n\n".join(context_parts)
    return context

if __name__ == "__main__":
    # 測試query_prediction
    result1 = query_prediction.invoke({"dyad": "CHN-JPN"})
    print(result1)

    # 測試query_news
    result2 = query_news.invoke({"question": "台韓關係如何", "dyad": "KOR-TWN"})
    print(result2)
