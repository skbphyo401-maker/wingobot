import asyncio
import hashlib
import json
import random
import time
import requests
import urllib3
from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TELEGRAM_BOT_TOKEN = "8627859015:AAH22tUL126grjh6NDk5yMwKqCKgFu3belc"
WINGO_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOiIxNzg2MDMwODYzIiwibmJmIjoiMTc4NjAzMDg2MyIsImV4cGlyYXRpb24iOiI4LzYvMjAyNiAxMDo0MTowMyBQTSIsIlVzZXJJZCI6IjU4NjkyMyJ9.XLvoZF6-VmGtfPX7M426I9S2-KbNTbls4sE3XZXtE_E"

API_BASE = "https://ckygjf6r.com/api/webapi/"
TYPE_ID = 30

active_chats = set()
last_processed_period = None
history_results = {}
current_bet_multiplier = 1

def generate_signature(data):
    sorted_data = {k: data[k] for k in sorted(data.keys())}
    json_str = json.dumps(sorted_data, separators=(',', ':'))
    return hashlib.md5(json_str.encode('utf-8')).hexdigest().upper()

def make_payload(extra={}):
    random_hex = "".join([random.choice("0123456789abcdef") for _ in range(16)])
    payload = {
        "language": 0,
        "random": random_hex,
        **extra
    }
    payload["signature"] = generate_signature(payload)
    payload["timestamp"] = int(time.time())
    return payload

def fetch_history():
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Authorization": f"Bearer {WINGO_TOKEN}",
        "Ar-Origin": "https://www.cklottery.club",
        "User-Agent": "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    }
    try:
        res = requests.post(
            API_BASE + "GetNoaverageEmerdList",
            json=make_payload({"pageSize": 30, "pageNo": 1, "typeId": TYPE_ID}),
            headers=headers,
            timeout=8,
            verify=False
        )
        if res.status_code == 200:
            data = res.json()
            if data.get("code") == 0:
                return data.get("data", {}).get("list", [])
    except Exception as e:
        print(f"API Fetch Error: {e}")
    return []

def calculate_prediction(history):
    if len(history) < 15:
        return None
    
    numbers = [int(x.get("number", 0)) for x in history]
    bs_list = ["BIG" if n >= 5 else "SMALL" for n in numbers]
    
    streak_count = 1
    for i in range(len(bs_list) - 1):
        if bs_list[i] == bs_list[i+1]:
            streak_count += 1
        else:
            break

    if streak_count >= 3:
        raw_pred = bs_list[0]
    else:
        score_b = 0.0
        score_s = 0.0
        weights = [3.0, 2.5, 2.0, 1.5, 1.0, 0.8, 0.6, 0.4, 0.2, 0.1]
        
        for idx, bs in enumerate(bs_list[:10]):
            if bs == "BIG":
                score_b += weights[idx]
            else:
                score_s += weights[idx]
                
        raw_pred = "BIG" if score_b >= score_s else "SMALL"
        
    current_issue = int(history[0].get("issueNumber"))
    next_issue = str(current_issue + 1)
    
    return {
        "current_period": str(current_issue),
        "next_period": next_issue,
        "last_num": history[0].get("number"),
        "raw_pred": raw_pred
    }

async def auto_prediction_worker(app: Application):
    global last_processed_period, current_bet_multiplier
    while True:
        try:
            if active_chats:
                history = await asyncio.to_thread(fetch_history)
                if history:
                    latest_period = str(history[0].get("issueNumber"))
                    
                    if latest_period != last_processed_period:
                        res = calculate_prediction(history)
                        if res:
                            last_num = int(res["last_num"])
                            last_bs = "BIG" if last_num >= 5 else "SMALL"
                            
                            if res["current_period"] in history_results:
                                prev_pred = history_results[res["current_period"]]
                                if prev_pred == last_bs:
                                    current_bet_multiplier = 1
                                else:
                                    current_bet_multiplier *= 3
                            
                            history_results[res["next_period"]] = res["raw_pred"]
                            
                            msg = (
                                f"🔥 **WIN GO 30S** 🔥\n\n"
                                f"🏀 **MATCH**   ;   `{res['next_period'][-3:]}`\n\n"
                                f"🔮 **BUY**     ;   **{res['raw_pred']}**\n\n"
                                f"💲 **BET**     ;   **{current_bet_multiplier} x**"
                            )
                            
                            for chat_id in list(active_chats):
                                try:
                                    await app.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
                                except Exception as err:
                                    print(f"Send Error ({chat_id}): {err}")
                            
                            last_processed_period = latest_period
        except Exception as e:
            print(f"Worker Exception: {e}")
            
        await asyncio.sleep(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    active_chats.add(chat_id)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in active_chats:
        active_chats.remove(chat_id)

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    
    async def post_init(application: Application):
        commands = [
            BotCommand("start", "Start predictor"),
            BotCommand("stop", "Stop predictor")
        ]
        await application.bot.set_my_commands(commands)
        asyncio.create_task(auto_prediction_worker(application))
        
    app.post_init = post_init
    print("🤖 VIP Bot Started...")
    app.run_polling()

if __name__ == "__main__":
    main()
  
