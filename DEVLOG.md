## EDA

### 資料範圍
- Dyad：e.g. CHN ↔ TWN（雙向）
- 時間範圍：2023-01-01 ～ 2025-12-31（先用小範圍做 EDA，建模採用的是 2015-2025）
- 資料來源：GDELT 2.0 events（BigQuery `gdelt-bq.gdeltv2.events`）
- 總筆數：165,047

### GDELT
1. 事件數量存在一定差異(月)：2023-04 為全期最高峰（16,695 筆，約為月均值的 3-4 倍），2024-01 為次高峰（9,300 筆），其餘月份大致落在 2,000-6,000 筆區間
2. 事件數量與衝突加劇不一定存在因果關係：
    - 2023-04：GoldsteinScale 月均 -0.753，QuadClass 4（物質衝突）佔比 18.3% → 數量暴增與性質轉向衝突「同步發生」
    - 2024-01：GoldsteinScale 月均 +0.103（中性偏正），QuadClass 4 佔比僅 8.9% → 數量暴增但性質偏言論/中性
    - 2025-07：GoldsteinScale 月均 -1.189（全期最低），QuadClass 4 佔比 19.75%；2025-12：GoldsteinScale 月均 -1.109（全期次低），QuadClass 4 佔比 18.9%。但事件總數在這兩個月並未特別突出 → 代表僅看事件數量會漏掉這類「安靜但緊張」的模式
    - 邏輯來看，這本來就不太意外，因為事件增加，也有可能是正向事件增加

---

## LGBM Model A（不含 `regime_diff`）

**Classification Report**

| 版本 | HC Recall | LC Recall | Precision | F1 | Test Accuracy | 訓練/測試落差 |
|---|---|---|---|---|---|---|
| LGBM 原始參數 | 0.36 | 0.59 | 0.53 | 0.43 | 0.79 | 大，過擬合 |
| LGBM 調參 | 0.52 | 0.67 | 0.62 | 0.57 | 0.83 | 縮小至0.05，過擬合大幅改善 |
| LGBM 調參 + 完全加權 | **0.75** | **0.71** | 0.59 | **0.66** | 0.82 | 穩定 |
| LGBM 調參 + 開根號加權 | 0.59 | 0.67 | 0.55 | 0.57 | 0.82 | 穩定，但 F1 未優於完全加權 |

**AUC**

| 版本 | Macro AUC | Cooperation AUC | High_Conflict AUC | Low_Conflict AUC |
|---|---|---|---|---|
| LGBM 原始參數 | 0.920 | 0.941 | 0.939 | 0.879 |
| LGBM 調參 + 開根號加權 | 0.911 | 0.944 | 0.928 | 0.860 |
| LGBM 調參 + 完全加權（最終選定） | 0.917 | 0.944 | 0.935 | 0.873 |

**資料切分邏輯**：時間切分（非隨機切分，因資料具時間序列與 panel 特性），以 2023-01 為界，之前為訓練集（1,044 筆），之後為測試集（396 筆）。之後可嘗試 Walk-Forward Validation。

**加權策略比較**：原先預期開根號加權會在「不加權」與「完全加權」間取得更好平衡，但實測結果 F1 與不加權版本打平，兩者皆低於完全加權版本。顯示對此資料集而言，直接使用類別頻率完全反比的加權方式即為目前測試範圍內的最佳選擇，而非越保守/越精緻的調整必然越好。

**關鍵發現**：三個版本的 AUC 差距極小（Macro AUC 皆落在 0.91-0.92），但 recall/precision 在不同加權策略下差距很大（如 High_Conflict recall 從 0.36 到 0.75）。這代表模型本身區分「像不像 High_Conflict」的排序能力，從頭到尾都相當穩定良好；class_weight/sample_weight 加權策略改變的主要是「最終判斷門檻的敏感度」，而非模型底層的學習能力。也就是說，問題不在模型學得好不好（AUC 已證實學得不錯），而在於「用什麼門檻把機率轉換成最終標籤」這個決策層面的選擇——這代表未來可透過 threshold tuning，在不重新訓練模型的前提下於 recall/precision 間找到更精確的平衡點。或者未來預測改採輸出機率的方式而不強制分類，機率輸出可避免單一門檻選擇造成的資訊損失，讓使用者自行判讀風險程度。

> 這個調參只是先大致修正預設參數，之後透過 Optuna 進行更精細的調參。

---

## VDEM

根據民主和平論，政體性質差異越大的兩國，理論上衝突傾向越高。本預測系統加入 V-Dem 的自由民主指數（`v2x_libdem`），計算兩國政體差異（`regime_diff = |分數差|`），作為 dyad 層級的結構性特徵，補充 GDELT 逐月動態特徵沒辦法捕捉到的「這組關係天生的基準傾向」。

不過實測後發現，在只有 11 組 dyad 的樣本下，這個變數的 gain 遠高於其他特徵，懷疑模型可能只是學到「看到某個 regime_diff 數值就認出是哪組 dyad」，而不是真正學到政體差異的效果。用 Leave-One-Dyad-Out 驗證後，發現結果其實不一致（時間切分驗證下表現變差，LODO 驗證下反而略好）。最後決定保留這個特徵，主要考量是模型最終要輸出機率而非硬分類，AUC 顯示底層判斷力沒有明顯受影響。

---

## LGBM Model B（加入 `regime_diff`）

### 資料處理
- V-Dem Country-Year Core 資料集，篩選 CHN/TWN/JPN/KOR/PRK/PHL/VNM 共 7 國
- `regime_diff = |國家A v2x_libdem - 國家B v2x_libdem|`
- 年度資料以 `merge_asof`（LOCF 邏輯）合併回月度特徵，避免年份缺值

### Model A vs Model B 對照（時間切分驗證）

| 版本 | HC Recall | LC Recall | HC Precision | Macro AUC |
|---|---|---|---|---|
| Model A（無 regime_diff） | 0.75 | 0.71 | 0.59 | 0.917 |
| Model B（含 regime_diff） | 0.61 | 0.72 | 0.56 | 0.894 |

### Feature Importance 診斷
`regime_diff` 的 gain 遠高於其他特徵（5848 vs 第二名的 4218），懷疑模型把它當成「認出是哪組 dyad」的身份標籤在用，而非真正學到政體差異的效果。

### Leave-One-Dyad-Out 驗證
每次留一組 dyad 完全不參與訓練，測試泛化能力：

| 版本 | 平均 recall_macro |
|---|---|
| 含 regime_diff | 0.461 |
| 不含 regime_diff | 0.442 |

結果跟時間切分驗證方向相反——證據不一致，可能反映 11 組 dyad 的樣本量本身不足以支撐這類判斷。

### 最終決定
保留 `regime_diff`。主要理由是最終產品採機率輸出（而非強制分類），AUC 顯示底層判斷力沒有明顯受影響（0.917 → 0.894，差距不大），且 recall/precision 的變化本質上是門檻選擇的問題，可透過 threshold tuning 調整。

### Optuna 調參 + Threshold Tuning
- Optuna 改用 AUC 當目標，weight_power 也交給它搜尋 → 找到 0.30（接近不加權）
- Test Macro AUC 0.918，比之前手動調參略高
- 但 `predict()` 預設 0.5 門檻下 recall 很低（HC 0.36, LC 0.35），因為機率普遍壓低
- 掃描門檻後找到較佳點：
  - HC 門檻 0.225：recall 0.705, precision 0.620, f1 0.660
  - LC 門檻 0.275：recall 0.713, precision 0.726, f1 0.720
- 跟之前手動調參版本打平略優，定案採用這組

這裡呼應前面的觀察：AUC 高不代表 `predict()` 直接分類就好用，問題不在模型學得好不好，而在「用什麼門檻把機率轉成標籤」——這也是最後決定改用機率輸出、搭配這組門檻做輔助分類的原因。

---

## 2026-08-18 — 首次 End-to-End 預測成功

成功執行完整預測流程：資料抓取 → 特徵工程 → 合併政體差異 → 模型預測 → 產出結果。用 2026 年 7 月的完整資料，預測 2026 年 8 月的關係走向。

| Dyad | Cooperation | Low Conflict | High Conflict | 預測標籤 |
|---|---|---|---|---|
| CHN-JPN | 53.0% | 34.0% | 13.0% | Low_Conflict |
| CHN-TWN | 40.0% | 50.5% | 9.5% | Low_Conflict |
| CHN-PRK | 78.9% | 13.3% | 7.8% | Cooperation |
| CHN-PHL | 53.3% | 34.4% | 12.3% | Low_Conflict |
| CHN-VNM | 79.0% | 13.1% | 7.8% | Cooperation |
| JPN-PRK | 58.8% | 26.4% | 14.8% | Cooperation |
| JPN-KOR | 79.0% | 13.1% | 7.8% | Cooperation |
| JPN-TWN | 79.0% | 13.1% | 7.8% | Cooperation |
| CHN-KOR | 78.7% | 13.3% | 8.1% | Cooperation |
| KOR-PRK | 61.7% | 24.7% | 13.5% | Cooperation |
| KOR-TWN | 79.0% | 13.1% | 7.8% | Cooperation |


###　2026-08-20 BigQuery查詢優化

發現這幾天測試 GitHub Actions 期間，BigQuery 帳單累積到近萬元台幣（雖然都在抵免額範圍內），排查後找到根本原因：

**問題一：沒有使用分區表**
原本查詢的是 `gdelt-bq.gdeltv2.events`（非分區版本），該表沒有分區設定，
`WHERE SQLDATE >= ... AND SQLDATE <= ...` 這種篩選完全無法讓 BigQuery 跳過不相關資料，
等同全表掃描。實測不管查一天還是查十年，預估掃描量都是同一個數字（366.6 GB），
證實了掃描量根本沒有隨時間範圍縮小而減少。

改用 GDELT 官方提供的分區版本表 `gdelt-bq.gdeltv2.events_partitioned`，
搭配 `_PARTITIONTIME` 篩選語法後，同樣查詢（半年、單一dyad）掃描量降到 11.9 GB，
減少約 31 倍。

**問題二：SELECT \* 讀取了用不到的欄位**
原始表有 62 個欄位，但 `build_feature()` 實際只用到 8 個。
把 `SELECT *` 改成明確列出必要欄位後，掃描量從 11.9 GB 再降到 1.65 GB。

**問題三：用迴圈對 12 組 dyad 各自查詢一次**
原本 `for actor1, actor2 in DYAD_LIST` 逐一查詢，12 次相當於 12 倍掃描成本。
改用 `Actor1CountryCode IN (...) AND Actor2CountryCode IN (...)`，
一次查詢涵蓋所有國家兩兩配對，實測掃描量依然是 1.65 GB——
與查單一組完全相同，證實掃描成本主要來自「讀取這段時間的分區資料」，
篩選條件的複雜度幾乎不影響掃描量。

**三項優化疊加效果**

| 版本 | 單次查詢掃描量 |
|---|---|
| 原始（非分區 + SELECT * + 12次迴圈） | 366.6 GB × 12 ≈ 4,399 GB |
| + 改用分區表 | 11.9 GB × 12 ≈ 143 GB |
| + 只選必要欄位 | 1.65 GB × 12 ≈ 19.8 GB |
| + 一次查詢取代迴圈 | **1.65 GB** |

總計掃描量從約 4,399 GB 降到 1.65 GB，減少約 **2,666 倍**。
換算費用，一次完整 pipeline 執行從原本約 670 元台幣，降到約 0.25 元台幣。

最後在 `fetch_all_dyads_events()` 加上 `maximum_bytes_billed=5GB` 的流量限制，
無論未來程式碼是否有其他潛在問題，單次查詢都會被強制限制在 5GB 以內，
超過直接報錯，避免重演這次的意外高額掃描。

**參考資料**：https://blog.gdeltproject.org/announcing-partitioned-gdelt-bigquery-tables/