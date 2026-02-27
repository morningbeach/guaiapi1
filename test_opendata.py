import requests

url = "https://opendata.judicial.gov.tw/api/SJudgment"
params = {
    "$filter": "contains(JFULL,'邱于軒')",
    "$top": 5,
    "$orderby": "JDATE desc",
    "$format": "json",
}

try:
    resp = requests.get(url, params=params)
    data = resp.json()
    print("Found cases:", len(data))
    for idx, case in enumerate(data):
        print(f"{idx+1}. {case.get('JTITLE')} - {case.get('JDATE')} - {case.get('JID')}")
except Exception as e:
    print("Failed API fetch HTTP", resp.status_code)
    print("Content:", resp.text[:200])
