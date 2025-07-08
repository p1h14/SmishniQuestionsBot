import logging
import os
import random
import asyncio

from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 8443))
APP_URL = os.environ.get("APP_URL")

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

players = {}
group_id = None
questions = []
answers = {}
current_question_index = 0
scores = {}
voting_message_ids = []
vote_mapping = {}  # vote_id -> user_id (автор відповіді)
voted_users = set()

def load_questions():
    global questions
    with open("questions.txt", "r", encoding="utf-8") as f:
        questions = [line.strip() for line in f if line.strip()]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global group_id, players, scores, voted_users
    group_id = update.effective_chat.id
    players.clear()
    scores.clear()
    voted_users.clear()

    keyboard = [[InlineKeyboardButton("🎮 Приєднатися", callback_data="join")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=group_id,
        text="🎉 <b>Гра \"Смішні Питання\" починається!</b>\nНатисни кнопку, щоб приєднатися!",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not players:
        await update.message.reply_text("Немає активної гри.")
        return

    result = "<b>🏆 Фінальні результати:</b>\n"
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    for uid, score in sorted_scores:
        name = players.get(uid, "???")
        result += f"{name}: {score} балів\n"

    await context.bot.send_message(chat_id=group_id, text=result, parse_mode=ParseMode.HTML)

    players.clear()
    scores.clear()
    answers.clear()
    voted_users.clear()

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global players
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
    global current_question_index, answers
    answers.clear()
    current_question_index = 0

    await context.bot.send_message(chat_id=group_id, text="🔔 Починаємо новий раунд!")

    for i in range(5):
        question = questions[current_question_index]
        await context.bot.send_message(chat_id=group_id, text=f"❓ Питання {i+1}: {question}")

        for user_id in players.keys():
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✍️ Напиши відповідь на питання:\n\n{question}"
            )

        await asyncio.sleep(20)
        current_question_index += 1

    await post_answers(context)

async def post_answers(context: ContextTypes.DEFAULT_TYPE):
    global vote_mapping, voted_users
    vote_mapping.clear()
    voted_users.clear()

    await context.bot.send_message(chat_id=group_id, text="📤 Відповіді:")

    for i, question in enumerate(questions[:5]):
        await context.bot.send_message(chat_id=group_id, text=f"❓ {question}")
        q_answers = answers.get(question, [])
        if not q_answers:
            await context.bot.send_message(chat_id=group_id, text="(Немає відповідей)")
            continue

        buttons = []
        for idx, ans in enumerate(q_answers):
            vote_id = f"{question[:10]}-{idx}-{random.randint(1000,9999)}"
            vote_mapping[vote_id] = get_author_by_answer(question, ans)
            buttons.append([InlineKeyboardButton(f"🗳 Голосувати за #{idx+1}", callback_data=f"vote_{vote_id}")])
            await context.bot.send_message(chat_id=group_id, text=f"#{idx+1}: {ans}")

        markup = InlineKeyboardMarkup(buttons)
        await context.bot.send_message(chat_id=group_id, text="🗳 Голосування:", reply_markup=markup)

    await context.bot.send_message(chat_id=group_id, text="🏁 Голосування завершиться через 30 секунд...")
    await asyncio.sleep(30)
    await context.bot.send_message(chat_id=group_id, text="🛑 Голосування завершено.")
    await show_scores(context)

def get_author_by_answer(question, answer):
    for uid, name in players.items():
        if question in answers:
            if answer in answers[question]:
                return uid
    return None

async def vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if user_id in voted_users:
        await query.answer("Ти вже голосував 🛑", show_alert=True)
        return

    vote_id = query.data.replace("vote_", "")
    voted_users.add(user_id)

    voted_uid = vote_mapping.get(vote_id)
    if voted_uid:
        scores[voted_uid] = scores.get(voted_uid, 0) + 1

    await query.answer("Голос прийнято ✅", show_alert=True)

async def show_scores(context: ContextTypes.DEFAULT_TYPE):
    if not scores:
        await context.bot.send_message(chat_id=group_id, text="Ніхто не проголосував 😢")
        return

    result = "<b>📊 Поточні бали:</b>\n"
    for uid, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        result += f"{players.get(uid, '???')}: {score} балів\n"

    await context.bot.send_message(chat_id=group_id, text=result, parse_mode=ParseMode.HTML)

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text

    if current_question_index == 0:
        return

    question = questions[current_question_index - 1]
    if question not in answers:
        answers[question] = []

    answers[question].append(text)
    await context.bot.send_message(chat_id=user.id, text="✅ Відповідь прийнята!")

# === main ===

async def main():
    load_questions()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stopgame", stop_game))
    app.add_handler(CallbackQueryHandler(vote_callback, pattern="^vote_"))
    app.add_handler(CallbackQueryHandler(join))
    app.add_handler(MessageHandler(filters.PRIVATE & filters.TEXT, handle_private_message))

    await app.start()
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{APP_URL}/{TOKEN}",
    )
    await app.updater.idle()

if __name__ == "__main__":
    asyncio.run(main())
