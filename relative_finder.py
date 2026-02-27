"""
近親搜尋模組
透過公開資料搜尋公眾人物的近親關係
資料來源：維基百科、新聞報導等公開資訊
"""
import re
import logging
from dataclasses import dataclass, asdict

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from config import Config

logger = logging.getLogger(__name__)
ua = UserAgent(fallback="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")

# 中文親屬關係詞彙
RELATION_KEYWORDS = {
    # 配偶
    "配偶": ["妻子", "丈夫", "配偶", "夫人", "先生", "太太", "老婆", "老公", "妻", "夫"],
    # 父母
    "父母": ["父親", "母親", "父", "母", "爸爸", "媽媽", "生父", "生母", "繼父", "繼母", "養父", "養母"],
    # 子女
    "子女": ["兒子", "女兒", "長子", "次子", "長女", "次女", "子", "女", "養子", "養女"],
    # 兄弟姊妹
    "兄弟姊妹": ["兄長", "弟弟", "姊姊", "妹妹", "兄", "弟", "姊", "妹", "胞兄", "胞弟", "胞姊", "胞妹",
                "哥哥", "姐姐"],
    # 其他親屬
    "其他親屬": ["祖父", "祖母", "外祖父", "外祖母", "岳父", "岳母", "公公", "婆婆",
                "叔叔", "伯父", "舅舅", "姑姑", "阿姨", "姪子", "姪女", "外甥", "外甥女",
                "孫子", "孫女", "外孫", "外孫女", "媳婦", "女婿", "嫂嫂", "弟媳"],
}

# 建立反向對照表：關係詞 → 類別
RELATION_WORD_MAP = {}
for category, words in RELATION_KEYWORDS.items():
    for word in words:
        RELATION_WORD_MAP[word] = category


@dataclass
class Relative:
    """親屬資料結構"""
    name: str              # 姓名
    relation: str          # 與目標人物的關係
    relation_category: str  # 關係類別
    source: str = ""       # 資料來源
    confidence: str = "中"  # 可信度（高/中/低）

    def to_dict(self) -> dict:
        return asdict(self)


class RelativeFinder:
    """
    公眾人物近親搜尋器
    透過維基百科和新聞報導搜尋公眾人物的親屬
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": ua.random,
            "Accept-Language": "zh-TW,zh;q=0.9",
        })

    def find_relatives(self, name: str) -> list[Relative]:
        """
        搜尋公眾人物的近親

        Args:
            name: 公眾人物姓名

        Returns:
            Relative 列表
        """
        relatives = []

        # 1. 從維基百科搜尋
        wiki_relatives = self._search_wikipedia(name)
        relatives.extend(wiki_relatives)

        # 2. 從新聞報導搜尋
        news_relatives = self._search_news(name)
        relatives.extend(news_relatives)

        # 去重
        seen = set()
        unique_relatives = []
        for r in relatives:
            key = (r.name, r.relation_category)
            if key not in seen and r.name != name:
                seen.add(key)
                unique_relatives.append(r)

        return unique_relatives

    def _search_wikipedia(self, name: str) -> list[Relative]:
        """從維基百科搜尋親屬資訊"""
        relatives = []

        try:
            # 使用中文維基百科 API
            api_url = "https://zh.wikipedia.org/w/api.php"

            # Step 1: 搜尋頁面
            search_params = {
                "action": "query",
                "list": "search",
                "srsearch": name,
                "srnamespace": "0",
                "srlimit": 3,
                "format": "json",
            }

            resp = self.session.get(api_url, params=search_params, timeout=10)
            if resp.status_code != 200:
                return relatives

            data = resp.json()
            search_results = data.get("query", {}).get("search", [])

            if not search_results:
                return relatives

            # Step 2: 取得頁面內容
            page_title = search_results[0].get("title", "")
            content_params = {
                "action": "parse",
                "page": page_title,
                "prop": "text|wikitext",
                "format": "json",
            }

            resp = self.session.get(api_url, params=content_params, timeout=10)
            if resp.status_code != 200:
                return relatives

            data = resp.json()
            html_content = data.get("parse", {}).get("text", {}).get("*", "")
            wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")

            # 從 HTML 解析 infobox
            relatives.extend(self._parse_wiki_infobox(html_content, name))

            # 從 wikitext 解析親屬關係
            relatives.extend(self._parse_wiki_text(wikitext or html_content, name))

        except Exception as e:
            logger.error(f"維基百科搜尋失敗: {e}")

        return relatives

    def _parse_wiki_infobox(self, html: str, target_name: str) -> list[Relative]:
        """解析維基百科 infobox 中的親屬資訊"""
        relatives = []
        soup = BeautifulSoup(html, "lxml")

        # 找 infobox 表格
        infobox = soup.select_one("table.infobox, table.vcard, .infobox")
        if not infobox:
            return relatives

        rows = infobox.select("tr")
        for row in rows:
            header = row.select_one("th")
            value = row.select_one("td")

            if not header or not value:
                continue

            header_text = header.get_text(strip=True)
            value_text = value.get_text(strip=True)

            # 檢查是否為親屬關係欄位
            for relation_word, category in RELATION_WORD_MAP.items():
                if relation_word in header_text:
                    # 提取姓名（通常是連結文字或純文字）
                    names = self._extract_names_from_text(value_text)
                    for n in names:
                        if n != target_name:
                            # 使用嚴格的姓名驗證
                            if self._is_valid_chinese_name(n) and not self._is_common_word(n):
                                relatives.append(Relative(
                                    name=n,
                                    relation=header_text,
                                    relation_category=category,
                                    source="維基百科",
                                    confidence="高",
                                ))
                    break

        return relatives

    def _parse_wiki_text(self, text: str, target_name: str) -> list[Relative]:
        """從維基百科文字內容中提取親屬關係"""
        relatives = []

        # 清理 HTML 標籤
        clean_text = BeautifulSoup(text, "lxml").get_text() if "<" in text else text

        # 搜尋親屬關係模式
        for relation_word, category in RELATION_WORD_MAP.items():
            # 模式：「其{關係詞}{姓名}」或「{關係詞}為{姓名}」
            patterns = [
                rf"(?:{relation_word})\s*(?:為|是|叫做?|名[為叫]?)\s*([\u4e00-\u9fff]{{2,4}})",
                rf"([\u4e00-\u9fff]{{2,4}})\s*(?:是|為)\s*(?:其|他的?|她的?)\s*{relation_word}",
                rf"(?:其|他的?|她的?)\s*{relation_word}\s*([\u4e00-\u9fff]{{2,4}})",
                rf"{relation_word}\s*[：:]\s*([\u4e00-\u9fff]{{2,4}})",
            ]

            for pattern in patterns:
                matches = re.findall(pattern, clean_text)
                for match in matches:
                    extracted_name = match.strip()
                    if extracted_name and extracted_name != target_name:
                        # 使用嚴格的姓名驗證
                        if self._is_valid_chinese_name(extracted_name) and not self._is_common_word(extracted_name):
                            relatives.append(Relative(
                                name=extracted_name,
                                relation=relation_word,
                                relation_category=category,
                                source="維基百科",
                                confidence="中",
                            ))

        return relatives

    def _search_news(self, name: str) -> list[Relative]:
        """從新聞報導搜尋親屬資訊（使用 Bing）"""
        relatives = []

        try:
            # 使用 Bing 搜尋新聞中的親屬關係
            query = f"{name} 家人 親屬 配偶 子女 父母"
            url = "https://www.bing.com/search"
            params = {"q": query, "setlang": "zh-TW", "count": 10}
            
            headers = {
                "User-Agent": ua.random,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            }

            resp = self.session.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code != 200:
                return relatives

            soup = BeautifulSoup(resp.text, "lxml")

            # 提取 Bing 搜尋結果摘要
            snippets = []
            for item in soup.select("li.b_algo, .b_algo"):
                caption = item.select_one(".b_caption p, p")
                if caption:
                    snippets.append(caption.get_text(strip=True))

            # 從摘要中提取親屬關係
            full_text = " ".join(snippets)
            for relation_word, category in RELATION_WORD_MAP.items():
                if relation_word in full_text:
                    patterns = [
                        rf"(?:{relation_word})\s*([\u4e00-\u9fff]{{2,4}})",
                        rf"([\u4e00-\u9fff]{{2,4}})\s*(?:是|為).*?{relation_word}",
                    ]
                    for pattern in patterns:
                        matches = re.findall(pattern, full_text)
                        for match in matches:
                            n = match.strip()
                            if n and n != name:
                                # 使用嚴格的姓名驗證
                                if self._is_valid_chinese_name(n) and not self._is_common_word(n):
                                    relatives.append(Relative(
                                        name=n,
                                        relation=relation_word,
                                        relation_category=category,
                                        source="新聞報導",
                                        confidence="低",
                                    ))

        except Exception as e:
            logger.error(f"新聞搜尋失敗: {e}")

        return relatives

    @staticmethod
    def _extract_names_from_text(text: str) -> list[str]:
        """從文字中提取中文姓名"""
        # 移除括號內容
        clean = re.sub(r"[（\(].+?[）\)]", "", text)
        # 分割多個姓名
        names = re.split(r"[、，,；;\s]+", clean)
        # 過濾有效姓名（2-4 個中文字）
        valid_names = []
        for n in names:
            n = n.strip()
            if re.match(r"^[\u4e00-\u9fff]{2,4}$", n):
                valid_names.append(n)
        return valid_names

    @staticmethod
    def _is_common_word(text: str) -> bool:
        """檢查是否為常見非人名詞彙"""
        common_words = {
            # 常見動詞/副詞
            "表示", "認為", "指出", "透露", "曾經", "目前", "之後",
            "當時", "因此", "但是", "雖然", "不過", "然而", "其中",
            "這些", "那些", "已經", "可能", "應該", "似乎", "根據",
            "沒錯", "沒有", "可以", "不能", "不要", "還是", "就是",
            "因為", "所以", "而且", "或者", "如果", "那麼", "這樣",
            "怎麼", "什麼", "為何", "為什", "哪裡", "哪些", "這個",
            "那個", "自己", "他們", "她們", "我們", "你們", "大家",
            # 常見名詞
            "政府", "公司", "社會", "國家", "台灣", "中國", "世界",
            "記者", "媒體", "報導", "新聞", "調查", "選舉", "政治",
            "環保", "蟑螂", "老鼠", "問題", "事件", "案件", "情況",
            "時間", "地點", "方式", "原因", "結果", "影響", "關係",
            "市長", "議員", "立委", "部長", "院長", "總統", "主席",
            "縣長", "鄉長", "區長", "村長", "里長", "局長", "處長",
            "警察", "檢察", "法官", "律師", "醫生", "老師", "教授",
            # 負面詞彙（不會是人名）
            "貪污", "詐欺", "詐騙", "洗錢", "逃稅", "受賄", "行賄",
            "醜聞", "爭議", "違法", "違規", "犯罪", "前科", "判刑",
            "起訴", "緩刑", "無罪", "有罪", "開庭", "審判", "上訴",
        }
        
        # 檢查是否包含常見詞
        if text in common_words:
            return True
        
        # 檢查是否包含非人名特徵
        non_name_patterns = [
            "蟑螂", "老鼠", "環保", "沒錯", "不是", "就是", "還是",
            "可能", "應該", "怎麼", "什麼", "為何", "其他", "之後",
        ]
        for pattern in non_name_patterns:
            if pattern in text:
                return True
        
        return False
    
    @staticmethod
    def _is_valid_chinese_name(name: str) -> bool:
        """檢查是否為有效的中文姓名"""
        if not name or len(name) < 2 or len(name) > 4:
            return False
        
        # 必須全部是中文字
        if not re.match(r"^[\u4e00-\u9fff]+$", name):
            return False
        
        # 常見中文姓氏（前 100 大）
        common_surnames = {
            "陳", "林", "黃", "張", "李", "王", "吳", "劉", "蔡", "楊",
            "許", "鄭", "謝", "郭", "洪", "曾", "邱", "廖", "賴", "周",
            "徐", "蘇", "葉", "莊", "呂", "江", "何", "蕭", "羅", "高",
            "潘", "簡", "朱", "鍾", "彭", "游", "詹", "胡", "施", "沈",
            "余", "趙", "盧", "梁", "顏", "柯", "翁", "魏", "孫", "戴",
            "范", "方", "宋", "鄧", "杜", "傅", "侯", "曹", "薛", "丁",
            "卓", "馬", "阮", "董", "唐", "温", "藍", "石", "蔣", "古",
            "紀", "姚", "連", "馮", "歐", "程", "湯", "黃", "田", "康",
            "姜", "白", "汪", "鄒", "尤", "巫", "鑽", "錢", "卜", "金",
            "童", "陸", "夏", "柳", "凃", "邵", "錡", "韓", "龔", "嚴",
        }
        
        # 檢查第一個字是否為常見姓氏
        first_char = name[0]
        if first_char not in common_surnames:
            # 如果不是常見姓氏，可信度較低但不完全排除
            # 檢查是否包含明顯的非人名詞
            if RelativeFinder._is_common_word(name):
                return False
        
        return True
