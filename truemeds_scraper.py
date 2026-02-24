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


async def scrape_truemeds(browser, medicine_name, max_products=10):
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
    )
    page = await context.new_page()

    results = []

    try:
        search_url = (
            f"https://www.truemeds.in/search/{medicine_name.lower().replace(' ', '-')}"
        )
        print(f"Scraping: {search_url}")

        await page.goto(search_url, wait_until="load", timeout=90000)
        await page.wait_for_timeout(15000)

        print(f"Page title: {await page.title()}")

        txt = await page.locator("body").inner_text()
        lines = txt.split("\n")

        skip_words = [
            "Login",
            "Search",
            "Cart",
            "Medicines",
            "Deliver to",
            "Download App",
            "Login / Signup",
            "Showing all results",
            "FLAT",
        ]

        product_started = False
        i = 0
        while i < len(lines) and len(results) < max_products:
            line = lines[i].strip()

            if "Showing all results for" in line:
                product_started = True
                i += 1
                continue

            if not product_started or not line or line in skip_words:
                i += 1
                continue

            if (
                "Get Substitute" in line
                or "₹" in line
                or "MRP" in line
                or "% OFF" in line
                or "Strip of" in line
                or "Add To Cart" in line
            ):
                i += 1
                continue

            if 3 < len(line) < 70:
                name = line
                company = ""
                pack = ""
                price = ""
                mrp = ""
                discount = ""
                stock = "Out of Stock"

                j = i + 1
                while j < len(lines) and j < i + 15:
                    next_line = lines[j].strip()

                    if not next_line or next_line in skip_words:
                        j += 1
                        continue

                    if "Get Substitute" in next_line:
                        break

                    if not company and any(
                        x in next_line
                        for x in [
                            "Pharmaceuticals",
                            "Ltd",
                            "Inc",
                            "Glenmark",
                            "Cipla",
                            "Sun",
                            "Mankind",
                        ]
                    ):
                        company = next_line
                    elif not pack and "Strip of" in next_line:
                        pack = next_line
                    elif not price and "₹" in next_line:
                        price = next_line.replace("₹", "").strip()
                    elif not mrp and "MRP" in next_line:
                        mrp = next_line.replace("MRP ₹", "").strip()
                    elif not discount and "%" in next_line and "OFF" in next_line:
                        discount = next_line  # Keep full text for extraction
                    elif "Add To Cart" in next_line:
                        stock = "In Stock"
                        j += 1
                        break

                    j += 1

                if name and price and extract_price(price):
                    results.append(
                        {
                            "medicine_name": f"{name} ({company})" if company else name,
                            "medicine_url": search_url,
                            "medicine_id": None,
                            "mrp": extract_price(mrp) if mrp else None,
                            "selling_price": extract_price(price),
                            "discount_percentage": extract_discount(discount)
                            if discount
                            else None,
                            "expected_delivery_date": None,
                            "in_stock": stock == "In Stock",
                            "stock_status": stock,
                            "pack_size_quantity": pack,
                        }
                    )
                    print(
                        f"  [OK] {name[:35]} | Rs.{extract_price(price)} | {discount}% off | {stock}"
                    )
                    i = j
                else:
                    i += 1
            else:
                i += 1

        print(f"Found {len(results)} products")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await context.close()

    return results


async def main():
    medicine_name = "telma"
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

    print(f"Searching TrueMeds for: {medicine_name} (max {max_products} products)")
    print("=" * 50)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        results = await scrape_truemeds(browser, medicine_name, max_products)
        await browser.close()

    print(f"\n=== Found {len(results)} products ===")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
