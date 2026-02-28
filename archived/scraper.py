import asyncio
import re
import json
from playwright.async_api import async_playwright

WEBSITES = [
    {
        "name": "PlatinumRx",
        "base_url": "https://www.platinumrx.in",
        "search_path": "/search",
    },
    {
        "name": "ApolloPharmacy",
        "base_url": "https://www.apollopharmacy.in",
        "search_path": "/search",
    },
    {
        "name": "TrueMeds",
        "base_url": "https://www.truemeds.in",
        "search_path": "/catalog/search",
    },
    {"name": "1mg", "base_url": "https://www.1mg.com", "search_path": "/search"},
    {
        "name": "PharmEasy",
        "base_url": "https://pharmeasy.in",
        "search_path": "/search/all",
    },
]

SELECTORS = {
    "platinumrx": {
        "product_link": "a[href*='/product/'], a[href*='/medicine/'], a[href*='/drug/']",
        "name": "h1, h2, [class*='product-name'], [class*='medicine-name'], [class*='product-title']",
        "mrp": "[class*='mrp'], [class*='MRP'], [class*='max-price'], .strike-price, [class*='price--old'], [class*='original']",
        "selling_price": "[class*='selling'], [class*='selling-price'], [class*='final-price'], [class*='discount-price'], [class*='OurPrice'], [class*='price--new'], [class*='our-price']",
        "discount": "[class*='discount'], [class*='off'], [class*='save'], [class*='save-percent']",
        "delivery": "[class*='delivery'], [class*='deliver'], [class*='delivery-time'], [class*='delivery-date'], [class*='expected']",
        "stock": "[class*='stock'], [class*='availability'], [class*='out-of-stock'], [class*='in-stock'], [class*='status']",
        "pack_size": "[class*='pack'], [class*='quantity'], [class*='size'], [class*='tablet'], [class*='strip'], [class*='unit'], [class*='formulation']",
    },
    "apollopharmacy": {
        "product_link": "a[href*='/product/'], a[href*='/drug/'], a[href*='/medicine/']",
        "name": "h1, h2, [class*='product-name'], [class*='medicine-name'], [data-testid*='name'], [class*='title']",
        "mrp": "[class*='mrp'], [class*='max-price'], [class*='MRP'], [class*='price--mrp']",
        "selling_price": "[class*='selling'], [class*='sell-price'], [class*='our-price'], [class*='final-price'], [class*='price--final']",
        "discount": "[class*='discount'], [class*='save'], [class*='off'], [class*='save-percent']",
        "delivery": "[class*='delivery'], [class*='delivery-time'], [class*='delivery-date'], [class*='expected']",
        "stock": "[class*='stock'], [class*='availability'], [class*='out-of-stock'], [class*='in-stock']",
        "pack_size": "[class*='pack'], [class*='quantity'], [class*='strip'], [class*='tablet'], [class*='formulation']",
    },
    "truemeds": {
        "product_link": "a[href*='/product/'], a[href*='/drug/'], a[href*='/medicine/']",
        "name": "h1, h2, [class*='product-name'], [class*='product-title'], [class*='drug-name']",
        "mrp": "[class*='mrp'], [class*='mrp-price'], [class*='max-price'], [class*='price--mrp']",
        "selling_price": "[class*='selling'], [class*='selling-price'], [class*='final-price'], [class*='price'], [class*='price--final']",
        "discount": "[class*='discount'], [class*='discount-percent'], [class*='off'], [class*='save']",
        "delivery": "[class*='delivery'], [class*='delivery-time'], [class*='delivery-date'], [class*='expected']",
        "stock": "[class*='stock'], [class*='stock-status'], [class*='availability'], [class*='in-stock']",
        "pack_size": "[class*='pack'], [class*='quantity'], [class*='strip'], [class*='tablet'], [class*='formulation']",
    },
    "onemg": {
        "product_link": "a[href*='/products/'], a[href*='/drug/'], a[href*='/medicine/']",
        "name": "h1, h2, [class*='product-name'], [class*='name'], [data-testid*='name'], [class*='title']",
        "mrp": "[class*='mrp'], [class*='price__mrp'], [class*='max-price'], [class*='price--mrp']",
        "selling_price": "[class*='selling'], [class*='price__selling'], [class*='price__final'], [class*='price--final']",
        "discount": "[class*='discount'], [class*='price__discount'], [class*='off'], [class*='save']",
        "delivery": "[class*='delivery'], [class*='delivery-time'], [class*='delivery-date'], [class*='expected']",
        "stock": "[class*='stock'], [class*='stock-status'], [class*='availability'], [class*='in-stock']",
        "pack_size": "[class*='pack'], [class*='quantity'], [class*='strip'], [class*='tablet'], [class*='formulation']",
    },
    "pharmeasy": {
        "product_link": "a[href*='/product/'], a[href*='/drug/'], a[href*='/medicine/']",
        "name": "h1, h2, [class*='product-name'], [class*='name'], [data-testid*='name'], [class*='title']",
        "mrp": "[class*='mrp'], [class*='PriceStrike'], [class*='max-price'], [class*='price--mrp']",
        "selling_price": "[class*='selling'], [class*='PriceFinal'], [class*='final-price'], [class*='price--final']",
        "discount": "[class*='discount'], [class*='DiscountText'], [class*='off'], [class*='save']",
        "delivery": "[class*='delivery'], [class*='delivery-time'], [class*='delivery-date'], [class*='expected']",
        "stock": "[class*='stock'], [class*='stock-status'], [class*='availability'], [class*='in-stock']",
        "pack_size": "[class*='pack'], [class*='quantity'], [class*='strip'], [class*='tablet'], [class*='formulation']",
    },
}


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


def extract_pack_size(text):
    if not text:
        return None
    patterns = [
        r"(\d+)\s*(?:tablet|capsule|strip|ml|mg|piece|pcs|tablet[s]?|capsule[s]?)",
        r"(\d+)\s*(?:x\s*)?\d+",
        r"pack\s*of\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group()
    return text.strip() if text else None


def extract_medicine_id(url):
    if not url:
        return None
    match = re.search(r"/(?:product|drug|medicine)[-/]?(\w+)", url, re.IGNORECASE)
    return match.group(1) if match else None


async def get_product_links(page, selectors, base_url, max_products=10):
    links = []
    try:
        all_links = await page.locator(selectors["product_link"]).all()
        seen = set()
        for link in all_links:
            try:
                href = await link.get_attribute("href")
                if href and href not in seen:
                    seen.add(href)
                    full_url = href if href.startswith("http") else base_url + href
                    links.append(full_url)
                    if len(links) >= max_products:
                        break
            except:
                continue
    except Exception as e:
        print(f"  Error getting product links: {e}")
    return links


async def scrape_product_detail(page, url, selectors):
    result = {
        "medicine_name": None,
        "medicine_url": url,
        "medicine_id": extract_medicine_id(url),
        "mrp": None,
        "selling_price": None,
        "discount_percentage": None,
        "expected_delivery_date": None,
        "in_stock": None,
        "stock_status": None,
        "pack_size_quantity": None,
    }

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        name_el = page.locator(selectors["name"]).first
        mrp_el = page.locator(selectors["mrp"]).first
        selling_el = page.locator(selectors["selling_price"]).first
        discount_el = page.locator(selectors["discount"]).first
        delivery_el = page.locator(selectors["delivery"]).first
        stock_el = page.locator(selectors["stock"]).first
        pack_el = page.locator(selectors["pack_size"]).first

        try:
            name = await name_el.inner_text(timeout=3000)
            result["medicine_name"] = name.strip() if name else None
        except:
            pass

        try:
            mrp_text = await mrp_el.inner_text(timeout=2000)
            result["mrp"] = extract_price(mrp_text)
        except:
            pass

        try:
            selling_text = await selling_el.inner_text(timeout=2000)
            result["selling_price"] = extract_price(selling_text)
        except:
            pass

        try:
            discount_text = await discount_el.inner_text(timeout=2000)
            result["discount_percentage"] = extract_discount(discount_text)
        except:
            pass

        try:
            delivery_text = await delivery_el.inner_text(timeout=2000)
            result["expected_delivery_date"] = (
                delivery_text.strip() if delivery_text else None
            )
        except:
            pass

        try:
            stock_text = await stock_el.inner_text(timeout=2000)
            result["stock_status"] = stock_text.strip() if stock_text else None
            stock_lower = stock_text.lower() if stock_text else ""
            result["in_stock"] = not (
                "out of stock" in stock_lower
                or "unavailable" in stock_lower
                or "sold out" in stock_lower
                or "no stock" in stock_lower
            )
        except:
            pass

        try:
            pack_text = await pack_el.inner_text(timeout=2000)
            result["pack_size_quantity"] = extract_pack_size(pack_text)
        except:
            pass

    except Exception as e:
        print(f"  Error scraping product detail: {e}")

    return result


async def scrape_website(browser, website, medicine_name, max_products=10):
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        permissions=["geolocation"],
    )
    page = await context.new_page()

    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
        window.chrome = {};
    """)

    results = []

    try:
        base_url = website["base_url"]
        search_path = website["search_path"]

        if website["name"] == "PlatinumRx":
            search_url = (
                f"{base_url}{search_path}?query={medicine_name.replace(' ', '+')}"
            )
        elif website["name"] == "ApolloPharmacy":
            search_url = (
                f"{base_url}{search_path}/{medicine_name.replace(' ', '-').lower()}"
            )
        elif website["name"] == "TrueMeds":
            search_url = (
                f"{base_url}{search_path}/{medicine_name.replace(' ', '-').lower()}"
            )
        elif website["name"] == "1mg":
            search_url = f"{base_url}{search_path}?q={medicine_name.replace(' ', '+')}"
        elif website["name"] == "PharmEasy":
            search_url = (
                f"{base_url}{search_path}?name={medicine_name.replace(' ', '+')}"
            )
        else:
            search_url = f"{base_url}{search_path}?q={medicine_name.replace(' ', '+')}"

        print(f"Scraping search: {search_url}")

        try:
            await page.goto(search_url, wait_until="load", timeout=60000)
        except Exception as e:
            print(f"Navigation error: {e}")
            await context.close()
            return results

        await page.wait_for_timeout(8000)

        page_title = await page.title()
        print(f"Page title: {page_title[:50] if page_title else 'No title'}")

        if not page_title or len(page_title) < 5:
            print("Warning: Page may not have loaded properly")

        if (
            "captcha" in (page_title or "").lower()
            or "blocked" in (page_title or "").lower()
        ):
            print("Bot detection triggered!")
            await context.close()
            return results

        site_key = (
            website["name"]
            .lower()
            .replace("pharmacy", "")
            .replace("1mg", "onemg")
            .replace("pharmeasy", "pharmeasy")
        )
        selectors = SELECTORS.get(site_key, SELECTORS["platinumrx"])

        print(f"Getting product links from search...")
        product_links = await get_product_links(page, selectors, base_url, max_products)
        print(f"Found {len(product_links)} product links")

        for i, product_url in enumerate(product_links):
            print(
                f"  Visiting product {i + 1}/{len(product_links)}: {product_url[:80]}..."
            )
            product_data = await scrape_product_detail(page, product_url, selectors)
            if product_data["medicine_name"]:
                results.append(product_data)
                print(
                    f"    Got: {product_data['medicine_name'][:40]} | Rs.{product_data['selling_price']} | Stock: {product_data['in_stock']}"
                )

    except Exception as e:
        print(f"Error scraping {website['name']}: {e}")
    finally:
        await context.close()

    return results


async def scrape_all_websites(medicine_name, max_products_per_site=10):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        all_results = {}

        for website in WEBSITES:
            print(f"\n{'=' * 50}")
            print(f"--- Scraping {website['name']} ---")
            print(f"{'=' * 50}")
            results = await scrape_website(
                browser, website, medicine_name, max_products_per_site
            )
            all_results[website["name"]] = results
            print(f"Found {len(results)} products on {website['name']}")

        await browser.close()
        return all_results


async def scrape_single_website(website_name, medicine_name, max_products=10):
    website = next(
        (w for w in WEBSITES if w["name"].lower() == website_name.lower()), None
    )

    if not website:
        print(f"Website not found: {website_name}")
        return None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        results = await scrape_website(browser, website, medicine_name, max_products)
        await browser.close()
        return results


async def main():
    import sys

    site_name = None
    max_products = 10

    args = [a for a in sys.argv[1:] if a]

    if "--site" in args:
        site_idx = args.index("--site")
        if site_idx + 1 < len(args):
            site_name = args[site_idx + 1]

    if "--limit" in args:
        limit_idx = args.index("--limit")
        if limit_idx + 1 < len(args):
            max_products = int(args[limit_idx + 1])

    medicine_name = "paracetamol"
    for arg in args:
        if arg in ("--site", "--limit"):
            continue
        if arg.isdigit():
            continue
        if site_name and arg == site_name:
            continue
        if arg != site_name:
            medicine_name = arg
            break

    if site_name:
        results = await scrape_single_website(site_name, medicine_name, max_products)
        if results:
            print("\n--- Results ---")
            print(json.dumps(results, indent=2))
        return

    print(f"Searching for: {medicine_name} (max {max_products} products per site)")
    results = await scrape_all_websites(medicine_name, max_products)
    print("\n=== Final Results ===")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
