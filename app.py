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

        # Step 1: 搜尋近親
        relatives = []
        if search_relatives:
            logger.info(f"正在搜尋 {name} 的近親...")
            relatives_obj = relative_finder.find_relatives(name)
            relatives = [r.to_dict() for r in relatives_obj]
            logger.info(f"找到 {len(relatives)} 位近親")

        # Step 2: 爬取法院資料（本人）
        logger.info(f"正在搜尋 {name} 的法院裁判書...")
        court_cases_obj = court_crawler.search_by_name(name, case_type)
        court_cases = [c.to_dict() for c in court_cases_obj]

        # 深度爬取本人判決書全文（前3筆）
        for case in court_cases[:3]:
            if case.get('url'):
                logger.info(f"正在深度爬取本人判決書全文: {case.get('case_number')}")
                detail = court_crawler.get_case_detail(case['url'])
                if detail:
                    case['full_text'] = detail.full_text
                    if detail.verdict:
                        case['verdict'] = detail.verdict

        logger.info(f"找到 {len(court_cases)} 筆法院記錄")

        # Step 3: 爬取法院資料（近親）
        for relative in relatives[:5]:  # 最多查詢 5 位近親
            rel_name = relative.get("name", "")
            if rel_name:
                logger.info(f"正在搜尋近親 {rel_name} 的法院裁判書...")
                rel_cases = court_crawler.search_by_name(rel_name, case_type)
                
                # 深度爬取近親判決書全文（每個近親前2筆）
                for i, case_obj in enumerate(rel_cases):
                    case_dict = case_obj.to_dict()
                    if i < 2 and case_dict.get('url'):
                        logger.info(f"正在深度爬取近親判決書全文: {case_dict.get('case_number')}")
                        detail = court_crawler.get_case_detail(case_dict['url'])
                        if detail:
                            case_dict['full_text'] = detail.full_text
                            if detail.verdict:
                                case_dict['verdict'] = detail.verdict

                    case_dict["related_person"] = rel_name
                    case_dict["relation"] = relative.get("relation", "")
                    court_cases.append(case_dict)

        # Step 4: Google 補充搜尋
        logger.info(f"正在進行 Google 補充搜尋...")
        news_results = google_searcher.search(name)
        logger.info(f"找到 {len(news_results)} 筆相關網路資料")

        # Step 5: AI 風險分析
        logger.info(f"正在進行 AI 風險分析...")
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
                "news_results": news_results[:15],  # 最多15條（負面優先）
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
