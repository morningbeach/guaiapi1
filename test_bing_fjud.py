from court_crawler import GoogleCourtSearcher
import requests
from bs4 import BeautifulSoup
import re

searcher = GoogleCourtSearcher()
# Hack: we use the bing searcher to search specifically for FJUD
query = "site:judgment.judicial.gov.tw 李四川"
results = searcher._bing_search(query, False)

print(f"Found {len(results)} results from Bing for site:judgment.judicial.gov.tw 李四川")
for idx, r in enumerate(results):
    print(f"{idx+1}.", r["title"])
    print("  URL:", r["url"])
    
    # Try fetching the detail page directly
    if "id=" in r["url"] or "FJUD" in r["url"]:
        try:
            resp = requests.get(r["url"], timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            content_div = soup.select_one("#jud_content") or soup.select_one(".judgement-content")
            if content_div:
                print("  => Successfully fetched full text length:", len(content_div.get_text()))
        except Exception as e:
            print("  => Failed to fetch detail:", e)
    print()
