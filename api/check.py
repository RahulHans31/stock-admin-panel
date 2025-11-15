import os, json, requests, psycopg2, datetime, time
import concurrent.futures
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
from http.server import BaseHTTPRequestHandler

# ==================================
# 🔧 CONFIGURATION
# ==================================
# This is your main group/channel for stock alerts
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID", "-5096879661") 

PINCODES_STR = os.getenv("PINCODES_TO_CHECK", "110016") 
PINCODES_TO_CHECK = [p.strip() for p in PINCODES_STR.split(',') if p.strip()]

DATABASE_URL = os.getenv("DATABASE_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Flipkart Proxy (AlwaysData)
FLIPKART_PROXY_URL = "https://rknldeals.alwaysdata.net/flipkart_check"
CRON_SECRET = os.getenv("CRON_SECRET")

# Map for alert formatting
STORE_EMOJIS = {
    "croma": "🟢", "flipkart": "🟣", "amazon": "🟡", 
    "unicorn": "🦄", "iqoo": "📱", "vivo": "🤳", 
    "reliance_digital": "🌐"
}


# ==================================
# 💬 TELEGRAM UTILITIES
# ==================================

def send_telegram_message(message, chat_id=TELEGRAM_GROUP_ID):
    """Sends a single message to a specified chat ID."""
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        print(f"[warn] Missing Telegram config for chat {chat_id}.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code != 200:
            print(f"[warn] Telegram send failed to chat {chat_id}: {res.text}")
    except Exception as e:
        print(f"[error] Telegram message error to chat {chat_id}: {e}")

# ==================================
# 🗄️ DATABASE
# ==================================
def get_products_from_db():
    print("[info] Connecting to database...")
    # NOTE: psycopg2 should be installed if running this locally: pip install psycopg2-binary
    conn = psycopg2.connect(DATABASE_URL) 
    cursor = conn.cursor()
    cursor.execute("SELECT name, url, product_id, store_type, affiliate_link FROM products")
    products = cursor.fetchall()
    conn.close()

    products_list = [
        {
            "name": row[0],
            "url": row[1],
            "productId": row[2],
            "storeType": row[3],
            "affiliateLink": row[4],
        }
        for row in products
    ]
    print(f"[info] Loaded {len(products_list)} products from database.")
    return products_list

# ==================================
# 🛒 STORE CHECKERS - RETURN FORMATTED MESSAGE STRING OR None
# ==================================

# --- Unicorn Checker (Product by Product logic is inside the parent caller) ---
def check_unicorn_product(color_name, color_id, storage_id):
    """Checks stock for a single iPhone 17 (256GB) variant at Unicorn Store."""
    
    BASE_URL = "https://fe01.beamcommerce.in/get_product_by_option_id"
    HEADERS = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "customer-id": "unicorn",
        "origin": "https://shop.unicornstore.in",
        "referer": "https://shop.unicornstore.in/",
    }
    
    # Fixed product attributes for iPhone 17 (Category 456)
    CATEGORY_ID = "456" 
    FAMILY_ID = "94"
    GROUP_IDS = "57,58"
    
    variant_name = f"iPhone 17 {color_name} 256GB"
    
    payload = {
        "category_id": CATEGORY_ID,
        "family_id": FAMILY_ID,
        "group_ids": GROUP_IDS,
        "option_ids": f"{color_id},{storage_id}"
    }

    try:
        res = requests.post(BASE_URL, headers=HEADERS, json=payload, timeout=10)
        res.raise_for_status()
        data = res.json()
        
        product_data = data.get("data", {}).get("product", {})
        quantity = product_data.get("quantity", 0)
        
        price = f"₹{int(product_data.get('price', 0)):,}" if product_data.get('price') else "N/A"
        sku = product_data.get("sku", "N/A")
        product_url = "https://shop.unicornstore.in/iphone-17" 
        
        if int(quantity) > 0:
            print(f"[UNICORN] ✅ {variant_name} is IN STOCK ({quantity} units)")
            return (
                f"[{variant_name} - {sku}]({product_url})"
                f"\n💰 Price: {price}, Qty: {quantity}"
            )
        else:
            dispatch_note = product_data.get("custom_column_4", "Out of Stock").strip()
            print(f"[UNICORN] ❌ {variant_name} unavailable: {dispatch_note}")
            
    except Exception as e:
        print(f"[error] Unicorn check failed for {variant_name}: {e}")
    
    return None

# --- Croma Checker ---
def check_croma_product(product, pincode):
    """Checks stock for a single Croma product at one pincode."""
    url = "https://api.croma.com/inventory/oms/v2/tms/details-pwa/"
    payload = {
        "promise": {
            "allocationRuleID": "SYSTEM",
            "checkInventory": "Y",
            "organizationCode": "CROMA",
            "sourcingClassification": "EC",
            "promiseLines": {
                "promiseLine": [
                    {
                        "fulfillmentType": "HDEL",
                        "itemID": product["productId"],
                        "lineId": "1",
                        "requiredQty": "1",
                        "shipToAddress": {"zipCode": pincode},
                        "extn": {"widerStoreFlag": "N"},
                    }
                ]
            },
        }
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "oms-apim-subscription-key": "1131858141634e2abe2efb2b3a2a2a5d",
        "origin": "https://www.croma.com",
        "referer": "https://www.croma.com/",
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        data = res.json()

        lines = (
            data.get("promise", {})
            .get("suggestedOption", {})
            .get("option", {})
            .get("promiseLines", {})
            .get("promiseLine", [])
        )

        if lines:
            print(f"[CROMA] ✅ {product['name']} deliverable to {pincode}")
            return f"[{product['name']}]({product['affiliateLink'] or product['url']})\n📍 Pincode: {pincode}"

        print(f"[CROMA] ❌ {product['name']} unavailable at {pincode}")
    except Exception as e:
        print(f"[error] Croma check failed for {product['name']}: {e}")
    return None

# --- Flipkart Checker (via Proxy) ---
def check_flipkart_product(product, pincode):
    """Checks stock for a single Flipkart product at one pincode via proxy."""
    try:
        payload = {"productId": product["productId"], "pincode": pincode}
        res = requests.post(FLIPKART_PROXY_URL, json=payload, timeout=25)

        if res.status_code != 200:
            print(f"[FLIPKART] ⚠️ Proxy failed ({res.status_code}) for {product['name']}")
            return None

        data = res.json()
        response = data.get("RESPONSE", {}).get(product["productId"], {})
        listing = response.get("listingSummary", {})
        available = listing.get("available", False)

        if available:
            price = listing.get("pricing", {}).get("finalPrice", {}).get("decimalValue", None)
            print(f"[FLIPKART] ✅ {product['name']} deliverable to {pincode}")
            return (
                f"[{product['name']}]({product['affiliateLink'] or product['url']})\n"
                f"📍 Pincode: {pincode}"
                + (f", 💰 Price: ₹{price}" if price else "")
            )

        print(f"[FLIPKART] ❌ {product['name']} not deliverable at {pincode}")
        return None

    except Exception as e:
        print(f"[error] Flipkart proxy check failed for {product['name']}: {e}")
        return None

# --- Amazon HTML Parser Checker ---
def check_amazon_product(product):
    """Check stock availability by scraping the Amazon product page."""
    url = product["url"]
    print(f"[AMAZON] Checking: {url}")

    headers = {
        "authority": "www.amazon.in",
        "method": "GET",
        "scheme": "https",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "max-age=0",
        "sec-ch-ua": '"Not_A Brand";v="99", "Google Chrome";v="137", "Chromium";v="137"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "upgrade-insecure-requests": "1",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/137.0.0.0 Safari/537.36"
        ),
    }

    try:
        res = requests.get(url, headers=headers, timeout=20)
        print(f"[AMAZON] Status code: {res.status_code}")
        html = res.text
        soup = BeautifulSoup(html, "html.parser")

        title_el = soup.select_one("#productTitle")
        price_el = soup.select_one(".a-price .a-offscreen")
        availability_el = soup.select_one("#availability span")

        title = title_el.get_text(strip=True) if title_el else product["name"]
        price = price_el.get_text(strip=True) if price_el else None
        availability = availability_el.get_text(strip=True).lower() if availability_el else ""

        available_phrases = [
            "in stock",
            "free delivery",
            "delivery by",
            "usually dispatched",
            "get it by",
            "available",
        ]
        available = any(phrase in availability for phrase in available_phrases)

        if available:
            print(f"[AMAZON] ✅ {title} is available at {price}")
            return (
                f"[{title}]({product['affiliateLink'] or url})"
                + (f", 💰 Price: {price}" if price else "")
            )
        else:
            print(f"[AMAZON] ❌ {title} appears unavailable. (Availability text: '{availability}')")
            return None

    except Exception as e:
        print(f"[error] Amazon HTML check failed for {product['name']}: {e}")
        return None

# --- Reliance Digital API Checker ---
def check_reliance_digital_product(product, pincode):
    """
    Check stock availability for a Reliance Digital product by querying the 
    inventory API directly using the internal 'article_id'.
    """
    name = product["name"]
    url = product["url"]
    article_id = product["productId"] 
    
    if not article_id:
        print(f"[RD] ❌ Cannot check {name}: Missing internal Article ID.")
        return None

    print(f"[RD] Checking stock: {name} (ID: {article_id}) for Pincode {pincode}")

    inventory_url = "https://www.reliancedigital.in/ext/raven-api/inventory/multi/articles-v2"
    
    inventory_headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "origin": "https://www.reliancedigital.in",
        "referer": "https://www.reliancedigital.in/",
    }

    payload = {
        "articles": [
            {
                "article_id": str(article_id),
                "custom_json": {}, 
                "quantity": 1
            }
        ],
        "phone_number": "0",
        "pincode": str(pincode),
        "request_page": "pdp"
    }

    try:
        res = requests.post(inventory_url, headers=inventory_headers, json=payload, timeout=20)
        res.raise_for_status() 
        data = res.json()
        
        article_data = data.get("data", {}).get("articles", [])
        if not article_data:
            return None

        article = article_data[0]
        article_error = article.get("error", {})
        error_type = article_error.get("type")
        
        is_in_stock = not (error_type and error_type in ["OutOfStockError", "FaultyArticleError"])
        
        price = None
        try:
            res_html = requests.get(url, headers=inventory_headers, timeout=10)
            soup = BeautifulSoup(res_html.text, "html.parser")
            price_el = soup.select_one('.pdpPrice, .product-price .amount, .final-price, [class*="Price"]')
            if price_el:
                price = price_el.get_text(strip=True).replace('\n', ' ').replace('₹', '').strip() 
        except Exception:
            pass 

        if is_in_stock:
            print(f"[RD] ✅ {name} is IN STOCK at {pincode}.")
            return (
                f"[{name}]({product['affiliateLink'] or url})"
                f"\n📍 Pincode: {pincode}"
                + (f", 💰 Price: ₹{price}" if price else "")
            )
        else:
            error_message = article_error.get("message", "Stock Error")
            print(f"[RD] ❌ {name} is UNAVAILABLE at {pincode}. (Error: {error_message})")
            return None

    except requests.exceptions.RequestException as e:
        print(f"[error] Reliance Digital inventory check failed for {name}: {e}")
        return None
    except Exception as e:
        print(f"[error] Reliance Digital check failed for {name} (general): {e}")
        return None

# --- iQOO HTML Parser Checker ---
def check_iqoo_product(product):
    """Check stock availability for an iQOO product by scraping its product page."""
    url = product["url"]
    original_name = product["name"]
    print(f"[IQOO] Checking: {original_name} at {url}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/137.0.0.0 Safari/537.36"
        ),
    }

    try:
        res = requests.get(url, headers=headers, timeout=20)
        html = res.text
        soup = BeautifulSoup(html, "html.parser")

        page_title = soup.find('title')
        product_name = page_title.get_text(strip=True).split('|')[0].strip() if page_title else original_name
        
        buy_now_button = soup.select_one('button:contains("Buy Now"), a:contains("Buy Now")')
        out_of_stock_phrases = ["out of stock", "currently unavailable", "notify me"]
        page_text = soup.get_text().lower()
        
        is_available = True
        availability_text = "Status indeterminate."
        
        if buy_now_button:
            is_disabled = buy_now_button.get('disabled') or 'disabled' in buy_now_button.get('class', []) or 'out-of-stock' in buy_now_button.get('class', [])
            
            if is_disabled:
                is_available = False
                availability_text = "Buy Now button disabled/out-of-stock class found."
            else:
                is_available = True
                availability_text = "Active Buy Now button found."
        
        if not is_available and any(phrase in page_text for phrase in out_of_stock_phrases):
             is_available = False
             availability_text = "Explicit 'out of stock' phrase found in page text."
             
        if not buy_now_button and any(phrase in page_text for phrase in out_of_stock_phrases):
             is_available = False
             availability_text = "No clear button, but OOS text found."

        price_el = soup.select_one('.price-tag, .product-price, .current_price, .selling-price')
        price = price_el.get_text(strip=True) if price_el else None
        
        offer_el = soup.select_one('.product-offers, .discount-details, .emi-details')
        offers = offer_el.get_text(strip=True) if offer_el else None
        
        price_info = ""
        if price:
            price_info += f", 💰 Price: {price.strip()}"
        if offers and len(offers) < 150: 
             price_info += f", 🎁 Offers: {offers.strip()}"


        if is_available:
            print(f"[IQOO] ✅ {product_name} is available.")
            return (
                f"[{product_name}]({product['affiliateLink'] or url})"
                f"{price_info}"
            )
        else:
            print(f"[IQOO] ❌ {product_name} appears unavailable. ({availability_text})")
            return None

    except Exception as e:
        print(f"[error] iQOO check failed for {original_name}: {e}")
        return None

# --- Vivo HTML Parser Checker ---
def check_vivo_product(product):
    """
    Check stock availability for a Vivo product by scraping its product page.
    """
    url = product["url"]
    original_name = product["name"]
    print(f"[VIVO] Checking: {original_name} at {url}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/137.0.0.0 Safari/537.36"
        ),
    }

    try:
        res = requests.get(url, headers=headers, timeout=20)
        print(f"[VIVO] Status code: {res.status_code}")
        html = res.text
        soup = BeautifulSoup(html, "html.parser")

        page_title = soup.find('title')
        product_name = page_title.get_text(strip=True).split('|')[0].strip() if page_title else original_name

        buy_now_link = soup.select_one('a.buyNow, .addToCart, .buyButton')
        out_of_stock_phrases = ["out of stock", "notify me", "currently unavailable"]
        page_text_lower = soup.get_text().lower()
        
        is_available = True
        availability_text = "Status indeterminate."

        if buy_now_link:
            is_disabled = 'disabled' in buy_now_link.get('class', [])
            
            if is_disabled:
                is_available = False
                availability_text = f"Buy Now link found but disabled."
            else:
                is_available = True
                availability_text = f"Active Buy Now link found."
        
        if not is_available and any(phrase in page_text_lower for phrase in out_of_stock_phrases):
             is_available = False
             availability_text = "Explicit 'out of stock' phrase found in page text."
             
        if not buy_now_link and any(phrase in page_text_lower for phrase in out_of_stock_phrases):
             is_available = False
             availability_text = "No active Buy Now link found."

        price_el = soup.select_one('.price-tag, .product-price, .current_price, .selling-price, .js-final-price')
        price = price_el.get_text(strip=True) if price_el else None
        
        offer_el = soup.select_one('.product-offers, .discount-details, .emi-details')
        offers = offer_el.get_text(strip=True) if offer_el else None
        
        price_info = ""
        if price:
            price_info += f", 💰 Price: {price.strip()}"
        if offers and len(offers) < 150: 
             price_info += f", 🎁 Offers: {offers.strip()}"


        if is_available:
            print(f"[VIVO] ✅ {product_name} is available.")
            return (
                f"[{product_name}]({product['affiliateLink'] or url})"
                f"{price_info}"
            )
        else:
            print(f"[VIVO] ❌ {product_name} appears unavailable. ({availability_text})")
            return None

    except Exception as e:
        print(f"[error] Vivo check failed for {original_name}: {e}")
        return None


# Map store type to the specific checker function (single product check)
STORE_CHECKERS_MAP = {
    "croma": check_croma_product,
    "flipkart": check_flipkart_product,
    "amazon": check_amazon_product,
    "reliance_digital": check_reliance_digital_product,
    "iqoo": check_iqoo_product,
    "vivo": check_vivo_product,
}

# Helper wrapper for concurrent execution of DB-tracked products
def check_store_products(store_type, products_to_check, pincodes):
    """
    Checks all products of a specific store type, running inner checks sequentially.
    If stock is found, it sends a Telegram message for this store type.
    Returns a dict with total and found count.
    """
    checker_func = STORE_CHECKERS_MAP.get(store_type)
    if not checker_func:
        return {"total": 0, "found": 0}

    messages_found = []
    
    # Stores where we check against all pincodes
    if store_type in ["croma", "flipkart", "reliance_digital"]:
        for product in products_to_check:
            for pincode in pincodes:
                message = checker_func(product, pincode)
                if message:
                    messages_found.append(message)
                    break # Stop checking other pincodes once stock is found
    else:
        # Stores with no pincode or fixed stock (Amazon, iQOO, Vivo)
        for product in products_to_check:
            message = checker_func(product)
            if message:
                messages_found.append(message)

    found_count = len(messages_found)
    
    # *** Send message if any stock was found for this store type ***
    if found_count > 0:
        header = f"🔥 *Stock Alert: {store_type.replace('_', ' ').title()}* {STORE_EMOJIS.get(store_type, '📦')}\n\n"
        full_message = header + "\n---\n".join(messages_found)
        send_telegram_message(full_message, chat_id=TELEGRAM_GROUP_ID)
        print(f"[STORE_SENDER] ✅ Sent alert for {store_type.title()} with {found_count} products.")
    else:
        print(f"[STORE_SENDER] ❌ No stock found for {store_type.title()}. Skipping alert.")

    # Return counts for the final summary
    return {"total": len(products_to_check), "found": found_count}

def check_unicorn_store():
    """Checks all unicorn products, sends a message if stock is found."""
    COLOR_VARIANTS = {
        "Lavender": "313", "Sage": "311", "Mist Blue": "312", 
        "White": "314", "Black": "315",
    }
    STORAGE_256GB_ID = "250"
    
    messages_found = []

    for color_name, color_id in COLOR_VARIANTS.items():
        message = check_unicorn_product(color_name, color_id, STORAGE_256GB_ID)
        if message:
            messages_found.append(message)
            
    found_count = len(messages_found)
    
    # *** Send message if any stock was found for Unicorn ***
    if found_count > 0:
        header = f"🔥 *Stock Alert: Unicorn* {STORE_EMOJIS.get('unicorn', '📦')}\n\n"
        full_message = header + "\n---\n".join(messages_found)
        send_telegram_message(full_message, chat_id=TELEGRAM_GROUP_ID)
        print(f"[STORE_SENDER] ✅ Sent alert for Unicorn with {found_count} products.")
    else:
        print(f"[STORE_SENDER] ❌ No stock found for Unicorn. Skipping alert.")

    # Return counts for the final summary
    return {"total": len(COLOR_VARIANTS), "found": found_count}


def main_logic():
    start_time = time.time()
    print("[info] Starting stock check...")
    products = get_products_from_db()
    
    # 1. Separate DB products by store type
    products_by_store = {
        store_type: [p for p in products if p["storeType"] == store_type]
        for store_type in STORE_CHECKERS_MAP.keys()
    }
    
    # Stores to check concurrently
    all_store_types = list(STORE_CHECKERS_MAP.keys()) + ["unicorn"]
    tracked_stores = {
        store: {"total": len(products_by_store.get(store, [])), "found": 0}
        for store in all_store_types
    }
    
    total_tracked = sum(data['total'] for data in tracked_stores.values())


    # --- Concurrent Check using ThreadPoolExecutor ---
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_store = {}
        
        # Submit tasks for DB-tracked stores
        for store_type in STORE_CHECKERS_MAP.keys():
            if products_by_store.get(store_type):
                future = executor.submit(
                    check_store_products, 
                    store_type, 
                    products_by_store[store_type], 
                    PINCODES_TO_CHECK
                )
                future_to_store[future] = store_type

        # Submit Unicorn task separately
        future_to_store[executor.submit(check_unicorn_store)] = "unicorn"
        
        # Collect results (counts only)
        for future in concurrent.futures.as_completed(future_to_store):
            store_type = future_to_store[future]
            try:
                result = future.result()
                tracked_stores[store_type].update(result)
            except Exception as e:
                print(f"[ERROR] Concurrent check for {store_type} failed: {e}")

    # 3. Compile final results for handler JSON response
    total_found = sum(data['found'] for data in tracked_stores.values())
    duration = round(time.time() - start_time, 2)
    timestamp = datetime.datetime.now().strftime("%d %b %Y %I:%M %p")
    
    summary_lines = [
        f"Found: {total_found}/{total_tracked} products available.",
        f"Time taken: {duration}s",
        f"Checked at: {timestamp}",
    ]
    final_summary = "\n".join(summary_lines)

    print(f"[info] ✅ Finished check. Found {total_found} products in stock.")
    
    return total_found, total_tracked, final_summary


# ==================================
# 🧠 VERCEL HANDLER
# ==================================
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        print("[info] Handler started.")
        query_components = parse_qs(urlparse(self.path).query)
        auth_key = query_components.get("secret", [None])[0]

        if auth_key != CRON_SECRET:
            print("[error] Unauthorized access attempt.")
            self.send_response(401)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Unauthorized"}).encode())
            return

        try:
            # Main logic runs checks and sends store-specific messages via worker threads
            total_found, total_tracked, final_summary = main_logic()

            # The final summary and logs are SKIPPED as requested.
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            # Still return status in the HTTP response body for Vercel/cron job status tracking
            self.wfile.write(
                json.dumps(
                    {"status": "ok", "found": total_found, "total": total_tracked, "summary": final_summary}
                ).encode()
            )

        except Exception as e:
            print(f"[fatal error] {e}")

            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
