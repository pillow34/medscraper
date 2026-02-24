import asyncio
import re
import json
import sys
import io
from playwright.async_api import async_playwright

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


async def scrape_platinumrx(browser, medicine_name, max_products=10):
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
    )
    page = await context.new_page()

    results = []

    try:
        search_url = f"https://www.platinumrx.in/product-listing/{medicine_name.lower().replace(' ', '-')}"
        print(f"Scraping: {search_url}")

        await page.goto(search_url, wait_until="load", timeout=90000)
        await page.wait_for_timeout(15000)

        txt = await page.locator("body").inner_text()
        lines = txt.split("\n")

        skip_words = [
            "Download App",
            "Login",
            "Personal Care",
            "Health Conditions",
            "Healthcare Devices",
            "Vitamins And Supplements",
            "Health Resources",
            "You Searched",
            "We Recommend",
            "PlatinumRx Recommended Medicines",
            "Same salt composition and dosage",
            "Top Brands, 100% safe and effective",
            "FDA and WHO certified medicines",
            "Add to Cart",
        ]

        product_started = False
        i = 0

        while i < len(lines) and len(results) < max_products:
            line = lines[i].strip()

            if "You Searched" in line:
                product_started = True
                i += 1
                continue

            if not product_started or not line or line in skip_words:
                i += 1
                continue

            if (
                any(
                    x in line.lower()
                    for x in ["tablet", "mg", "capsule", "syrup", "drops"]
                )
                and not line.isupper()
                and len(line) > 5
            ):
                main_name = line
                main_company = ""
                main_pack = ""
                main_price = ""

                j = i + 1
                while j < len(lines) and j < i + 8:
                    next_line = lines[j].strip()
                    if not next_line or next_line in skip_words:
                        j += 1
                        continue
                    if next_line.isupper() and len(next_line) < 50:
                        break
                    if any(
                        x in next_line
                        for x in [
                            "Pharmaceuticals",
                            "Ltd",
                            "Inc",
                            "Glenmark",
                            "Cipla",
                            "Sun",
                            "Mankind",
                            "Dr.",
                            "Abbott",
                            "Alkem",
                            "Lupin",
                        ]
                    ):
                        main_company = next_line
                    elif "Strip of" in next_line:
                        main_pack = next_line
                    elif "₹" in next_line and "MRP" not in next_line:
                        main_price = next_line.replace("₹", "").strip()
                        j += 1
                        break
                    j += 1

                sub_name = ""
                sub_company = ""
                sub_pack = ""
                sub_price = ""
                sub_mrp = ""

                k = j
                while k < len(lines) and k < j + 20:
                    next_line = lines[k].strip()

                    if not next_line or next_line in skip_words:
                        k += 1
                        continue
                    # Check if it's a header (all caps, contains no numbers - but exclude MRP lines)
                    if (
                        next_line.isupper()
                        and len(next_line) < 50
                        and not next_line.startswith("MRP")
                    ):
                        break
                    if "Salt Composition" in next_line:
                        k += 1
                        break

                    # Capture substitute fields
                    if not sub_name and any(
                        x in next_line.lower()
                        for x in ["tablet", "mg", "capsule", "syrup", "drops"]
                    ):
                        sub_name = next_line
                    elif (
                        sub_name
                        and not sub_company
                        and any(
                            x in next_line
                            for x in [
                                "Pharmaceuticals",
                                "Ltd",
                                "Inc",
                                "Glenmark",
                                "Cipla",
                                "Sun",
                                "Mankind",
                                "Dr.",
                                "Abbott",
                                "Alkem",
                                "Lupin",
                            ]
                        )
                    ):
                        sub_company = next_line
                    elif sub_name and not sub_pack and "Strip of" in next_line:
                        sub_pack = next_line
                    elif sub_name and sub_company and sub_pack:
                        if (
                            "₹" in next_line
                            and "MRP" not in next_line
                            and not sub_price
                        ):
                            sub_price = next_line.replace("₹", "").strip()
                        elif "MRP" in next_line:
                            sub_mrp = next_line.replace("MRP ₹", "").strip()

                    k += 1

                if main_name and main_price and extract_price(main_price):
                    product_data = {
                        "medicine_name": main_name,
                        "medicine_url": search_url,
                        "medicine_id": None,
                        "mrp": None,
                        "selling_price": extract_price(main_price),
                        "discount_percentage": None,
                        "expected_delivery_date": None,
                        "in_stock": True,
                        "stock_status": "In Stock",
                        "pack_size_quantity": main_pack,
                        "substitute": None,
                    }

                    if sub_name and sub_price:
                        product_data["substitute"] = {
                            "medicine_name": sub_name,
                            "company": sub_company,
                            "pack_size_quantity": sub_pack,
                            "selling_price": extract_price(sub_price),
                            "mrp": extract_price(sub_mrp) if sub_mrp else None,
                            "discount_percentage": None,
                            "savings_percentage": None,
                        }

                    results.append(product_data)

                    sub_info = ""
                    if sub_name:
                        sub_info = f" | Sub: {sub_name[:15]} Rs.{extract_price(sub_price)} MRP:{sub_mrp}"
                    print(
                        f"  [OK] {main_name[:25]} | Rs.{extract_price(main_price)}{sub_info}"
                    )
                    i = k
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

    args = [a for a in sys.argv[1:] if a]

    if "--limit" in args:
        limit_idx = args.index("--limit")
        if limit_idx + 1 < len(args):
            max_products = int(args[limit_idx + 1])

    for arg in args:
        if arg.startswith("--") or arg.isdigit():
            continue
        medicine_name = arg
        break

    print(f"Searching PlatinumRx for: {medicine_name} (max {max_products} products)")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        results = await scrape_platinumrx(browser, medicine_name, max_products)
        await browser.close()

    print(f"\n=== Found {len(results)} products ===")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
