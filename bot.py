import logging
import random
import time
import threading
from dotenv import load_dotenv
import os

from telegram import (
    Bot,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ParseMode,
)
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    CallbackQueryHandler,
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

bot = Bot(token=TOKEN)
updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Змінні гри
players = {}
group_id = None
questions = []
answers = {}
current_question_index = 0
votes = {}
scores = {}

def load_questions():
    global questions
    with open("questions.txt", "r", encoding="utf-8") as f:
        questions = [line.strip() for line in f if line.strip()]

def start(update: Update, context: CallbackContext):
    global group_id
    group_id = update.effective_chat.id
    players.clear()
    scores.clear()

    keyboard = [[InlineKeyboardButton("🎮 Приєднатися", callback_data="join")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    context.bot.send_message(
        chat_id=group_id,
        text="🎉 <b>Гра \"Смішні Питання\" починається!</b>\nНатисни кнопку, щоб приєднатися!",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

def join(update: Update, context: CallbackContext):
    query = update.callback_query
    user = query.from_user

    if user.id not in players:
        players[user.id] = user.first_name
        query.answer("Ти приєднався до гри!")
    else:
        query.answer("Ти вже в грі 😉")

    player_list = "\n".join([f"• {name}" for name in players.values()])
    query.edit_message_text(
        text=f"✅ Учасники гри:\n{player_list}\n\nСкоро почнемо..."
    )

    # Якщо 2+ гравців, запускаємо гру
    if len(players) >= 2:
        threading.Timer(5, start_round, [context]).start()

def start_round(context: CallbackContext):
    global current_question_index, answers, votes
    answers.clear()
    votes.clear()
    current_question_index = 0

    context.bot.send_message(chat_id=group_id, text="🔔 Починаємо новий раунд!")

    for i in range(5):
        q = questions[current_question_index]
        context.bot.send_message(chat_id=group_id, text=f"❓ Питання {i+1}: {q}")
        for user_id in players.keys():
            context.bot.send_message(
                chat_id=user_id,
                text=f"✍️ Напиши відповідь на питання:\n\n{q}"
            )
        time.sleep(20)
        current_question_index += 1

    post_answers(context)

def post_answers(context: CallbackContext):
    context.bot.send_message(chat_id=group_id, text="📤 Відповіді:")
    question_number = 1
    for q in questions[:5]:
        context.bot.send_message(chat_id=group_id, text=f"❓ {q}")
        anon_answers = [f"📝 {a}" for a in answers.get(q, [])]
        context.bot.send_message(chat_id=group_id, text="\n".join(anon_answers))
        question_number += 1

    # Тут може бути логіка голосування
    # Або просте підрахування хто найкумедніше відповів (ручне або через /vote)

    context.bot.send_message(chat_id=group_id, text="✅ Гру завершено (демо версія).")

def handle_private_message(update: Update, context: CallbackContext):
    user = update.message.from_user
    text = update.message.text
    if current_question_index == 0:
        return

    question = questions[current_question_index - 1]
    if question not in answers:
        answers[question] = []

    if text:
        answers[question].append(text)
        context.bot.send_message(chat_id=user.id, text="✅ Відповідь прийнята!")

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CallbackQueryHandler(join))
dispatcher.add_handler(MessageHandler(Filters.private & Filters.text, handle_private_message))

if __name__ == "__main__":
    load_questions()
    updater.start_polling()
    updater.idle()
