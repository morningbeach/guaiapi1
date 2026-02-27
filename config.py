"""
設定模組 - 集中管理所有環境變數與預設值
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Anthropic
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

    # Flask
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    PORT = int(os.getenv("FLASK_PORT", 5000))

    # 爬蟲
    CRAWLER_DELAY = float(os.getenv("CRAWLER_DELAY", 1.5))
    CRAWLER_MAX_RESULTS = int(os.getenv("CRAWLER_MAX_RESULTS", 30))

    # 司法院裁判書查詢系統
    COURT_BASE_URL = "https://judgment.judicial.gov.tw/FJUD"
    COURT_SEARCH_URL = f"{COURT_BASE_URL}/default.aspx"
    COURT_DETAIL_URL = f"{COURT_BASE_URL}/FJUDQRY03_1.aspx"

    # 請求標頭
    DEFAULT_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
    }
