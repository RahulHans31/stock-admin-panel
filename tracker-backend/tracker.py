import os, json, requests, psycopg2, datetime, time
import concurrent.futures
from urllib.parse import urlparse, parse_qs
import hashlib
import hmac

# ==================================
# 🔧 CONFIGURATION
# ==================================
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")
PINCODES_STR = os.getenv("PINCODES_TO_CHECK", "110016")
PINCODES_TO_CHECK = [p.strip() for p in PINCODES_STR.split(',') if p.strip()]

WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "")
WHATSAPP_GROUP_NAME = os.getenv("WHATSAPP_GROUP_NAME", "Stock Alerts")

DATABASE_URL = os.getenv("DATABASE_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Amazon PAAPI Credentials
AMAZON_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AMAZON_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AMAZON_PARTNER_TAG = os.getenv("AMAZON_PARTNER_TAG")
AMAZON_HOST = "webservices.amazon.in"
AMAZON_REGION = "eu-west-1"
AMAZON_SERVICE = "ProductAdvertisingAPI"
AMAZON_ENDPOINT = "https://webservices.amazon.in/paapi5/getitems"

# OPPO Configuration
OPPO_SERVICEABILITY_URL = "https://opsg-gateway-in.oppo.com/v2/api/rest/mall/product/retail/store/fetch"
OPPO_BASE_HEADERS = {
    "Content-Type": "application/json",
    "client-version": "13.0.0.0",
    "platform": "web",
    "language": "en-IN",
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.oppo.com",
    "Accept-Language": "en-US,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}

STORE_EMOJIS = {
    "croma": "🟢", "flipkart": "🟣", "amazon": "🟡",
    "unicorn": "🦄", "iqoo": "📱", "vivo": "🤳",
    "reliance_digital": "🌐", "vijay_sales": "🛍️",
    "sangeetha": "🟠", "oppo": "🔵", "jiomart": "🛍️",
}

STORE_TOPIC_IDS = {
    "croma": os.getenv("CROMA_TOPIC_ID"),
    "flipkart": os.getenv("FLIPKART_TOPIC_ID"),
    "amazon": os.getenv("AMAZON_TOPIC_ID"),
    "unicorn": os.getenv("UNICORN_TOPIC_ID"),
    "iqoo": os.getenv("IQOO_TOPIC_ID"),
    "vivo": os.getenv("VIVO_TOPIC_ID"),
    "reliance_digital": os.getenv("RELIANCE_TOPIC_ID"),
    "vijay_sales": os.getenv("VIJAY_SALES_TOPIC_ID"),
    "sangeetha": os.getenv("SANGEETHA_TOPIC_ID"),
    "oppo": os.getenv("OPPO_TOPIC_ID"),
    "jiomart": os.getenv("JIOMART_TOPIC_ID"),
}

CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))  # Default 5 minutes

def send_whatsapp_message(message):
    if not WHATSAPP_API_URL:
        return
    try:
        import re
        clean_message = re.sub(r'\[(.*?)\]\((.*?)\)', r'\1: \2', message)
        payload = {"group": WHATSAPP_GROUP_NAME, "message": clean_message}
        requests.post(WHATSAPP_API_URL, json=payload, timeout=1)
    except Exception:
        pass

def send_telegram_message(message, chat_id=TELEGRAM_GROUP_ID, thread_id=None):
    send_whatsapp_message(message)

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

    if thread_id:
        try:
            payload["message_thread_id"] = int(thread_id)
        except (ValueError, TypeError):
            print(f"[warn] Invalid thread_id: {thread_id}.")

    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code != 200:
            print(f"[warn] Telegram send failed: {res.text}")
    except Exception as e:
        print(f"[error] Telegram message error: {e}")

def get_products_from_db():
    print("[info] Connecting to database...")
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

def sign(key, msg):
    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

def getSignatureKey(key, dateStamp, regionName, serviceName):
    kDate = sign(('AWS4' + key).encode('utf-8'), dateStamp)
    kRegion = sign(kDate, regionName)
    kService = sign(kRegion, serviceName)
    kSigning = sign(kService, 'aws4_request')
    return kSigning

def extract_sku_id(url):
    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        sku_id = query_params.get("skuId", [None])[0]
        return str(sku_id) if sku_id else None
    except Exception as e:
        print(f"[error] Failed to parse SKU from URL {url}: {e}")
        return None

# ==================================
# 🛒 STORE CHECKERS (Direct API calls - no proxy)
# ==================================

def check_croma_product(product, pincode):
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

def check_flipkart_product(product, pincode):
    """Direct Flipkart API call - no proxy"""
    try:
        flipkart_payload = {
            "requestContext": {
                "products": [{"productId": product["productId"]}],
                "marketplace": "FLIPKART"
            },
            "locationContext": {"pincode": pincode}
        }

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "https://www.flipkart.com",
            "Referer": "https://www.flipkart.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.60 Safari/537.36",
            "X-User-Agent": "Mozilla/5.0 FKUA/msite/0.0.3/msite/Mobile",
            "flipkart_secure": "true"
        }

        res = requests.post(
            "https://2.rome.api.flipkart.com/api/3/product/serviceability",
            json=flipkart_payload,
            headers=headers,
            timeout=25
        )

        if res.status_code != 200:
            print(f"[FLIPKART] ⚠️ API failed ({res.status_code})")
            return None

        data = res.json()
        response = data.get("RESPONSE", {}).get(product["productId"], {})
        listing = response.get("listingSummary", {})

        serviceable = listing.get("serviceable", False)
        available = listing.get("available", False)

        if serviceable and available:
            price = listing.get("pricing", {}).get("finalPrice", {}).get("decimalValue", None)
            print(f"[FLIPKART] ✅ {product['name']} deliverable to {pincode}")
            return (
                f"[{product['name']}]({product['affiliateLink'] or product['url']})\n"
                f"📍 Pincode: {pincode}"
                + (f", 💰 Price: ₹{price}" if price else "")
            )

        print(f"[FLIPKART] ❌ {product['name']} not available at {pincode}")
        return None

    except Exception as e:
        print(f"[error] Flipkart check failed: {e}")
        return None

def check_amazon_api(product):
    asin = product["productId"]
    print(f"[AMAZON_API] Checking: {asin}")

    if not all([AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_PARTNER_TAG]):
        print("[error] Amazon API credentials missing.")
        return None

    t = datetime.datetime.utcnow()
    amz_date = t.strftime('%Y%m%dT%H%M%SZ')
    date_stamp = t.strftime('%Y%m%d')

    payload = {
        "ItemIds": [asin],
        "PartnerTag": AMAZON_PARTNER_TAG,
        "PartnerType": "Associates",
        "Marketplace": "www.amazon.in",
        "Resources": [
            "OffersV2.Listings.Availability",
            "ItemInfo.Title"
        ]
    }
    payload_str = json.dumps(payload)

    method = 'POST'
    target = 'com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems'
    content_type = 'application/json; charset=UTF-8'

    canonical_headers = (
        f'content-type:{content_type}\n'
        f'host:{AMAZON_HOST}\n'
        f'x-amz-date:{amz_date}\n'
        f'x-amz-target:{target}\n'
    )
    signed_headers = 'content-type;host;x-amz-date;x-amz-target'
    payload_hash = hashlib.sha256(payload_str.encode('utf-8')).hexdigest()

    canonical_request = (
        f'{method}\n'
        '/paapi5/getitems\n'
        '\n'
        f'{canonical_headers}\n'
        f'{signed_headers}\n'
        f'{payload_hash}'
    )

    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = f'{date_stamp}/{AMAZON_REGION}/{AMAZON_SERVICE}/aws4_request'
    canonical_request_hash = hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()

    string_to_sign = (
        f'{algorithm}\n'
        f'{amz_date}\n'
        f'{credential_scope}\n'
        f'{canonical_request_hash}'
    )

    signing_key = getSignatureKey(AMAZON_SECRET_KEY, date_stamp, AMAZON_REGION, AMAZON_SERVICE)
    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

    authorization_header = (
        f'{algorithm} '
        f'Credential={AMAZON_ACCESS_KEY}/{credential_scope}, '
        f'SignedHeaders={signed_headers}, '
        f'Signature={signature}'
    )

    headers = {
        'Content-Type': content_type,
        'X-Amz-Date': amz_date,
        'X-Amz-Target': target,
        'Authorization': authorization_header,
        'Content-Encoding': 'amz-1.0',
        'Host': AMAZON_HOST
    }

    try:
        res = requests.post(AMAZON_ENDPOINT, data=payload_str, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()

        item = data.get("ItemsResult", {}).get("Items", [{}])[0]
        listing = item.get("OffersV2", {}).get("Listings", [{}])[0]
        availability = listing.get("Availability", {})
        availability_message = availability.get("Message", "Status Unknown")
        availability_type = availability.get("Type", "OUT_OF_STOCK")

        if availability_type == "IN_STOCK" or "in stock" in availability_message.lower():
            product_title = item.get("ItemInfo", {}).get("Title", {}).get("DisplayValue", product["name"])
            print(f"[AMAZON_API] ✅ {product_title} is IN STOCK")
            return (
                f"[{product_title}]({product['affiliateLink'] or product['url']})\n"
                f"💰 Stock Available"
            )
        else:
            print(f"[AMAZON_API] ❌ {product['name']} is {availability_message}")
            return None

    except Exception as e:
        print(f"[error] Amazon API check failed: {e}")
        return None

def check_reliance_digital_product(product, pincode):
    """Direct Reliance Digital API call"""
    try:
        url = "https://www.reliancedigital.in/rildigitalws/v2/rrldigital/edd/details"
        payload = {
            "pincode": pincode,
            "skuId": product["productId"],
            "pincodeType": "D"
        }

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "origin": "https://www.reliancedigital.in",
            "referer": "https://www.reliancedigital.in/",
            "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36"
        }

        res = requests.post(url, json=payload, headers=headers, timeout=15)

        if res.status_code != 200:
            print(f"[RD] Error: {res.status_code}")
            return None

        data = res.json()

        # Check if delivery is available
        delivery_available = data.get("deliveryAvailability", False)

        if delivery_available:
            print(f"[RD] ✅ {product['name']} deliverable to {pincode}")
            return (
                f"[{product['name']}]({product['affiliateLink'] or product['url']})\n"
                f"📍 Pincode: {pincode}"
            )

        print(f"[RD] ❌ Not available at {pincode}")
        return None

    except Exception as e:
        print(f"[error] RD check failed: {e}")
        return None

def check_iqoo_api(product):
    return check_vivo_iqoo_api(product, "iqoo")

def check_vivo_api(product):
    return check_vivo_iqoo_api(product, "vivo")

def check_vivo_iqoo_api(product, store_type):
    product_id = product["productId"]
    store_url_base = f"https://mshop.{store_type}.com/in"
    API_URL = f"{store_url_base}/api/product/all/{product_id}"

    target_sku_id = extract_sku_id(product["url"])
    if not target_sku_id:
        print(f"[{store_type.upper()}_API] ⚠️ Skipping. No 'skuId' in URL.")
        return None

    print(f"[{store_type.upper()}_API] Checking: SPU={product_id}, SKU={target_sku_id}")

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"{store_url_base}/product/{product_id}",
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36"
    }

    try:
        res = requests.get(API_URL, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()

        if data.get("success") != "1" or not data.get("data"):
            print(f"[{store_type.upper()}_API] ❌ API failed.")
            return None

        spu_data = data["data"].get("commodityDetailSpu", {})
        sku_list = spu_data.get("skuList", [])

        if not sku_list:
            print(f"[{store_type.upper()}_API] ❌ No SKU list.")
            return None

        is_in_stock = False
        product_title = product["name"]
        sku_price = None

        for sku in sku_list:
            sku_id_from_api = str(sku.get("skuId"))

            if sku_id_from_api == target_sku_id:
                stock_qty = sku.get("stock", 0)
                stock_out_checked = sku.get("stockOutChecked", 1)
                marketable = sku.get("marketable", 0)

                color_name = sku.get("colorName", "")
                rom_name = sku.get("romName", "")
                if color_name and rom_name:
                    product_title = f"{product['name']} ({color_name} / {rom_name})"
                elif color_name:
                    product_title = f"{product['name']} ({color_name})"

                sku_price = sku.get("salePrice") or sku.get("proPrice")

                if int(stock_qty) > 0 and int(stock_out_checked) == 0 and int(marketable) == 1:
                    is_in_stock = True

                break

        if is_in_stock:
            print(f"[{store_type.upper()}_API] ✅ {product_title} IN STOCK")
            price_str = f"💰 Price: ₹{int(sku_price):,}" if sku_price else "💰 Price: N/A"
            return (
                f"[{product_title}]({product['affiliateLink'] or product['url']})\n"
                f"{price_str}"
            )
        else:
            print(f"[{store_type.upper()}_API] ❌ Out of Stock")
            return None

    except Exception as e:
        print(f"[error] {store_type.upper()} check failed: {e}")
        return None

def check_oppo_product(product, pincode):
    sku = product["productId"]
    print(f"[OPPO] Checking SKU: {sku} at {pincode}")

    payload = {
        "pincode": str(pincode),
        "skuCodes": [sku],
        "storeViewCode": "in",
        "configModule": 3,
        "settleChannel": 3
    }

    try:
        res = requests.post(OPPO_SERVICEABILITY_URL, json=payload, headers=OPPO_BASE_HEADERS, timeout=15)
        res.raise_for_status()
        data = res.json()

        if not data or not isinstance(data, dict):
            print(f"[OPPO] ❌ Invalid API response")
            return None

        products_data = data.get("data", {}).get("products", []) if data.get("data") else []

        is_available = False
        for product_data in products_data:
            if product_data.get("skuCode") == sku:
                is_available = product_data.get("deliveryOnlineSupport", False)
                break

        if is_available:
            print(f"[OPPO] ✅ {product['name']} deliverable to {pincode}")
            return (
                f"[{product['name']}]({product['affiliateLink'] or product['url']})\n"
                f"📍 Pincode: {pincode}"
            )

        print(f"[OPPO] ❌ Not deliverable at {pincode}")
        return None

    except Exception as e:
        print(f"[error] OPPO check failed: {e}")
        return None

def check_jiomart_product(product, pincode):
    product_id = product["productId"]
    print(f"[JIOMART] Checking: {product_id} at {pincode}")

    url = f"https://www.jiomart.com/catalog/productdetails/get/{product_id}"

    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36",
        "x-requested-with": "XMLHttpRequest",
        "pin": str(pincode),
        "referer": product['url'] or f"https://www.jiomart.com/p/generic/{product_id}"
    }

    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        r = res.json()

        if r.get("status") != "success":
            print(f"[JIOMART] ❌ API failed")
            return None

        data = r.get("data", {})

        is_available_and_deliverable = (data.get("availability_status") == "A")
        stock_qty = data.get("stock_qty")
        price = data.get("selling_price")

        if is_available_and_deliverable:
            stock_info = f" ({stock_qty} units)" if stock_qty and stock_qty > 0 else ""
            print(f"[JIOMART] ✅ IN STOCK{stock_info}")
            return (
                f"[{product['name']}]({product['affiliateLink'] or product['url']})\n"
                f"📍 Pincode: {pincode}"
                + (f", 💰 Price: ₹{price}" if price else "")
            )
        else:
            print(f"[JIOMART] ❌ Out of Stock at {pincode}")
            return None

    except Exception as e:
        print(f"[error] Jiomart check failed: {e}")
        return None

STORE_CHECKERS_MAP = {
    "croma": check_croma_product,
    "flipkart": check_flipkart_product,
    "amazon": check_amazon_api,
    "reliance_digital": check_reliance_digital_product,
    "iqoo": check_iqoo_api,
    "vivo": check_vivo_api,
    "oppo": check_oppo_product,
    "jiomart": check_jiomart_product,
}

def check_store_products(store_type, products_to_check, pincodes):
    checker_func = STORE_CHECKERS_MAP.get(store_type)
    if not checker_func:
        return {"total": 0, "found": 0}

    messages_found = []

    if store_type in ["croma", "flipkart", "reliance_digital", "oppo", "jiomart"]:
        for product in products_to_check:
            for pincode in pincodes:
                message = checker_func(product, pincode)
                if message:
                    messages_found.append(message)
                    break
    else:
        for product in products_to_check:
            message = checker_func(product)
            if message:
                messages_found.append(message)

    found_count = len(messages_found)

    if found_count > 0:
        header = f"🔥 *Stock Alert: {store_type.replace('_', ' ').title()}* {STORE_EMOJIS.get(store_type, '📦')}\n\n"
        full_message = header + "\n---\n".join(messages_found)

        thread_id = STORE_TOPIC_IDS.get(store_type)
        send_telegram_message(full_message, chat_id=TELEGRAM_GROUP_ID, thread_id=thread_id)

        print(f"[STORE_SENDER] ✅ Sent alert for {store_type} with {found_count} products.")
    else:
        print(f"[STORE_SENDER] ❌ No stock found for {store_type}.")

    return {"total": len(products_to_check), "found": found_count}

def main_logic():
    start_time = time.time()
    print("[info] Starting stock check...")
    products = get_products_from_db()

    products_by_store = {
        store_type: [p for p in products if p["storeType"] == store_type]
        for store_type in STORE_CHECKERS_MAP.keys()
    }

    all_store_types = list(STORE_CHECKERS_MAP.keys())
    tracked_stores = {
        store: {"total": len(products_by_store.get(store, [])), "found": 0}
        for store in all_store_types
    }

    total_tracked = sum(data['total'] for data in tracked_stores.values())

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_store = {}

        for store_type in STORE_CHECKERS_MAP.keys():
            if products_by_store.get(store_type):
                future = executor.submit(
                    check_store_products,
                    store_type,
                    products_by_store[store_type],
                    PINCODES_TO_CHECK
                )
                future_to_store[future] = store_type

        for future in concurrent.futures.as_completed(future_to_store):
            store_type = future_to_store[future]
            try:
                result = future.result()
                tracked_stores[store_type]["found"] = result.get("found", 0)
            except Exception as e:
                print(f"[ERROR] Check for {store_type} failed: {e}")

    total_found = sum(data['found'] for data in tracked_stores.values())
    duration = round(time.time() - start_time, 2)
    timestamp = datetime.datetime.now().strftime("%d %b %Y %I:%M %p")

    print(f"[info] ✅ Finished. Found {total_found}/{total_tracked} in {duration}s at {timestamp}")

    return total_found, total_tracked, duration

if __name__ == "__main__":
    print("🚀 Stock Tracker Started - Running continuously")
    print("⏱️ 20 seconds delay between checks")

    while True:
        try:
            main_logic()
            print("[info] ✅ Check completed. Waiting 20 seconds before next check...")
            time.sleep(20)
        except Exception as e:
            print(f"[FATAL ERROR] {e}")
            print("[info] Waiting 10 seconds before retry...")
            time.sleep(10)
