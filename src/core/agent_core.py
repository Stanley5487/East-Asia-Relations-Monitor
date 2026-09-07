import os
import re
from datetime import datetime
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_groq import ChatGroq
from agent_tools import query_prediction, query_news, query_system_info, _last_sources

load_dotenv()

# 預設使用能力最強的模型；若當日流量/token額度用盡，會自動切換到備用模型繼續服務
PRIMARY_MODEL = "openai/gpt-oss-120b"
FALLBACK_MODEL = "openai/gpt-oss-20b"

tools = [query_prediction, query_news, query_system_info]

system_prompt = """
你是一個東亞地緣政治的分析助手，專門用於回答關於東亞地區的雙邊關係問題。

你有3個工具可以使用：
1. `query_prediction`：查詢結構化的預測數據（合作/低度衝突/高度衝突機率），
   適合回答「現在如何」、「機率多少」、「目前狀態」這類純粹的數字量化問題。
2. `query_news`：查詢新聞資料庫，適合回答「為什麼」、「發生了什麼事」、
   「最近有什麼新聞」這類需要具體事件、背景解釋的問題。
3. `query_system_info`：查詢本系統自身的技術架構、資料來源、建模方法等資訊，
   適合回答「這個系統怎麼做的」、「模型怎麼訓練的」這類關於系統本身的問題。

呼叫query_prediction或query_news時，dyad參數必須使用以下確切格式，
不論使用者提及兩個地區的先後順序為何，都要對應到以下正確代碼，不要自行調換順序：
CHN-TWN（中國/台灣）、CHN-JPN（中國/日本）、CHN-KOR（中國/南韓）、
CHN-PRK（中國/北韓）、JPN-KOR（日本/南韓）、JPN-PRK（日本/北韓）、
JPN-TWN（日本/台灣）、KOR-PRK（南韓/北韓）、KOR-TWN（南韓/台灣）、
CHN-PHL（中國/菲律賓）、CHN-VNM（中國/越南）

回答格式依問題類型而定：
**若問題是關於東亞雙邊關係（使用query_prediction或query_news回答）**，
請遵循以下結構：
- 如果問題只需要單一工具就能完整回答，請只呼叫該工具，不要為了「看起來更完整」而多呼叫不必要的工具。
- 如果問題確實同時需要數據和背景解釋，才呼叫兩個工具。

## 現況摘要
（1-2句話總結目前狀態）

## 詳細說明
（用條列式，依主題分類說明，每點請直接引用對應的[新聞X]代號標記來源，
   例如：某某事件[新聞1]。不需要自己寫參考來源區塊，系統會自動補上。）

**若問題是關於系統本身（使用query_system_info回答）**，
請直接用條列式清楚說明，不需要套用「現況摘要」這種格式，
可以視內容需要自行安排標題（例如：## 系統架構、## 建模方法等）

若引用query_prediction的數據，請在該處標註「【本專案數據】」，
不要直接寫出工具的程式碼名稱（例如query_prediction）。

回答時使用繁體中文，語氣客觀中立。
"""

def _build_agent(model_name: str):
    llm = ChatGroq(model=model_name,
                    groq_api_key=os.getenv("GROQ_API_KEY"),
                    temperature=0.2)
    return create_agent(llm, tools, system_prompt=system_prompt)


agent = _build_agent(PRIMARY_MODEL)
_fallback_agent = _build_agent(FALLBACK_MODEL)


def _is_rate_limit_error(e: Exception) -> bool:
    err_text = str(e).lower()
    return "rate_limit" in err_text or "429" in err_text or "tokens per" in err_text


def invoke_with_fallback(messages: list) -> tuple:
    """
    預設用最強的主要模型回答；若主要模型當下流量/token已達上限，
    自動切換到備用模型重試這一次請求，讓使用者不會完全無法使用。
    回傳 (response, used_fallback)。若備用模型也失敗，則會提醒使用者錯誤。
    """
    try:
        return agent.invoke({"messages": messages}), False
    except Exception as e:
        if not _is_rate_limit_error(e):
            raise
        return _fallback_agent.invoke({"messages": messages}), True


def parse_date_to_apa(raw_date: str) -> str:
    """把RSS原始日期格式，轉成APA格式需要的『年, 月日』"""
    try:
        dt = datetime.strptime(raw_date, "%a, %d %b %Y %H:%M:%S %Z")
        return dt.strftime("%Y, %m月%d日")
    except (ValueError, TypeError):
        return raw_date


def format_sources(answer_text: str) -> tuple:
    """
    掃描回答文字裡引用了哪些新聞編號，組成APA格式的參考來源清單
    修正:編號顯示跳號問題
    """
    numbers_used = re.findall(r"新聞(\d+)", answer_text)
    numbers_used = sorted(set(numbers_used), key=int)

    if not numbers_used:
        return answer_text, ""

    # 建立「原始編號 -> 連續新編號」的對照表(因最初只會顯示其內部檢索的編號，使用者閱讀起來會很奇怪)
    renumber_map = {old: str(new) for new, old in enumerate(numbers_used, start=1)}

    # 把內文裡的舊編號，替換成連續的新編號
    def replace_number(match):
        old_num = match.group(1)
        return f"新聞{renumber_map[old_num]}"

    fixed_answer = re.sub(r"新聞(\d+)", replace_number, answer_text)

    lines = ["\n\n## 參考來源"]
    for old_num in numbers_used:
        new_num = renumber_map[old_num]
        tag = f"[新聞{old_num}]"
        info = _last_sources.get(tag)
        if info:
            apa_date = parse_date_to_apa(info["published"])
            lines.append(f"- **[新聞{new_num}]** {info['publisher']}. ({apa_date}). {info['title']}. {info['url']}")

    sources_text = "\n\n".join(lines)
    return fixed_answer, sources_text


if __name__ == "__main__":
    print("Agent已啟動，輸入問題開始對話（輸入 exit 結束）")
    print("-" * 40)

    while True:
        question = input("你的問題：")
        if question.lower() in ["exit", "quit", "q"]:
            print("結束測試")
            break

        response = agent.invoke({"messages": [{"role": "user", "content": question}]})
        answer = response["messages"][-1].content

        fixed_answer, sources = format_sources(answer)
        final_answer = answer + sources

        print("\nAgent回答：")
        print(final_answer)
        print("-" * 40)