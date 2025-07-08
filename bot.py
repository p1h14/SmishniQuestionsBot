import os
import time
import random
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
URL = f"https://api.telegram.org/bot{TOKEN}/"

last_update_id = 0
active_users = {}
game_state = {}

# Завантаження питань
with open("questions.txt", "r", encoding="utf-8") as f:
    all_questions = [line.strip() for line in f if line.strip()]
used_questions = set()

def get_updates(offset=None):
    params = {"timeout": 100, "offset": offset}
    response = requests.get(URL + "getUpdates", params=params)
    return response.json()

def send_message(chat_id, text):
    requests.post(URL + "sendMessage", data={"chat_id": chat_id, "text": text})

def start_game(chat_id, user_id):
    # Вибір 5 унікальних питань
    global used_questions
    remaining = list(set(all_questions) - used_questions)
    if len(remaining) < 5:
        used_questions = set()  # якщо питання закінчились — обнуляємо
        remaining = all_questions[:]
    questions = random.sample(remaining, 5)
    used_questions.update(questions)

    game_state[user_id] = {
        "questions": questions,
        "answers": [],
        "current": 0
    }

    send_message(chat_id, "🎮 Гра почалась! Відповідай на питання 👇")
    send_message(chat_id, f"❓ {questions[0]}")

def handle_answer(chat_id, user_id, text):
    state = game_state[user_id]
    state["answers"].append(text)
    state["current"] += 1

    if state["current"] >= 5:
        send_message(chat_id, "✅ Дякую! Твої відповіді записані.\nОсь, що ти написав:")
        for i in range(5):
            q = state["questions"][i]
            a = state["answers"][i]
            send_message(chat_id, f"❓ {q}\n📝 {a}")
        del game_state[user_id]
    else:
        send_message(chat_id, f"❓ {state['questions'][state['current']]}")

def main():
    global last_update_id
    print("Бот запущено!")

    while True:
        updates = get_updates(last_update_id)
        if "result" in updates:
            for update in updates["result"]:
                last_update_id = update["update_id"] + 1

                if "message" not in update:
                    continue

                message = update["message"]
                chat_id = message["chat"]["id"]
                user_id = message["from"]["id"]
                text = message.get("text", "")

                if text == "/start":
                    send_message(chat_id, "Привіт! Напиши /game щоб почати гру 🎉")
                elif text == "/game":
                    if user_id not in game_state:
                        start_game(chat_id, user_id)
                    else:
                        send_message(chat_id, "⏳ Ти вже в грі. Відповідай на питання!")
                elif user_id in game_state:
                    handle_answer(chat_id, user_id, text)
                else:
                    send_message(chat_id, "Натисни /game, щоб почати гру 😎")

        time.sleep(1)

if __name__ == "__main__":
    main()
