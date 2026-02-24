import asyncio
import re
import json
import sys
import io
from playwright.async_api import async_playwright

# Fix encoding for Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


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
    match = re.search(r"/drugs/[\w-]+-(\d+)", url)
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
        print(f"Scraping: {search_url}")

        await page.goto(search_url, wait_until="load", timeout=90000)
        await page.wait_for_timeout(15000)

        print(f"Page title: {await page.title()}")

        # Get product containers
        cards = await page.locator('[class*="VerticalProductTile__container"]').all()
        print(f"Found {len(cards)} product containers")

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
                    print(
                        f"  [OK] {result['medicine_name'][:45]} | Rs.{result['selling_price']} | {result['discount_percentage']}% off"
                    )

            except Exception as e:
                print(f"  [Error] {str(e)[:60]}")
                continue

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await context.close()

    return results


async def main():
    medicine_name = "paracetamol"
    max_products = 10
    headless = False

    args = [a for a in sys.argv[1:] if a]

    if "--limit" in args:
        limit_idx = args.index("--limit")
        if limit_idx + 1 < len(args):
            max_products = int(args[limit_idx + 1])

    if "--headless" in args:
        headless = True

    for arg in args:
        if arg.startswith("--"):
            continue
        if arg.isdigit():
            continue
        medicine_name = arg
        break

    print(f"Searching 1mg for: {medicine_name} (max {max_products} products)")
    print("=" * 50)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        results = await scrape_1mg(browser, medicine_name, max_products)
        await browser.close()

    print(f"\n=== Found {len(results)} products ===")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
