import os, json, requests, psycopg2, datetime, time
import concurrent.futures
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler
import hashlib # Added for Amazon API
import hmac     # Added for Amazon API

# ==================================
# 🔧 CONFIGURATION
# ==================================
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")
PINCODES_STR = os.getenv("PINCODES_TO_CHECK", "110016")
PINCODES_TO_CHECK = [p.strip() for p in PINCODES_STR.split(',') if p.strip()]

DATABASE_URL = os.getenv("DATABASE_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Flipkart Proxy (AlwaysData)
FLIPKART_PROXY_URL = "https://my-flipkart-worker.rahulhns41.workers.dev/flipkart_check"
# Reliance Digital Proxy (AlwaysData)

CRON_SECRET = os.getenv("CRON_SECRET")

# --- Amazon PAAPI Credentials ---
AMAZON_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AMAZON_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AMAZON_PARTNER_TAG = os.getenv("AMAZON_PARTNER_TAG")
AMAZON_HOST = "webservices.amazon.in"
AMAZON_REGION = "eu-west-1"
AMAZON_SERVICE = "ProductAdvertisingAPI"
AMAZON_ENDPOINT = "https://webservices.amazon.in/paapi5/getitems"

# --- OPPO Configuration ---
# New API endpoint for serviceability check
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
    "reliance_digital": "🌐",
    "vijay_sales": "🛍️",
    "sangeetha": "🟠",
    "oppo": "🔵",
    "jiomart": "🛍️", # Added Jiomart emoji
}


# --- MODIFIED: Load Topic IDs from environment variables ---
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
    "jiomart": os.getenv("JIOMART_TOPIC_ID"), # Added Jiomart topic ID
}

# --- END MODIFIED ---

# ==================================
# 💬 TELEGRAM UTILITIES
# ==================================
# --- MODIFIED: Function now accepts an optional thread_id ---
def send_telegram_message(message, chat_id=TELEGRAM_GROUP_ID, thread_id=None):
    """Sends a single message to a specified chat ID and optional topic thread."""
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
    
    # --- MODIFIED: Add message_thread_id to payload if it exists ---
    if thread_id:
        try:
            payload["message_thread_id"] = int(thread_id)
        except (ValueError, TypeError):
            print(f"[warn] Invalid thread_id: {thread_id}. Sending to main group.")
    # --- END MODIFIED ---

    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code != 200:
            print(f"[warn] Telegram send failed to chat {chat_id} (Thread: {thread_id}): {res.text}")
    except Exception as e:
        print(f"[error] Telegram message error to chat {chat_id} (Thread: {thread_id}): {e}")
# --- END MODIFIED ---

# ==================================
# 🗄️ DATABASE
# ==================================
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

# ==================================
# 🔑 AMAZON V4 SIGNATURE HELPERS
# ==================================
def sign(key, msg):
    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

def getSignatureKey(key, dateStamp, regionName, serviceName):
    kDate = sign(('AWS4' + key).encode('utf-8'), dateStamp)
    kRegion = sign(kDate, regionName)
    kService = sign(kRegion, serviceName)
    kSigning = sign(kService, 'aws4_request')
    return kSigning

# ==================================
# 🛒 STORE CHECKERS (API-ONLY)
# ==================================

# --- Unicorn Checker (API - OK) ---
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

# --- Croma Checker (API - OK) ---
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

        # FULL REAL LOGIC
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

        print(f"[FLIPKART] ❌ {product['name']} not available or not deliverable at {pincode}")
        return None

    except Exception as e:
        print(f"[error] Flipkart proxy check failed for {product['name']}: {e}")
        return None

# --- Amazon API Checker (PAAPI v5) ---
def check_amazon_api(product):
    """Checks Amazon stock using the direct PAAPI v5."""
    asin = product["productId"]
    print(f"[AMAZON_API] Checking: {asin}")

    if not all([AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_PARTNER_TAG]):
        print("[error] Amazon API credentials (KEY, SECRET, TAG) are not set.")
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
                f"💰 Price: N/A (Price check removed)"
            )
        else:
            print(f"[AMAZON_API] ❌ {product['name']} is {availability_message}")
            return None

    except Exception as e:
        print(f"[error] Amazon API check failed for {asin}: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"[error] Amazon Response: {e.response.text}")
        return None
RELIANCE_WORKER_URL = "https://proxyrd.rahulhns41.workers.dev/"

def check_reliance_digital_product(product, pincode):
    try:
        payload = {
            "article_id": product["productId"],
            "pincode": pincode
        }

        res = requests.post(
            "https://proxyrd.rahulhns41.workers.dev/",
            json=payload,
            headers={"X-Bypass": str(time.time())},  # Prevent Cloudflare caching
            timeout=25
        )

        if res.status_code != 200:
            print("[RD] Error:", res.status_code, res.text)
            return None

        try:
            data = res.json()
        except Exception:
            print("[RD] JSON Parse Error:", res.text)
            return None

        print("[RD] available:", data.get("available") , payload)

        if data.get("available"):
            return (
                f"[{product['name']}]({product['affiliateLink'] or product['url']})\n"
                f"📍 Pincode: {pincode}"
            )

        return data

    except Exception as e:
        print("[RD] Worker failed:", e)
        return None

# --- iQOO API Checker (FINAL) ---
def check_iqoo_api(product):
    """Checks iQOO stock using the direct API endpoint."""
    product_id = product["productId"] # This is the SPU ID
    IQOO_API_URL = f"https://mshop.iqoo.com/in/api/product/activityInfo/all/{product_id}"
    
    print(f"[IQOO_API] Checking: {product_id} at {IQOO_API_URL}")

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://mshop.iqoo.com/in/product/{product_id}",
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/5.36"
    }

    try:
        res = requests.get(IQOO_API_URL, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()

        if data.get("success") != "1" or "data" not in data:
            print(f"[IQOO_API] ❌ {product['name']} failed. API success was not '1'.")
            return None

        sku_list = data.get("data", {}).get("activitySkuList", [])
        if not sku_list:
            print(f"[IQOO_API] ❌ {product['name']} - No SKU list found in response.")
            return None

        is_in_stock = False
        for sku in sku_list:
            reservable_id = sku.get("activityInfo", {}).get("reservableId")
            if reservable_id == -1:
                is_in_stock = True
                break 

        if is_in_stock:
            print(f"[IQOO_API] ✅ {product['name']} is IN STOCK")
            return (
                f"[{product['name']}]({product['affiliateLink'] or product['url']})\n"
                f"💰 Price: N/A (API doesn't show price)"
            )
        else:
            print(f"[IQOO_API] ❌ {product['name']} is Out of Stock (reservableId was not -1).")
            return None
            
    except Exception as e:
        print(f"[error] iQOO API check failed for {product_id}: {e}")
        return None

# --- Vivo API Checker (FINAL) ---
def check_vivo_api(product):
    """Checks Vivo stock using the direct API endpoint."""
    product_id = product["productId"] # This is the SPU ID
    VIVO_API_URL = f"https://mshop.vivo.com/in/api/product/activityInfo/all/{product_id}"
    
    print(f"[VIVO_API] Checking: {product_id} at {VIVO_API_URL}")

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://mshop.vivo.com/in/product/{product_id}",
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/5.36"
    }

    try:
        res = requests.get(VIVO_API_URL, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()

        if data.get("success") != "1" or "data" not in data:
            print(f"[VIVO_API] ❌ {product['name']} failed. API success was not '1'.")
            return None

        sku_list = data.get("data", {}).get("activitySkuList", [])
        if not sku_list:
            print(f"[VIVO_API] ❌ {product['name']} - No SKU list found in response.")
            return None

        is_in_stock = False
        for sku in sku_list:
            reservable_id = sku.get("activityInfo", {}).get("reservableId")
            if reservable_id == -1:
                is_in_stock = True
                break 

        if is_in_stock:
            print(f"[VIVO_API] ✅ {product['name']} is IN STOCK")
            return (
                f"[{product['name']}]({product['affiliateLink'] or product['url']})\n"
                f"💰 Price: N/A (API doesn't show price)"
            )
        else:
            print(f"[VIVO_API] ❌ {product['name']} is Out of Stock (reservableId was not -1).")
            return None
            
    except Exception as e:
        print(f"[error] Vivo API check failed for {product_id}: {e}")
        return None

# --- MODIFIED: OPPO Serviceability Checker (Uses SKU + Pincode) ---
def check_oppo_product(product, pincode):
    """Checks OPPO serviceability for exact SKU at a specific pincode."""
    sku = product["productId"]
    print(f"[OPPO] Checking SKU: {sku} at Pincode: {pincode}")

    payload = {
        "pincode": str(pincode),
        "skuCodes": [sku],
        "storeViewCode": "in",
        "configModule": 3,
        "settleChannel": 3
    }

    try:
        # Use the dedicated serviceability URL and headers
        res = requests.post(OPPO_SERVICEABILITY_URL, json=payload, headers=OPPO_BASE_HEADERS, timeout=15)
        res.raise_for_status()
        data = res.json()
        
        products_data = data.get("data", {}).get("products", [])
        
        is_available = False
        for product_data in products_data:
            if product_data.get("skuCode") == sku:
                # deliveryOnlineSupport is true if in stock AND deliverable
                is_available = product_data.get("deliveryOnlineSupport", False)
                break
        
        if is_available:
            print(f"[OPPO] ✅ {product['name']} deliverable to {pincode}")
            return (
                f"[{product['name']}]({product['affiliateLink'] or product['url']})\n"
                f"📍 Pincode: {pincode}"
            )

        print(f"[OPPO] ❌ {product['name']} not deliverable at {pincode}")
        return None

    except Exception as e:
        print(f"[error] OPPO serviceability check failed for {sku} at {pincode}: {e}")
        return None

# --- NEW: Jiomart Checker ---
def check_jiomart_product(product, pincode):
    """Checks Jiomart stock using the direct API endpoint for the given product ID and pincode."""
    product_id = product["productId"]
    print(f"[JIOMART] Checking Product: {product_id} at Pincode: {pincode}")

    url = f"https://www.jiomart.com/catalog/productdetails/get/{product_id}"
    
    # Jiomart uses the 'pin' in the header for the check
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36",
        "x-requested-with": "XMLHttpRequest",
        "pin": str(pincode),
        # Use the stored URL for a more accurate referrer, falling back to a generic one
        "referer": product['url'] or f"https://www.jiomart.com/p/generic/{product_id}" 
    }

    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        r = res.json()

        if r.get("status") != "success":
            print(f"[JIOMART] ❌ {product['name']} failed API response: {r.get('status')}")
            return None

        data = r.get("data", {})
        
        # FIX: Rely primarily on availability_status == "A" for stock/deliverability
        is_available_and_deliverable = (data.get("availability_status") == "A")
        stock_qty = data.get("stock_qty")
        price = data.get("selling_price")

        if is_available_and_deliverable:
            # Optionally include stock_qty if available, but don't fail if it's zero
            stock_info = f" ({stock_qty} units)" if stock_qty is not None and stock_qty > 0 else ""
            print(f"[JIOMART] ✅ {product['name']} is IN STOCK{stock_info} at {pincode}")
            return (
                f"[{product['name']}]({product['affiliateLink'] or product['url']})\n"
                f"📍 Pincode: {pincode}"
                + (f", 💰 Price: ₹{price}" if price else "")
            )
        else:
            print(f"[JIOMART] ❌ {product['name']} OUT OF STOCK or UNDELIVERABLE at {pincode}")
            return None

    except Exception as e:
        print(f"[error] Jiomart check failed for {product_id} at {pincode}: {e}")
        return None
# --- END NEW JIOMART CHECKER ---


# ==================================
# 🗺️ STORE CHECKER MAP (UPDATED)
# ==================================

# Map store type to the specific checker function (single product check)
STORE_CHECKERS_MAP = {
    "croma": check_croma_product,
    "flipkart": check_flipkart_product,
    "amazon": check_amazon_api,                
    "reliance_digital": check_reliance_digital_product, 
    "iqoo": check_iqoo_api,                      
    "vivo": check_vivo_api, 
    "oppo": check_oppo_product,
    "jiomart": check_jiomart_product, # Added Jiomart
}

# ==================================
# 🚀 CHECKER HELPERS
# ==================================

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
    if store_type in ["croma", "flipkart", "reliance_digital", "oppo", "jiomart"]:
        for product in products_to_check:
            for pincode in pincodes:
                message = checker_func(product, pincode)
                if message:
                    messages_found.append(message)
                    break # Stop checking other pincodes once stock is found
    else:
        # Stores with no pincode (Amazon, iQOO, Vivo, etc.)
        for product in products_to_check:
            message = checker_func(product)
            if message:
                messages_found.append(message)

    found_count = len(messages_found)
    
    # *** Send message if any stock was found for this store type ***
    if found_count > 0:
        header = f"🔥 *Stock Alert: {store_type.replace('_', ' ').title()}* {STORE_EMOJIS.get(store_type, '📦')}\n\n"
        full_message = header + "\n---\n".join(messages_found)
        
        # --- MODIFIED: Get the thread_id for this store ---
        thread_id = STORE_TOPIC_IDS.get(store_type)
        send_telegram_message(full_message, chat_id=TELEGRAM_GROUP_ID, thread_id=thread_id)
        # --- END MODIFIED ---
        
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
    
    if found_count > 0:
        header = f"🔥 *Stock Alert: Unicorn* {STORE_EMOJIS.get('unicorn', '📦')}\n\n"
        full_message = header + "\n---\n".join(messages_found)
        
        # --- MODIFIED: Get the thread_id for this store ---
        thread_id = STORE_TOPIC_IDS.get('unicorn')
        send_telegram_message(full_message, chat_id=TELEGRAM_GROUP_ID, thread_id=thread_id)
        # --- END MODIFIED ---
        
        print(f"[STORE_SENDER] ✅ Sent alert for Unicorn with {found_count} products.")
    else:
        print(f"[STORE_SENDER] ❌ No stock found for Unicorn. Skipping alert.")

    return {"total": len(COLOR_VARIANTS), "found": found_count}

# ==================================
# 🛍️ VIJAY SALES STATIC CHECKER (NEW)
# ==================================
def check_vijay_sales_store():
    """Checks stock for the 5 fixed iPhone 17 variants on Vijay Sales."""
    # Use the globally loaded pincodes
    PINCODES = PINCODES_TO_CHECK  
    
    # Hardcoded products (like Unicorn function)
    PRODUCTS = {
        "iPhone 17 Mist Blue 256GB": {
            "vanNo": "245181",
            "url": "https://www.vijaysales.com/p/P245179/245181/apple-iphone-17-256gb-storage-mist-blue"
        },
        "iPhone 17 Black 256GB": {
            "vanNo": "245179",
            "url": "https://www.vijaysales.com/p/P245179/245179/apple-iphone-17-256gb-storage-black"
        },
        "iPhone 17 White 256GB": {
            "vanNo": "245180",
            "url": "https://www.vijaysales.com/p/P245179/245180/apple-iphone-17-256gb-storage-white"
        },
        "iPhone 17 Lavender 256GB": {
            "vanNo": "245182",
            "url": "https://www.vijaysales.com/p/P245179/245182/apple-iphone-17-256gb-storage-lavender"
        },
        "iPhone 17 Sage 256GB": {
            "vanNo": "245183",
            "url": "https://www.vijaysales.com/p/P245179/245183/apple-iphone-17-256gb-storage-sage"
        }
    }

    messages_found = []
    total_variants = len(PRODUCTS)

    for name, info in PRODUCTS.items():
        vanNo = info["vanNo"]
        url = info["url"]

        for pin in PINCODES:
            api_url = (
                f"https://mdm.vijaysales.com/web/api/oms/check-servicibility/v1"
                f"?pincode={pin}&vanNo={vanNo}&storeList=true"
            )

            headers = {
                "accept": "*/*",
                "origin": "https://www.vijaysales.com",
                "referer": "https://www.vijaysales.com/",
                "user-agent": (
                    "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142 Mobile Safari/537.36"
                )
            }

            try:
                res = requests.get(api_url, headers=headers, timeout=10)
                data = res.json()

                detail = data.get("data", {}).get(str(vanNo), {})
                delivery = detail.get("isServiceable", False)
                pickup_list = detail.get("storePickupList", [])
                pickup = len(pickup_list) > 0

                if delivery or pickup:
                    print(f"[VS] ✅ {name} available at {pin}")
                    msg = (
                        f"[{name}]({url})\n"
                        f"📦 Delivery: {'YES' if delivery else 'NO'}, "
                        f"🏬 Pickup: {'YES' if pickup else 'NO'}\n"
                        f"📍 Pincode: {pin}"
                    )
                    messages_found.append(msg)
                    break  # no need to check other pincodes

                else:
                    print(f"[VS] ❌ {name} not at {pin}")

            except Exception as e:
                print(f"[error] Vijay Sales failed for {name}: {e}")
    
    # --- Add the Telegram sending logic ---
    found_count = len(messages_found)
    
    if found_count > 0:
        header = f"🔥 *Stock Alert: Vijay Sales* {STORE_EMOJIS.get('vijay_sales', '🛍️')}\n\n"
        full_message = header + "\n---\n".join(messages_found)
        
        # --- MODIFIED: Get the thread_id for this store ---
        thread_id = STORE_TOPIC_IDS.get('vijay_sales')
        send_telegram_message(full_message, chat_id=TELEGRAM_GROUP_ID, thread_id=thread_id)
        # --- END MODIFIED ---
        
        print(f"[STORE_SENDER] ✅ Sent alert for Vijay Sales with {found_count} products.")
    else:
        print(f"[STORE_SENDER] ❌ No stock found for Vijay Sales. Skipping alert.")

    # --- Return the standard count dictionary ---
    return {"total": total_variants, "found": found_count}



def check_sangeetha_store():
    """Checks hardcoded iPhone 17 variants for Sangeetha Mobiles."""
    
    PRODUCTS = {
        19685: "iPhone 17 Sage",
        19681: "iPhone 17 Lavender",
        19678: "iPhone 17 White",
        19680: "iPhone 17 Black",
        19683: "iPhone 17 Blue",
    }

    PINCODES = PINCODES_TO_CHECK
    API_URL = "https://www.sangeethamobiles.com/b/customer/api/v3/product-eta-details"

    HEADERS = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "origin": "https://www.sangeethamobiles.com",
        "referer": "https://www.sangeethamobiles.com/",
        "user-agent": (
            "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36"
        ),
        "number1": "1",
        "number2": "1",
    }

    messages_found = []
    total_variants = len(PRODUCTS)

    for product_id, product_name in PRODUCTS.items():
        for pincode in PINCODES:
            payload = {
                "type": "pwa",
                "product_id": str(product_id),
                "pinCode": str(pincode),
                "user_id": "70638581",
                "user_location": "AutoCheck",
            }

            try:
                res = requests.post(API_URL, json=payload, headers=HEADERS, timeout=15)

                # OOS means product removed → 500 or 404
                if res.status_code in [500, 404]:
                    print(f"[SANGEETHA] ❌ {product_name} removed/OOS")
                    continue

                if res.status_code != 200:
                    print(f"[SANGEETHA] ❌ Unexpected status {res.status_code}")
                    continue

                data = res.json()
                eta = data.get("data", {}).get("product_eta")

                if eta and eta.get("stock_status", "").lower() == "instock":
                    print(f"[SANGEETHA] ✅ {product_name} IN STOCK at {pincode}")
                    url = f"https://www.sangeethamobiles.com/product-details/{product_id}"
                    msg = (
                        f"[{product_name}]({url})\n"
                        f"📍 Pincode: {pincode}\n"
                        f"ETA: {eta.get('eta_title', '')}"
                    )
                    messages_found.append(msg)
                    break

                else:
                    print(f"[SANGEETHA] ❌ {product_name} OOS")

            except Exception as e:
                print(f"[error] Sangeetha failed for {product_name}: {e}")

    # Send Telegram message
    found_count = len(messages_found)

    if found_count > 0:
        header = f"🔥 *Stock Alert: Sangeetha Mobiles* {STORE_EMOJIS.get('sangeetha', '📱')}\n\n"
        full_message = header + "\n---\n".join(messages_found)
        thread_id = STORE_TOPIC_IDS.get("sangeetha")
        send_telegram_message(full_message, chat_id=TELEGRAM_GROUP_ID, thread_id=thread_id)
        print(f"[STORE_SENDER] ✅ Sent alert for Sangeetha with {found_count} products.")
    else:
        print(f"[STORE_SENDER] ❌ No stock found for Sangeetha.")

    return {"total": total_variants, "found": found_count}



# ==================================
# 🧠 MAIN LOGIC (Original - No Bucketing)
# ==================================
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
    # The dictionary keys must contain all store types, including static ones, for the summary.
    all_store_types = list(STORE_CHECKERS_MAP.keys()) + ["unicorn", "vijay_sales" , "sangeetha"]
    tracked_stores = {
        store: {"total": len(products_by_store.get(store, [])), "found": 0}
        for store in all_store_types
    }
    
    # Manually set total for static checkers - PAUSED/IGNORED
    # Setting them to 0 prevents them from skewing the total_tracked count when paused.
    tracked_stores["unicorn"]["total"] = 0 
    tracked_stores["vijay_sales"]["total"] = 5
    tracked_stores["sangeetha"]["total"] = 0

    
    total_tracked = sum(data['total'] for data in tracked_stores.values())


    # --- Concurrent Check using ThreadPoolExecutor ---
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_store = {}
        
        # Submit tasks for DB-tracked stores (Jiomart, Oppo, Flipkart, etc.)
        for store_type in STORE_CHECKERS_MAP.keys():
            if products_by_store.get(store_type):
                future = executor.submit(
                    check_store_products, 
                    store_type, 
                    products_by_store[store_type], 
                    PINCODES_TO_CHECK
                )
                future_to_store[future] = store_type

        # Submit static store tasks (PAUSED)
        # We explicitly skip the submission of the hardcoded checkers here
        
        # future_to_store[executor.submit(check_unicorn_store)] = "unicorn"
        future_to_store[executor.submit(check_vijay_sales_store)] = "vijay_sales"
        # future_to_store[executor.submit(check_sangeetha_store)] = "sangeetha"

        
        # Collect results (counts only)
        for future in concurrent.futures.as_completed(future_to_store):
            store_type = future_to_store[future]
            try:
                result = future.result()
                # Update found count, but keep total as set above
                tracked_stores[store_type]["found"] = result.get("found", 0)
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

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
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
