import asyncio
import csv
import json
import os
from playwright.async_api import async_playwright

# Configuration
BASE_URL = "https://www.platinumrx.in/medicines"
OUTPUT_FILE = "platinumrx_all_medicines.csv"
HEADLESS = True

async def get_max_page(page, label):
    """Find the maximum page number for a given label."""
    try:
        url = f"{BASE_URL}?label={label}"
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000) # Wait for hydration
        
        pagination_elements = await page.query_selector_all('a[href*="page="]')
        page_numbers = []
        for el in pagination_elements:
            text = await el.inner_text()
            if text.isdigit():
                page_numbers.append(int(text))
        
        return max(page_numbers) if page_numbers else 0
    except Exception as e:
        print(f"  Error getting max page for label {label}: {e}")
        return 0

async def scrape_page(page, label, page_num):
    """Scrape a single list page for items."""
    url = f"{BASE_URL}?label={label}&page={page_num}"
    print(f"  Scraping Label: {label}, Page: {page_num} -> {url}")
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2000)
        
        items = await page.query_selector_all('a[href^="/medicines/"]')
        page_data = []
        
        for item in items:
            text = await item.inner_text()
            href = await item.get_attribute('href')
            
            if "View Product" in text:
                # Extract name - usually the first line
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                name = lines[0] if lines else "N/A"
                
                # Full URL
                full_url = f"https://www.platinumrx.in{href}" if href.startswith('/') else href
                
                page_data.append({
                    'label': label,
                    'page': page_num,
                    'name': name,
                    'url': full_url
                })
        
        return page_data
    except Exception as e:
        print(f"  Error scraping page {page_num} for label {label}: {e}")
        return []

async def main():
    # Initialize CSV file
    file_exists = os.path.isfile(OUTPUT_FILE)
    fieldnames = ['label', 'page', 'name', 'url']
    
    # Labels to scrape
    labels = ['0-9'] + [chr(i) for i in range(ord('A'), ord('Z') + 1)]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            
            for label in labels:
                print(f"Starting Scrape for Label: {label}")
                max_page = await get_max_page(page, label)
                print(f"Found {max_page + 1} pages for label {label}")
                
                for page_num in range(max_page + 1):
                    items = await scrape_page(page, label, page_num)
                    if items:
                        writer.writerows(items)
                        f.flush() # Save to disk after each page
                        print(f"    Saved {len(items)} items.")
                    else:
                        print(f"    No items found on page {page_num}.")
                    
                    # Small sleep to be polite
                    await asyncio.sleep(1)
                
                print(f"Completed Label: {label}\n")

        await browser.close()
    print(f"Scraping completed. Data saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
