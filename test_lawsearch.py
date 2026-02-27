import requests

url = "https://lawsearch.judicial.gov.tw/default.aspx"
try:
    print("Testing lawsearch.judicial.gov.tw")
    # Lawsearch might also have viewstate...
    resp = requests.get(url, timeout=15)
    print("Status:", resp.status_code)
    print("Content snippet:", resp.text[:500])
except Exception as e:
    print("Request failed:", e)
