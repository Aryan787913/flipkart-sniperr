import os
import time
import requests
from playwright.sync_api import sync_playwright

# ============================================================
#  YOUR SETTINGS — Edit these to change what you're hunting!
# ============================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# HOW TO ADD A PRODUCT:
# 1. Go to Flipkart, open the product page
# 2. Copy the full URL from the browser
# 3. Paste it below in "url"
# 4. Set your target_price (the max price you want to pay)
# 5. Set min_discount (e.g. 70 means alert only if 70%+ off)

TARGETS = [
    {
        "name": "Mi 20000mAh Power Bank",
        "url": "https://www.flipkart.com/mi-pb20i2zm-20000-mah-power-bank/p/itm5432", # REPLACE WITH YOUR PRODUCT URL
        "target_price": 500,    # Alert if price drops to ₹500 or below
        "min_discount": 70      # Alert only if 70% or more off
    },
    # ADD MORE PRODUCTS BELOW (remove the # symbols):
    # {
    #     "name": "boAt Rockerz Earbuds",
    #     "url": "https://www.flipkart.com/your-product-url-here",
    #     "target_price": 300,
    #     "min_discount": 75
    # },
]

# ============================================================
#  DO NOT EDIT BELOW THIS LINE
# ============================================================

ALERTED_PRODUCTS = set()  # Tracks which products already sent alerts this run

def send_telegram_alert(message):
    """Send a message to your Telegram bot."""
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
            print("✅ Telegram alert sent successfully!")
        else:
            print(f"⚠️ Telegram error: {response.text}")
    except Exception as e:
        print(f"❌ Failed to send Telegram alert: {e}")


def send_startup_message():
    """Send a startup notification so you know the bot is alive."""
    targets_list = "\n".join([f"• {t['name']} — Target: ₹{t['target_price']}" for t in TARGETS])
    msg = (
        f"🤖 *Price Sniper Bot Started!*\n\n"
        f"Currently hunting:\n{targets_list}\n\n"
        f"_Checking every 60 seconds. I'll alert you the moment a price drops!_"
    )
    send_telegram_alert(msg)


def check_flipkart_price(page, item):
    """Visit a Flipkart product page and return the current price."""
    try:
        page.goto(item["url"], wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)  # Let JS finish loading

        # Try multiple CSS selectors Flipkart uses for price
        price_selectors = [
            'div.Nx9bqj',
            'div._30jeq3',
            'div._1vC4OE',
            'div._25b18c div._30jeq3',
            'div.CEmiEU div.Nx9bqj',
            'span._2_KrJI',
        ]

        price_str = None
        for selector in price_selectors:
            try:
                el = page.query_selector(selector)
                if el:
                    price_str = el.inner_text().strip()
                    if '₹' in price_str or price_str.replace(',', '').isdigit():
                        break
            except:
                continue

        if not price_str:
            print(f"  ⚠️  Could not find price for: {item['name']} — selector may have changed")
            return None, None

        # Clean price: "₹1,499" → 1499
        clean_price = int(price_str.replace('₹', '').replace(',', '').strip())

        # Try to find MRP (original price) to calculate discount
        mrp_selectors = [
            'div.yRaY8j',
            'div._3I9_wc',
            'div._3auQ3N',
            'span._2p6lqe',
        ]
        mrp = None
        for selector in mrp_selectors:
            try:
                el = page.query_selector(selector)
                if el:
                    mrp_str = el.inner_text().strip()
                    mrp = int(mrp_str.replace('₹', '').replace(',', '').strip())
                    break
            except:
                continue

        return clean_price, mrp

    except Exception as e:
        print(f"  ❌ Error checking {item['name']}: {e}")
        return None, None


def run_sniper():
    """Main loop: check prices every 60 seconds for 14 minutes."""
    print("🚀 Sniper Bot starting up...")
    send_startup_message()

    # Run for 14 minutes (GitHub Actions will restart every 15 min)
    end_time = time.time() + (14 * 60)
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
            print(f"\n🔍 Check #{check_count} at {time.strftime('%H:%M:%S')}")

            for item in TARGETS:
                if item["name"] in ALERTED_PRODUCTS:
                    print(f"  ✅ Already alerted for {item['name']}, skipping.")
                    continue

                print(f"  Checking: {item['name']}...")
                current_price, mrp = check_flipkart_price(page, item)

                if current_price is None:
                    continue

                print(f"  💰 Current Price: ₹{current_price} | Your Target: ₹{item['target_price']}")

                # Calculate discount if MRP is available
                discount_pct = 0
                if mrp and mrp > 0:
                    discount_pct = round(((mrp - current_price) / mrp) * 100)
                    print(f"  📉 Discount: {discount_pct}% off (MRP: ₹{mrp})")

                # Check if the deal meets our criteria
                price_hit = current_price <= item["target_price"]
                discount_hit = discount_pct >= item.get("min_discount", 0)

                if price_hit or (discount_pct > 0 and discount_hit):
                    # Build alert message
                    discount_text = f"{discount_pct}% OFF" if discount_pct > 0 else "HUGE DROP"
                    mrp_text = f"~~₹{mrp}~~ → " if mrp else ""

                    msg = (
                        f"🎯 *SNIPER HIT! {discount_text}*\n\n"
                        f"*{item['name']}*\n\n"
                        f"💸 Price: {mrp_text}*₹{current_price}*\n"
                        f"🎯 Your Target Was: ₹{item['target_price']}\n\n"
                        f"⚡ *BUY NOW BEFORE IT'S GONE!*\n"
                        f"[👉 Open on Flipkart]({item['url']})"
                    )
                    send_telegram_alert(msg)
                    ALERTED_PRODUCTS.add(item["name"])
                    print(f"  🚨 ALERT SENT for {item['name']}!")

                time.sleep(2)  # Small gap between products

            # Wait 60 seconds before next round of checks
            remaining = end_time - time.time()
            if remaining > 60:
                print(f"\n⏳ Waiting 60 seconds... ({int(remaining/60)} mins left in this run)")
                time.sleep(60)
            else:
                break

        browser.close()

    print("\n✅ 14-minute run complete. GitHub Actions will restart in 1 minute.")


if __name__ == "__main__":
    run_sniper()
