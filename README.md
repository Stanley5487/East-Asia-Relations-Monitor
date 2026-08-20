# East Asia Relations Monitor

使用 GDELT 事件資料，每月預測東亞 11 組雙邊關係下個月的互動狀態，分為 **合作、低度衝突、高度衝突** 三類。

這是一套從資料擷取、特徵工程、模型訓練到每月預測的完整機器學習流程。模型使用 LightGBM 產生各類別的預測機率，再透過 Streamlit 將結果整理成可以直接查看的 Dashboard。

> **目前預測的 11 組雙邊關係：** 中日、中台、兩韓等。

[**查看成果網站 →**](https://east-asia-relations-monitor-s4kkyibvoyugw6ik2j6feh.streamlit.app/)

第一次開啟網站可能需要等待約 10–20 秒，讓服務重新啟動。

---

## 專案簡介

系統每月使用前一個月的完整資料，預測下一個月的雙邊關係走向。

和單純輸出一個分類結果不同，模型會同時輸出：

- 合作機率
- 低度衝突機率
- 高度衝突機率

因此使用者可以自己判斷目前的風險程度。例如模型可能認為某組關係有 60% 的低度衝突機率，但同時仍有 25% 的高度衝突機率。這種情況下，比直接顯示「低度衝突」更能保留模型的不確定性。

目前系統主要針對已訓練的 11 組雙邊關係進行預測。

---

## 系統流程

```text
GDELT / V-Dem
      │
      ▼
資料自動化擷取與整理
      │
      ▼
月度雙邊特徵
      │
      ▼
LightGBM
      │
      ▼
三類別機率預測
      │
      ▼
每月自動更新
      │
      ▼
Streamlit Dashboard
```

GitHub Actions 負責排程資料更新與預測流程，網站則負責呈現最新預測與歷史趨勢。

## Model Evaluation

模型使用時間序列方式切分資料，避免使用未來資料訓練模型後再拿來預測過去。

目前調參後的結果：

| 指標 | 結果 |
|---|---:|
| Macro ROC-AUC | 約 0.92 |
| Recall（threshold = 0.5） | 約 0.36 |
| Validation | Temporal Split |
| Generalization Check | Leave-One-Dyad-Out |

這裡有一個值得特別說明的地方：

**AUC 很高，但直接分類的 recall 並不高。**

這並不是兩個結果互相矛盾。

AUC 主要衡量模型把不同類別的樣本排序開來的能力；而 recall 會受到分類 threshold 的影響。實驗中發現模型的機率排序能力相對穩定，但直接使用預設的 0.5 threshold 並不適合目前的資料分布。

因此目前系統比較重視模型輸出的 **機率分布**，而不是只看最後被分成哪一類。


---

## Dashboard

網站目前主要分成兩個部分。

### 本月關注清單

首頁會列出 11 組雙邊關係，並特別標出模型判定風險較高的關係。

![首頁：本月關注清單與 11 組 dyad 卡片網格](assets/homepage.png)

### Dyad Detail

點進單一雙邊關係後，可以查看：

- 三種類別的預測機率
- 過去十年的實際歷史趨勢
- 該組關係的歷史變化

![Detail 頁：機率分布與十年歷史趨勢](assets/detail.png)

---

## 模型診斷與幾個實驗

這個專案過程中，有幾個結果和一開始預期的不太一樣。這些實驗也影響了最後的資料處理與模型設計。

### 1. 高度衝突的標籤不能只看「有沒有發生」

一開始的想法很直接：

> 只要某個月出現過一次高度衝突事件，就把整個月份標成高度衝突。

實際測試後發現，這樣會讓大約 **92% 的月份都被標記為高度衝突**，幾乎失去了鑑別能力。

後來改成觀察每個月「高度衝突事件佔全部事件的比例」，再使用 90 分位數作為門檻。

這樣才比較能把真正異常的月份和一般月份區分開來。

---

### 2. V-Dem 特徵的重要性很高，但不一定代表模型真的學到了政體差異

延續原本研究中的民主和平論邏輯，我加入了兩國 V-Dem 民主分數的差異作為特徵。

結果發現，這個特徵的 LightGBM gain 遠高於其他特徵。

一個可能的問題是：

> 模型是不是只是利用這個特徵辨認「這是哪一組國家」，而不是學到政體差異本身和雙邊關係之間的關聯？

因此進一步使用 **Leave-One-Dyad-Out** 進行檢驗。

不同驗證方式得到的結果並不完全一致，所以最後沒有直接把這個特徵刪掉，而是保留它，同時把這個問題記錄為模型限制之一。

目前系統主要輸出的是機率，因此除了單一分類結果之外，也保留模型對不同結果的判斷程度。

---

### 3. AUC 很高，但直接分類效果不理想

調參後 Macro AUC 約為 **0.92**，但使用預設 0.5 threshold 直接分類時，recall 只有約 **0.36**。

這個結果讓我重新檢查了 evaluation 的方式。

後來比較清楚地分開兩件事情：

- **AUC**：模型能不能把不同風險程度的樣本正確排序
- **Threshold**：什麼機率以上才要把它判成某一類

因此，目前不把 0.5 視為理所當然的最佳門檻，而是將模型的 probability output 和最後的 classification threshold 分開處理。

完整的實驗過程與數字紀錄放在 [`DEVELOG.md`](DEVELOG.md)。

---

# Limitations & Future Work

### 目前只支援 11 組已訓練的雙邊關係

目前模型主要針對這 11 組關係進行訓練與預測。

Leave-One-Dyad-Out 驗證顯示，當模型需要預測完全沒看過的新國家組合時，表現會明顯下降。

因此目前網站沒有提供其他國家組合的預測。

下一版預計先擴大到更多亞洲國家，並加入美國作為新的模型對象。

### 月度資料的樣本數有限

目前將事件資料整理成「月」為單位，因此相較於事件層級資料，最終可用的樣本數會少很多。

未來可以進一步評估：

- Weekly model
- Daily model

看看更高頻率的資料是否能提供更多有效訊號。

### 目前只預測下一個月

系統目前回答的是：

> **「下一個月可能發生什麼？」**

而不是：

> **「這個月剩下的時間會怎麼發展？」**

未來可以考慮加入不同 forecasting horizon，例如：

- Next week
- Next month
- Next 3 months

---

## 技術棧

| 類別 | 使用技術 |
|---|---|
| Programming | Python |
| Data | GDELT 2.0、BigQuery、V-Dem |
| Machine Learning | LightGBM |
| Hyperparameter Optimization | Optuna |
| Validation | Temporal Split、Leave-One-Dyad-Out |
| Visualization | Plotly |
| Dashboard | Streamlit |
| Automation | GitHub Actions |

---

## 專案結構

```
.
├── src/
│   ├── core/                  # shared logic (feature engineering, data fetching)
│   ├── training/               # training-stage scripts (batch fetch, init history, retrain)
│   ├── predict_pipeline.py     # monthly prediction pipeline
│   └── app.py                  # Streamlit app
├── notebooks/                  # full analysis process
└── DEVLOG.md                  # detailed methodology & experiment log
```

---

## 本機執行

安裝套件：

```bash
pip install -r requirements.txt
```

啟動 Streamlit：

```bash
streamlit run src/app.py
```

---

## Live Demo

[**East Asia Relations Monitor →**](https://east-asia-relations-monitor-s4kkyibvoyugw6ik2j6feh.streamlit.app/)

第一次開啟可能需要等待約 10–20 秒，讓 Streamlit 服務重新啟動。

---

## 補充
這個專案的重點不只是模型最後得到多少分數，而是從原始事件資料開始，實際處理資料定義、label imbalance、時間切分、dyad generalization，以及 probability 和 threshold 之間的差異。

目前版本仍有不少限制，但也因此把模型在實際資料上的問題記錄下來，作為後續版本調整的依據。