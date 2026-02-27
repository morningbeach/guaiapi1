import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

ua = UserAgent(fallback="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")
s = requests.Session()
s.headers["User-Agent"] = ua.random

resp = s.get("https://judgment.judicial.gov.tw/FJUD/default.aspx")
soup = BeautifulSoup(resp.text, "lxml")
vs = soup.find("input", {"id": "__VIEWSTATE"})["value"]
vsg = soup.find("input", {"id": "__VIEWSTATEGENERATOR"})["value"]
ev = soup.find("input", {"id": "__EVENTVALIDATION"})["value"]

data = {
    "__VIEWSTATE": vs,
    "__VIEWSTATEGENERATOR": vsg,
    "__EVENTVALIDATION": ev,
    "txtKW": "邱于軒",
    "judtype": "",
    "whosearch": "0",
    "ctl00$cp_content$btnSimpleQry": "送出查詢",
}

resp = s.post("https://judgment.judicial.gov.tw/FJUD/default.aspx", data=data)
soup = BeautifulSoup(resp.text, "lxml")

for tr in soup.find_all("tr"):
    print("--TR--")
    print(tr.get_text(separator=' | ', strip=True).encode('utf-8').decode('utf-8')[:200])
