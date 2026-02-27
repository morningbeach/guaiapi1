"""
法院裁判書爬蟲模組
爬取司法院裁判書查詢系統 (https://judgment.judicial.gov.tw/FJUD/)
以及司法院開放資料 API
"""
import re
import time
import logging
from typing import Optional
from dataclasses import dataclass, field, asdict

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from config import Config

logger = logging.getLogger(__name__)

ua = UserAgent(fallback="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")


@dataclass
class CourtCase:
    """法院案件資料結構"""
    court: str = ""           # 法院名稱
    case_type: str = ""       # 案件類型（刑事/民事/行政）
    case_number: str = ""     # 案號
    date: str = ""            # 裁判日期
    title: str = ""           # 案由
    parties: str = ""         # 當事人
    summary: str = ""         # 裁判摘要
    full_text: str = ""       # 全文（節錄）
    url: str = ""             # 原始連結
    verdict: str = ""         # 判決結果

    def to_dict(self) -> dict:
        return asdict(self)


class CourtCrawler:
    """
    司法院裁判書查詢系統爬蟲
    支援：
    1. 司法院裁判書查詢系統 (FJUD) 網頁爬蟲
    2. 司法院開放資料 API
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(Config.DEFAULT_HEADERS)
        self.session.headers["User-Agent"] = ua.random
        self.delay = Config.CRAWLER_DELAY
        self.max_results = Config.CRAWLER_MAX_RESULTS

    def _sleep(self):
        """禮貌性延遲，避免對伺服器造成負擔"""
        time.sleep(self.delay)

    def _generate_redacted_names(self, name: str) -> list[str]:
        """產生司法院常用的隱蔽姓名變體"""
        if not name or len(name) < 2:
            return []
        
        variants = []
        if len(name) == 2:
            variants.extend([f"{name[0]}Ｏ", f"{name[0]}○"])
        elif len(name) == 3:
            variants.extend([f"{name[0]}Ｏ{name[2]}", f"{name[0]}○{name[2]}"])
        elif len(name) >= 4:
            # 有些複姓或是名字很長的情況，通常隱藏第二個字
            variants.extend([f"{name[0]}Ｏ{name[2:]}", f"{name[0]}○{name[2:]}"])
            
        return list(set(variants))

    # ─────────────────────────────────────────
    # 方法 1：司法院裁判書查詢系統 (FJUD 網頁)
    # ─────────────────────────────────────────

    def search_by_name(self, name: str, case_type: str = "all") -> list[CourtCase]:
        """
        透過司法院裁判書查詢系統搜尋當事人姓名

        Args:
            name: 當事人姓名
            case_type: 案件類型 (all/criminal/civil/administrative)

        Returns:
            CourtCase 列表
        """
        cases = []
        try:
            # 1. 先搜尋全名
            logger.info(f"開始搜尋全名：{name}")
            cases.extend(self._search_fjud(name, case_type))
            
            # 2. 搜尋隱蔽化名 (例如 邱Ｏ軒、邱○軒)
            redacted_names = self._generate_redacted_names(name)
            for redacted in redacted_names:
                logger.info(f"擴充搜尋隱蔽化名：{redacted}")
                cases.extend(self._search_fjud(redacted, case_type))
                
            # 3. 去除重複案號 (依據 case_number 或 url)
            unique_cases = {}
            for case in cases:
                # 若案號為空，用 URL 當 key
                key = case.case_number if case.case_number else case.url
                if key and key not in unique_cases:
                    unique_cases[key] = case
            
            cases = list(unique_cases.values())
            
        except Exception as e:
            logger.error(f"FJUD 搜尋失敗: {e}")

        # 備用：嘗試開放資料 API
        if not cases:
            try:
                cases = self._search_opendata(name, case_type)
            except Exception as e:
                logger.error(f"開放資料 API 搜尋失敗: {e}")

        return cases

    def _search_fjud(self, name: str, case_type: str) -> list[CourtCase]:
        """透過 FJUD 網頁使用 Playwright 搜尋"""
        cases = []
        logger.info(f"正在使用 Playwright 搜尋 FJUD：{name} (類型: {case_type})")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={'width': 1280, 'height': 800}
                )
                page = context.new_page()

                # Step 1: 進入搜尋頁面
                page.goto(Config.COURT_SEARCH_URL, wait_until="domcontentloaded", timeout=20000)

                # Step 2: 填寫表單
                page.wait_for_selector("#txtKW", timeout=10000)
                page.fill("#txtKW", name)

                if case_type == "criminal":
                    page.locator('input[name="judtype"][value="3"]').check()
                elif case_type == "civil":
                    page.locator('input[name="judtype"][value="1"]').check()
                elif case_type == "administrative":
                    page.locator('input[name="judtype"][value="4"]').check()

                # Step 3: 送出搜尋並等待結果 iframe
                with page.expect_navigation(wait_until="domcontentloaded", timeout=20000):
                    page.click("#btnSimpleQry")

                # Step 4: 等待 iframe 載入並解析
                iframe_locator = page.frame_locator("#iframe-data")
                try:
                    iframe_locator.locator("table#jud").wait_for(timeout=15000)
                except PlaywrightTimeoutError:
                    logger.warning(f"FJUD 搜尋 {name} 查無結果或 iframe 載入逾時")
                    browser.close()
                    return cases

                # 解析 iframe 內的 HTML
                html = iframe_locator.locator("body").inner_html()
                cases = self._parse_search_results(html, page.url)

                # 在同一個連線畫面中，模擬人類操作直接點進判決書抓取前 5 筆內文
                for i in range(min(5, len(cases))):
                    try:
                        # 每次操作後頁面結構可能重製，因此必須重新抓取標籤
                        links = page.frame_locator("#iframe-data").locator("table#jud tr a").element_handles()
                        if i >= len(links):
                            break
                            
                        links[i].click()
                        
                        detail_locator = page.frame_locator("#iframe-data").locator(".jud_content, #jud_content, .judgement-content, #divJudContent, pre").first
                        detail_locator.wait_for(timeout=10000)
                        
                        full_text = detail_locator.inner_text()
                        cases[i].full_text = full_text[:10000] # 最多擷取 10000 字
                        cases[i].verdict = self._extract_verdict(full_text)
                        
                        # 點擊上一頁返回裁判書列表
                        page.evaluate("window.history.back()")
                        # 等待搜尋陣列重新出現
                        page.frame_locator("#iframe-data").locator("table#jud").wait_for(timeout=10000)
                    except Exception as e:
                        logger.warning(f"擷取 {name} 第 {i+1} 筆判決全文失敗: {e}")

                browser.close()

        except Exception as e:
            logger.error(f"FJUD Playwright 搜尋發生錯誤: {e}")

        return cases

    def _search_opendata(self, name: str, case_type: str) -> list[CourtCase]:
        """
        備用方案：透過司法院開放資料平台搜尋
        https://opendata.judicial.gov.tw/
        """
        cases = []
        try:
            # 司法院開放資料 API
            api_url = "https://opendata.judicial.gov.tw/api/SJudgment"
            params = {
                "$filter": f"contains(JFULL,'{name}')",
                "$top": min(self.max_results, 20),
                "$orderby": "JDATE desc",
                "$format": "json",
            }

            resp = self.session.get(api_url, params=params, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    for item in data[:self.max_results]:
                        case = CourtCase(
                            court=item.get("JCOURT", ""),
                            case_type=self._classify_case_type(item.get("JTITLE", "")),
                            case_number=item.get("JID", ""),
                            date=item.get("JDATE", ""),
                            title=item.get("JTITLE", ""),
                            summary=self._extract_summary(item.get("JFULL", ""), name),
                            full_text=item.get("JFULL", "")[:2000],
                            verdict=self._extract_verdict(item.get("JFULL", "")),
                        )
                        cases.append(case)
        except Exception as e:
            logger.error(f"開放資料 API 錯誤: {e}")

        return cases

    def _parse_search_results(self, html: str, base_url: str) -> list[CourtCase]:
        """解析 FJUD 搜尋結果頁面"""
        cases = []
        soup = BeautifulSoup(html, "lxml")

        # FJUD iframe 中的 table
        result_rows = soup.select("table#jud tbody tr") or \
                      soup.select("table#jud tr") or \
                      soup.select("table.tab_results tr")

        import urllib.parse
        for row in result_rows:
            if len(cases) >= self.max_results:
                break
            
            # 通常第一欄是序號，第二欄是案號/法院，第三欄大小，第四欄日期，第五欄案由
            cells = row.select("td")
            if len(cells) < 4:
                continue

            try:
                # 提取案件資訊
                link_tag = cells[1].select_one("a[href]") if len(cells) > 1 else None
                detail_url = ""
                jud_id = ""
                case_number = ""
                court_name = ""
                
                if link_tag:
                    href = link_tag.get("href", "")
                    # "臺中高等行政法院 高等庭 114 年度 訴 字第 290 號裁定" -> court, case num
                    case_text = link_tag.get_text(strip=True)
                    parts = case_text.split(" ", 1)
                    if len(parts) > 1:
                        court_name = parts[0]
                        case_number = parts[1]
                    else:
                        case_number = case_text

                    # 嘗試提取判決書 ID
                    if "id=" in href:
                        jud_id = href.split("id=")[-1].split("&")[0]
                    
                    if jud_id:
                        detail_url = f"https://judgment.judicial.gov.tw/FJUD/data.aspx?ty=JD&id={jud_id}"
                    elif href and not href.startswith("http"):
                        detail_url = urllib.parse.urljoin(base_url, href)
                    else:
                        detail_url = href

                if not case_number and len(cells) > 1:
                    case_number = cells[1].get_text(strip=True)

                date_text = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                title_text = cells[4].get_text(strip=True) if len(cells) > 4 else ""

                # 提取 summary (通常緊接在案號 a tag 後面的 div，或者是下一行)
                summary_text = ""
                summary_div = cells[1].select_one("div.hl-area") or row.find("div", class_="hl-area")
                if summary_div:
                    summary_text = summary_div.get_text(strip=True)
                else:
                    # 也可能是直接接在字串後面
                    full_text = cells[1].get_text(separator=' ', strip=True)
                    if len(full_text) > len(case_text):
                        summary_text = full_text[len(case_text):].strip()

                case = CourtCase(
                    court=court_name,
                    case_number=case_number,
                    title=title_text,
                    date=date_text,
                    url=detail_url,
                    summary=summary_text[:200]
                )

                # 分類案件類型
                case.case_type = self._classify_case_type(case.title + " " + case.summary)
                cases.append(case)

            except Exception as e:
                logger.debug(f"解析結果列失敗: {e}")
                continue

        # 如果表格解析失敗，嘗試從頁面文字提取
        if not cases:
            cases = self._parse_results_fallback(soup)

        return cases

    def _parse_results_fallback(self, soup: BeautifulSoup) -> list[CourtCase]:
        """備用解析邏輯：當標準表格解析失敗時"""
        cases = []
        import urllib.parse

        # 嘗試找所有連結，看是否有裁判書連結
        links = soup.select("a[href*='FJUDQRY']") or soup.select("a[href*='jud']") or soup.select("a[href*='id=']")

        for link in links[:self.max_results]:
            text = link.get_text(strip=True)
            if not text or len(text) < 4:
                continue

            href = link.get("href", "")
            detail_url = ""
            
            # 嘗試提取判決書 ID
            if "id=" in href:
                jud_id = href.split("id=")[-1].split("&")[0]
                detail_url = f"https://judgment.judicial.gov.tw/FJUD/data.aspx?ty=JD&id={jud_id}"
            elif href and not href.startswith("http"):
                detail_url = f"{Config.COURT_BASE_URL}/{href}"
            else:
                detail_url = href
            
            # 如果還是沒有 URL，根據案號構建搜尋 URL
            if not detail_url and text:
                encoded_case = urllib.parse.quote(text)
                detail_url = f"https://judgment.judicial.gov.tw/FJUD/default.aspx?kw={encoded_case}"

            # 嘗試從連結文字提取案號和資訊
            case = CourtCase(
                case_number=text,
                url=detail_url,
                case_type=self._classify_case_type(text),
            )

            # 嘗試獲取相鄰的文字作為額外資訊
            parent = link.parent
            if parent:
                siblings_text = parent.get_text(strip=True)
                case.summary = siblings_text[:200]

            cases.append(case)

        return cases

    def get_case_detail(self, url: str) -> Optional[CourtCase]:
        """取得個別裁判書詳情（使用 Playwright）"""
        if not url:
            return None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                page.goto(url, wait_until="domcontentloaded", timeout=20000)

                # 等待內容載入
                try:
                    page.wait_for_selector("#jud_content, .judgement-content, #divJudContent", timeout=10000)
                except PlaywrightTimeoutError:
                    # 也許是在 iframe 裡面
                    iframe = page.frame_locator("iframe").first
                    if iframe:
                        try:
                            iframe.locator("#jud_content, .judgement-content").wait_for(timeout=10000)
                        except PlaywrightTimeoutError:
                            pass

                # 提取裁判書全文
                html = page.content()
                soup = BeautifulSoup(html, "lxml")

                content_div = soup.select_one("#jud_content") or \
                              soup.select_one(".judgement-content") or \
                              soup.select_one("#divJudContent") or \
                              soup.select_one("pre")

                if not content_div:
                    # Try probing iframe
                    iframe_elem = soup.find("iframe")
                    if iframe_elem and iframe_elem.get("src"):
                        # this is too complex if nested, return fallback
                        pass

                if not content_div:
                    browser.close()
                    return None

                full_text = content_div.get_text(strip=True)

                case = CourtCase(
                    full_text=full_text[:5000],
                    url=url,
                    verdict=self._extract_verdict(full_text),
                    case_type=self._classify_case_type(full_text),
                )

                # 嘗試提取案號
                title_elem = soup.select_one("title") or soup.select_one("h1")
                if title_elem:
                    case.case_number = title_elem.get_text(strip=True)

                browser.close()
                return case

        except Exception as e:
            logger.error(f"取得裁判書詳情 (Playwright) 失敗: {e}")
            return None

    # ─────────────────────────────────────────
    # 輔助方法
    # ─────────────────────────────────────────

    @staticmethod
    def _extract_field(soup: BeautifulSoup, field_id: str) -> str:
        """提取 ASP.NET 隱藏表單欄位"""
        tag = soup.find("input", {"id": field_id})
        return tag.get("value", "") if tag else ""

    @staticmethod
    def _classify_case_type(text: str) -> str:
        """根據文字內容分類案件類型"""
        if not text:
            return "未知"

        criminal_keywords = [
            "刑事", "公訴", "自訴", "聲請簡易", "上訴", "竊盜", "詐欺",
            "傷害", "殺人", "毒品", "槍砲", "貪污", "瀆職", "偽造",
            "妨害", "酒駕", "公共危險", "恐嚇", "強盜", "搶奪",
            "侵占", "背信", "洗錢", "組織犯罪", "賭博", "妨害性自主",
        ]
        civil_keywords = [
            "民事", "損害賠償", "給付", "確認", "返還", "履行",
            "離婚", "扶養", "監護", "繼承", "不動產", "租賃",
        ]
        admin_keywords = ["行政", "稅務", "環保", "都市計畫", "建築"]

        for kw in criminal_keywords:
            if kw in text:
                return "刑事"
        for kw in civil_keywords:
            if kw in text:
                return "民事"
        for kw in admin_keywords:
            if kw in text:
                return "行政"

        return "其他"

    @staticmethod
    def _extract_summary(full_text: str, name: str) -> str:
        """從全文中提取與當事人相關的摘要"""
        if not full_text:
            return ""

        sentences = re.split(r"[。；\n]", full_text)
        relevant = [s.strip() for s in sentences if name in s and len(s.strip()) > 10]
        return "。".join(relevant[:5])

    @staticmethod
    def _extract_verdict(full_text: str) -> str:
        """提取判決主文"""
        if not full_text:
            return ""

        # 常見判決主文標記
        patterns = [
            r"主\s*文[：:]\s*(.+?)(?=事\s*實|理\s*由|$)",
            r"主\s*文\s*\n(.+?)(?=事\s*實|理\s*由|\n\n)",
        ]

        for pattern in patterns:
            match = re.search(pattern, full_text, re.DOTALL)
            if match:
                verdict = match.group(1).strip()
                return verdict[:500]

        return ""


class GoogleCourtSearcher:
    """
    透過 Google 搜尋台灣法院相關公開資訊
    作為司法院系統的補充資料來源
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": ua.random,
            "Accept-Language": "zh-TW,zh;q=0.9",
        })

    def search(self, name: str) -> list[dict]:
        """
        搜尋公開新聞與法院相關資料
        使用合併查詢減少請求次數，避免被阻擋
        """
        results = []

        # 合併關鍵字，減少請求次數
        queries = [
            (f"{name} 提告 網友", True),
            (f"{name} 妨害名譽 訴訟", True),
            (f"{name} 判刑 貪污 詐欺", True),
            (f"{name} 爭議 弊案 違法", True),
            (f"{name} 新聞 報導", False),
        ]

        for query, is_negative in queries:
            try:
                items = []
                
                # 嘗試多個搜尋引擎
                # 1. Bing
                items = self._bing_search(query, is_negative)
                if items:
                    logger.info(f"Bing 搜尋「{query[:20]}...」找到 {len(items)} 筆")
                    results.extend(items)
                    time.sleep(1.5)
                    continue
                
                # 2. Yahoo 台灣
                items = self._yahoo_search(query, is_negative)
                if items:
                    logger.info(f"Yahoo 搜尋「{query[:20]}...」找到 {len(items)} 筆")
                    results.extend(items)
                    time.sleep(1.5)
                    continue
                
                # 3. DuckDuckGo
                items = self._duckduckgo_search(query, is_negative, self._get_negative_keywords())
                if items:
                    logger.info(f"DDG 搜尋「{query[:20]}...」找到 {len(items)} 筆")
                    results.extend(items)
                else:
                    logger.warning(f"所有搜尋引擎都未找到「{query[:20]}...」的結果")
                
                time.sleep(2)  # 延遲避免被阻擋
                
            except Exception as e:
                logger.warning(f"搜尋失敗 ({query[:20]}...): {e}")

        # 去重並排序（負面新聞優先）
        seen_urls = set()
        unique_results = []
        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(r)

        # 負面新聞排前面
        negative_news = [r for r in unique_results if r.get("is_negative")]
        other_news = [r for r in unique_results if not r.get("is_negative")]
        
        final_results = negative_news[:10] + other_news[:5]
        return final_results[:15]

    def _get_negative_keywords(self) -> list:
        """負面新聞關鍵字"""
        return [
            "起訴", "判刑", "判決", "貪污", "收賄", "賄賂", "詐欺", "詐騙",
            "吸金", "逃稅", "洗錢", "掏空", "性騷擾", "性侵", "猥褻",
            "黑道", "幫派", "暴力", "醜聞", "爭議", "違法", "違規",
            "罰款", "假學歷", "抄襲", "造假", "利益輸送", "圖利", "瀆職",
            "被告", "涉嫌", "遭控", "指控", "檢舉", "調查", "偵辦",
            "羈押", "交保", "緩刑", "有期徒刑", "罰金", "沒收",
            "犯罪", "前科", "入獄", "服刑", "坐牢", "監禁", "弊案",
            "提告", "告網友", "妨害名譽", "公然侮辱", "告訴人", "濫訴"
        ]

    def _bing_search(self, query: str, is_negative: bool) -> list[dict]:
        """使用 Bing 搜尋"""
        results = []
        negative_keywords = self._get_negative_keywords()
        
        try:
            url = "https://www.bing.com/search"
            params = {"q": query, "setlang": "zh-TW", "count": 15}
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            
            resp = self.session.get(url, params=params, headers=headers, timeout=15)
            logger.debug(f"Bing 狀態碼: {resp.status_code}")
            
            if resp.status_code != 200:
                logger.warning(f"Bing 返回狀態碼: {resp.status_code}")
                return results
            
            soup = BeautifulSoup(resp.text, "lxml")
            
            # Bing 結果選擇器（多種嘗試）
            items = soup.select("li.b_algo") or soup.select(".b_algo") or soup.select("ol#b_results > li")
            logger.debug(f"Bing 找到 {len(items)} 個結果元素")
            
            for item in items:
                title_tag = item.select_one("h2 a") or item.select_one("h2") or item.select_one("a")
                snippet_tag = item.select_one(".b_caption p") or item.select_one("p") or item.select_one(".b_caption")
                
                if title_tag:
                    title = title_tag.get_text(strip=True)
                    href = title_tag.get("href", "") if title_tag.name == "a" else ""
                    
                    # 如果 title_tag 不是 a，找子元素的 a
                    if not href:
                        a_tag = title_tag.select_one("a") or item.select_one("a[href]")
                        if a_tag:
                            href = a_tag.get("href", "")
                    
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                    
                    # 檢測負面新聞
                    combined_text = title + snippet
                    detected_negative = any(kw in combined_text for kw in negative_keywords)
                    
                    if title and href and href.startswith("http"):
                        results.append({
                            "title": title,
                            "url": href,
                            "snippet": snippet[:300],
                            "is_negative": is_negative or detected_negative,
                        })
        
        except Exception as e:
            logger.error(f"Bing 搜尋失敗: {e}")
        
        return results[:10]
    
    def _yahoo_search(self, query: str, is_negative: bool) -> list[dict]:
        """使用 Yahoo 台灣搜尋作為備用"""
        results = []
        negative_keywords = self._get_negative_keywords()
        
        try:
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            url = f"https://tw.search.yahoo.com/search?p={encoded_query}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-TW,zh;q=0.9",
            }
            
            resp = self.session.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                return results
            
            soup = BeautifulSoup(resp.text, "lxml")
            
            # Yahoo 結果選擇器
            for item in soup.select("div.dd.algo, li.searchCenterMiddle, .algo"):
                title_tag = item.select_one("h3 a") or item.select_one("a.ac-algo")
                snippet_tag = item.select_one("p") or item.select_one(".compText")
                
                if title_tag:
                    title = title_tag.get_text(strip=True)
                    href = title_tag.get("href", "")
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                    
                    combined_text = title + snippet
                    detected_negative = any(kw in combined_text for kw in negative_keywords)
                    
                    if title and href and href.startswith("http"):
                        results.append({
                            "title": title,
                            "url": href,
                            "snippet": snippet[:300],
                            "is_negative": is_negative or detected_negative,
                        })
        
        except Exception as e:
            logger.error(f"Yahoo 搜尋失敗: {e}")
        
        return results[:10]

    def _google_search(self, query: str, is_negative: bool = False) -> list[dict]:
        """備用 Google 搜尋"""
        results = []
        negative_keywords = self._get_negative_keywords()

        try:
            url = "https://www.google.com/search"
            params = {"q": query, "hl": "zh-TW", "num": 10}

            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                return results

            soup = BeautifulSoup(resp.text, "lxml")

            for g_div in soup.select("div.g, div[data-hveid]"):
                title_tag = g_div.select_one("h3")
                link_tag = g_div.select_one("a[href]")
                snippet_tag = g_div.select_one("div.VwiC3b, span.st, div[data-sncf]")

                if title_tag and link_tag:
                    href = link_tag.get("href", "")
                    if href.startswith("/url?q="):
                        href = href.split("/url?q=")[1].split("&")[0]

                    title = title_tag.get_text(strip=True)
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                    
                    combined_text = title + snippet
                    detected_negative = any(kw in combined_text for kw in negative_keywords)

                    results.append({
                        "title": title,
                        "url": href,
                        "snippet": snippet,
                        "is_negative": is_negative or detected_negative,
                    })

        except Exception as e:
            logger.error(f"Google 搜尋解析失敗: {e}")

        return results

    def _duckduckgo_search(self, query: str, is_negative: bool, negative_keywords: list) -> list[dict]:
        """使用 DuckDuckGo HTML 搜尋"""
        results = []
        
        try:
            # DuckDuckGo HTML 版本
            url = "https://html.duckduckgo.com/html/"
            data = {"q": query, "kl": "tw-tzh"}
            
            headers = {
                "User-Agent": ua.random,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            
            resp = self.session.post(url, data=data, headers=headers, timeout=15)
            if resp.status_code != 200:
                return results
                
            soup = BeautifulSoup(resp.text, "lxml")
            
            # DuckDuckGo 結果選擇器
            for result in soup.select(".result, .results_links"):
                title_tag = result.select_one(".result__title a, .result__a")
                snippet_tag = result.select_one(".result__snippet")
                
                if title_tag:
                    title = title_tag.get_text(strip=True)
                    href = title_tag.get("href", "")
                    
                    # 清理 DuckDuckGo 的重定向 URL
                    if "uddg=" in href:
                        import urllib.parse
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        href = parsed.get("uddg", [href])[0]
                    
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                    
                    # 檢測負面新聞
                    combined_text = title + snippet
                    detected_negative = any(kw in combined_text for kw in negative_keywords)
                    
                    if title and href:
                        results.append({
                            "title": title,
                            "url": href,
                            "snippet": snippet,
                            "is_negative": is_negative or detected_negative,
                        })
            
        except Exception as e:
            logger.error(f"DuckDuckGo 搜尋失敗: {e}")
        
        return results[:10]
