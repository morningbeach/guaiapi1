import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

ua = UserAgent(fallback="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")
s = requests.Session()
s.headers["User-Agent"] = ua.random

query = "site:judgment.judicial.gov.tw 邱于軒"
url = "https://www.google.com/search"
params = {"q": query, "hl": "zh-TW", "num": 10}

try:
    resp = s.get(url, params=params, timeout=10)
    soup = BeautifulSoup(resp.text, "lxml")
    
    results = soup.select("div.g, div[data-hveid]")
    print(f"Found {len(results)} FJUD results from Google for 邱于軒:")
    
    for g_div in results[:5]:
        title_tag = g_div.select_one("h3")
        if title_tag:
            print("-", title_tag.get_text(strip=True))
except Exception as e:
    print("Google search failed", e)
