import argparse
import asyncio
import os
# from datetime import datetime
import re
# import json
import sys
# import io
import logging
# from playwright.async_api import async_playwright
from db.db import Database
import requests

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

def extract_price(text):
    text = text.__str__()
    if not text:
        return None
    cleaned = re.sub(r"[,\s₹]", "", text)
    match = re.search(r"[\d.]+", cleaned)
    return float(match.group()) if match else None


def extract_discount(text):
    text = text.__str__()
    if not text:
        return None
    match = re.search(r"(\d+.?)", text)
    return float(match.group(1)) if match else None


async def scrape_truemeds(medicine_name, max_products=10):
    url = "https://nal.tmmumbai.in/CustomerService/getSearchResult"
    querystring = {"warehouseId":"20","elasticSearchType":"SKU_BRAND_SEARCH","searchString":medicine_name,"isMultiSearch":"true","pageName":"srp","variantId":"18","platform":"m_web"}
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-GB,en;q=0.5",
        "access-control-allow-origin": "*",
        "origin": "https://www.truemeds.in",
        "priority": "u=1, i",
        "referer": "https://www.truemeds.in/",
        "sec-ch-ua": "\"Not:A-Brand\";v=\"99\", \"Brave\";v=\"145\", \"Chromium\";v=\"145\"",
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": "\"Android\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
        "sec-gpc": "1",
        "strict-origin-when-cross-origin": "*"
    }

    try:
        logging.info(f"Searching TrueMeds via API for: {medicine_name}")
        response = requests.get(url, headers=headers, params=querystring)
        if response.status_code != 200:
            logging.error(f"API failed with status {response.status_code}")
            return []

        data = response.json()
        logging.debug(f"API response: {data}")
        results = []
        for item in data.get("responseData", []).get("elasticProductDetails", []):
            master = item.get("product", {})
            substitute = item.get("suggestion", {})
            if not substitute:
                substitute = {k: "" for k, v in master.items()}
            logging.debug(f"Master item: {master}")
            logging.debug(f"Substitute item: {substitute}")
            if not master: continue

            # Use display_name and salt for construction of a tracking URL
            name = master.get("skuName", "")
            salt = master.get("composition", "")
            drug_id = master.get("productCode", "")
            manufacturer_name = master.get("manufacturerName", "")

            # URL will be used in stage 2 (detail) to fetch substitutes by salt
            url_slug = master.get("productUrlSuffix", "")
            medicine_url = f"https://www.truemeds.in/{url_slug}"

            substitute_name = substitute.get("skuName", "")
            substitute_salt = substitute.get("composition", "")
            substitute_drug_id = substitute.get("productCode", "")
            substitute_manufacturer_name = substitute.get("manufacturerName", "")
            substitute_url_slug = substitute.get("productUrlSuffix", "")
            substitute_url = f"https://www.truemeds.in/{substitute_url_slug}"

            # result = {
            #     "medicine_url": medicine_url,
            #     "medicine_name": None,
            #     "medicine_composition": salt_name,
            #     "medicine_marketer": None,
            #     "medicine_storage": None,
            #     "medicine_mrp": None,
            #     "medicine_selling_price": None,
            #     "medicine_discount": None,
            #     "pack_size_information": None,
            #     "substitutes": [],
            #     "generic_alternative_available": False,
            #     "generic_alternative": None
            # }
            # "{""alternate_name"": ""Betaone Xl 25 Tablet"", ""url"": ""https://www.1mg.com/drugs/betaone-xl-25-tablet-356970"", ""price"": 56.5, ""by_who"": ""Dr Reddy's Laboratories Ltd"", ""contains_what"": ""Contains: Metoprolol Succinate (23.75mg)""}"

            results.append({
                "medicine_url": medicine_url,
                "medicine_id": drug_id,
                "medicine_name": name,
                "medicine_composition": salt,
                "medicine_marketer": manufacturer_name,
                "medicine_storage": "Cold storage" if master.get("coldStorage") else None,
                "medicine_mrp": extract_price(master.get("mrp")),
                "medicine_selling_price": extract_price(master.get("sellingPrice")),
                "medicine_discount": extract_discount(master.get("discount")),
                "pack_size_information": f"{master.get('packForm')}",
                "substitutes": [substitute],
                "generic_alternative_available": master.get("subsFound", False),
                "generic_alternative": {"alternate_name": substitute_name, "url": substitute_url,
                                        "price": extract_price(substitute.get("sellingPrice", None)),
                                        "by_who": substitute_manufacturer_name, "contains_what": substitute_salt} if substitute else None
            })
        return results
    except Exception as e:
        logging.error(f"Error in scrape_truemeds: {e}")
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        logging.error(exc_type, fname, exc_tb.tb_lineno)
        return []


async def scrape_truemeds_product_detail(browser, product_url):
    """
    Scrapes detailed information for a specific product from TrueMeds using product page selectors.
    """
#     context = await browser.new_context(
#         user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
#         viewport={"width": 1920, "height": 1080},
#     )
#     page = await context.new_page()
#
#     result = {
#         "medicine_url": product_url,
#         "medicine_name": None,
#         "medicine_composition": None,
#         "medicine_marketer": None,
#         "medicine_storage": None,
#         "medicine_mrp": None,
#         "medicine_selling_price": None,
#         "medicine_discount": None,
#         "pack_size_information": None,
#         "substitutes": [],
#         "generic_alternative_available": False,
#         "generic_alternative": None
#     }
#
#     try:
#         if '#prod-' in product_url:
#              logging.warning(f"Product detail scraping requires a direct product URL, not a search fragment: {product_url}")
#              return result
#
#         logging.info(f"Scraping TrueMeds product detail: {product_url}")
#         await page.goto(product_url, wait_until="networkidle", timeout=90000)
#
#         # Name: h1
#         name_el = await page.query_selector('h1')
#         if name_el: result["medicine_name"] = (await name_el.inner_text()).strip()
#
#         # Marketer: a.medCompany
#         marketer_el = await page.query_selector('a.medCompany')
#         if marketer_el: result["medicine_marketer"] = (await marketer_el.inner_text()).strip()
#
#         # Salt: .compositionValue a
#         salt_el = await page.query_selector('.compositionValue a')
#         if salt_el: result["medicine_composition"] = (await salt_el.inner_text()).strip()
#
#         # Pricing
#         mrp_el = await page.query_selector('.mrp')
#         if mrp_el: result["medicine_mrp"] = extract_price(await mrp_el.inner_text())
#
#         price_el = await page.query_selector('.sellingPrice')
#         if price_el: result["medicine_selling_price"] = extract_price(await price_el.inner_text())
#
#         discount_el = await page.query_selector('.discountPercentage')
#         if discount_el: result["medicine_discount"] = extract_discount(await discount_el.inner_text())
#
#         # Storage
#         # Typically after a div with text "Storage" or id storage
#         storage_el = await page.query_selector('#storage + div, #storage + p')
#         if storage_el: result["medicine_storage"] = (await storage_el.inner_text()).strip()
#
#         # Substitutes
#         sub_elements = await page.query_selector_all('.medName')
#         for sub_el in sub_elements:
#             sub_name = await sub_el.inner_text()
#             if sub_name:
#                 result["substitutes"].append({"name": sub_name.strip()})
#
#     except Exception as e:
#         logging.error(f"Error scraping TrueMeds product detail for {product_url}: {e}")
#     finally:
#         await context.close()
#     return result
#
#
# async def main(medicine_name, max_products=15, headless=True, dbase=None):
#     logging.info(f"Searching TrueMeds for: {medicine_name} (max {max_products} products)")
#
#     async with async_playwright() as p:
#         browser = await p.chromium.launch(headless=headless)
#         results = await scrape_truemeds(browser, medicine_name, max_products)
#         await browser.close()
#
#     for result in results:
#         if dbase:
#             dbase.insert_medicine(result, 'TrueMeds')
#
#     if dbase:
#         dbase.mark_brand_as_searched(medicine_name, 'TrueMeds')
#
# async def main2(medicine_url, headless=True, dbase=None):
#     logging.info(f"Scraping TrueMeds details for: {medicine_url}")
#
#     async with async_playwright() as p:
#         browser = await p.chromium.launch(headless=headless)
#         result = await scrape_truemeds_product_detail(browser, medicine_url)
#         await browser.close()
#
#     if dbase and result:
#         dbase.insert_scraped_details(result, 'TrueMeds')
    result = {}
    return result


async def main(medicine_name, max_products=15, headless=True, dbase=None):
    # Headless param is kept for signature consistency but unused now
    logging.info(f"Searching TrueMeds for: {medicine_name} (max {max_products} products)")

    results = await scrape_truemeds(medicine_name, max_products)

    for result in results:
        result_for_medicine = {'medicine_url': result.get("medicine_url", ""),
                               'medicine_id': result.get("medicine_id", ""),
                               'medicine_name': result.get("medicine_name", ""), 'mrp': result.get("medicine_mrp", ""),
                               'pack_size_quantity': result.get("medicine_pack_size_quantity", ""),
                               'selling_price': result.get("medicine_selling_price", ""),
                               'discount_percentage': result.get("medicine_discount", "")}

        if dbase:
            dbase.insert_medicine(result_for_medicine, 'TrueMeds')
            logging.info(f"Scraping TrueMeds details for: {result.get('medicine_url', '')}")
            dbase.insert_scraped_details(result, 'TrueMeds')

    if dbase:
        dbase.mark_brand_as_searched(medicine_name, 'TrueMeds')


async def main2(medicine_url, headless=True, dbase=None):
    # Headless param is kept for signature consistency but unused now
    logging.info(f"Scraping TrueMeds details for: {medicine_url}")

    result = await scrape_truemeds_product_detail(medicine_url)

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
