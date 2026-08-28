import os
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_groq import ChatGroq
from agent_tools import query_prediction, query_news

load_dotenv()

llm = ChatGroq(model="openai/gpt-oss-120b", 
               groq_api_key=os.getenv("GROQ_API_KEY"),
               temperature=0.2)

tools = [query_prediction, query_news]

system_prompt = """
你是一個東亞地緣政治的分析助手，專門用於回答關於東亞地區的雙邊關係問題。

你有兩個工具可以使用：
1. `query_prediction`：查詢結構化的預測數據（合作/低度衝突/高度衝突機率），
   適合回答「現在如何」、「機率多少」、「目前狀態」這類純粹的數字量化問題。
2. `query_news`：查詢新聞資料庫，適合回答「為什麼」、「發生了什麼事」、
   「最近有什麼新聞」這類需要具體事件、背景解釋的問題。

請根據使用者問題的性質，選擇合適的工具：
- 如果問題只需要單一工具就能完整回答，請只呼叫該工具，不要為了「看起來更完整」而多呼叫不必要的工具。
- 如果問題確實同時需要數據和背景解釋（例如問題明確要求「說明現況並解釋原因」），才呼叫兩個工具。

回答格式請固定遵循以下結構（若某個部分沒有對應資料，可省略該部分，但不要更動其餘部分的順序與標題）：
## 現況摘要
（1-2句話總結目前狀態）

## 詳細說明
（用條列式，依主題分類說明，每點附上（「媒體」與「發布日期」））

## 參考來源
（列出引用的新聞標題、日期、完整網址，格式：-[媒體] [日期] 標題 (網址)）

回答時使用繁體中文，語氣客觀中立。

"""

agent = create_agent(llm, tools, system_prompt=system_prompt)

# test
if __name__ == "__main__":
    print("Agent已啟動，輸入問題開始對話（輸入 exit 結束）")
    print("-" * 40)
    
    while True:
        question = input("你的問題：")
        if question.lower() in ["exit", "quit", "q"]:
            print("結束測試")
            break
        
        response = agent.invoke({"messages": [{"role": "user", "content": question}]})
        print("\nAgent回答：")
        print(response["messages"][-1].content)
        print("-" * 40)