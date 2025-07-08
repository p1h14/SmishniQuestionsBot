import os
import random
import asyncio
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Дані гри
group_id = None
players = {}
scores = {}
questions = []
used_questions = set()
current_round_questions = []
current_answers = {}
vote_stage = False
votes = {}
game_running = False
start_timer = None

# Завантажити питання з файлу
def load_questions():
    global questions
    with open("questions.txt", "r", encoding="utf-8") as f:
        questions = [line.strip() for line in f if line.strip()]

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global group_id, players, game_running, start_timer
    if game_running:
        await update.message.reply_text("⚠️ Гра вже йде!")
        return

    players.clear()
    scores.clear()
    group_id = update.effective_chat.id
    game_running = True

    keyboard = [[InlineKeyboardButton("🎮 Приєднатись", callback_data="join")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=group_id,
        text="🎉 <b>Гра почалась!</b> Натисни, щоб приєднатися!",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

# Обробка натискання "Приєднатись"
async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global start_timer
    query = update.callback_query
    user = query.from_user

    if user.id not in players:
        players[user.id] = user.first_name
        scores[user.id] = 0
        await query.answer("🎉 Ти приєднався!")
    else:
        await query.answer("✅ Ти вже в грі!")

    player_list = "\n".join([f"• {name}" for name in players.values()])
    await query.edit_message_text(f"✅ Гравці:\n{player_list}\n\nОчікуємо ще...")

    if len(players) == 2 and not start_timer:
        start_timer = asyncio.create_task(start_game_in_30_sec(context))

# Запуск гри через 30 секунд
async def start_game_in_30_sec(context):
    await asyncio.sleep(30)
    await start_round(context)

# Запуск раунду
async def start_round(context):
    global current_round_questions, current_answers, vote_stage
    current_answers.clear()
    vote_stage = False
    current_round_questions = get_random_questions(5)

    await context.bot.send_message(chat_id=group_id, text="🚨 Розпочинаємо раунд!")
    for i, q in enumerate(current_round_questions):
        await context.bot.send_message(chat_id=group_id, text=f"❓ Питання {i+1}: {q}")
        for player_id in players:
            await context.bot.send_message(chat_id=player_id, text=f"✍️ Відповідь на питання:\n{q}")
        await asyncio.sleep(20)

    await post_answers(context)

# Показати відповіді та запустити голосування
async def post_answers(context):
    global vote_stage, votes
    vote_stage = True
    votes.clear()

    await context.bot.send_message(chat_id=group_id, text="🗳 Голосування почалось!")
    for q in current_round_questions:
        q_answers = current_answers.get(q, [])
        buttons = []
        for i, ans in enumerate(q_answers):
            buttons.append([InlineKeyboardButton(ans, callback_data=f"vote_{q}_{i}")])
        if buttons:
            await context.bot.send_message(
                chat_id=group_id,
                text=f"❓ {q}",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    await asyncio.sleep(30)
    await end_round(context)

# Завершити раунд
async def end_round(context):
    global vote_stage, used_questions
    vote_stage = False
    used_questions.update(current_round_questions)
    await context.bot.send_message(chat_id=group_id, text="🏁 Раунд завершено!")

    score_table = "\n".join([f"{players[p]}: {scores[p]} балів" for p in players])
    await context.bot.send_message(chat_id=group_id, text=f"📊 Статистика:\n{score_table}")

# Отримати випадкові питання без повторів
used_all_once = False

def get_random_questions(n):
    global used_questions, used_all_once
    pool = [q for q in questions if q not in used_questions]
    if len(pool) < n:
        used_questions.clear()
        used_all_once = True
        pool = questions[:]
    return random.sample(pool, n)

# Обробка повідомлень у приват
async def handle_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not game_running or vote_stage:
        return
    user = update.message.from_user
    text = update.message.text
    if user.id not in players:
        return
    last_q = current_round_questions[len(current_answers)]
    if last_q not in current_answers:
        current_answers[last_q] = []
    current_answers[last_q].append(text)
    await update.message.reply_text("✅ Відповідь прийнята!")

# Обробка голосування
async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not vote_stage:
        return
    query = update.callback_query
    voter = query.from_user.id
    data = query.data.split("_")
    if len(data) < 3:
        return
    _, question, index = data
    try:
        answer = current_answers[question][int(index)]
        for pid in players:
            if pid != voter:
                scores[pid] += 1
        await query.answer("🗳 Голос зараховано!")
        await query.edit_message_reply_markup(None)
    except:
        await query.answer("⚠️ Помилка голосування")

# Зупинка гри
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_running
    game_running = False
    await update.message.reply_text("⛔️ Гру зупинено.")

# Старт бота
if __name__ == '__main__':
    load_questions()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stopgame", stop))
    app.add_handler(CallbackQueryHandler(join, pattern="^join$"))
    app.add_handler(CallbackQueryHandler(vote, pattern="^vote_"))
    app.add_handler(MessageHandler(filters.PRIVATE & filters.TEXT, handle_private))

    print("✅ Бот запущено...")
    app.run_polling()
