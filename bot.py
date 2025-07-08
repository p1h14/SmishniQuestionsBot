import logging
import os
import random
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

players = {}
group_id = None
all_questions = []
used_questions = set()
current_round_questions = []
current_answers = {}
votes = {}
scores = {}
game_started = False
start_timer_task = None

# Завантажити всі питання
def load_questions():
    global all_questions
    with open("questions.txt", encoding="utf-8") as f:
        all_questions = [q.strip() for q in f if q.strip()]
    logging.info(f"Завантажено {len(all_questions)} питань.")

def get_random_questions(n=5):
    global used_questions
    available = list(set(all_questions) - used_questions)
    if len(available) < n:
        used_questions.clear()
        available = all_questions.copy()
    selected = random.sample(available, n)
    used_questions.update(selected)
    return selected

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global players, group_id, game_started, start_timer_task
    if update.effective_chat.type != "group" and update.effective_chat.type != "supergroup":
        await update.message.reply_text("Ця команда працює тільки в групі.")
        return

    group_id = update.effective_chat.id
    players = {}
    scores.clear()
    game_started = False
    keyboard = [[InlineKeyboardButton("🎮 Приєднатися", callback_data="join")]]
    await update.message.reply_text(
        "🎉 Гра починається! Натисни кнопку, щоб приєднатися!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global players, game_started, start_timer_task

    query = update.callback_query
    user = query.from_user

    if game_started:
        await query.answer("Гра вже почалася!")
        return

    players[user.id] = user.first_name
    await query.answer("Ти в грі!")

    await update.effective_message.edit_text(
        "✅ Учасники:\n" + "\n".join(f"• {name}" for name in players.values())
    )

    if len(players) == 2 and not start_timer_task:
        start_timer_task = asyncio.create_task(start_game_after_delay(context))

async def start_game_after_delay(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=group_id, text="⏳ Гра почнеться через 30 секунд! Усі бажаючі можуть приєднатись.")
    await asyncio.sleep(30)
    await start_round(context)

async def start_round(context: ContextTypes.DEFAULT_TYPE):
    global current_round_questions, current_answers, votes, game_started
    current_round_questions = get_random_questions(5)
    current_answers = {q: [] for q in current_round_questions}
    votes.clear()
    game_started = True

    await context.bot.send_message(chat_id=group_id, text="🎮 Починаємо раунд!")

    for i, question in enumerate(current_round_questions):
        await context.bot.send_message(chat_id=group_id, text=f"❓ Питання {i+1}: {question}")
        for user_id in players:
            try:
                await context.bot.send_message(chat_id=user_id, text=f"✍️ Напиши відповідь на питання:\n{question}")
            except:
                pass
        await asyncio.sleep(20)

    await show_answers(context)

async def show_answers(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=group_id, text="📝 Відповіді:")

    for q in current_round_questions:
        await context.bot.send_message(chat_id=group_id, text=f"❓ {q}")
        options = current_answers[q]
        if not options:
            await context.bot.send_message(chat_id=group_id, text="(немає відповідей)")
            continue
        buttons = [
            [InlineKeyboardButton(f"{i+1}. {a}", callback_data=f"vote|{q}|{i}")]
            for i, a in enumerate(options)
        ]
        votes[q] = [0] * len(options)
        await context.bot.send_message(
            chat_id=group_id,
            text="Проголосуй за найкращу відповідь:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    await asyncio.sleep(30)
    await finish_round(context)

async def vote_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("|")
    if len(data) != 3: return

    _, question, index = data
    index = int(index)
    if question in votes and index < len(votes[question]):
        votes[question][index] += 1
        await query.answer("Твій голос прийнято!")

async def finish_round(context: ContextTypes.DEFAULT_TYPE):
    global scores
    await context.bot.send_message(chat_id=group_id, text="📊 Результати:")

    for q in current_round_questions:
        answers = current_answers[q]
        q_votes = votes.get(q, [])
        if not answers:
            continue
        max_votes = max(q_votes)
        winners = [i for i, v in enumerate(q_votes) if v == max_votes]
        for i in winners:
            text = answers[i]
            for user_id in players:
                if text in current_answers[q]:
                    scores[user_id] = scores.get(user_id, 0) + 1

    results = "\n".join(f"{players.get(uid, '??')}: {pts} балів" for uid, pts in scores.items())
    await context.bot.send_message(chat_id=group_id, text="🏆 Поточна статистика:\n" + results)

async def handle_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text
    for q in current_round_questions:
        if len(current_answers[q]) < len(players):
            current_answers[q].append(text)
            await update.message.reply_text("✅ Відповідь прийнята!")
            break

def main():
    load_questions()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(join, pattern="^join$"))
    app.add_handler(CallbackQueryHandler(vote_handler, pattern="^vote"))
    app.add_handler(MessageHandler(filters.PRIVATE & filters.TEXT, handle_private))

    app.run_polling()

if __name__ == "__main__":
    main()
