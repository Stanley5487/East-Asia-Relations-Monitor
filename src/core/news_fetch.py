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

_session = requests.Session()
_session.headers.update(_HEADERS)

_decode_cache = {}
_DECODE_WORKERS = 8
_FETCH_WORKERS = 8  # 抓全文也是I/O bound，一樣用平行處理


def _extract_base64_id(google_news_url):
    """從 Google News 的 rss/articles 或 read 連結取出後面那段 base64 id"""
    path = urlparse(google_news_url).path.split("/")
    if len(path) > 1 and path[-2] in ("articles", "read"):
        return path[-1]
    return None


def decode_google_news_url(google_news_url, timeout=10):
    """將 Google News RSS 的轉址連結，換成新聞原文的真實網址。"""
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

        parsed = json.loads(api_resp.text.split("\n\n")[1])
        real_url = json.loads(parsed[0][2])[1]
    except Exception as e:
        print(f"[decode_google_news_url] 解碼失敗，改用原始連結：{e}")

    _decode_cache[base64_str] = real_url
    return real_url


def _fetch_full_text(url, lang_code):
    """
    用 newspaper3k 抓全文，失敗時回傳 None（不中斷整體流程）。
    lang_code 是我們自己定義的語言代碼（如 'zh-TW', 'ja'），
    newspaper3k 只認識前兩碼的語言代碼，這裡做個簡單轉換。
    """
    newspaper_lang = lang_code.split("-")[0]  # 'zh-TW' -> 'zh', 'en-US' -> 'en'
    try:
        article = Article(url, language=newspaper_lang)
        article.download()
        article.parse()
        text = article.text.strip()
        return text if text else None
    except Exception as e:
        print(f"[_fetch_full_text] 抓全文失敗（{url}）：{e}")
        return None


def fetch_news_rss(keyword, lang="zh-TW", country="TW", days=7):
    """
    抓取Google News RSS訊息，將轉址連結解析回真實網址，並抓取每篇文章的全文。
    回傳的每筆資料包含：title, publisher, content, link, published
    """
    url = f"https://news.google.com/rss/search?q={keyword}+when:{days}d&hl={lang}&gl={country}&ceid={country}:{lang}"
    feed = feedparser.parse(url)
    entries = feed.entries

    # 第一步：平行解析出每篇文章的真實網址
    with ThreadPoolExecutor(max_workers=_DECODE_WORKERS) as pool:
        real_links = list(pool.map(decode_google_news_url, (entry.link for entry in entries)))

    # 第二步：平行抓取每個真實網址的全文
    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        contents = list(pool.map(lambda u: _fetch_full_text(u, lang), real_links))

    articles = []
    for entry, real_link, content in zip(entries, real_links, contents):
        if content is None:
            # 全文抓不到就跳過這篇，不存進資料庫（也可以選擇改成存標題當備案）
            continue
        articles.append({
            "title": entry.title,
            "publisher": entry.source.title,
            "content": content,
            "link": real_link,
            "published": entry.published,
        })
    return articles


if __name__ == "__main__":
    results = fetch_news_rss("中日關係", days=7)
    print(f"共抓到 {len(results)} 篇有全文的新聞")
    if results:
        print(results[5]["title"])
        print(results[5]["content"][:300])