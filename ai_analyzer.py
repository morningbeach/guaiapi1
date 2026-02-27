"""
AI 風險分析模組
使用 OpenAI API 對蒐集到的法院資料進行風險評估
"""
import json
import logging
from dataclasses import dataclass, asdict
from typing import Optional

from openai import OpenAI

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class RiskAssessment:
    """風險評估結果"""
    overall_risk: str = "未知"          # 整體風險等級（極高/高/中/低/極低/無資料）
    risk_score: int = 0                # 風險分數 0-100
    criminal_count: int = 0            # 刑事案件數量
    civil_count: int = 0              # 民事案件數量
    categories: list = None           # 涉及的案件類別
    key_findings: list = None         # 關鍵發現
    summary: str = ""                 # AI 總結
    relative_risks: list = None       # 近親風險
    recommendations: str = ""         # 建議
    disclaimer: str = ""              # 免責聲明

    def __post_init__(self):
        if self.categories is None:
            self.categories = []
        if self.key_findings is None:
            self.key_findings = []
        if self.relative_risks is None:
            self.relative_risks = []

    def to_dict(self) -> dict:
        return asdict(self)


class AIAnalyzer:
    """
    AI 風險分析器
    使用 OpenAI GPT 模型分析法院資料並評估風險
    """

    SYSTEM_PROMPT = """你是一位專業的台灣法律風險分析師。你的任務是根據提供的法院公開裁判書資料和相關資訊，
對一位公眾人物進行客觀的風險評估。

【重要】近親犯罪必須納入風險評估：
- 如果近親有刑事案件，應該顯著提高風險分數（每位近親有刑事案件 +15-25分）
- 近親有民事糾紛也要加分（每位近親有民事案件 +5-10分）
- 近親犯罪反映家庭背景和潛在的利益輸送、關係網絡風險
- 即使本人沒有案件，近親有重大犯罪記錄也應該給予「中」或「高」風險等級

【重要】「司法蟑螂 / 濫訴 / 司法恫嚇」偵測：
- 如果發現該對象在法院紀錄，或「補充新聞資料」中有大量且密集的案件紀錄，且多為「原告」或「告訴人」（特別是針對「妨害名譽」、「公然侮辱」、「誹謗」、「恐嚇」等容易被用來對付言論的罪名）
- 請強烈判定此人可能為「利用司法資源恫嚇、打壓百姓或反對者」的「司法蟑螂」
- 若有此傾向，請在 `overall_risk`、`key_findings` 和 `recommendations` 中明確標註「高度濫訴風險 / 疑似司法恫嚇」，並給予「高」或「極高」的風險等級
- 即使法院本身查無資料，但只要新聞顯示他「提告數十位網友」、「頻繁報案告人」，就必須將其視為高風險的司法蟑螂！

你必須：
1. 客觀分析所有提供的法院資料（本人+近親）以及「補充新聞資料（news_results）」
2. 如果在法院資料中查無結果，請強烈依賴「補充新聞資料」來判斷此人是否曾涉及重大訴訟或頻繁提告
3. 區分刑事案件（犯罪相關）和民事案件（糾紛/訴訟）
4. 區分是「原告/告訴人（提告方）」還是「被告方」
5. 考慮案件的嚴重程度、數量和時間
6. 【重要】近親的犯罪記錄必須大幅影響風險評估
7. 給出合理的風險等級和分數

風險等級定義：
- 極高（80-100分）：本人有重大刑事定罪、近親有多項重大犯罪，或有嚴重「濫訴恫嚇」行為
- 高（60-79分）：本人有刑事記錄、近親有刑事犯罪記錄，或有明顯「頻繁提告網友/百姓」的傾向
- 中（40-59分）：本人有民事糾紛，或近親有法律爭議
- 低（20-39分）：僅有少量民事案件或已和解，近親無爭議
- 極低（0-19分）：本人及近親幾乎無法律爭議記錄

你必須以 JSON 格式回覆，包含以下欄位：
{
    "overall_risk": "風險等級（極高/高/中/低/極低）",
    "risk_score": 0-100的整數,
    "criminal_count": 刑事案件數量,
    "civil_count": 民事案件數量,
    "categories": ["涉及的案件類別列表"],
    "key_findings": ["關鍵發現1", "關鍵發現2", ...],
    "summary": "200字以內的風險總結",
    "relative_risks": [
        {"name": "親屬姓名", "relation": "關係", "risk_note": "風險備註"}
    ],
    "recommendations": "給使用者的建議",
    "disclaimer": "免責聲明"
}

重要提醒：
- 僅根據公開可查證的法院資料進行分析
- 「被告」不等於「有罪」，須注意判決結果
- 「原告」頻繁提告妨害名譽可能是濫訴恫嚇
- 必須加入適當的免責聲明
- 保持客觀中立，不做政治立場判斷"""

    def __init__(self):
        self.provider = "none"
        self.client = None
        
        if Config.ANTHROPIC_API_KEY:
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
                self.model = getattr(Config, "ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
                self.provider = "anthropic"
                logger.info("已啟用 Anthropic (Claude) AI 分析")
            except ImportError:
                logger.error("未安裝 anthropic 套件，請執行 pip install anthropic")
        elif Config.OPENAI_API_KEY:
            self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
            self.model = Config.OPENAI_MODEL
            self.provider = "openai"
            logger.info("已啟用 OpenAI AI 分析")
        else:
            logger.warning("未設定任何 AI API Key，AI 分析功能將無法完整運作")

    def analyze(
        self,
        name: str,
        court_cases: list[dict],
        relatives: list[dict],
        news_results: Optional[list[dict]] = None,
    ) -> RiskAssessment:
        if not self.client:
            return self._no_api_fallback(name, court_cases, relatives)

        user_prompt = self._build_prompt(name, court_cases, relatives, news_results)

        if self.provider == "anthropic":
            return self._analyze_anthropic(name, user_prompt)
        elif self.provider == "openai":
            return self._analyze_openai(name, user_prompt)
        
        return self._no_api_fallback(name, court_cases, relatives)

    def _analyze_anthropic(self, name: str, user_prompt: str) -> RiskAssessment:
        try:
            system_prompt_json = self.SYSTEM_PROMPT + "\n\n請以純 JSON 格式回覆，不要包含任何 markdown 標記（如 ```json）。"
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.2,
                system=system_prompt_json,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            result_text = response.content[0].text.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            
            result_data = json.loads(result_text.strip())
            return self._parse_json_result(result_data)

        except json.JSONDecodeError as e:
            logger.error(f"Anthropic 回應 JSON 解析失敗: {e}")
            return self._error_fallback(name, str(e))
        except Exception as e:
            logger.error(f"Anthropic 分析失敗: {e}")
            return self._error_fallback(name, str(e))

    def _analyze_openai(self, name: str, user_prompt: str) -> RiskAssessment:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content
            result_data = json.loads(result_text)
            return self._parse_json_result(result_data)

        except json.JSONDecodeError as e:
            logger.error(f"OpenAI 回應 JSON 解析失敗: {e}")
            return self._error_fallback(name, str(e))
        except Exception as e:
            logger.error(f"OpenAI 分析失敗: {e}")
            return self._error_fallback(name, str(e))

    def _parse_json_result(self, result_data: dict) -> RiskAssessment:
        return RiskAssessment(
            overall_risk=result_data.get("overall_risk", "未知"),
            risk_score=result_data.get("risk_score", 0),
            criminal_count=result_data.get("criminal_count", 0),
            civil_count=result_data.get("civil_count", 0),
            categories=result_data.get("categories", []),
            key_findings=result_data.get("key_findings", []),
            summary=result_data.get("summary", ""),
            relative_risks=result_data.get("relative_risks", []),
            recommendations=result_data.get("recommendations", ""),
            disclaimer=result_data.get("disclaimer",
                "本報告已依據深度調查之相關判決文內容生成，供參考之用。"),
        )

    def _build_prompt(
        self,
        name: str,
        court_cases: list[dict],
        relatives: list[dict],
        news_results: Optional[list[dict]],
    ) -> str:
        """建構給 AI 的分析提示"""

        # 分離本人案件和近親案件
        own_cases = [c for c in court_cases if not c.get("related_person")]
        relative_cases = [c for c in court_cases if c.get("related_person")]
        
        own_criminal = sum(1 for c in own_cases if c.get("case_type") == "刑事")
        own_civil = sum(1 for c in own_cases if c.get("case_type") == "民事")
        rel_criminal = sum(1 for c in relative_cases if c.get("case_type") == "刑事")
        rel_civil = sum(1 for c in relative_cases if c.get("case_type") == "民事")

        prompt_parts = [
            f"## 查詢對象：{name}",
            f"## 查詢時間：{self._current_time()}",
            "",
            "## ⚠️ 重要統計（請務必納入評分）",
            f"- 本人刑事案件：{own_criminal} 件",
            f"- 本人民事案件：{own_civil} 件", 
            f"- **近親刑事案件：{rel_criminal} 件**（每件應 +15-25 分）",
            f"- **近親民事案件：{rel_civil} 件**（每件應 +5-10 分）",
            "",
        ]

        # 本人法院案件
        prompt_parts.append("## 本人法院裁判書記錄\n")
        if own_cases:
            for i, case in enumerate(own_cases, 1):
                prompt_parts.append(f"### 本人案件 {i}")
                prompt_parts.append(f"- 法院：{case.get('court', '未知')}")
                prompt_parts.append(f"- 案號：{case.get('case_number', '未知')}")
                prompt_parts.append(f"- 類型：{case.get('case_type', '未知')}")
                prompt_parts.append(f"- 日期：{case.get('date', '未知')}")
                prompt_parts.append(f"- 案由：{case.get('title', '未知')}")
                if case.get("verdict"):
                    prompt_parts.append(f"- 判決主文：{case['verdict']}")
                if case.get("full_text"):
                    prompt_parts.append(f"- 判決書內容節錄：\n{case['full_text'][:2500]}")
                prompt_parts.append("")
        else:
            prompt_parts.append("本人未找到法院裁判書記錄。\n")

        # 近親法院案件（重要！）
        prompt_parts.append("## ⚠️ 近親法院裁判書記錄（必須納入風險評估）\n")
        if relative_cases:
            for i, case in enumerate(relative_cases, 1):
                prompt_parts.append(f"### 近親案件 {i}（{case.get('related_person', '未知')} - {case.get('relation', '')}）")
                prompt_parts.append(f"- 當事人：{case.get('related_person', '未知')}（{case.get('relation', '關係未知')}）")
                prompt_parts.append(f"- 案號：{case.get('case_number', '未知')}")
                prompt_parts.append(f"- 類型：{case.get('case_type', '未知')}")
                prompt_parts.append(f"- 案由：{case.get('title', '未知')}")
                if case.get("verdict"):
                    prompt_parts.append(f"- 判決主文：{case['verdict']}")
                if case.get("full_text"):
                    prompt_parts.append(f"- 判決書內容節錄：\n{case['full_text'][:2500]}")
                prompt_parts.append("")
        else:
            prompt_parts.append("近親未找到法院裁判書記錄。\n")

        # 親屬資料
        prompt_parts.append("## 已搜尋的近親名單\n")
        if relatives:
            for r in relatives:
                prompt_parts.append(
                    f"- {r.get('name', '未知')}（{r.get('relation', '未知')}）"
                )
            prompt_parts.append("")

        # 新聞資料
        if news_results:
            prompt_parts.append("## 相關新聞/網路資料\n")
            for item in news_results[:10]:
                neg_tag = "【負面】" if item.get("is_negative") else ""
                prompt_parts.append(f"- {neg_tag}{item.get('title', '')}")
                if item.get("snippet"):
                    prompt_parts.append(f"  摘要：{item['snippet'][:200]}")
            prompt_parts.append("")

        prompt_parts.append(
            "\n## 評分要求\n"
            "請根據以上資料進行風險評估。\n"
            f"**重要**：本查詢發現近親有 {rel_criminal} 件刑事案件、{rel_civil} 件民事案件，"
            "這些必須納入風險分數計算，即使本人沒有案件記錄。\n"
            "請以 JSON 格式回覆。"
        )

        return "\n".join(prompt_parts)

    @staticmethod
    def _current_time() -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _no_api_fallback(name: str, court_cases: list, relatives: list) -> RiskAssessment:
        """無 API Key 時的簡易分析（含近親風險）"""
        # 本人案件
        own_cases = [c for c in court_cases if not c.get("related_person")]
        own_criminal = sum(1 for c in own_cases if c.get("case_type") == "刑事")
        own_civil = sum(1 for c in own_cases if c.get("case_type") == "民事")
        
        # 近親案件
        relative_cases = [c for c in court_cases if c.get("related_person")]
        rel_criminal = sum(1 for c in relative_cases if c.get("case_type") == "刑事")
        rel_civil = sum(1 for c in relative_cases if c.get("case_type") == "民事")
        
        # 計算基礎分數
        score = 0
        
        # 本人刑事案件
        score += own_criminal * 25
        # 本人民事案件
        score += own_civil * 8
        # 近親刑事案件（重要！）
        score += rel_criminal * 18
        # 近親民事案件
        score += rel_civil * 5
        
        # 限制最高分
        score = min(score, 100)
        
        # 決定風險等級
        if score >= 80:
            risk = "極高"
        elif score >= 60:
            risk = "高"
        elif score >= 40:
            risk = "中"
        elif score >= 20:
            risk = "低"
        else:
            risk = "極低"

        categories = list(set(c.get("case_type", "未知") for c in court_cases))
        
        # 關鍵發現
        key_findings = [
            f"本人：{own_criminal} 筆刑事、{own_civil} 筆民事案件",
        ]
        if relative_cases:
            key_findings.append(f"近親：{rel_criminal} 筆刑事、{rel_civil} 筆民事案件")
            if rel_criminal > 0:
                key_findings.append("⚠️ 近親有刑事案件記錄，已納入風險評估")
        
        # 近親風險列表
        relative_risks = []
        rel_case_by_person = {}
        for c in relative_cases:
            rp = c.get("related_person", "")
            if rp not in rel_case_by_person:
                rel_case_by_person[rp] = {"criminal": 0, "civil": 0, "relation": c.get("relation", "")}
            if c.get("case_type") == "刑事":
                rel_case_by_person[rp]["criminal"] += 1
            else:
                rel_case_by_person[rp]["civil"] += 1
        
        for rp, info in rel_case_by_person.items():
            note = f"刑事 {info['criminal']} 件、民事 {info['civil']} 件"
            relative_risks.append({
                "name": rp,
                "relation": info["relation"],
                "risk_note": note
            })

        return RiskAssessment(
            overall_risk=risk,
            risk_score=score,
            criminal_count=own_criminal,
            civil_count=own_civil,
            categories=categories,
            key_findings=key_findings,
            summary=(
                f"「{name}」本人有 {own_criminal} 筆刑事、{own_civil} 筆民事案件。"
                f"近親有 {rel_criminal} 筆刑事、{rel_civil} 筆民事案件。"
                f"綜合評估風險等級為「{risk}」（{score}分）。"
                "（此為簡易分析，設定 OPENAI_API_KEY 可獲得更完整評估。）"
            ),
            relative_risks=relative_risks,
            recommendations="近親的法律爭議可能反映家庭背景或利益關係，建議深入了解。",
            disclaimer="本報告僅基於公開法院資料自動生成，不構成任何法律意見。資料可能不完整或有誤，請以官方資料為準。",
        )

    @staticmethod
    def _error_fallback(name: str, error: str) -> RiskAssessment:
        """AI 分析失敗時的回傳"""
        return RiskAssessment(
            overall_risk="未知",
            risk_score=0,
            summary=f"AI 分析「{name}」時發生錯誤：{error}",
            recommendations="請稍後再試，或檢查 API Key 是否正確。",
            disclaimer="本報告僅基於公開法院資料自動生成，不構成任何法律意見。",
        )
