import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

url = "https://judgment.judicial.gov.tw/FJUD/data.aspx?ty=JD&id=TNDM,114%2C%E6%98%93%2C2725%2C20250226"
ua = UserAgent(fallback="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")
s = requests.Session()
s.headers["User-Agent"] = ua.random

try:
    print(f"Fetching {url}")
    resp = s.get(url, timeout=10)
    print("Status:", resp.status_code)
    soup = BeautifulSoup(resp.text, "lxml")
    content = soup.select_one(".judgement-content, #jud_content")
    if content:
        print("Success! Got full text length:", len(content.get_text()))
        print("Snippet:", content.get_text()[:200].replace('\n', ' '))
    else:
        print("Failed to get content. Snippet:", resp.text[:200])
except Exception as e:
    print("Failed", e)
