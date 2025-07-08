import logging
import os
import random
import asyncio
from dotenv import load_dotenv
from collections import defaultdict

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Дані гри
players = {}
group_id = None
questions = []
answers = defaultdict(list)
votes = defaultdict(lambda: defaultdict(int))
scores = defaultdict(int)
current_question = None
game_running = False

def load_questions():
    global questions
    with open("questions.txt", "r", encoding="utf-8") as f:
        questions = [line.strip() for line in f if line.strip()]

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global group_id, players, scores, game_running
    if game_running:
        await update.message.reply_text("⛔ Гра вже триває.")
        return

    group_id = update.effective_chat.id
    players.clear()
    scores.clear()
    game_running = True

    keyboard = [[InlineKeyboardButton("🎮 Приєднатися", callback_data="join")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=group_id,
        text="🎉 <b>Гра \"Смішні Питання\" починається!</b>\nНатисни кнопку, щоб приєднатися!",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    if user.id not in players:
        players[user.id] = user.first_name
        await query.answer("Ти приєднався до гри!")
    else:
        await query.answer("Ти вже в грі 😉")

    player_list = "\n".join([f"• {name}" for name in players.values()])
    await query.edit_message_text(
        text=f"✅ Учасники гри:\n{player_list}\n\nСкоро почнемо..."
    )

    if len(players) >= 2:
        await asyncio.sleep(5)
        await start_round(context)

async def start_round(context: ContextTypes.DEFAULT_TYPE):
    global current_question, answers
    answers.clear()
    await context.bot.send_message(chat_id=group_id, text="🔔 Починаємо новий раунд!")

    for i in range(5):
        current_question = random.choice(questions)
        await context.bot.send_message(chat_id=group_id, text=f"❓ Питання {i+1}: {current_question}")
        for user_id in players.keys():
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✍️ Напиши відповідь на питання:\n\n{current_question}"
                )
            except Exception as e:
                logging.warning(f"Не вдалося надіслати повідомлення гравцю {user_id}: {e}")

        await asyncio.sleep(20)

    await post_answers(context)

async def post_answers(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=group_id, text="📤 Відповіді:")

    q = current_question
    anon_answers = answers.get(q, [])
    keyboard = []

    for i, ans in enumerate(anon_answers):
        keyboard.append([InlineKeyboardButton(f"Голос за {i+1}", callback_data=f"vote_{i}")])

    text = f"❓ {q}\n\n" + "\n".join([f"{i+1}. {a}" for i, a in enumerate(anon_answers)])
    await context.bot.send_message(chat_id=group_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))

    await asyncio.sleep(20)
    await show_results(context)

async def show_results(context: ContextTypes.DEFAULT_TYPE):
    global scores

    vote_counts = {i: 0 for i in range(len(answers[current_question]))}
    for voter in votes[current_question]:
        idx = votes[current_question][voter]
        vote_counts[idx] += 1

    msg = "🏆 Результати голосування:\n"
    for i, count in vote_counts.items():
        msg += f"Варіант {i+1}: {count} голос(ів)\n"
        scores[i] += count

    await context.bot.send_message(chat_id=group_id, text=msg)
    await context.bot.send_message(chat_id=group_id, text="Гру завершено. Можна писати /stats або /stopgame.")

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not game_running or current_question is None:
        return

    answers[current_question].append(update.message.text)
    await update.message.reply_text("✅ Відповідь прийнята!")

async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    if not data.startswith("vote_"):
        return

    index = int(data.split("_")[1])
    votes[current_question][user.id] = index
    await query.answer("Голос прийнято!")

async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_running
    game_running = False
    await update.message.reply_text("🛑 Гру зупинено.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not scores:
        await update.message.reply_text("Статистики ще немає.")
        return

    msg = "📊 Поточна статистика:\n"
    for i, score in scores.items():
        msg += f"Варіант {i+1}: {score} балів\n"

    await update.message.reply_text(msg)

def main():
    load_questions()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stopgame", stop_game))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(join, pattern="^join$"))
    app.add_handler(CallbackQueryHandler(handle_vote, pattern="^vote_"))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT, handle_answer))

    app.run_polling()

if __name__ == "__main__":
    main()
