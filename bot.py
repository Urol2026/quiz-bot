#!/usr/bin/env python3
"""
Telegram Quiz Bot — 521 ta savol
pip install python-telegram-bot==20.7
"""

import json
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

# ── SOZLAMALAR ─────────────────────────────────────────────────────────────────
BOT_TOKEN = "8863972910:AAHA4faZMEJXdRo34q1rJezjgY1xbZVwgTE"   # <-- o'z tokeningizni kiriting
QUESTIONS_FILE = "questions.json"
QUIZ_LENGTH = 10   # Har bir sessiyada nechta savol
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Savollarni yuklash
with open(QUESTIONS_FILE, encoding="utf-8") as f:
    ALL_QUESTIONS = json.load(f)

# Foydalanuvchi ma'lumotlari (xotira)
user_data = {}  # {user_id: {questions, current, score, answers}}

# ── LEADERBOARD ────────────────────────────────────────────────────────────────
leaderboard = {}  # {user_id: {name, best_score, games}}

def save_score(user_id, name, score, total):
    if user_id not in leaderboard:
        leaderboard[user_id] = {"name": name, "best_score": 0, "games": 0, "total_score": 0}
    leaderboard[user_id]["games"] += 1
    leaderboard[user_id]["total_score"] += score
    leaderboard[user_id]["name"] = name
    if score > leaderboard[user_id]["best_score"]:
        leaderboard[user_id]["best_score"] = score

def get_top10():
    if not leaderboard:
        return "Hali hech kim o'ynamagan!"
    sorted_lb = sorted(leaderboard.items(), key=lambda x: x[1]["best_score"], reverse=True)[:10]
    text = "🏆 *TOP 10 LIDERLAR*\n\n"
    medals = ["🥇", "🥈", "🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    for i, (uid, data) in enumerate(sorted_lb):
        avg = data["total_score"] / data["games"] if data["games"] else 0
        text += (f"{medals[i]} *{data['name']}*\n"
                 f"   🎯 Eng yaxshi: {data['best_score']}/{QUIZ_LENGTH} | "
                 f"O'yinlar: {data['games']} | O'rtacha: {avg:.1f}\n\n")
    return text

# ── START ──────────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 Salom, *{user.first_name}*!\n\n"
        f"📚 Bu bot *Lexicology* fanidan *521 ta savol* bilan quiz o'ynashga imkon beradi.\n\n"
        f"🎯 Har o'yinda *{QUIZ_LENGTH} ta* tasodifiy savol beriladi.\n"
        f"✅ To'g'ri javob — 1 ball\n"
        f"❌ Noto'g'ri javob — tushuntirish ko'rsatiladi\n\n"
        f"Boshlaylik! 👇"
    )
    keyboard = [
        [InlineKeyboardButton("▶️ O'yinni boshlash", callback_data="start_quiz")],
        [InlineKeyboardButton("🏆 Liderlar jadvali", callback_data="leaderboard")],
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
    ]
    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ── MENU CALLBACK ──────────────────────────────────────────────────────────────
async def menu_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if query.data == "start_quiz":
        await begin_quiz(query, uid)

    elif query.data == "leaderboard":
        text = get_top10()
        keyboard = [[InlineKeyboardButton("🔙 Ortga", callback_data="main_menu")]]
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "stats":
        if uid in leaderboard:
            d = leaderboard[uid]
            avg = d["total_score"] / d["games"] if d["games"] else 0
            text = (f"📊 *Sizning statistikangiz*\n\n"
                    f"🎮 O'yinlar: {d['games']}\n"
                    f"🏆 Eng yaxshi natija: {d['best_score']}/{QUIZ_LENGTH}\n"
                    f"📈 O'rtacha ball: {avg:.1f}\n"
                    f"🎯 Jami to'g'ri: {d['total_score']}")
        else:
            text = "📊 Siz hali o'ynamagansiz! Boshlang! 🎮"
        keyboard = [[InlineKeyboardButton("▶️ O'ynash", callback_data="start_quiz")],
                    [InlineKeyboardButton("🔙 Ortga", callback_data="main_menu")]]
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "main_menu":
        user = query.from_user
        text = (f"📚 *Lexicology Quiz*\n\n"
                f"Salom, *{user.first_name}*! Nimani tanlaysiz?")
        keyboard = [
            [InlineKeyboardButton("▶️ O'yinni boshlash", callback_data="start_quiz")],
            [InlineKeyboardButton("🏆 Liderlar jadvali", callback_data="leaderboard")],
            [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
        ]
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup(keyboard))

# ── QUIZ BOSHLASH ──────────────────────────────────────────────────────────────
async def begin_quiz(query, uid):
    selected = random.sample(ALL_QUESTIONS, QUIZ_LENGTH)
    user_data[uid] = {
        "questions": selected,
        "current": 0,
        "score": 0,
    }
    await send_question(query, uid)

async def send_question(query, uid):
    data = user_data[uid]
    idx = data["current"]
    q = data["questions"][idx]

    options = q["options"][:]
    random.shuffle(options)

    progress = f"❓ Savol {idx+1}/{QUIZ_LENGTH}"
    score_text = f"✅ Ball: {data['score']}"
    question_text = f"\n\n*{q['q']}*"

    keyboard = []
    for i, opt in enumerate(options):
        # Encode: answer_INDEX_CORRECT_SHUFFLED_OPT
        cb = f"ans|{idx}|{opt}"
        keyboard.append([InlineKeyboardButton(f"{chr(65+i)}) {opt}", callback_data=cb)])

    text = f"{progress}  {score_text}{question_text}"
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ── JAVOB CALLBACK ─────────────────────────────────────────────────────────────
async def answer_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if uid not in user_data:
        await query.edit_message_text("❌ O'yin topilmadi. /start bosing.")
        return

    parts = query.data.split("|", 2)
    if len(parts) != 3:
        return
    _, idx_str, chosen = parts
    idx = int(idx_str)

    data = user_data[uid]
    if idx != data["current"]:
        return  # old button

    q = data["questions"][idx]
    correct = q["correct"]
    is_correct = chosen.strip() == correct.strip()

    if is_correct:
        data["score"] += 1
        feedback = f"✅ *To'g'ri!*\n\n_{correct}_"
    else:
        feedback = (f"❌ *Noto'g'ri!*\n\n"
                    f"Sizning javobingiz: _{chosen}_\n"
                    f"To'g'ri javob: ✅ _{correct}_")

    data["current"] += 1

    # Keyingi tugma
    if data["current"] < QUIZ_LENGTH:
        keyboard = [[InlineKeyboardButton("➡️ Keyingi savol", callback_data=f"next|{data['current']}")]]
        text = (f"❓ Savol {idx+1}/{QUIZ_LENGTH}  ✅ Ball: {data['score']}\n\n"
                f"{feedback}")
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        # O'yin tugadi
        await finish_quiz(query, uid)

# ── KEYINGI SAVOL ──────────────────────────────────────────────────────────────
async def next_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if uid not in user_data:
        await query.edit_message_text("❌ /start bosing.")
        return

    parts = query.data.split("|")
    expected_idx = int(parts[1])
    if expected_idx != user_data[uid]["current"]:
        return

    await send_question(query, uid)

# ── O'YIN TUGADI ───────────────────────────────────────────────────────────────
async def finish_quiz(query, uid):
    data = user_data[uid]
    score = data["score"]
    total = QUIZ_LENGTH

    # Baho
    pct = score / total * 100
    if pct == 100:
        grade = "🏆 Mukammal! Ajoyib!"
    elif pct >= 80:
        grade = "🌟 A'lo natija!"
    elif pct >= 60:
        grade = "👍 Yaxshi!"
    elif pct >= 40:
        grade = "📚 Qoniqarli. Ko'proq o'qing!"
    else:
        grade = "😅 Qiyin bo'ldi. Yana bir urinib ko'ring!"

    name = query.from_user.full_name
    save_score(uid, name, score, total)

    text = (
        f"🎉 *O'yin tugadi!*\n\n"
        f"👤 {name}\n"
        f"🎯 Natija: *{score}/{total}* ({pct:.0f}%)\n"
        f"{grade}\n\n"
        f"🏆 Eng yaxshi natijangiz: {leaderboard[uid]['best_score']}/{total}"
    )
    keyboard = [
        [InlineKeyboardButton("🔄 Yana o'ynash", callback_data="start_quiz")],
        [InlineKeyboardButton("🏆 Liderlar jadvali", callback_data="leaderboard")],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")],
    ]
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(keyboard))
    del user_data[uid]

# ── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_callback,
        pattern="^(start_quiz|leaderboard|stats|main_menu)$"))
    app.add_handler(CallbackQueryHandler(answer_callback, pattern=r"^ans\|"))
    app.add_handler(CallbackQueryHandler(next_callback, pattern=r"^next\|"))

    logger.info("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
