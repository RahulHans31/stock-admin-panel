from http.server import BaseHTTPRequestHandler
import os, json, requests, psycopg2
from urllib.parse import urlparse, parse_qs

# --- NEW, SIMPLER AMAZON IMPORTS ---
from amazon.paapi import AmazonAPI, Country
# ------------------------------------

# --- 1. CONFIGURATION ---
PINCODES_TO_CHECK = ['132001']
DATABASE_URL = os.environ.get('DATABASE_URL')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CRON_SECRET = os.environ.get('CRON_SECRET')

# --- AMAZON SECRETS ---
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AMAZON_PARTNER_TAG = os.environ.get('AMAZON_PARTNER_TAG')
# ---------------------------

# --- 2. VERCEK HANDLER ---
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query_components = parse_qs(urlparse(self.path).query)
        auth_key = query_components.get('secret', [None])[0]

        if auth_key != CRON_SECRET:
            self.send_response(401) # Unauthorized
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Unauthorized. Check your CRON_SECRET.'}).encode())
            return

        try:
            in_stock_messages = main_logic()
            
            if in_stock_messages:
                print(f"Found {len(in_stock_messages)} items in stock. Sending Telegram message.")
                final_message = "🔥 *Stock Alert!*\n\n" + "\n\n".join(in_stock_messages)
                send_telegram_message(final_message)
            else:
                print("All items out of stock. No message sent.")

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok', 'found': len(in_stock_messages)}).encode())
            
        except Exception as e:
            print(f"An error occurred: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

# --- 3. DATABASE: FETCH PRODUCTS ---
def get_products_from_db():
    print("Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT name, url, product_id, store_type, affiliate_link FROM products WHERE store_type IN ('croma', 'amazon')")
    products = cursor.fetchall()
    conn.close()
    
    products_list = [
        {"name": row[0], "url": row[1], "productId": row[2], "storeType": row[3], "affiliateLink": row[4]}
        for row in products
    ]
    print(f"Found {len(products_list)} Croma & Amazon products in the database.")
    return products_list

# --- 4. TELEGRAM SENDER ---
def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN:
        print("Telegram BOT TOKEN not set. Skipping message.")
        return
    chat_ids = ['7992845749', '984016385' , '6644657779' , '8240484793' , '1813686494' ,'1438419270' ,'939758815' , '7500224400' , '8284863866' , '837532484' , '667911343' , '1476695901' , '6878100797' , '574316265' , '1460192633' , '978243265' ,'5871190519' ,'766044262' ,'1639167211' , '849850934' ,'757029917' , '5756316614' ,'5339576661' , '6137007196' , '7570729917' ,'79843912' , '1642837409' , '724035898'] 
    
    print(f"Sending message to {len(chat_ids)} users...")

    for chat_id in chat_ids:
        if not chat_id.strip(): continue
        url = f"https{api.telegram.org/bot}{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {'chat_id': chat_id.strip(), 'text': message, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print(f"Failed to send message to {chat_id}: {e}")

# --- 5. CROMA CHECKER ---
def check_croma(product, pincode):
    url = 'https://api.croma.com/inventory/oms/v2/tms/details-pwa/'
    payload = {"promise": {"allocationRuleID": "SYSTEM", "checkInventory": "Y", "organizationCode": "CROMA", "sourcingClassification": "EC", "promiseLines": {"promiseLine": [{"fulfillmentType": "HDEL", "itemID": product["productId"], "lineId": "1", "requiredQty": "1", "shipToAddress": {"zipCode": pincode}, "extn": {"widerStoreFlag": "N"}}]}}}
    headers = {'accept': 'application/json', 'content-type': 'application/json', 'oms-apim-subscription-key': '1131858141634e2abe2efb2b3a2a2a5d', 'origin': 'https://www.croma.com', 'referer': 'https://www.croma.com/'}
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        res.raise_for_status() 
        data = res.json()
        if data.get("promise", {}).get("suggestedOption", {}).get("option", {}).get("promiseLines", {}).get("promiseLine"):
            link_to_send = product["affiliateLink"] or product["url"]
            return f'✅ *In Stock at Croma ({pincode})*\n[{product["name"]}]({link_to_send})'
    except Exception as e:
        print(f'Error checking Croma ({product["name"]}): {e}')
    return None 

# --- 6. NEW AMAZON CHECKER (Using amazon-paapi5) ---
def check_amazon(product):
    if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AMAZON_PARTNER_TAG]):
        print("Amazon API credentials not set. Skipping Amazon.")
        return None

    asin = product["productId"]
    
    try:
        # Initialize the API client using the library you found
        amazon = AmazonAPI(
            AWS_ACCESS_KEY_ID, 
            AWS_SECRET_ACCESS_KEY, 
            AMAZON_PARTNER_TAG, 
            Country.IN # Use Country.IN for webservices.amazon.in
        )
        
        print(f"Checking Amazon for: {product['name']}...")
        # Call the API to get item info
        # This matches your curl request for Availability.Message
        response = amazon.get_items(
            item_ids=[asin],
            resources=["Offers.Listings.Availability.Message"]
        )

        # Check for API errors
        if response.get('errors'):
            print(f"Error checking Amazon API for ASIN {asin}: {response['errors'][0].message}")
            return None
        
        # Get the item data
        item = response.get('data', {}).get(asin)
        
        if item and item.offers and item.offers.listings:
            availability = item.offers.listings[0].availability.message
            print(f"...Amazon item {product['name']} is: {availability}")
            
            # Check if the message is "In Stock."
            if "in stock" in availability.lower():
                link_to_send = product["affiliateLink"] or product["url"]
                return f'✅ *In Stock at Amazon*\n[{product["name"]}]({link_to_send})'
        
        print(f"...Amazon item {product['name']} is Out of Stock.")
        return None

    except Exception as e:
        print(f"Non-API error checking Amazon ({product['name']}): {e}")
    
    return None

# --- 7. MAIN LOGIC (Called by Vercel Handler) ---
def main_logic():
    print("Starting stock check...")
    try:
        products_to_track = get_products_from_db()
    except Exception as e:
        print(f"Failed to fetch products from database: {e}")
        send_telegram_message(f"❌ Your checker script failed to connect to the database.")
        return []

    in_stock_messages = []
    
    for product in products_to_track:
        result_message = None
        if product["storeType"] == 'croma':
            for pincode in PINCODES_TO_CHECK:
                result_message = check_croma(product, pincode)
                if result_message:
                    in_stock_messages.append(result_message)
                    break 
        
        elif product["storeType"] == 'amazon':
            result_message = check_amazon(product)
            if result_message:
                in_stock_messages.append(result_message)
    
    return in_stock_messages