from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document


load_dotenv()


embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-base")

system_vectorstore = Chroma(
    collection_name="system_info",
    embedding_function=embeddings,
    persist_directory="outputs/chroma_db"  
)

with open("docs/about_system.md", "r", encoding="utf-8") as f:
    content = f.read()


sections = content.split("\n## ")
documents = []
for i, section in enumerate(sections):
    if i > 0:
        section = "## " + section  
    documents.append(Document(page_content=section))

system_vectorstore.add_documents(documents)
print(f"已將 {len(documents)} 個段落存入 system_info collection")