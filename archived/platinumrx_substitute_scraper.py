import asyncio
import csv
import os
import re
from playwright.async_api import async_playwright

# Configuration
INPUT_FILE = "platinumrx_all_medicines.csv"
OUTPUT_FILE = "platinumrx_medicines_with_substitutes.csv"
CONCURRENCY = 5  # Reduced for stability
HEADLESS = True

def extract_price(text):
    if not text:
        return None
    cleaned = re.sub(r"[,\s₹]", "", text)
    match = re.search(r"[\d.]+", cleaned)
    return float(match.group()) if match else None

async def scrape_detail_page(browser_context, original_item, semaphore, writer, f_out, lock):
    async with semaphore:
        url = original_item['url']
        print(f"Processing: {url}")
        
        page = await browser_context.new_page()
        try:
            # Set a shorter timeout for navigation but wait for content
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(3000) # Wait for hydration
            
            # Try to find the recommendation container using class or text
            container = await page.query_selector('div[class*="conditionalsubstituteContainer"]')
            if not container:
                # Fallback: Find the div that contains "Our Recommendation" and pick its parent/sibling
                recommendation_header = await page.query_selector('div:has-text("Our Recommendation")')
                if recommendation_header:
                    # In many layouts, the actual info is in a sibling or the same container
                    container = recommendation_header
            
            sub_name = "N/A"
            sub_mrp = "N/A"
            sub_price = "N/A"
            sub_pack = "N/A"
            found_sub = False

            if container:
                container_text = await container.inner_text()
                if "unavailable" in container_text.lower():
                    sub_name = "Substitute currently unavailable"
                    found_sub = False
                else:
                    found_sub = True
                    # Extract Name
                    name_el = await container.query_selector('p[class*="displayName"], div[class*="displayName"]')
                    if name_el:
                        sub_name = (await name_el.inner_text()).strip()
                    
                    # Extract Pack
                    pack_el = await container.query_selector('div[class*="drugCategory"]')
                    if pack_el:
                        sub_pack = (await pack_el.inner_text()).strip()
                        # Clean up "Strip of" etc if it has comments
                        sub_pack = sub_pack.replace('\n', ' ').strip()
                    
                    # Extract Selling Price
                    price_el = await container.query_selector('p[class*="substitutePrice"]')
                    if price_el:
                        sub_price = str(extract_price(await price_el.inner_text()))
                    
                    # Extract MRP
                    mrp_el = await container.query_selector('p[class*="itemMrp"]')
                    if mrp_el:
                        sub_mrp = str(extract_price(await mrp_el.inner_text()))

            # Original details (from page to confirm)
            orig_price = "N/A"
            orig_pack = "N/A"
            # Look for "You Searched" area
            search_container = await page.query_selector('div:has-text("You Searched")')
            if search_container:
                # Based on previous dump, it's nearby
                lines = [l.strip() for l in (await search_container.inner_text()).split('\n') if l.strip()]
                if "You Searched" in lines:
                    idx = lines.index("You Searched")
                    for i in range(idx+1, min(idx+10, len(lines))):
                        line = lines[i]
                        if any(x in line for x in ["Strip of", "Bottle of", "Tube of", "Capsule of"]):
                            orig_pack = line
                        elif "₹" in line and "/" not in line:
                            val = extract_price(line)
                            if val:
                                orig_price = str(val)
                                break
            
            output_row = {
                'original_name': original_item['name'],
                'original_url': url,
                'original_price': orig_price,
                'original_pack': orig_pack,
                'has_substitute': 'Yes' if found_sub else 'No',
                'substitute_name': sub_name,
                'substitute_mrp': sub_mrp,
                'substitute_selling_price': sub_price,
                'substitute_pack': sub_pack
            }
            
            async with lock:
                writer.writerow(output_row)
                f_out.flush()
            
            print(f"  [OK] {original_item['name']} -> Sub: {sub_name if found_sub else 'None'}")
            
        except Exception as e:
            print(f"  [ERR] {url}: {e}")
        finally:
            await page.close()

async def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found. Run the list scraper first.")
        return

    # Read original medicines
    originals = []
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            originals.append(row)
    
    print(f"Found {len(originals)} medicines to process.")

    # Check for progress
    processed_urls = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                processed_urls.add(row['original_url'])
    
    remaining = [o for o in originals if o['url'] not in processed_urls]
    print(f"Remaining: {len(remaining)} (Already processed: {len(processed_urls)})")

    fieldnames = [
        'original_name', 'original_url', 'original_price', 'original_pack',
        'has_substitute', 'substitute_name', 'substitute_mrp', 
        'substitute_selling_price', 'substitute_pack'
    ]
    
    lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        mode = 'a' if os.path.exists(OUTPUT_FILE) else 'w'
        with open(OUTPUT_FILE, mode, newline='', encoding='utf-8') as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            if mode == 'w':
                writer.writeheader()
            
            tasks = [scrape_detail_page(context, item, semaphore, writer, f_out, lock) for item in remaining]
            await asyncio.gather(*tasks)
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
