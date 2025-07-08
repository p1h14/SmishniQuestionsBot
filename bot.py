import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
URL = f"https://api.telegram.org/bot{TOKEN}/"

last_update_id = 0

def get_updates(offset=None):
    params = {"timeout": 100, "offset": offset}
    response = requests.get(URL + "getUpdates", params=params)
    return response.json()

def send_message(chat_id, text):
    params = {"chat_id": chat_id, "text": text}
    requests.post(URL + "sendMessage", params=params)

def main():
    global last_update_id
    print("Бот запущено...")

    while True:
        updates = get_updates(last_update_id)
        if "result" in updates:
            for update in updates["result"]:
                if "message" in update:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"].get("text", "")
                    
                    if text == "/start":
                        send_message(chat_id, "Привіт! Я простий бот без бібліотек 🤖")
                    else:
                        send_message(chat_id, f"Ти написав: {text}")
                
                last_update_id = update["update_id"] + 1

        time.sleep(1)

if __name__ == "__main__":
    main()
