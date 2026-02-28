import argparse
import asyncio
import os
from datetime import datetime
import re
import json
import sys
import io
from playwright.async_api import async_playwright, expect
from db.db import Database
import logging



# Fix encoding for Windows
# if sys.platform == "win32":
#     sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

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


def extract_medicine_id(url):
    if not url:
        return None
    # match = re.search(r"/drugs/[\w-]+-(\d+)", url)
    match = re.search(r"(\d+)$", url)
    return match.group(1) if match else None


async def scrape_1mg(browser, medicine_name, max_products=10):
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
    )
    page = await context.new_page()

    results = []

    try:
        search_url = (
            f"https://www.1mg.com/search/all?name={medicine_name.replace(' ', '+')}"
        )
        logging.info(f"Scraping: {search_url}")

        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(2300)

        logging.debug(f"Page title: {await page.title()}")

        # Get product containers
        cards = await page.locator('[class*="VerticalProductTile__container"]').all()
        logging.debug(f"Found {len(cards)} product containers")

        for card in cards:
            if len(results) >= max_products:
                break

            try:
                # Get link from header
                header_el = card.locator('[class*="VerticalProductTile__header"]').first
                link = ""
                if await header_el.count() > 0:
                    parent_a = header_el.locator("xpath=ancestor::a").first
                    if await parent_a.count() > 0:
                        href = await parent_a.get_attribute("href")
                        link = f"https://www.1mg.com{href}" if href else ""

                # Product name
                name_el = card.locator('[class*="VerticalProductTile__header"]').first
                name = (
                    (await name_el.inner_text()).strip()
                    if await name_el.count() > 0
                    else None
                )

                # Pack size - look in the text for strip of X
                card_text = await card.inner_text()
                pack_match = re.search(
                    r"strip of (\d+ [\w]+)|(\d+ [\w]+) in (strip|tablet|capsule)",
                    card_text,
                    re.IGNORECASE,
                )
                pack_size = pack_match.group() if pack_match else None

                # If no pack found, try other pattern
                if not pack_size:
                    pack_match = re.search(r"of (\d+\s*\w+)", card_text, re.IGNORECASE)
                    pack_size = pack_match.group() if pack_match else None

                # Selling Price - look for "Discounted Price"
                sell_el = card.locator("text=Discounted Price").first
                selling_price = None
                if await sell_el.count() > 0:
                    parent = sell_el.locator("xpath=..").first
                    txt = (await parent.inner_text()).strip()
                    price_match = re.search(r"₹?([\d.]+)", txt)
                    selling_price = float(price_match.group(1)) if price_match else None

                # Original Price (MRP)
                orig_el = card.locator("text=Original Price").first
                mrp = None
                if await orig_el.count() > 0:
                    parent = orig_el.locator("xpath=..").first
                    txt = (await parent.inner_text()).strip()
                    price_match = re.search(r"₹?([\d.]+)", txt)
                    mrp = float(price_match.group(1)) if price_match else None

                # Discount
                disc_el = card.locator("text=Discount Percentage").first
                discount_pct = None
                if await disc_el.count() > 0:
                    parent = disc_el.locator("xpath=..").first
                    txt = (await parent.inner_text()).strip()
                    discount_pct = extract_discount(txt)

                # Stock - check for Add to Cart
                cart_btn = card.locator("text=Add to cart").first
                in_stock = await cart_btn.count() > 0
                stock_status = "In Stock" if in_stock else "Out of Stock"

                result = {
                    "medicine_name": name,
                    "medicine_url": link,
                    "medicine_id": extract_medicine_id(link),
                    "mrp": mrp,
                    "selling_price": selling_price,
                    "discount_percentage": discount_pct,
                    "expected_delivery_date": None,
                    "in_stock": in_stock,
                    "stock_status": stock_status,
                    "pack_size_quantity": pack_size,
                }

                if result["medicine_name"] and result["selling_price"]:
                    results.append(result)
                    logging.debug(
                        f"  [OK] {result['medicine_name'][:45]} | Rs.{result['selling_price']} | {result['discount_percentage']}% off"
                    )

            except Exception as e:
                logging.error(f"  [Error] {str(e)[:60]}")
                continue

    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        await context.close()

    return results


async def scrape_1mg_product_detail(browser, product_url):
    """
    Scrapes detailed information from a specific 1mg product page.

    Args:
        browser: Playwright browser instance
        product_url: Full URL to the 1mg product page

    Returns:
        Dictionary with detailed product information
    """
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
    )
    page = await context.new_page()

    result = {}

    try:
        logging.info(f"Scraping product: {product_url}")
        await page.goto(product_url, wait_until="load", timeout=90000)
        await page.wait_for_timeout(3000)
        logging.debug(f"{page.content}")


        # Medicine Name
        name_el = page.locator('h1[class*="DrugHeader__title"]').first
        result["medicine_name"] = (
            (await name_el.inner_text()).strip() if await name_el.count() > 0 else None
        )

        # Medicine Composition
        comp_el = page.locator('div[class*="saltInfo"]').first
        result["medicine_composition"] = (
            (await comp_el.inner_text()).strip() if await comp_el.count() > 0 else None
        )

        # Medicine Marketer (Manufacturer)
        mfr_el = page.locator('div[class*="DrugHeader__meta-value"]').first
        result["medicine_marketer"] = (
            (await mfr_el.inner_text()).strip() if await mfr_el.count() > 0 else None
        )

        # Medicine Storage
        storage_el = page.locator('text=/Store.*below/i').first
        if await storage_el.count() == 0:
            storage_el = page.locator('text=/Storage/i').locator("xpath=following-sibling::*").first
        result["medicine_storage"] = (
            (await storage_el.inner_text()).strip() if await storage_el.count() > 0 else None
        )

        # MRP (Original Price)
        mrp_el = page.locator('span[class*="DrugPriceBox__slashed-price"]').first
        result["medicine_mrp"] = extract_price(
            await mrp_el.inner_text() if await mrp_el.count() > 0 else None
        )

        # Selling Price
        # price_el = page.locator('div[class*="DrugPriceBox__best-price"]').first
        price_el = page.locator('div[class*="DrugPriceBox__best-price___32JXw"]')
        result["medicine_selling_price"] = extract_price(
            await price_el.inner_text() if await price_el.count() > 0 else None
        )
        if result["medicine_selling_price"] is None:
            price_el_backup = page.locator('div[class*="DrugPriceBox__mrp-wrapper___2o5TZ"]').locator('div[class*="DrugPriceBox__price___dj2lv"]')
            result["medicine_selling_price"] = extract_price(
                await price_el_backup.inner_text() if await price_el_backup.count() > 0 else None
            )

        # Discount Percentage
        discount_el = page.locator('span[class*="DrugPriceBox__slashed-percent"]').first
        result["medicine_discount"] = extract_discount(
            await discount_el.inner_text() if await discount_el.count() > 0 else None
        )

        # Pack Size Information
        pack_el = page.locator('div[class*="DrugPriceBox__quantity"]').first
        result["pack_size_information"] = (
            (await pack_el.inner_text()).strip() if await pack_el.count() > 0 else None
        )

        # Substitutes
        result["substitutes"] = []
        substitute_section = page.locator('div[class*="SubstituteList__container"]').first
        if await substitute_section.count() > 0:
            sub_cards = await substitute_section.locator('div[class*="SubstituteItem__item"]').all()
            logging.debug(f"  Found {len(sub_cards)} substitutes")

            for sub_card in sub_cards:
                try:
                    # Substitute name
                    sub_name_el = sub_card
                    sub_name = (
                        (await sub_name_el.locator('div[class*="SubstituteItem__name"]').inner_text()).strip()
                        if await sub_name_el.count() > 0
                        else None
                    )

                    # Substitute URL
                    sub_link_el = sub_card.locator('a').first
                    sub_url = None
                    if await sub_link_el.count() > 0:
                        href = await sub_link_el.get_attribute("href")
                        sub_url = f"https://www.1mg.com{href}" if href else None

                    # Substitute Price
                    sub_price_el = sub_card.locator('div[class*="SubstituteItem__unit-price"]').first
                    sub_price = extract_price(
                        await sub_price_el.inner_text() \
                        if await sub_price_el.count() > 0 \
                        else None)

                    # Cheaper percentage
                    cheaper_perc_el = sub_card.locator('div[class*="SubstituteItem__save-text"]').first
                    cheaper_pct = \
                        await cheaper_perc_el.inner_text() \
                        if await cheaper_perc_el.count() > 0 \
                        else None


                    # Calculate cheaper percentage
                    # cheaper_pct = None
                    # if (
                    #     sub_price
                    #     and result["medicine_selling_price"]
                    #     and result["medicine_selling_price"] > 0
                    # ):
                    #     cheaper_pct = round(
                    #         ((result["medicine_selling_price"] - sub_price)
                    #          / result["medicine_selling_price"])
                    #         * 100,
                    #         2,
                    #     )

                    if sub_name and sub_url:
                        result["substitutes"].append(
                            {
                                "substitute_name": sub_name,
                                "url": sub_url,
                                "price_per_unit": sub_price,
                                "cheaper_percentage": cheaper_pct,
                            }
                        )
                except Exception as e:
                    logging.error(f"  [Error parsing substitute] {str(e)[:60]}")
                    continue

        # Generic Alternative Information
        result["generic_alternative_available"] = False
        result["generic_alternative"] = None

        # Look for the cheaper alternative section - it's usually in a card showing "Cheaper alternative available"
        # Try to find the section with class containing "InStockRxSubstitution"
        generic_container = page.locator('div[class*="InStockRxSubstitution__rightSku"]').first
        if await generic_container.count() <= 0:
            generic_container = page.locator('div[class*="OOSRxSubstitution__skuCard"]').first

        if await generic_container.count() > 0:
            result["generic_alternative_available"] = True

            # Get the link to the generic product
            gen_link_el = generic_container.locator('a[href*="/drugs/"]').first
            gen_name = None
            gen_url = None

            if await gen_link_el.count() > 0:
                # Get URL
                href = await gen_link_el.get_attribute("href")
                gen_url = f"https://www.1mg.com{href}" if href and href.startswith("/") else href

            # Get the product name - extract from URL (most reliable method)
            if gen_url:
                # URL pattern: /drugs/durite-5-tablet-737465
                # Extract and convert to title case
                match = re.search(r"/drugs/([\w-]+)-(\d+)$", gen_url)
                if match:
                    slug = match.group(1)
                    # Convert slug to title: durite-5-tablet -> Durite 5 Tablet
                    gen_name = " ".join(word.capitalize() for word in slug.split("-"))

            # Generic price - look for price with rupee symbol
            gen_price = None
            price_text_el = generic_container.locator('text=/₹\\s*[\\d,]+/').first
            if await price_text_el.count() > 0:
                gen_price = extract_price(await price_text_el.inner_text())

            # Generic manufacturer/marketer - look for "by" text
            gen_by = None
            by_text_el = generic_container.locator('text=/^by /i').first
            if await by_text_el.count() > 0:
                by_text = (await by_text_el.inner_text()).strip()
                if by_text.lower().startswith("by "):
                    gen_by = by_text[3:].strip()

            # Generic contains (composition) - look for salt info or composition text
            gen_contains = None
            # Try finding text with composition pattern like "Torasemide (5mg)"
            contains_el = generic_container.locator('text=/[A-Z][a-z]+.*\\([\\d.]+\\s*[mgu]+\\)/').first
            if await contains_el.count() > 0:
                gen_contains = (await contains_el.inner_text()).strip()
            else:
                contains_el_backup = page.locator('div[class*="OOSRxSubstitution__saltComposition"]').first
                gen_contains = (await contains_el_backup.inner_text()).strip()

            result["generic_alternative"] = {
                "alternate_name": gen_name,
                "url": gen_url,
                "price": gen_price,
                "by_who": gen_by,
                "contains_what": gen_contains,
            }

        logging.debug(f"  [OK] Extracted: {result['medicine_name']}")

    except Exception as e:
        logging.error(f"Error scraping product detail: {e}")
    finally:
        await context.close()

    return result


async def main(medicine_name, max_products=15, headless=True, dbase=None):

    logging.info(f"Searching 1mg for: {medicine_name} (max {max_products} products)")
    logging.info("=" * 50)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        results = await scrape_1mg(browser, medicine_name, max_products)
        await browser.close()

    logging.info(f"\n=== Found {len(results)} products ===")
    logging.debug(f"Results: {results}")
    # print(json.dumps(results, indent=4))
    for i, result in enumerate(results, start=1):
        dbase.insert_1mg(
            result
        )


async def main2(medicine_url, headless=True, dbase=None):
    """
    Main function for scraping detailed product information from a specific 1mg product URL.
    Usage: python onemg_scraper_v2.py --detail <product_url> [--headless]
    Example: python onemg_scraper_v2.py --detail https://www.1mg.com/drugs/torget-5-tablet-116470
    """
    # product_url = "https://www.1mg.com/drugs/torget-5-tablet-116470"
    # headless = False


    # Look for product URL
    product_url = medicine_url

    logging.debug(f"Scraping detailed product info from: {product_url}")
    logging.debug("=" * 50)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        result = await scrape_1mg_product_detail(browser, product_url)
        await browser.close()

    logging.debug(f"\n=== Product Details ===")
    logging.debug(json.dumps(result, indent=4))
    result["medicine_url"] = product_url
    # result["medicine_id"] = extract_medicine_id(product_url)
    # logging.debug(f"{extract_medicine_id(product_url)=}")
    dbase.insert_scraped_1mg(result)


if __name__ == "__main__":

    argparse.ArgumentParser(description="Scrape 1mg.com for medicine information.")
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Limit the number of products to scrape")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("medicine_name", nargs="?", help="Name of the medicine to search for")
    parser.add_argument("--debug", action="store_true", help="DEBUG level logging")
    parser.add_argument("--brands", action="store_true", help="extract brands using search from file")
    parser.add_argument("--detail", action="store_true", help="extract pdp data along with substitutes using url from extracted brands")
    parser.add_argument("--extract_scraped_data", action="store_true", help="extract scraped data from db")

    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    # Use absolute path for database relative to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, 'db', 'db.duckdb')
    dbase = Database(dbpath=db_path)
    dbase.init()

    if args.brands:
        brands_file = os.path.join(script_dir, 'brands_to_fetch.txt')
        with open(brands_file, 'r') as f:
            brands = f.read().splitlines()

        for brand in brands:
            asyncio.run(main(medicine_name=brand, max_products=args.limit, headless=args.headless, dbase=dbase))

    if args.detail:
        brands = dbase.get_brands()
        logging.info(f"Found {len(brands)} brands")
        for _, url in brands.iterrows():
            asyncio.run(main2(medicine_url=url['url'], headless=args.headless, dbase=dbase))

    if args.extract_scraped_data:
        df = dbase.extract_scraped_data()
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        df.to_excel(f'scraped_data_{now}.xlsx', index=False)

    pass
