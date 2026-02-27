from playwright.sync_api import sync_playwright
import time

def scrape_fjud(keyword: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print(f"Navigating to FJUD for keyword: {keyword}")
        page.goto("https://judgment.judicial.gov.tw/FJUD/default.aspx", wait_until="networkidle")
        
        page.fill("#txtKW", keyword)
        print("Clicking search...")
        
        # Click and wait for navigation
        with page.expect_navigation(wait_until="domcontentloaded"):
            page.click("#btnSimpleQry")
            
        print("Waiting for iframe...")
        iframe_locator = page.frame_locator("#iframe-data")
        
        try:
            # Wait for the result table inside the iframe
            iframe_locator.locator("table#jud").wait_for(timeout=10000)
            
            rows = iframe_locator.locator("table#jud tbody tr, table#jud tr").element_handles()
            print(f"Found {len(rows)} rows.")
            
            for i, row in enumerate(rows[:5]):
                text = row.inner_text().replace('\n', ' ')
                print(f"{i+1}. {text[:200]}")
                
            links = iframe_locator.locator("table#jud tr a").element_handles()
            if links:
                print("Clicking first link...")
                # The link opens in the SAME iframe usually, or updates the whole page.
                with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                    links[0].click()
                
                content = iframe_locator.locator("#jud_content, .judgement-content").first
                if content.count() > 0:
                    text_len = len(content.inner_text())
                    print("Full text length:", text_len)
                    print("Snippet:", content.inner_text()[:100].replace('\n', ' '))
                else:
                    print("Could not find full text div after click.")
                    
        except Exception as e:
            print("No cases found or timeout:", e)
            
        browser.close()

if __name__ == "__main__":
    print("--- Searching 柯文哲 ---")
    scrape_fjud("柯文哲")
    print("\n--- Searching 邱于軒 ---")
    scrape_fjud("邱于軒")
