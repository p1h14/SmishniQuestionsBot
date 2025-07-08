import os
import random
import logging
from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes
)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Game state
players = {}
answers = {}
votes = {}
questions = []
asked_questions = set()
current_questions = []
current_round = 0
group_chat_id = None
game_started = False
scoreboard = {}
round_timer_started = False

# Load questions from file
def load_questions():
    global questions
    with open("questions.txt", "r", encoding="utf-8") as f:
        questions = [line.strip() for line in f if line.strip()]

# Helper to choose unique questions
def get_unique_questions(n=5):
    global asked_questions
    remaining = list(set(questions) - asked_questions)
    if len(remaining) < n:
        asked_questions.clear()
        remaining = questions.copy()
    selected = random.sample(remaining, n)
    asked_questions.update(selected)
    return selected

# /startgame
async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global players, group_chat_id, game_started, round_timer_started
    if update.effective_chat.type != "group":
        await update.message.reply_text("Цю команду можна використовувати тільки в групі.")
        return

    group_chat_id = update.effective_chat.id
    players.clear()
    game_started = False
    round_timer_started = False

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Приєднатися", callback_data="join")]
    ])

    await context.bot.send_message(
        chat_id=group_chat_id,
        text="🎉 Починається нова гра! Натисни кнопку, щоб приєднатися:",
        reply_markup=keyboard
    )

# Кнопка приєднання
async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global players, round_timer_started
    query = update.callback_query
    user = query.from_user

    if user.id not in players:
        players[user.id] = {"name": user.first_name, "answers": [], "votes": 0}
        await query.answer("Ти приєднався до гри!")
    else:
        await query.answer("Ти вже в грі 😉")

    text = "✅ Гравці:\n" + "\n".join([f"• {p['name']}" for p in players.values()])
    await query.edit_message_text(text)

    # Запускаємо таймер гри якщо приєдналось 2 гравці
    if len(players) == 2 and not round_timer_started:
        round_timer_started = True
        await context.bot.send_message(chat_id=group_chat_id, text="⏳ Початок гри через 30 секунд...")
        await context.application.job_queue.run_once(start_round, 30)

# Початок раунду
async def start_round(context: ContextTypes.DEFAULT_TYPE):
    global current_questions, answers, votes, current_round, game_started
    game_started = True
    answers.clear()
    votes.clear()
    current_questions = get_unique_questions()
    current_round += 1

    await context.bot.send_message(chat_id=group_chat_id, text=f"🔔 Раунд {current_round} починається!")

    for q in current_questions:
        await context.bot.send_message(chat_id=group_chat_id, text=f"❓ {q}")
        for user_id in players.keys():
            try:
                await context.bot.send_message(chat_id=user_id, text=f"✍️ Напиши відповідь на:\n{q}")
            except:
                await context.bot.send_message(chat_id=group_chat_id, text=f"⚠️ Не можу надіслати повідомлення {players[user_id]['name']}. Перевірте, чи бот доданий у приват.")

    await context.application.job_queue.run_once(collect_answers, 40)

# Збір відповідей
async def collect_answers(context: ContextTypes.DEFAULT_TYPE):
    global current_questions
    await context.bot.send_message(chat_id=group_chat_id, text="📤 Відповіді на запитання:")

    for q in current_questions:
        anon_answers = []
        for uid, data in players.items():
            if data["answers"]:
                a = data["answers"].pop(0)
                anon_answers.append((uid, a))

        random.shuffle(anon_answers)

        keyboard = [
            [InlineKeyboardButton(f"{a[1][:30]}", callback_data=f"vote_{a[0]}")] for a in anon_answers
        ]

        await context.bot.send_message(
            chat_id=group_chat_id,
            text=f"❓ {q}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    await context.application.job_queue.run_once(end_round, 40)

# Голосування
async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global votes, scoreboard
    query = update.callback_query
    voter = query.from_user.id
    data = query.data

    voted_id = int(data.split("_")[1])
    if voter == voted_id:
        await query.answer("Не можна голосувати за себе!", show_alert=True)
        return

    if voter in votes:
        await query.answer("Ти вже проголосував!", show_alert=True)
        return

    votes[voter] = voted_id
    players[voted_id]["votes"] += 1
    await query.answer("Твій голос зараховано!")

# Завершення раунду
async def end_round(context: ContextTypes.DEFAULT_TYPE):
    text = "🏆 Результати раунду:\n"
    for uid, p in players.items():
        votes_received = p["votes"]
        scoreboard[uid] = scoreboard.get(uid, 0) + votes_received
        text += f"{p['name']}: +{votes_received} балів\n"
        p["votes"] = 0

    await context.bot.send_message(chat_id=group_chat_id, text=text)

    # Далі можна додати ще раунди або зупинити гру
    await context.bot.send_message(chat_id=group_chat_id, text="Хочете ще раунд? /startgame\nДля завершення /stopgame")

# Збір відповідей із приватних
async def handle_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in players:
        await update.message.reply_text("Ти не в грі.")
        return

    players[user_id]["answers"].append(update.message.text)
    await update.message.reply_text("✅ Відповідь збережено!")

# Стоп гра
async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_started, players
    if update.effective_chat.id != group_chat_id:
        return

    game_started = False
    players.clear()
    await context.bot.send_message(chat_id=group_chat_id, text="🛑 Гру завершено.")

# Статистика
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not scoreboard:
        await update.message.reply_text("Ще немає статистики.")
        return

    text = "📊 Статистика гравців:\n"
    sorted_scores = sorted(scoreboard.items(), key=lambda x: x[1], reverse=True)
    for uid, score in sorted_scores:
        name = players.get(uid, {}).get("name", "Гравець")
        text += f"{name}: {score} балів\n"

    await update.message.reply_text(text)

# Main
async def main():
    load_questions()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("stopgame", stop_game))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(join_game, pattern="^join$"))
    app.add_handler(CallbackQueryHandler(handle_vote, pattern="^vote_"))
    app.add_handler(MessageHandler(filters.PRIVATE & filters.TEXT, handle_private))

    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
