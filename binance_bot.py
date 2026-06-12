import os
import threading
from flask import Flask
import requests
import websocket
import json
import time

# Flask для поддержания "жизни" на бесплатном тарифе Render
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is running!"

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
rsi_cache = {}

LIQUIDATION_THRESHOLDS = {
    "btcusdt": 149000, "ethusdt": 79000, "bnbusdt": 79000, "xrpusdt": 79000,
    "solusdt": 79000, "dogeusdt": 79000, "dotusdt": 49000, "atomusdt": 39000,
    "linkusdt": 39000, "trxusdt": 59000, "wifusdt": 39000, "ltcusdt": 29000,
    "aiusdt": 49000, "seisdt": 49000, "suisdt": 49000, "xlmsdt": 39000,
    "mkrsdt": 39000, "zecsdt": 29000, "aavesdt": 49000, "tonusdt": 49000,
    "pepeusdt": 49000, "aptusdt": 49000, "wldusdt": 49000, "opusdt": 49000,
    "ldousdt": 49000, "trbusdt": 49000, "bchusdt": 49000, "virtualusdt": 49000,
    "grassusdt": 49000, "sandusdt": 49000, "axsusdt": 49000, "taousdt": 49000,
    "penguusdt": 49000, "zenusdt": 49000, "tokenusdt": 49000, "sushiusdt": 49000,
    "bnxusdt": 39000, "reefusdt": 49000, "eigenusdt": 29000, "trumpusdt": 79000,
    "1000satsusdt": 39000, "popcatusdt": 39000, "ilvusdt": 29000
}

SPOT_THRESHOLDS = {
    "btcusdt": 189000, "ethusdt": 120000, "bnbusdt": 79000, "xrpusdt": 99000,
    "solusdt": 99000, "dogeusdt": 89000, "yggusdt": 189000, "adausdt": 49000,
    "trxusdt": 59000, "tonusdt": 49000, "suiusdt": 59000, "linkusdt": 49000,
    "seiusdt": 49000, "wifusdt": 49000, "dashusdt": 49000, "zecusdt": 49000,
    "mkrusdt": 49000, "bnxusdt": 49000, "eosusdt": 49000, "galausdt": 49000,
    "aevousdt": 49000, "atomusdt": 49000, "filusdt": 49000, "vetusdt": 49000,
    "aptusdt": 49000, "virtualusdt": 49000, "aaveusdt": 49000, "nearusdt": 49000,
    "icpusdt": 49000, "ltcusdt": 49000, "pepeusdt": 49000, "uniusdt": 49000,
    "bchusdt": 49000, "dotusdt": 49000, "xlmusdt": 49000, "dydxusdt": 49000,
    "neousdt": 49000, "bomeusdt": 49000, "sushiusdt": 49000, "gmtusdt": 49000,
    "axsusdt": 49000, "trbusdt": 49000, "1inchusdt": 49000, "mewusdt": 49000,
    "omgusdt": 49000, "wavesusdt": 49000, "bakeusdt": 44000, "glmrusdt": 44000,
    "enjusdt": 44000, "woousdt": 44000, "mavusdt": 44000, "mboxusdt": 44000,
    "slerfusdt": 44000, "c98usdt": 44000, "audiousdt": 44000, "alphausdt": 44000,
    "dogsusdt": 31000, "opusdt": 31000, "reefusdt": 49000, "eigenusdt": 29000,
    "trumpusdt": 79000
}

def get_rsi(symbol, interval, period=14):
    key = f"{symbol}_{interval}"
    if key in rsi_cache and (time.time() - rsi_cache[key][0] < 60):
        return rsi_cache[key][1]
    try:
        data = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol.upper()}&interval={interval}&limit={period+1}", timeout=5).json()
        closes = [float(c[4]) for c in data]
        gains = [max(closes[i]-closes[i-1], 0) for i in range(1, len(closes))]
        losses = [abs(min(closes[i]-closes[i-1], 0)) for i in range(1, len(closes))]
        avg_g, avg_l = sum(gains)/period, sum(losses)/period
        rs = avg_g/avg_l if avg_l != 0 else 100
        val = round(100 - (100/(1+rs)), 2)
        rsi_cache[key] = (time.time(), val)
        return val
    except: return None

def send_telegram(msg):
    try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=5)
    except: pass

def on_message(ws, message, is_futures):
    data = json.loads(message)
    if is_futures and data.get('e') == "forceOrder":
        o = data['o']
        s, side, price, qty = o['s'].lower(), o['S'], float(o['p']), float(o['q'])
        amt = price * qty
        if s in LIQUIDATION_THRESHOLDS and amt >= LIQUIDATION_THRESHOLDS[s]:
            send_telegram(f"<b>{'❇️ Short liq' if side == 'BUY' else '🩸 Long liq'}</b>\n{s.upper()}\n{amt:.0f} USDT\nRSI 4H: {get_rsi(s, '4h')}")
    elif not is_futures and data.get('e') == "trade":
        s, price, qty = data['s'].lower(), float(data['p']), float(data['q'])
        amt = price * qty
        if s in SPOT_THRESHOLDS and amt >= SPOT_THRESHOLDS[s]:
            send_telegram(f"<b>Spot Trade</b>\n{s.upper()}\n{amt:.0f} USDT\nRSI 4H: {get_rsi(s, '4h')}")

if __name__ == "__main__":
    threading.Thread(target=lambda: websocket.WebSocketApp("wss://fstream.binance.com/ws/!forceOrder@arr", on_message=lambda ws, m: on_message(ws, m, True)).run_forever(ping_interval=30), daemon=True).start()
    threading.Thread(target=lambda: websocket.WebSocketApp(f"wss://stream.binance.com:9443/ws/{'/@trade/'.join(SPOT_THRESHOLDS.keys())}@trade", on_message=lambda ws, m: on_message(ws, m, False)).run_forever(ping_interval=30), daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
