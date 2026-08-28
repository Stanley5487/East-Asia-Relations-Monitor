# 關於 East Asia Relations Monitor
## 簡介
East Asia Relations Monitor 是一套端到端的機器學習系統，每月自動預測東亞 11 組雙邊關係
（如中日、中台、兩韓等）下個月的「合作 / 低度衝突 / 高度衝突」機率分布，並整合了一個
AI 問答助手，讓使用者能用自然語言查詢預測結果與相關新聞背景。

### 政體指標：V-Dem
模型訓練時額外納入 V-Dem（Varieties of Democracy）資料庫的政體指標，
作為特徵工程的一部分。

### 非結構化資料：新聞文章
系統另外透過 Google News RSS，依關係相關性差異化蒐集中文（繁體/簡體）、
英文、日文、韓文、越南文的新聞報導，並解析 Google News 的轉址機制取得
新聞原文的真實網址，再擷取全文存入資料庫，供 RAG 問答系統檢索使用。

## 建模方法

### 模型與特徵
使用 LightGBM 訓練三分類模型（合作 / 低度衝突 / 高度衝突），並加入
lag1（前一期）特徵，捕捉關係的時間延續性。

### 驗證方式
模型驗證採用兩種方式：
- **時序分割（Temporal Split）**：確保訓練資料的時間點早於測試資料，避免用未來
  資訊預測過去。
- **Leave-One-Dyad-Out（LODO）**：每次保留一組雙邊關係完全不參與訓練，
  測試模型對「未見過的關係組合」的泛化能力。

### 目前的模型表現
Macro ROC-AUC 約為 0.92，高度衝突（High Conflict）類別的 AUC 約為 0.938。

### 已知限制
LODO 驗證顯示，模型對訓練資料中未出現過的雙邊關係組合，泛化能力明顯較弱。
因此系統僅對這 11 組已納入訓練的雙邊關係產生預測，不對訓練範圍外的關係組合
提供預測結果。

## 自動化與部署

- 使用 GitHub Actions 排程，每月自動重新抓取資料、更新特徵、產生最新一期預測，
  不需要人工手動介入。
- 前端使用 Streamlit 建置互動式儀表板，呈現 11 組關係的預測機率與近十年歷史趨勢。
- 新聞資料的抓取與更新，同樣透過 GitHub Actions 排程自動執行。

## AI 問答助手（RAG Agent）架構

系統整合了一個基於 LangChain 的 Agent，能根據使用者問題的性質，自主判斷該查詢
哪一種資料來源：

- **結構化查詢工具**：查詢最新的預測機率數據，適合回答「現在如何」、
  「機率多少」這類量化問題。
- **新聞檢索工具**：在向量資料庫（Chroma）中做語意檢索，適合回答「為什麼」、
  「發生了什麼事」這類需要背景解釋的問題。

新聞內容透過多語言 embedding 模型（intfloat/multilingual-e5-base）轉換為向量，
讓使用者能用任一種語言提問，並檢索到不同語言的相關報導。語言模型部分使用
Groq 平台提供的 openai/gpt-oss-120b 模型進行推論。

回答時，系統會標註引用新聞的發布日期、媒體來源與原文網址，方便使用者自行查證。

## 技術棧總覽

Python、LightGBM、Optuna、GDELT/BigQuery、V-Dem、Streamlit、Plotly、
GitHub Actions、LangChain、Chroma、Groq、HuggingFace Embeddings、SQLite。
