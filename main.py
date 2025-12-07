import os
import time
import pytz
from datetime import datetime
from kiteconnect import KiteConnect, KiteTicker

# 🔐 Load secrets from Render environment variables
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")

# 🔄 Auto-renew access token (no login needed)
kite = KiteConnect(api_key=API_KEY)
try:
    session = kite.renew_access_token(REFRESH_TOKEN, API_SECRET)
    ACCESS_TOKEN = session["access_token"]
    print(f"✅ Token renewed. Bot active for 24h.")
except Exception as e:
    print(f"❌ Token renewal failed: {e}")
    exit(1)

# 📈 Strategy parameters
SYMBOL = "NIFTYBEES"
EXCHANGE = "NSE"
INSTRUMENT_TOKEN = 256788  # NIFTYBEES (Nippon India ETF)
INVESTMENT_AMOUNT = 10000  # ₹10,000
THRESHOLD_PCT = -1.0       # Trigger at -1% drop
BOUGHT = False

# 📡 WebSocket callback
def on_ticks(ws, ticks):
    global BOUGHT
    if BOUGHT:
        return

    tick = ticks[0]
    ltp = tick["last_price"]
    
    # Set CMP on first tick (market open)
    if not hasattr(on_ticks, "cmp"):
        on_ticks.cmp = ltp
        print(f"📌 CMP set: ₹{ltp:.2f} at {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')}")
    
    # Calculate % change
    change_pct = ((ltp - on_ticks.cmp) / on_ticks.cmp) * 100
    print(f"LTP: ₹{ltp:.2f} | Δ: {change_pct:.2f}%")

    # 🛒 Execute buy if condition met
    if change_pct <= THRESHOLD_PCT:
        qty = int(INVESTMENT_AMOUNT // ltp)
        if qty < 1:
            print("⚠️ Quantity < 1 — skipping")
            return
        
        try:
            # Place MARKET buy order (CNC = delivery)
            order_id = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=EXCHANGE,
                tradingsymbol=SYMBOL,
                transaction_type=kite.TRANSACTION_TYPE_BUY,
                quantity=qty,
                product=kite.PRODUCT_CNC,
                order_type=kite.ORDER_TYPE_MARKET
            )
            print(f"✅ BOUGHT {qty} NIFTYBEES @ ₹{ltp:.2f} (₹{ltp*qty:.0f}) | Order: {order_id}")
            BOUGHT = True
        except Exception as e:
            print(f"❌ Order failed: {e}")

# 🔌 Connect to Zerodha WebSocket
print("🚀 Connecting to Zerodha WebSocket...")
kws = KiteTicker(API_KEY, ACCESS_TOKEN)
kws.on_ticks = on_ticks
kws.on_connect = lambda ws, resp: (
    print("✅ WebSocket connected"),
    ws.subscribe([INSTRUMENT_TOKEN]),
    ws.set_mode(ws.MODE_LTP, [INSTRUMENT_TOKEN])
)
kws.connect(threaded=True)

# ⏳ Keep bot alive until market close
IST = pytz.timezone('Asia/Kolkata')
print("🕒 Bot running. Monitoring for ≥2% drop...")

while True:
    now = datetime.now(IST)
    # Exit at 3:30 PM IST
    if now.hour >= 15 and now.minute >= 30:
        print("🔚 Market closed. Bot shutting down.")
        break
    time.sleep(1)
