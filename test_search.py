import json
import logging
import sys

# 將 log 等級設為 INFO 以利觀察
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

from app import app

def test_search(name):
    print(f"\n[{name}] 開始進行 API 測試...")
    with app.test_client() as client:
        resp = client.post("/api/search", json={"name": name, "search_relatives": True, "case_type": "all"})
        print("API Status:", resp.status_code)
        try:
            data = resp.get_json()
            if data and data.get("success"):
                res_data = data["data"]
                print("\n==== 深度調查與 AI 評估結果 ====")
                print("Risk Score:", res_data["risk_assessment"]["risk_score"])
                print("Overall Risk:", res_data["risk_assessment"]["overall_risk"])
                print("Summary:\n", res_data["risk_assessment"]["summary"])
                
                print("\n==== 查扣到的判決書數量 ====")
                print("總件數:", len(res_data["court_cases"]))
                
                # Check if full_text was actually populated
                full_text_cases = [c for c in res_data["court_cases"] if c.get("full_text")]
                print("擁有全文的判決書件數:", len(full_text_cases))
                if full_text_cases:
                    print("範例全文開頭:", full_text_cases[0]["full_text"][:100] + "...")
            else:
                print("API 回傳失敗:", data)
        except Exception as e:
            print("解析回傳錯誤:", e)
            print("Text:", resp.text)

if __name__ == "__main__":
    test_search("李四川")
