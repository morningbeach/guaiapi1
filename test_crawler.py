from court_crawler import CourtCrawler
import logging

logging.basicConfig(level=logging.DEBUG)
crawler = CourtCrawler()
cases = crawler.search_by_name("邱于軒", "all")

print("FOUND CASES:", len(cases))
for c in cases[:5]:
    print(c.to_dict())
