import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import urllib.parse

ua = UserAgent(fallback="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")
s = requests.Session()
s.headers["User-Agent"] = ua.random
BASE_URL = "https://judgment.judicial.gov.tw/FJUD"

resp = s.get(f"{BASE_URL}/default.aspx")
soup = BeautifulSoup(resp.text, "lxml")
vs = soup.find("input", {"id": "__VIEWSTATE"}).get("value", "")
vsg = soup.find("input", {"id": "__VIEWSTATEGENERATOR"}).get("value", "")
ev = soup.find("input", {"id": "__EVENTVALIDATION"}).get("value", "")

kw = "李四川"

# Emulate the JS cookie
s.cookies.set("JUDBOOK_onekw", urllib.parse.quote(kw), domain="judgment.judicial.gov.tw")

data = {
    "__VIEWSTATE": vs,
    "__VIEWSTATEGENERATOR": vsg,
    "__EVENTVALIDATION": ev,
    "txtKW": kw,
    "judtype": "",
    "whosearch": "0",
    "ctl00$cp_content$btnSimpleQry": "送出查詢",
}

resp = s.post(f"{BASE_URL}/default.aspx", data=data)
soup = BeautifulSoup(resp.text, "lxml")

iframe = soup.find("iframe", {"id": "iframe-data"})
if iframe and iframe.get("src"):
    iframe_src = iframe.get("src")
    print("Found iframe:", iframe_src)
    iframe_url = urllib.parse.urljoin(f"{BASE_URL}/default.aspx", iframe_src)
    
    # fetch iframe
    resp2 = s.get(iframe_url)
    soup2 = BeautifulSoup(resp2.text, "lxml")
    
    rows = soup2.select("table#jud tbody tr") or soup2.select("table#jud tr")
    print("Rows:", len(rows))
    for r in rows[:3]:
        print(r.get_text(separator=' | ', strip=True)[:200])
else:
    print("No iframe found")
