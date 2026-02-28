import argparse
import asyncio
import os
from datetime import datetime
import re
import json
import sys
import io
import logging
from playwright.async_api import async_playwright
from db.db import Database

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

def extract_price(text):
    if not text:
        return None
    cleaned = re.sub(r"[,\s₹]", "", text)
    match = re.search(r"[\d.]+", cleaned)
    return float(match.group()) if match else None


def extract_discount(text):
    if not text:
        return None
    match = re.search(r"(\d+)%", text)
    return int(match.group(1)) if match else None


async def scrape_truemeds(browser, medicine_name, max_products=10):
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
    )
    page = await context.new_page()

    results = []

    try:
        search_url = (
            f"https://www.truemeds.in/search/{medicine_name.lower().replace(' ', '%20')}"
        )
        logging.info(f"Scraping TrueMeds: {search_url}")

        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        
        # Wait for product cards to appear
        # The observed classes sc-f8b3c8b1-0 is part of the card
        card_selector = 'div[class*="sc-f8b3c8b1-0"]'
        try:
            await page.wait_for_selector(card_selector, timeout=5000)
        except:
            logging.warning("No product cards found within timeout. Page might have different structure.")
            # Fallback to a more generic selector if needed
            card_selector = 'div:has(img) + div:has(button:has-text("Add To Cart"))'
            # Note: the above is a complex selector but might work if classes are missing

        cards = await page.query_selector(card_selector)
        logging.info(f"Found {len(cards)} product cards")

        for i, card in enumerate(cards):
            if len(results) >= max_products:
                break
                
            # Name: typically a bold p tag or similar
            name_el = await card.query_selector('p[class*="sc-f8b3c8b1-11"]')
            if not name_el:
                 name_el = await card.query_selector('div > div:first-child') # fallback
            name = await name_el.inner_text() if name_el else ""
            
            # Marketer
            marketer_el = await card.query_selector('p[class*="sc-f8b3c8b1-14"]')
            marketer = await marketer_el.inner_text() if marketer_el else ""
            
            # Pack
            pack_el = await card.query_selector('p[class*="sc-f8b3c8b1-15"]')
            pack = await pack_el.inner_text() if pack_el else ""
            
            # Price info container
            price_container = await card.query_selector('div[class*="sc-f8b3c8b1-18"]')
            price_text = ""
            mrp_text = ""
            discount_text = ""
            
            if price_container:
                price_el = await price_container.query_selector('div[class*="sc-f8b3c8b1-17"]')
                if price_el: price_text = await price_el.inner_text()
                
                mrp_el = await price_container.query_selector('div[class*="sc-f8b3c8b1-20"]')
                if mrp_el: mrp_text = await mrp_el.inner_text()
                
                discount_el = await price_container.query_selector('div[class*="sc-f8b3c8b1-21"]')
                if discount_el: discount_text = await discount_el.inner_text()

            # Stock status
            add_to_cart = await card.query_selector('button:has-text("Add To Cart")')
            stock_status = "In Stock" if add_to_cart else "Out of Stock"
            
            if name:
                results.append({
                    "medicine_name": name.strip(),
                    "medicine_url": f"{search_url}#prod-{i}",
                    "medicine_id": None,
                    "mrp": extract_price(mrp_text) if mrp_text else None,
                    "selling_price": extract_price(price_text) if price_text else None,
                    "discount_percentage": str(extract_discount(discount_text)) if discount_text else None,
                    "expected_delivery_date": None,
                    "in_stock": stock_status == "In Stock",
                    "stock_status": stock_status,
                    "pack_size_quantity": pack.strip(),
                    "medicine_marketer": marketer.strip(),
                })
                logging.debug(f"  [OK] {name[:35]} | Rs.{extract_price(price_text)}")

        logging.info(f"Successfully scraped {len(results)} products from TrueMeds")

    except Exception as e:
        logging.error(f"Error scraping TrueMeds: {e}")
    finally:
        await context.close()

    return results



async def scrape_truemeds_product_detail(browser, product_url):
    """
    Scrapes detailed information for a specific product from TrueMeds using product page selectors.
    """
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
    )
    page = await context.new_page()
    
    result = {
        "medicine_url": product_url,
        "medicine_name": None,
        "medicine_composition": None,
        "medicine_marketer": None,
        "medicine_storage": None,
        "medicine_mrp": None,
        "medicine_selling_price": None,
        "medicine_discount": None,
        "pack_size_information": None,
        "substitutes": [],
        "generic_alternative_available": False,
        "generic_alternative": None
    }

    try:
        if '#prod-' in product_url:
             logging.warning(f"Product detail scraping requires a direct product URL, not a search fragment: {product_url}")
             return result

        logging.info(f"Scraping TrueMeds product detail: {product_url}")
        await page.goto(product_url, wait_until="networkidle", timeout=90000)

        # Name: h1
        name_el = await page.query_selector('h1')
        if name_el: result["medicine_name"] = (await name_el.inner_text()).strip()

        # Marketer: a.medCompany
        marketer_el = await page.query_selector('a.medCompany')
        if marketer_el: result["medicine_marketer"] = (await marketer_el.inner_text()).strip()

        # Salt: .compositionValue a
        salt_el = await page.query_selector('.compositionValue a')
        if salt_el: result["medicine_composition"] = (await salt_el.inner_text()).strip()

        # Pricing
        mrp_el = await page.query_selector('.mrp')
        if mrp_el: result["medicine_mrp"] = extract_price(await mrp_el.inner_text())

        price_el = await page.query_selector('.sellingPrice')
        if price_el: result["medicine_selling_price"] = extract_price(await price_el.inner_text())

        discount_el = await page.query_selector('.discountPercentage')
        if discount_el: result["medicine_discount"] = extract_discount(await discount_el.inner_text())

        # Storage
        # Typically after a div with text "Storage" or id storage
        storage_el = await page.query_selector('#storage + div, #storage + p')
        if storage_el: result["medicine_storage"] = (await storage_el.inner_text()).strip()

        # Substitutes
        sub_elements = await page.query_selector_all('.medName')
        for sub_el in sub_elements:
            sub_name = await sub_el.inner_text()
            if sub_name:
                result["substitutes"].append({"name": sub_name.strip()})

    except Exception as e:
        logging.error(f"Error scraping TrueMeds product detail: {e}")
    finally:
        await context.close()
    return result


async def main(medicine_name, max_products=15, headless=True, dbase=None):
    logging.info(f"Searching TrueMeds for: {medicine_name} (max {max_products} products)")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        results = await scrape_truemeds(browser, medicine_name, max_products)
        await browser.close()

    for result in results:
        if dbase:
            dbase.insert_medicine(result, 'TrueMeds')

    if dbase:
        dbase.mark_brand_as_searched(medicine_name, 'TrueMeds')

async def main2(medicine_url, headless=True, dbase=None):
    logging.info(f"Scraping TrueMeds details for: {medicine_url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        result = await scrape_truemeds_product_detail(browser, medicine_url)
        await browser.close()

    if dbase and result:
        dbase.insert_scraped_details(result, 'TrueMeds')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape TrueMeds for medicine information.")
    parser.add_argument("medicine_name", nargs="?", help="Name of the medicine to search for")
    parser.add_argument("--limit", type=int, default=15, help="Limit the number of products to scrape")
    parser.add_argument("--headless", action="store_true", default=True, help="Run in headless mode")
    parser.add_argument("--brands", action="store_true", help="Extract brands using search from file")
    parser.add_argument("--detail", action="store_true", help="Extract detailed data for existing brands")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()
    
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, 'db', 'db.duckdb')
    dbase = Database(dbpath=db_path)
    dbase.init()

    if args.brands:
        brands_file = os.path.join(script_dir, 'brands_to_fetch.txt')
        if os.path.exists(brands_file):
            with open(brands_file, 'r') as f:
                brands = f.read().splitlines()
            for brand in brands:
                if brand.strip():
                    asyncio.run(main(brand, max_products=args.limit, headless=args.headless, dbase=dbase))
    elif args.detail:
        brands = dbase.get_brands(source='TrueMeds')
        for _, row in brands.iterrows():
            asyncio.run(main2(row['url'], headless=args.headless, dbase=dbase))
    elif args.medicine_name:
        asyncio.run(main(args.medicine_name, max_products=args.limit, headless=args.headless, dbase=dbase))
    else:
        parser.print_help()
