import os, random, logging, asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🧩 Стан гри
players = {}  # user_id -> {"name":..., "score":...}
group_id = None
all_questions = []
used = set()
current_round_q = []
current_answers = {}
vote_counts = {}
round_task = None
game_active = False

# ✅ Завантаження питань
def load_questions():
    global all_questions
    with open("questions.txt", encoding="utf-8") as f:
        all_questions = [q.strip() for q in f if q.strip()]
    logger.info(f"Loaded {len(all_questions)} questions")

def pick_questions(n=5):
    global used
    avail = [q for q in all_questions if q not in used]
    if len(avail) < n:
        used.clear()
        avail = all_questions.copy()
    chosen = random.sample(avail, n)
    used.update(chosen)
    return chosen

# --- Команди

async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Для початку гри напиши /game у групі.")

async def game_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global group_id, players, game_active, round_task
    if update.effective_chat.type not in ["group", "supergroup"]:
        return await update.message.reply_text("Ця команда працює лише в групі.")
    group_id = update.effective_chat.id
    players.clear()
    game_active = False
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🎮 Приєднатися", callback_data="join")]])
    await ctx.bot.send_message(chat_id=group_id, text="🎲 Гра стартує! Приєднуйтесь:", reply_markup=keyboard)

async def join_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global round_task, game_active
    q = update.callback_query
    uid, name = q.from_user.id, q.from_user.first_name
    if uid not in players:
        players[uid] = {"name": name, "score": 0}
        await q.answer("Ти в грі!")
    else:
        await q.answer("Вже в грі")
    text = "✅ Учасники:\n" + "\n".join(f"• {p['name']}" for p in players.values())
    await q.edit_message_text(text=text)
    if len(players) >= 2 and round_task is None:
        await ctx.bot.send_message(chat_id=group_id, text="⏳ Гра стартує через 30 секунд. Інші можуть приєднатися.")
        round_task = asyncio.create_task(start_round_after_delay(ctx))

async def start_round_after_delay(ctx: ContextTypes.DEFAULT_TYPE):
    await asyncio.sleep(30)
    await start_round(ctx)

async def start_round(ctx: ContextTypes.DEFAULT_TYPE):
    global current_round_q, current_answers, vote_counts, game_active, round_task
    round_task = None
    game_active = True
    current_round_q = pick_questions()
    current_answers = {q: [] for q in current_round_q}
    vote_counts = {}
    await ctx.bot.send_message(chat_id=group_id, text="🎯 Починаємо раунд!")
    for q_text in current_round_q:
        await ctx.bot.send_message(chat_id=group_id, text=f"❓ {q_text}")
        for uid in list(players):
            await ctx.bot.send_message(chat_id=uid, text=f"✍️ Твоя відповідь:\n{q_text}")
        await asyncio.sleep(20)
    await present_answers(ctx)

async def present_answers(ctx: ContextTypes.DEFAULT_TYPE):
    await ctx.bot.send_message(chat_id=group_id, text="📤 Анонімні відповіді—голосуйте:")
    for q_text in current_round_q:
        opts = current_answers[q_text]
        if not opts:
            await ctx.bot.send_message(chat_id=group_id, text=f"(Питання пропущене: {q_text})")
            continue
        vote_counts[q_text] = [0]*len(opts)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{i+1}. {opt}", callback_data=f"vote|{qid}|{idx}")]
                                   for idx,opt in enumerate(opts) for qid in [q_text]])
        await ctx.bot.send_message(chat_id=group_id, text=f"❓ {q_text}", reply_markup=kb)
    await asyncio.sleep(30)
    await tally_round(ctx)

async def vote_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not game_active:
        return
    q = update.callback_query
    _, q_text, idx = q.data.split("|")
    idx=int(idx)
    if q.from_user.id in q.message.entities: pass
    if q_text in vote_counts and 0<=idx<len(vote_counts[q_text]):
        vote_counts[q_text][idx]+=1
        await q.answer("✅ Твій голос зараховано!")

async def tally_round(ctx: ContextTypes.DEFAULT_TYPE):
    global game_active
    text="🏆 Результати раунду:\n"
    for q_text in current_round_q:
        opts = current_answers[q_text]
        votes_arr = vote_counts.get(q_text, [])
        if not opts: continue
        max_v = max(votes_arr)
        winner_idxs = [i for i,v in enumerate(votes_arr) if v==max_v]
        for i in winner_idxs:
            # Збираємо хто відповів цю опцію
            winner_name = players[list(players.keys())[i]]["name"]
            players[list(players.keys())[i]]["score"]+=1
            text+=f"• {winner_name}+{max_v} балів\n"
    await ctx.bot.send_message(chat_id=group_id, text=text)
    # Перевірка переможця
    for uid,data in players.items():
        if data["score"]>=5:
            await ctx.bot.send_message(chat_id=group_id, text=f"🎉 🎉 {data['name']} переміг з {data['score']} балами!")
            game_active=False
            return
    await ctx.bot.send_message(chat_id=group_id, text="Щоб продовжити гру введіть /game знову.")

async def stop_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global game_active, round_task
    game_active=False
    if round_task:
        round_task.cancel()
        round_task=None
    await update.message.reply_text("🛑 Гру зупинено.")

async def private_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not game_active: return
    uid, text = update.effective_user.id, update.message.text
    for q_text in current_round_q:
        if len(current_answers[q_text])<len(players):
            current_answers[q_text].append(text)
            await update.message.reply_text("✅ Відповідь збережена!")
            break

def main():
    load_questions()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("game", game_cmd))
    app.add_handler(CommandHandler("stopgame", stop_cmd))
    app.add_handler(CallbackQueryHandler(join_cb, pattern="^join$"))
    app.add_handler(CallbackQueryHandler(vote_cb, pattern="^vote"))
    app.add_handler(MessageHandler(filters.PRIVATE & filters.TEXT, private_answer))
    app.run_polling()

if __name__=="__main__":
    main()
