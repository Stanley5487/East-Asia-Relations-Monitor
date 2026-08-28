"""
dyad_config.py
==============
11組東亞雙邊關係的新聞搜尋關鍵字設定表。
- 每組關係固定查詢「中文（繁體）」與「英文」。
- 若該組關係牽涉中國大陸，額外加上「簡體中文」關鍵字（兩岸對同一事件的
  用詞、立場經常有明顯差異，繁體中文來源多為台灣媒體視角，簡體中文來源
  能補上另一種敘事角度；但須留意 Google 在中國大陸本身被封鎖，zh-CN 抓到的
  內容不完全等同「中國官方媒體第一手報導」）。
- 若該組關係牽涉日本，額外加上「日文」關鍵字；若該組關係牽涉南／北韓，額外加上「韓文」
  關鍵字；若該組關係牽涉越南，額外加上「越南文」關鍵字。
- 不對每組關係都查詢所有語言，避免資源浪費在關聯性低的語言組合上。

lang 對應 Google News 的 hl 參數，country 對應 gl 參數：
    zh-TW -> 台灣繁中版
    zh-CN -> 中國大陸簡中版
    en-US -> 美國英文版
    ja    -> 日本日文版
    ko    -> 韓國韓文版
    vi    -> 越南文版
"""


DYAD_KEYWORDS = {
    "CHN-TWN": {
        "zh-TW": {"keyword": "中國台灣關係", "country": "TW"},
        "zh-CN": {"keyword": "中国台湾关系", "country": "CN"},
        "en-US": {"keyword": "China Taiwan relations", "country": "US"},
    },
    "CHN-JPN": {
        "zh-TW": {"keyword": "中日關係", "country": "TW"},
        "zh-CN": {"keyword": "中日关系", "country": "CN"},
        "en-US": {"keyword": "China Japan relations", "country": "US"},
        "ja": {"keyword": "日中関係", "country": "JP"},
    },
    "CHN-KOR": {
        "zh-TW": {"keyword": "中韓關係", "country": "TW"},
        "zh-CN": {"keyword": "中韩关系", "country": "CN"},
        "en-US": {"keyword": "China South Korea relations", "country": "US"},
        "ko": {"keyword": "한중 관계", "country": "KR"},
    },
    "CHN-PRK": {
        "zh-TW": {"keyword": "中國北韓關係", "country": "TW"},
        "zh-CN": {"keyword": "中国朝鲜关系", "country": "CN"},
        "en-US": {"keyword": "China North Korea relations", "country": "US"},
        "ko": {"keyword": "북중 관계", "country": "KR"},
    },
    "JPN-KOR": {
        "zh-TW": {"keyword": "日韓關係", "country": "TW"},
        "en-US": {"keyword": "Japan South Korea relations", "country": "US"},
        "ja": {"keyword": "日韓関係", "country": "JP"},
        "ko": {"keyword": "한일 관계", "country": "KR"},
    },
    "JPN-PRK": {
        "zh-TW": {"keyword": "日本北韓關係", "country": "TW"},
        "en-US": {"keyword": "Japan North Korea relations", "country": "US"},
        "ja": {"keyword": "日朝関係", "country": "JP"},
    },
    "JPN-TWN": {
        "zh-TW": {"keyword": "台日關係", "country": "TW"},
        "en-US": {"keyword": "Japan Taiwan relations", "country": "US"},
        "ja": {"keyword": "日台関係", "country": "JP"},
    },
    "KOR-PRK": {
        "zh-TW": {"keyword": "南北韓關係", "country": "TW"},
        "en-US": {"keyword": "North Korea South Korea relations", "country": "US"},
        "ko": {"keyword": "남북관계", "country": "KR"},
    },
    "KOR-TWN": {
        "zh-TW": {"keyword": "台灣韓國關係", "country": "TW"},
        "en-US": {"keyword": "Taiwan South Korea relations", "country": "US"},
        "ko": {"keyword": "대만 한국 관계", "country": "KR"},
    },
    "CHN-PHL": {
        "zh-TW": {"keyword": "中國菲律賓關係", "country": "TW"},
        "zh-CN": {"keyword": "中国菲律宾关系", "country": "CN"},
        "en-US": {"keyword": "China Philippines relations", "country": "US"},
    },
    "CHN-VNM": {
        "zh-TW": {"keyword": "中國越南關係", "country": "TW"},
        "zh-CN": {"keyword": "中国越南关系", "country": "CN"},
        "en-US": {"keyword": "China Vietnam relations", "country": "US"},
        "vi": {"keyword": "quan hệ Trung Quốc Việt Nam", "country": "VN"},
    },
}