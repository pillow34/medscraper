import argparse
import asyncio
import os
from datetime import datetime
import re
import json
import sys
import io
import logging
import requests
from db.db import Database

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

def extract_price(text):
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    cleaned = re.sub(r"[,\s₹]", "", str(text))
    match = re.search(r"[\d.]+", cleaned)
    return float(match.group()) if match else None

def extract_discount(text):
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
    match = re.search(r"(\d+)%", str(text))
    return int(match.group(1)) if match else None

async def scrape_platinumrx(medicine_name, max_products=10):
    url = "https://backend.platinumrx.in/pdp/fetchPlpInfo"
    payload = {
        "drugName": medicine_name,
        "searchType": None
    }
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-GB,en;q=0.5",
        "content-type": "application/json",
        "origin": "https://www.platinumrx.in",
        "referer": "https://www.platinumrx.in/"
    }

    try:
        logging.info(f"Searching PlatinumRx via API for: {medicine_name}")
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            logging.error(f"API failed with status {response.status_code}")
            return []

        data = response.json()
        logging.debug(f"API response: {data}")
        results = []
        for item in data.get("message", [])[:max_products]:
            master = item.get("masterItemData", {})
            substitute = item.get("substituteItemData", {})
            logging.debug(f"Master item: {master}")
            logging.debug(f"Substitute item: {substitute}")
            if not master: continue

            # Use display_name and salt for construction of a tracking URL
            name = master.get("display_name", "")
            salt = master.get("salt_composition", "")
            drug_id = master.get("master_drug_code", "")
            manufacturer_name = master.get("manufacturer_name", "")

            # URL will be used in stage 2 (detail) to fetch substitutes by salt
            import urllib.parse
            logging.debug(f"Encoding name: {name}")
            encoded_name = urllib.parse.quote(name)
            logging.debug(f"Encoding id: {drug_id}")
            # encoded_id = urllib.parse.quote(drug_id)
            medicine_url = f"https://www.platinumrx.in/medicines/{encoded_name}/{drug_id}"

            substitute_name = substitute.get("display_name", "")
            substitute_salt = substitute.get("salt_composition", "")
            substitute_drug_id = substitute.get("master_drug_code", "")
            substitute_manufacturer_name = substitute.get("manufacturer_name", "")
            logging.debug(f"Substitute manufacturer name: {substitute_manufacturer_name}")
            logging.debug(f"Encoding substitute name: {substitute_name}")
            encoded_substitute_name = urllib.parse.quote(substitute_name)
            logging.debug(f"Encoding substitute id: {substitute_drug_id}")
            # encoded_substitute_id = urllib.parse.quote(substitute_drug_id)
            substitute_url = f"https://www.platinumrx.in/medicines/{encoded_substitute_name}/{substitute_drug_id}"

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
                "medicine_storage": None,
                "medicine_mrp": extract_price(master.get("mrp")),
                "medicine_selling_price": extract_price(master.get("discounted_price")),
                "medicine_discount": extract_discount(master.get("discount_percentage")),
                "pack_size_information": f"{master.get('pack_quantity_value')} {master.get('unit_of_measurement')}",
                "substitutes": [substitute],
                "generic_alternative_available": item.get("hasSubstitute", False),
                "generic_alternative": {"alternate_name": substitute_name, "url": substitute_url, "price": extract_price(substitute.get("discounted_price", None)), "by_who": substitute_manufacturer_name, "contains_what": substitute_salt}
            })
        return results
    except Exception as e:
        logging.error(f"Error in scrape_platinumrx: {e}")
        return []

async def scrape_platinumrx_product_detail():
    """
    Scrapes detailed information for a specific product using its salt composition
    to find all substitutes via the search API.
    """
    # import urllib.parse
    # parsed_url = urllib.parse.urlparse(medicine_url)
    # params = urllib.parse.parse_qs(parsed_url.query)
    #
    # drug_id = params.get('id', [None])[0]
    # salt_name = params.get('salt', [None])[0]
    #
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
    #
    # if not salt_name:
    #     logging.warning("No salt composition found in URL for detail scraping")
    #     return result
    #
    # url = "https://backend.platinumrx.in/pdp/fetchPlpInfo"
    # payload = {
    #     "drugName": salt_name,
    #     "searchType": None
    # }
    # headers = {
    #     "accept": "application/json, text/plain, */*",
    #     "content-type": "application/json",
    #     "origin": "https://www.platinumrx.in",
    #     "referer": "https://www.platinumrx.in/"
    # }
    #
    # try:
    #     logging.info(f"Fetching detail/substitutes for salt: {salt_name}")
    #     response = requests.post(url, json=payload, headers=headers)
    #     if response.status_code != 200:
    #         return result
    #
    #     data = response.json()
    #     all_items = data.get("message", [])
    #
    #     for item in all_items:
    #         master = item.get("masterItemData", {})
    #         if not master: continue
    #
    #         item_id = master.get("master_drug_code")
    #         name = master.get("display_name")
    #         marketer = master.get("manufacturer_name")
    #         mrp = extract_price(master.get("mrp"))
    #         selling_price = extract_price(master.get("discounted_price"))
    #         pack = f"{master.get('pack_quantity_value')} {master.get('unit_of_measurement')}"
    #
    #         if item_id == drug_id:
    #             # This is the original medicine
    #             result["medicine_name"] = name
    #             result["medicine_marketer"] = marketer
    #             result["medicine_mrp"] = mrp
    #             result["medicine_selling_price"] = selling_price
    #             result["medicine_discount"] = extract_discount(master.get("discount_percentage"))
    #             result["pack_size_information"] = pack
    #         else:
    #             # This is a substitute
    #             result["substitutes"].append({
    #                 "name": name,
    #                 "marketer": marketer,
    #                 "pack_size": pack,
    #                 "selling_price": selling_price,
    #                 "mrp": mrp,
    #                 "url": f"https://www.platinumrx.in/pdp?id={item_id}&salt={urllib.parse.quote(salt_name)}"
    #             })
    #
    #     # Sort substitutes by price to find the cheapest alternative
    #     if result["substitutes"]:
    #         result["generic_alternative_available"] = True
    #         cheapest = min(result["substitutes"], key=lambda x: x["selling_price"] if x.get("selling_price") else 999999)
    #         result["generic_alternative"] = f"{cheapest['name']} by {cheapest['marketer']} at ₹{cheapest['selling_price']}"
    #
    #     logging.info(f"Finished fetching details for {result['medicine_name']}. Found {len(result['substitutes'])} substitutes.")
    # except Exception as e:
    #     logging.error(f"Error fetching PlatinumRx product detail: {e}")

    result = {}
    return result

async def main(medicine_name, max_products=15, headless=True, dbase=None):
    # Headless param is kept for signature consistency but unused now
    logging.info(f"Searching PlatinumRx for: {medicine_name} (max {max_products} products)")
    
    results = await scrape_platinumrx(medicine_name, max_products)

    for result in results:
        result_for_medicine = {'medicine_url': result.get("medicine_url", ""),
                               'medicine_id': result.get("medicine_id", ""), 'medicine_name': result.get("medicine_name", ""), 'mrp': result.get("medicine_mrp", ""), 'pack_size_quantity': result.get("medicine_pack_size_quantity", ""), 'selling_price': result.get("medicine_selling_price", ""), 'discount_percentage': result.get("medicine_discount", "")}

        if dbase:
            dbase.insert_medicine(result_for_medicine, 'PlatinumRx')
            logging.info(f"Scraping PlatinumRx details for: {result.get('medicine_url', '')}")
            dbase.insert_scraped_details(result, 'PlatinumRx')

    if dbase:
        dbase.mark_brand_as_searched(medicine_name, 'PlatinumRx')


async def main2(medicine_url, headless=True, dbase=None):
    # Headless param is kept for signature consistency but unused now
    logging.info(f"Scraping PlatinumRx details for: {medicine_url}")
    
    result = await scrape_platinumrx_product_detail(medicine_url)

    if dbase and result:
        dbase.insert_scraped_details(result, 'PlatinumRx')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape PlatinumRx for medicine information.")
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
        brands = dbase.get_brands(source='PlatinumRx')
        for _, row in brands.iterrows():
            asyncio.run(main2(row['url'], headless=args.headless, dbase=dbase))
    elif args.medicine_name:
        asyncio.run(main(args.medicine_name, max_products=args.limit, headless=args.headless, dbase=dbase))
    else:
        parser.print_help()
