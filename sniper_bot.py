import os
import time
import requests
from playwright.sync_api import sync_playwright

# ============================================================
#  YOUR SETTINGS — Only change these!
# ============================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

MIN_DISCOUNT = 70   # Alert if 70% or more off (change to 80 for 80%+ only)
MAX_PRICE = 600     # Alert only if price is ₹600 or below (change as you like)

# ============================================================
#  CATEGORIES TO SCAN
#  Bot scans ALL products in these categories automatically
#  Add or remove categories as you like!
# ============================================================

CATEGORY_PAGES = [
    {
        "name": "Power Banks",
        "url": "https://www.flipkart.com/search?q=power+bank&sort=discount_desc"
    },
    {
        "name": "Earbuds",
        "url": "https://www.flipkart.com/search?q=earbuds&sort=discount_desc"
    },
    {
        "name": "Smartwatches",
        "url": "https://www.flipkart.com/search?q=smartwatch&sort=discount_desc"
    },
    {
        "name": "Bluetooth Speakers",
        "url": "https://www.flipkart.com/search?q=bluetooth+speaker&sort=discount_desc"
    },
    {
        "name": "Mobile Phones",
        "url": "https://www.flipkart.com/search?q=mobile+phone&sort=discount_desc"
    },
    {
        "name": "Headphones",
        "url": "https://www.flipkart.com/search?q=headphones&sort=discount_desc"
    },
    {
        "name": "T-Shirts",
        "url": "https://www.flipkart.com/search?q=tshirt+men&sort=discount_desc"
    },
    {
        "name": "Shoes",
        "url": "https://www.flipkart.com/search?q=shoes+men&sort=discount_desc"
    },
]

# ============================================================
#  DO NOT EDIT BELOW THIS LINE
# ============================================================

already_alerted = set()


def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print("  ✅ Telegram alert sent!")
        else:
            print(f"  ⚠️ Telegram error: {response.text}")
    except Exception as e:
        print(f"  ❌ Failed to send alert: {e}")


def send_startup_message():
    categories = "\n".join([f"• {c['name']}" for c in CATEGORY_PAGES])
    msg = (
        f"🤖 *Loot Deal Sniper Started!*\n\n"
        f"📦 Scanning:\n{categories}\n\n"
        f"🎯 Alert when: *{MIN_DISCOUNT}%+ OFF* and price ≤ *₹{MAX_PRICE}*\n\n"
        f"_Checking every 60 seconds. Will ping you instantly for any loot!_"
    )
    send_telegram_alert(msg)


def scan_category(page, category):
    deals_found = []
    try:
        print(f"  🔍 Scanning: {category['name']}...")
        page.goto(category["url"], wait_until="domcontentloaded", timeout=60000)
        time.sleep(4)

        # Try multiple card selectors Flipkart uses
        product_cards = page.query_selector_all('div._1AtVbE')
        if not product_cards:
            product_cards = page.query_selector_all('div.tUxRFH')
        if not product_cards:
            product_cards = page.query_selector_all('div._13oc-S')

        print(f"     Found {len(product_cards)} products")

        for card in product_cards:
            try:
                # Get name
                name_el = (
                    card.query_selector('div.KzDlHZ') or
                    card.query_selector('div._4rR01T') or
                    card.query_selector('a.IRpwTa') or
                    card.query_selector('a.s1Q9rs')
                )
                if not name_el:
                    continue
                name = name_el.inner_text().strip()
                if not name:
                    continue

                # Get current price
                price_el = (
                    card.query_selector('div.Nx9bqj') or
                    card.query_selector('div._30jeq3') or
                    card.query_selector('div._1_WHN1')
                )
                if not price_el:
                    continue
                price_str = price_el.inner_text().strip()
                current_price = int(price_str.replace('₹', '').replace(',', '').strip())

                # Get discount %
                discount_el = (
                    card.query_selector('div.UkUFwK') or
                    card.query_selector('div._3Ay6Sb') or
                    card.query_selector('div.G_ZGT0') or
                    card.query_selector('span._2p6lqe')
                )
                discount_pct = 0
                if discount_el:
                    discount_str = discount_el.inner_text().strip()
                    digits = ''.join(filter(str.isdigit, discount_str))
                    if digits:
                        discount_pct = int(digits)

                # Get product link
                product_url = ""
                link_el = card.query_selector('a')
                if link_el:
                    href = link_el.get_attribute('href')
                    if href:
                        product_url = f"https://www.flipkart.com{href}" if href.startswith('/') else href

                # Check if loot deal
                if discount_pct >= MIN_DISCOUNT and current_price <= MAX_PRICE:
                    deal_key = f"{name[:30]}_{current_price}"
                    if deal_key not in already_alerted:
                        deals_found.append({
                            "name": name,
                            "price": current_price,
                            "discount": discount_pct,
                            "url": product_url,
                            "category": category["name"]
                        })
                        already_alerted.add(deal_key)

            except Exception:
                continue

    except Exception as e:
        print(f"  ❌ Error scanning {category['name']}: {e}")

    return deals_found


def run_sniper():
    print("🚀 Loot Deal Sniper starting...")
    send_startup_message()

    end_time = time.time() + (14 * 60)  # Run for 14 minutes
    check_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
        )
        page = context.new_page()

        while time.time() < end_time:
            check_count += 1
            print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"🔍 Scan #{check_count} — {time.strftime('%H:%M:%S')}")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            all_deals = []
            for category in CATEGORY_PAGES:
                deals = scan_category(page, category)
                all_deals.extend(deals)
                time.sleep(2)

            if all_deals:
                print(f"\n🚨 {len(all_deals)} LOOT DEALS FOUND!")
                for deal in all_deals:
                    msg = (
                        f"🔥 *LOOT DEAL — {deal['discount']}% OFF!*\n\n"
                        f"📦 *{deal['name']}*\n\n"
                        f"💸 Current Price: *₹{deal['price']}*\n"
                        f"📉 Discount: *{deal['discount']}% OFF*\n"
                        f"🏷️ Category: {deal['category']}\n\n"
                        f"⚡ *BUY NOW BEFORE STOCK ENDS!*\n"
                        f"[👉 Open on Flipkart]({deal['url']})"
                    )
                    send_telegram_alert(msg)
                    time.sleep(1)
            else:
                print("  No loot deals this round.")

            remaining = end_time - time.time()
            if remaining > 60:
                print(f"\n⏳ Next scan in 60 seconds... ({int(remaining / 60)} mins left)")
                time.sleep(60)
            else:
                break

        browser.close()

    print("\n✅ 14-minute run complete. GitHub Actions will restart shortly.")


if __name__ == "__main__":
    run_sniper()
