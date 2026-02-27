import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

ua = UserAgent(fallback="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")
s = requests.Session()
s.headers.update({
    "User-Agent": ua.random,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
    "Origin": "https://judgment.judicial.gov.tw",
    "Referer": "https://judgment.judicial.gov.tw/FJUD/default.aspx",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
})

BASE_URL = "https://judgment.judicial.gov.tw/FJUD"

# 1. GET initial page and set cookies
print("Fetching default.aspx...")
resp1 = s.get(f"{BASE_URL}/default.aspx")
soup = BeautifulSoup(resp1.text, "lxml")
vs = soup.find("input", {"id": "__VIEWSTATE"}).get("value", "")
vsg = soup.find("input", {"id": "__VIEWSTATEGENERATOR"}).get("value", "")
ev = soup.find("input", {"id": "__EVENTVALIDATION"}).get("value", "")
print("Got hidden fields")

kw = "邱于軒"

data = {
    "__VIEWSTATE": vs,
    "__VIEWSTATEGENERATOR": vsg,
    "__EVENTVALIDATION": ev,
    "txtKW": kw,
    "judtype": "",
    "whosearch": "0",
    "ctl00$cp_content$btnSimpleQry": "送出查詢",
}

print("POSTing search...")
resp2 = s.post(f"{BASE_URL}/default.aspx", data=data)
soup = BeautifulSoup(resp2.text, "lxml")

iframe = soup.find("iframe", {"id": "iframe-data"})
if iframe and iframe.get("src"):
    iframe_src = iframe.get("src")
    print("Found iframe:", iframe_src)
else:
    print("No iframe found.")
