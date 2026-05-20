#!/usr/bin/env python3
import json, random, logging, os, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
QUIZ_LENGTH = 20
TIME_LIMIT = 15

with open("questions.json", encoding="utf-8") as f:
    ALL_QUESTIONS = json.load(f)

user_sessions = {}
leaderboard = {}
timer_tasks = {}

# ── YORDAMCHI: Markdown maxsus belgilarni tozalash ────────────────────────────
def safe(text):
    """Markdown belgilarini escaped qiladi"""
    if not text:
        return ""
    for ch in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(ch, '\\' + ch)
    return text

# ── LEADERBOARD ────────────────────────────────────────────────────────────────
def save_score(uid, name, score):
    if uid not in leaderboard:
        leaderboard[uid] = {"name": name, "best": 0, "games": 0, "total": 0}
    leaderboard[uid]["games"] += 1
    leaderboard[uid]["total"] += score
    leaderboard[uid]["name"] = name
    if score > leaderboard[uid]["best"]:
        leaderboard[uid]["best"] = score

def top10_text():
    if not leaderboard:
        return "🏆 TOP 10 LIDERLAR\n\nHali hech kim o'ynamagan!"
    items = sorted(leaderboard.items(), key=lambda x: x[1]["best"], reverse=True)[:10]
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = ["🏆 TOP 10 LIDERLAR\n"]
    for i, (_, d) in enumerate(items):
        avg = d["total"] / d["games"] if d["games"] else 0
        lines.append(
            f"{medals[i]} {d['name']}\n"
            f"   🎯 Eng yaxshi: {d['best']}/{QUIZ_LENGTH} | "
            f"O'yinlar: {d['games']} | O'rtacha: {avg:.1f}\n"
        )
    return "\n".join(lines)

def get_grade(pct):
    if pct == 100:  return "🏆 Mukammal! Barcha savollar to'g'ri!"
    if pct >= 85:   return "🌟 A'lo natija!"
    if pct >= 70:   return "👍 Yaxshi!"
    if pct >= 50:   return "📚 Qoniqarli. Ko'proq o'qing!"
    return "😅 Qiyin bo'ldi. Yana urinib ko'ring!"

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ O'yinni boshlash", callback_data="start_quiz")],
        [InlineKeyboardButton("🏆 Liderlar jadvali", callback_data="leaderboard")],
        [InlineKeyboardButton("📊 Statistika",        callback_data="stats")],
    ])

# ── TAYMER BEKOR QILISH ────────────────────────────────────────────────────────
def cancel_timer(uid):
    if uid in timer_tasks:
        try:
            timer_tasks[uid].cancel()
        except Exception:
            pass
        del timer_tasks[uid]

# ── SAVOL KO'RSATISH ───────────────────────────────────────────────────────────
async def show_question(q, uid):
    session = user_sessions[uid]
    idx = session["current"]
    qobj = session["questions"][idx]

    options = qobj["options"][:]
    random.shuffle(options)

    keyboard = [
        [InlineKeyboardButton(f"{chr(65+i)}) {opt}", callback_data=f"ans|{idx}|{opt}")]
        for i, opt in enumerate(options)
    ]

    # Savol matnini oddiy (Markdown'siz) ko'rsatamiz — xavfsiz
    text = (
        f"⏱ {TIME_LIMIT} sek  |  "
        f"Savol {idx+1}/{QUIZ_LENGTH}  |  "
        f"Ball: {session['score']}\n\n"
        f"❓ {qobj['q']}"
    )

    try:
        msg = await q.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        session["message_id"] = msg.message_id
        session["chat_id"] = msg.chat.id
    except Exception as e:
        logger.warning(f"show_question edit error: {e}")
        return

    # Taymerni qayta boshlash
    cancel_timer(uid)
    app = session.get("app")
    if app:
        task = asyncio.create_task(time_is_up(uid, idx, app.bot))
        timer_tasks[uid] = task

# ── TAYMER TUGADI ──────────────────────────────────────────────────────────────
async def time_is_up(uid, idx, bot):
    await asyncio.sleep(TIME_LIMIT)

    if uid not in user_sessions:
        return
    session = user_sessions[uid]
    if session["current"] != idx:
        return

    qobj = session["questions"][idx]
    correct = qobj["correct"]
    session["current"] += 1

    feedback = f"⏰ Vaqt tugadi!\n\nTo'g'ri javob: ✅ {correct}"

    if session["current"] < QUIZ_LENGTH:
        try:
            await bot.edit_message_text(
                chat_id=session["chat_id"],
                message_id=session["message_id"],
                text=f"Savol {idx+1}/{QUIZ_LENGTH}  |  Ball: {session['score']}\n\n{feedback}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("➡️ Keyingi savol", callback_data=f"next|{session['current']}")
                ]])
            )
        except Exception as e:
            logger.warning(f"time_is_up edit error: {e}")
    else:
        await finish_auto(uid, bot, session)

async def finish_auto(uid, bot, session):
    score = session["score"]
    pct = score / QUIZ_LENGTH * 100
    grade = get_grade(pct)
    name = session.get("name", "Foydalanuvchi")
    save_score(uid, name, score)
    if uid in user_sessions:
        del user_sessions[uid]
    try:
        await bot.edit_message_text(
            chat_id=session["chat_id"],
            message_id=session["message_id"],
            text=(
                f"🎉 O'yin tugadi!\n\n"
                f"👤 {name}\n"
                f"🎯 Natija: {score}/{QUIZ_LENGTH} ({pct:.0f}%)\n"
                f"{grade}\n\n"
                f"🏆 Eng yaxshi natijangiz: {leaderboard[uid]['best']}/{QUIZ_LENGTH}"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Yana o'ynash", callback_data="start_quiz")],
                [InlineKeyboardButton("🏆 Liderlar",     callback_data="leaderboard")],
                [InlineKeyboardButton("🏠 Menyu",        callback_data="menu")],
            ])
        )
    except Exception as e:
        logger.warning(f"finish_auto error: {e}")

# ── /start ─────────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"👋 Salom, {name}!\n\n"
        f"📚 Lexicology Quiz\n\n"
        f"📌 {len(ALL_QUESTIONS)} ta savol mavjud\n"
        f"🎯 Har o'yinda {QUIZ_LENGTH} ta tasodifiy savol\n"
        f"⏱ Har bir savolga {TIME_LIMIT} sekund vaqt\n"
        f"🔀 Javob variantlari har safar aralashtirilib beriladi\n\n"
        f"Boshlaylik! 👇",
        reply_markup=main_keyboard()
    )

# ── TUGMALAR ───────────────────────────────────────────────────────────────────
async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data

    if data == "menu":
        cancel_timer(uid)
        if uid in user_sessions:
            del user_sessions[uid]
        await q.edit_message_text(
            "📚 Lexicology Quiz\n\nNimani tanlaysiz?",
            reply_markup=main_keyboard()
        )

    elif data == "start_quiz":
        cancel_timer(uid)
        selected = random.sample(ALL_QUESTIONS, QUIZ_LENGTH)
        user_sessions[uid] = {
            "questions": selected,
            "current": 0,
            "score": 0,
            "name": q.from_user.full_name,
            "chat_id": q.message.chat.id,
            "message_id": q.message.message_id,
            "app": ctx.application,
        }
        await show_question(q, uid)

    elif data == "leaderboard":
        await q.edit_message_text(
            top10_text(),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Ortga", callback_data="menu")
            ]])
        )

    elif data == "stats":
        if uid in leaderboard:
            d = leaderboard[uid]
            avg = d["total"] / d["games"] if d["games"] else 0
            text = (
                f"📊 Sizning statistikangiz\n\n"
                f"🎮 O'yinlar: {d['games']}\n"
                f"🏆 Eng yaxshi: {d['best']}/{QUIZ_LENGTH}\n"
                f"📈 O'rtacha ball: {avg:.1f}\n"
                f"🎯 Jami to'g'ri: {d['total']}"
            )
        else:
            text = "📊 Siz hali o'ynamagansiz! Boshlang 🎮"
        await q.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ O'ynash", callback_data="start_quiz")],
                [InlineKeyboardButton("🔙 Ortga",   callback_data="menu")],
            ])
        )

    elif data.startswith("ans|"):
        parts = data.split("|", 2)
        if len(parts) != 3:
            return
        idx = int(parts[1])
        chosen = parts[2]

        if uid not in user_sessions:
            await q.answer("O'yin topilmadi. /start bosing.", show_alert=True)
            return

        session = user_sessions[uid]
        if session["current"] != idx:
            await q.answer("Bu savol o'tib ketgan!", show_alert=True)
            return

        cancel_timer(uid)

        qobj = session["questions"][idx]
        correct = qobj["correct"]

        if chosen.strip() == correct.strip():
            session["score"] += 1
            feedback = f"✅ To'g'ri!\n\n{correct}"
        else:
            feedback = (
                f"❌ Noto'g'ri!\n\n"
                f"Sizning javobingiz: {chosen}\n"
                f"To'g'ri javob: ✅ {correct}"
            )

        session["current"] += 1

        if session["current"] < QUIZ_LENGTH:
            try:
                await q.edit_message_text(
                    f"Savol {idx+1}/{QUIZ_LENGTH}  |  Ball: {session['score']}\n\n{feedback}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("➡️ Keyingi savol", callback_data=f"next|{session['current']}")
                    ]])
                )
            except Exception as e:
                logger.warning(f"ans edit error: {e}")
        else:
            await finish(q, uid)

    elif data.startswith("next|"):
        parts = data.split("|")
        idx = int(parts[1])

        if uid not in user_sessions:
            await q.answer("O'yin topilmadi. /start bosing.", show_alert=True)
            return

        session = user_sessions[uid]
        if session["current"] != idx:
            return

        await show_question(q, uid)

# ── O'YIN TUGADI ───────────────────────────────────────────────────────────────
async def finish(q, uid):
    cancel_timer(uid)
    session = user_sessions.pop(uid, None)
    if not session:
        return
    score = session["score"]
    pct = score / QUIZ_LENGTH * 100
    grade = get_grade(pct)
    name = q.from_user.full_name
    save_score(uid, name, score)

    try:
        await q.edit_message_text(
            f"🎉 O'yin tugadi!\n\n"
            f"👤 {name}\n"
            f"🎯 Natija: {score}/{QUIZ_LENGTH} ({pct:.0f}%)\n"
            f"{grade}\n\n"
            f"🏆 Eng yaxshi natijangiz: {leaderboard[uid]['best']}/{QUIZ_LENGTH}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Yana o'ynash", callback_data="start_quiz")],
                [InlineKeyboardButton("🏆 Liderlar",     callback_data="leaderboard")],
                [InlineKeyboardButton("🏠 Menyu",        callback_data="menu")],
            ])
        )
    except Exception as e:
        logger.warning(f"finish error: {e}")

# ── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    logger.info(f"Bot ishga tushdi! {QUIZ_LENGTH} savol | {TIME_LIMIT} sek taymer")
    app.run_polling()

if __name__ == "__main__":
    main()
