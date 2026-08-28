import json
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlparse

import feedparser
from newspaper import Article
import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# 重用 TCP/TLS 連線，同網域的多次請求不用每次重新握手
_session = requests.Session()
_session.headers.update(_HEADERS)

# Google News 的 RSS 連結是「轉址頁」，同一顆 base64 id 短時間內解碼結果不會變，
# 用 cache 避免同一次抓取重複打 batchexecute
_decode_cache = {}

# 解碼是網路 I/O bound，平行打請求換取速度；數字抓保守一點避免被 Google 暫時限流
_DECODE_WORKERS = 8


def _extract_base64_id(google_news_url):
    """從 Google News 的 rss/articles 或 read 連結取出後面那段 base64 id"""
    path = urlparse(google_news_url).path.split("/")
    if len(path) > 1 and path[-2] in ("articles", "read"):
        return path[-1]
    return None


def decode_google_news_url(google_news_url, timeout=10):
    """
    將 Google News RSS 的轉址連結，換成新聞原文的真實網址。

    做法：Google 從2024年起把 base64 id 加上簽章，不能直接解碼，
    必須先 GET 轉址頁拿到頁面裡的 data-n-a-sg（簽章）、data-n-a-ts（timestamp），
    再拿這兩個值去打 Google 內部的 batchexecute API 換回原始網址。

    解碼失敗時回傳原本的 google_news_url，不中斷整體流程。
    """
    base64_str = _extract_base64_id(google_news_url)
    if not base64_str:
        return google_news_url

    if base64_str in _decode_cache:
        return _decode_cache[base64_str]

    real_url = google_news_url
    try:
        resp = _session.get(google_news_url, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        div = soup.select_one("c-wiz > div")
        if div is None:
            raise ValueError("找不到含簽章的 div，Google 頁面結構可能又變了")

        signature = div.get("data-n-a-sg")
        timestamp = div.get("data-n-a-ts")
        if not signature or not timestamp:
            raise ValueError("找不到 data-n-a-sg / data-n-a-ts")

        payload = [
            "Fbv4je",
            (
                '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",'
                'null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],'
                f'1,1,null,0,0,null,0],"{base64_str}",{timestamp},"{signature}"]'
            ),
        ]
        data = f"f.req={quote(json.dumps([[payload]]))}"
        api_headers = {
            **_HEADERS,
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        }
        api_resp = _session.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute",
            headers=api_headers,
            data=data,
            timeout=timeout,
        )
        api_resp.raise_for_status()

        # 回應前兩行是防注入用的 )]}'，真正的資料從第三行開始
        parsed = json.loads(api_resp.text.split("\n\n")[1])
        real_url = json.loads(parsed[0][2])[1]
    except Exception as e:
        print(f"[decode_google_news_url] 解碼失敗，改用原始連結：{e}")

    _decode_cache[base64_str] = real_url
    return real_url


def fetch_news_rss(keyword, lang="zh-TW", country="TW", days=7):
    """
    固定抓取Google News RSS訊息，並將每篇文章的轉址連結解析回原文真實網址
    使用方法：關鍵字、語言
    """
    url = f"https://news.google.com/rss/search?q={keyword}+when:{days}d&hl={lang}&gl={country}&ceid={country}:{lang}"
    feed = feedparser.parse(url)
    entries = feed.entries

    # 解碼是網路 I/O bound（大部分時間在等 Google 回應），平行處理換取速度
    with ThreadPoolExecutor(max_workers=_DECODE_WORKERS) as pool:
        real_links = list(pool.map(decode_google_news_url, (entry.link for entry in entries)))

    articles = []
    for entry, real_link in zip(entries, real_links):
        soup = BeautifulSoup(entry.summary, 'html.parser')
        clean_summary = soup.get_text()
        articles.append({
            "title": entry.title,
            "publisher": entry.source.title,
            "summary": clean_summary,
            "link": real_link,
            "published": entry.published
    })
    return articles

feed_test = feedparser.parse(
    "https://news.google.com/rss/search?q=中日關係+when:7d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
)
first_entry = feed_test.entries[0]
print("原始連結:", first_entry.link)
real_url = decode_google_news_url(first_entry.link)
print("解析後連結:", real_url)

from newspaper import Article

article = Article(real_url, language='zh')
article.download()
article.parse()

print("標題:", article.title)
print("內文前300字:", article.text)