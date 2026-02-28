import asyncio
import re
import json
import sys
import io
from playwright.async_api import async_playwright

# Fix encoding for Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

WEBSITES = [
    {
        "name": "PharmEasy",
        "base_url": "https://pharmeasy.in",
        "search_path": "/search/all",
    },
]


def extract_price(text):
    if not text:
        return None
    cleaned = re.sub(r"[,\s₹*]", "", text)
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
    match = re.search(r"/online-medicine-order/[\w-]+-(\d+)", url)
    return match.group(1) if match else None


async def scrape_pharmeasy(browser, medicine_name, max_products=10, headless=False):
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
    )
    page = await context.new_page()

    results = []

    try:
        search_url = (
            f"https://pharmeasy.in/search/all?name={medicine_name.replace(' ', '+')}"
        )
        print(f"Scraping: {search_url}")

        await page.goto(search_url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        print(f"Page title: {await page.title()}")

        cards = await page.locator('[class*="ProductCard_"]').all()
        print(f"Found {len(cards)} product cards")

        for card in cards:
            if len(results) >= max_products:
                break

            try:
                # Get link first
                link_el = card.locator("a").first
                href = (
                    await link_el.get_attribute("href")
                    if await link_el.count() > 0
                    else None
                )

                if not href or "/online-medicine-order/" not in href:
                    continue

                full_url = "https://pharmeasy.in" + href

                # Product name
                name_el = card.locator(
                    '[class*="ProductCard_nameAndDeleteIconWrapper__"]'
                ).first
                name = (
                    (await name_el.inner_text()).strip()
                    if await name_el.count() > 0
                    else None
                )

                # Brand
                brand_el = card.locator('[class*="ProductCard_brandName__"]').first
                brand = (
                    (await brand_el.inner_text()).strip()
                    if await brand_el.count() > 0
                    else None
                )

                # Full medicine name with brand
                medicine_name_full = name
                if brand:
                    brand_text = brand.replace("By ", "").strip()
                    medicine_name_full = f"{name} ({brand_text})"

                # MRP
                mrp_el = card.locator('[class*="ProductCard_originalMrp__"]').first
                mrp_text = (
                    (await mrp_el.inner_text()).strip()
                    if await mrp_el.count() > 0
                    else None
                )

                # Selling Price
                selling_el = card.locator('[class*="ProductCard_ourPrice__"]').first
                selling_text = (
                    (await selling_el.inner_text()).strip()
                    if await selling_el.count() > 0
                    else None
                )

                # Discount
                discount_el = card.locator(
                    '[class*="ProductCard_priceDiscountWrapper__"]'
                ).first
                discount_text = (
                    (await discount_el.inner_text()).strip()
                    if await discount_el.count() > 0
                    else None
                )

                # Pack size / Measurement
                pack_el = card.locator('[class*="ProductCard_measurementUnit__"]').first
                pack_text = (
                    (await pack_el.inner_text()).strip()
                    if await pack_el.count() > 0
                    else None
                )

                # Stock - check for Add to Cart button
                cart_btn = card.locator("text=Add To Cart").first
                in_stock = await cart_btn.count() > 0
                stock_status = "In Stock" if in_stock else "Out of Stock"

                # Extract discount percentage from discount text
                discount_pct = extract_discount(discount_text)

                result = {
                    "medicine_name": medicine_name_full,
                    "medicine_url": full_url,
                    "medicine_id": extract_medicine_id(full_url),
                    "mrp": extract_price(mrp_text),
                    "selling_price": extract_price(selling_text),
                    "discount_percentage": discount_pct,
                    "expected_delivery_date": None,
                    "in_stock": in_stock,
                    "stock_status": stock_status,
                    "pack_size_quantity": pack_text,
                }

                if result["medicine_name"] and result["selling_price"]:
                    results.append(result)
                    print(
                        f"  [OK] {result['medicine_name'][:45]} | Rs.{result['selling_price']} | {result['discount_percentage']}% off"
                    )

            except Exception as e:
                print(f"  [Error] {str(e)[:50]}")
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

    print(f"Searching PharmEasy for: {medicine_name} (max {max_products} products)")
    print("=" * 50)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        results = await scrape_pharmeasy(browser, medicine_name, max_products, headless)
        await browser.close()

    print(f"\n=== Found {len(results)} products ===")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
