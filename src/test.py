import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

load_dotenv()

embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-base")
vectorstore = Chroma(
    collection_name="news_articles",
    embedding_function=embeddings,
    persist_directory="outputs/chroma_db"
)

llm = ChatGroq(model="openai/gpt-oss-120b", groq_api_key=os.getenv("GROQ_API_KEY"))

question = "台灣和韓國關係如何"

results = vectorstore.similarity_search(question, k=5, filter={"dyad": "KOR-TWN"})

# 把每篇文章的發布日期、標題，一併組進context，讓LLM看得到
context_parts = []
for doc in results:
    published = doc.metadata.get("published", "日期不詳")
    title = doc.metadata.get("title", "")
    part = f"【發布日期：{published}】【標題：{title}】\n{doc.page_content}"
    context_parts.append(part)

context = "\n\n---\n\n".join(context_parts)

prompt = f"""根據以下新聞資料回答問題，請用繁體中文回答，並在引用內容時標註該則新聞的發布日期：

{context}

問題：{question}
"""

response = llm.invoke(prompt)
print(response.content)