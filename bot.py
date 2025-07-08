import os
import random
import logging
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

players = {}
group_id = None
questions = []
answers = {}
used_questions = set()
scores = {}
game_started = False
game_timer = None

# Завантаження питань
def load_questions():
    global questions
    with open("questions.txt", "r", encoding="utf-8") as f:
        questions = [line.strip() for line in f if line.strip()]

# Старт гри
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global group_id, players, scores, game_started, game_timer

    if game_started:
        await update.message.reply_text("Гра вже запущена.")
        return

    players.clear()
    scores.clear()
    group_id = update.effective_chat.id
    game_started = True

    keyboard = [[InlineKeyboardButton("🎮 Приєднатися", callback_data="join")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=group_id,
        text="🎉 Гра починається! Натисни, щоб приєднатися.",
        reply_markup=reply_markup
    )

    # Чекаємо 30 секунд для приєднання гравців
    await asyncio.sleep(30)

    if len(players) >= 2:
        await start_round(context)
    else:
        await context.bot.send_message(chat_id=group_id, text="Недостатньо гравців 😢")
        game_started = False

# Приєднання гравця
async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global players

    query = update.callback_query
    user = query.from_user

    if user.id not in players:
        players[user.id] = user.first_name
        await query.answer("Ти приєднався!")
    else:
        await query.answer("Ти вже в грі 😉")

    player_list = "\n".join([f"• {name}" for name in players.values()])
    await query.edit_message_text(
        text=f"✅ Учасники гри:\n{player_list}\n(Старт за 30 сек...)"
    )

# Початок раунду
async def start_round(context: ContextTypes.DEFAULT_TYPE):
    global used_questions, questions, group_id, answers

    selected = []
    answers.clear()

    while len(selected) < 5:
        q = random.choice(questions)
        if q not in used_questions:
            selected.append(q)
            used_questions.add(q)
        if len(used_questions) == len(questions):
            used_questions.clear()

    for i, q in enumerate(selected):
        await context.bot.send_message(chat_id=group_id, text=f"❓ Питання {i+1}: {q}")
        for user_id in players:
            await context.bot.send_message(chat_id=user_id, text=f"Питання:\n{q}")
        await asyncio.sleep(20)

    await context.bot.send_message(chat_id=group_id, text="📝 Завершено! Перегляд відповідей пізніше.")

# Обробка приватних повідомлень
async def handle_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text
    if not text:
        return

    question = "остання"  # Тут можна зберігати питання → відповідь
    if question not in answers:
        answers[question] = []
    answers[question].append(f"{user.first_name}: {text}")
    await context.bot.send_message(chat_id=user.id, text="✅ Відповідь збережена!")

# Запуск бота
async def main():
    load_questions()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(join))
    app.add_handler(MessageHandler(filters.PRIVATE & filters.TEXT, handle_private))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
