import requests

url = "https://opendata.judicial.gov.tw/api/SJudgment"
params = {
    "$filter": "contains(JFULL,'邱于軒')",
    "$top": 10,
    "$format": "json",
}

try:
    print("Testing OpenData API for 邱于軒")
    resp = requests.get(url, params=params, timeout=15)
    print("OpenData Status:", resp.status_code)
    print("Content-Type:", resp.headers.get("Content-Type"))
    print("Content snippet:", resp.text[:500])
except Exception as e:
    print("Request failed:", e)
