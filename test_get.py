import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import urllib.parse

ua = UserAgent()
s = requests.Session()
s.headers["User-Agent"] = ua.random

# URL encoding the keyword
name = "邱于軒"
encoded_name = urllib.parse.quote(name)

# Attempting GET
url = f"https://judgment.judicial.gov.tw/FJUD/qryresultlst.aspx?kw={encoded_name}"
print("Fetching:", url)
resp = s.get(url, allow_redirects=True)
print("Result URL:", resp.url)

soup = BeautifulSoup(resp.text, "lxml")
iframe = soup.find("iframe", {"id": "iframe-data"})
if iframe:
    print("Found iframe:", iframe.get("src"))
else:
    print("No iframe. Text snippet:", soup.get_text()[:300])
