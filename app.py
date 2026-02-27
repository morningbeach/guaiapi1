"""
台灣公眾人物前科查詢機 - Flask 主應用程式
==========================================
功能：
1. 輸入公眾人物姓名
2. 自動搜尋其近親
3. 爬取司法院公開裁判書資料
4. 以 AI 分析並評估風險等級
"""
import logging
from flask import Flask, render_template, request, jsonify

from config import Config
from court_crawler import CourtCrawler, GoogleCourtSearcher
from relative_finder import RelativeFinder
from ai_analyzer import AIAnalyzer

# ─── 日誌設定 ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Flask 應用程式 ───
app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# ─── 初始化模組 ───
court_crawler = CourtCrawler()
google_searcher = GoogleCourtSearcher()
relative_finder = RelativeFinder()
ai_analyzer = AIAnalyzer()


# ─── 路由 ───

@app.route("/")
def index():
    """首頁"""
    return render_template("index.html")


@app.route("/api/search", methods=["POST"])
def search():
    """
    主要搜尋 API

    Request JSON:
        {
            "name": "公眾人物姓名",
            "search_relatives": true,
            "case_type": "all"
        }

    Response JSON:
        {
            "success": true,
            "data": {
                "name": "...",
                "court_cases": [...],
                "relatives": [...],
                "news_results": [...],
                "risk_assessment": {...}
            }
        }
    """
    try:
        data = request.get_json()
        if not data or not data.get("name"):
            return jsonify({"success": False, "error": "請輸入姓名"}), 400

        name = data["name"].strip()
        search_relatives = data.get("search_relatives", True)
        case_type = data.get("case_type", "all")

        if len(name) < 2 or len(name) > 10:
            return jsonify({"success": False, "error": "姓名長度應為 2-10 個字"}), 400

        logger.info(f"開始查詢：{name}")

        # ═══════════════════════════════════════════════════
        # Step 1: 搜尋近親
        # ═══════════════════════════════════════════════════
        relatives = []
        if search_relatives:
            logger.info(f"正在搜尋 {name} 的近親...")
            relatives_obj = relative_finder.find_relatives(name)
            relatives = [r.to_dict() for r in relatives_obj]
            logger.info(f"找到 {len(relatives)} 位近親")

        # ═══════════════════════════════════════════════════
        # Step 2: 階段一 — 廣泛名單探索（僅抓取列表標題與摘要）
        # ═══════════════════════════════════════════════════
        logger.info(f"【階段一】正在搜尋 {name} 的法院裁判書列表...")
        court_cases_obj = court_crawler.search_by_name(name, case_type)
        court_cases = [c.to_dict() for c in court_cases_obj]

        # 過濾掉明顯的假資料（例如「法學資料檢索系統」的測試頁面）
        court_cases = [
            c for c in court_cases 
            if "法學資料檢索系統" not in str(c.get("case_number", ""))
        ]

        logger.info(f"【階段一】找到 {len(court_cases)} 筆法院記錄")

        # 統計刑事 / 民事案件數量
        criminal_keywords = ["刑事", "上訴", "簡", "訴", "金訴", "金簡", "原訴", "原簡", "軍訴"]
        criminal_count = 0
        civil_count = 0
        for c in court_cases:
            cn = str(c.get("case_number", ""))
            ct = str(c.get("case_type", ""))
            if ct == "刑事" or "刑事" in cn or any(kw in cn for kw in criminal_keywords):
                criminal_count += 1
            else:
                civil_count += 1

        # ═══════════════════════════════════════════════════
        # Step 2.5: 檢查 > 15 筆高風險阻斷
        # ═══════════════════════════════════════════════════
        if criminal_count > 15:
            logger.warning(f"【高風險阻斷】{name} 刑事案件 {criminal_count} 筆，觸發阻斷！")
            
            # Google 新聞搜尋（仍執行，供前端顯示）
            news_results = google_searcher.search(name)
            
            return jsonify({
                "success": True,
                "data": {
                    "name": name,
                    "court_cases": court_cases[:20],  # 僅回傳前 20 筆標題
                    "relatives": relatives,
                    "news_results": news_results[:15],
                    "risk_assessment": {
                        "overall_risk": "極高",
                        "risk_score": 95,
                        "criminal_count": criminal_count,
                        "civil_count": civil_count,
                        "categories": ["刑事案件密集"],
                        "key_findings": [
                            f"⚠️ 此人在司法院裁判書系統中搜尋到 {criminal_count} 筆刑事相關案件，數量異常極高！",
                            "系統已自動觸發高風險阻斷機制，建議直接前往司法院網站查閱。",
                            f"總計發現 {len(court_cases)} 筆相關案件（含化名搜尋結果）。",
                        ],
                        "summary": (
                            f"「{name}」在法院裁判書查詢系統中被發現有 {criminal_count} 筆刑事相關案件，"
                            f"總計 {len(court_cases)} 筆相關紀錄。此訴訟頻率異常極高，"
                            "系統判定為極高風險，強烈建議使用者直接前往司法院網站親自查閱完整內容。"
                        ),
                        "relative_risks": [],
                        "recommendations": (
                            f"⚠️ 極高風險警告：此人涉及 {criminal_count} 筆刑事案件。"
                            "請直接前往 https://judgment.judicial.gov.tw 輸入其姓名進行完整檢索。"
                            "此數量已超過系統安全閾值，不建議盲目信任此人。"
                        ),
                        "disclaimer": "本報告基於司法院公開裁判書系統檢索結果自動生成，資料可能包含同名同姓者，請以官方資料為準。",
                    },
                },
            })

        # ═══════════════════════════════════════════════════
        # Step 3: Google 補充搜尋（新聞資料）
        # ═══════════════════════════════════════════════════
        logger.info(f"正在進行 Google 補充搜尋...")
        news_results = google_searcher.search(name)
        logger.info(f"找到 {len(news_results)} 筆相關網路資料")

        # ═══════════════════════════════════════════════════
        # Step 4: 階段一 AI 篩選 — 讓 AI 挑選最值得深入調查的 3 篇
        # ═══════════════════════════════════════════════════
        if court_cases:
            # 建構摘要供 AI 篩選（需要記住每一筆在哪個搜尋變體名下找到的）
            cases_summary = []
            for i, c in enumerate(court_cases):
                cases_summary.append({
                    "index": i,
                    "court": c.get("court", ""),
                    "case_number": c.get("case_number", ""),
                    "title": c.get("title", ""),
                    "date": c.get("date", ""),
                    "search_name": c.get("case_number", "").split(" ")[0] if c.get("case_number") else name,
                })

            logger.info(f"【AI 篩選】正在請 AI 從 {len(cases_summary)} 筆中挑選最值得調查的 3 篇...")
            selected_indices = ai_analyzer.select_top_cases(name, cases_summary, news_results)
            logger.info(f"【AI 篩選】AI 挑選結果：索引 {selected_indices}")

            # ═══════════════════════════════════════════════════
            # Step 5: 階段二 — 精準全文調閱（僅抓取 AI 指定的 3 篇）
            # ═══════════════════════════════════════════════════
            # 需要將全域索引轉換為每個搜尋變體的本地索引
            # 由於 search_by_name 已合併所有變體的結果，我們需要重新搜尋
            # 最簡單的方式：直接用全名搜尋一次，用索引對應
            if selected_indices:
                logger.info(f"【階段二】精準抓取 {len(selected_indices)} 篇判決全文...")
                # 嘗試用全名搜尋（因為列表是合併的，我們需要找到適合的搜尋詞）
                # 我們依序嘗試每個變體
                search_variants = [name] + court_crawler._generate_redacted_names(name)
                
                fetched = set()  # 已成功抓取的全域索引
                
                for variant in search_variants:
                    # 找出此 variant 對應的案件在全域列表中的索引
                    variant_cases = court_crawler._search_fjud(variant, case_type)
                    variant_case_numbers = {vc.case_number for vc in variant_cases if vc.case_number}
                    
                    # 找出尚未抓取且屬於此 variant 的目標索引
                    variant_targets = []
                    for si in selected_indices:
                        if si < len(court_cases) and si not in fetched:
                            target_cn = court_cases[si].get("case_number", "")
                            if target_cn in variant_case_numbers:
                                # 找到此案件在 variant 搜尋結果中的本地索引
                                for local_idx, vc in enumerate(variant_cases):
                                    if vc.case_number == target_cn:
                                        variant_targets.append((si, local_idx))
                                        break
                    
                    if variant_targets:
                        local_indices = [vt[1] for vt in variant_targets]
                        detail_results = court_crawler.fetch_specific_cases(variant, local_indices, case_type)
                        
                        for dr in detail_results:
                            # 找到對應的全域索引
                            for si, local_idx in variant_targets:
                                if dr["index"] == local_idx:
                                    court_cases[si]["full_text"] = dr["full_text"]
                                    court_cases[si]["verdict"] = dr["verdict"]
                                    fetched.add(si)
                                    logger.info(f"成功抓取索引 {si} 的判決全文 ({len(dr['full_text'])} 字)")
                                    break

        # ═══════════════════════════════════════════════════
        # Step 6: 爬取法院資料（近親）— 僅抓列表，不深度爬取
        # ═══════════════════════════════════════════════════
        for relative in relatives[:5]:
            rel_name = relative.get("name", "")
            if rel_name:
                logger.info(f"正在搜尋近親 {rel_name} 的法院裁判書...")
                rel_cases = court_crawler.search_by_name(rel_name, case_type)

                for case_obj in rel_cases:
                    cd = case_obj.to_dict()
                    if "法學資料檢索系統" not in str(cd.get("case_number", "")):
                        cd["related_person"] = rel_name
                        cd["relation"] = relative.get("relation", "")
                        court_cases.append(cd)

        # ═══════════════════════════════════════════════════
        # Step 7: AI 最終風險分析（含完整判決全文 + 新聞資料 + 統計數據）
        # ═══════════════════════════════════════════════════
        logger.info(f"正在進行 AI 最終風險分析...")
        
        # 將統計數據傳給 AI
        ai_analyzer._case_stats = {
            "total_cases": len(court_cases),
            "redacted_cases": sum(1 for c in court_cases if any(x in str(c.get("case_number", "")) for x in ["Ｏ", "○"])),
            "criminal_total": criminal_count,
            "civil_total": civil_count,
        }
        
        risk_assessment = ai_analyzer.analyze(
            name=name,
            court_cases=court_cases,
            relatives=relatives,
            news_results=news_results,
        )
        logger.info(f"風險評估完成：{risk_assessment.overall_risk} ({risk_assessment.risk_score}分)")

        return jsonify({
            "success": True,
            "data": {
                "name": name,
                "court_cases": court_cases,
                "relatives": relatives,
                "news_results": news_results[:15],
                "risk_assessment": risk_assessment.to_dict(),
            },
        })

    except Exception as e:
        logger.error(f"搜尋發生錯誤: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"搜尋發生錯誤：{str(e)}"}), 500


@app.route("/api/health")
def health():
    """健康檢查"""
    return jsonify({
        "status": "ok",
        "openai_configured": bool(Config.OPENAI_API_KEY),
    })


# ─── 啟動 ───

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("台灣公眾人物前科查詢機 啟動中...")
    logger.info(f"OpenAI API: {'已設定' if Config.OPENAI_API_KEY else '❌ 未設定'}")
    logger.info(f"伺服器：http://127.0.0.1:{Config.PORT}")
    logger.info("=" * 50)

    app.run(
        host="127.0.0.1",
        port=Config.PORT,
        debug=Config.DEBUG,
    )
