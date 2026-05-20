#!/usr/bin/env python3
import json, random, logging, os, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
QUIZ_LENGTH = 20
TIME_LIMIT = 15  # sekund

with open("questions.json", encoding="utf-8") as f:
    ALL_QUESTIONS = json.load(f)

user_sessions = {}
leaderboard = {}
timer_tasks = {}  # {uid: asyncio.Task}

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
        return "🏆 *TOP 10 LIDERLAR*\n\nHali hech kim o'ynamagan!"
    items = sorted(leaderboard.items(), key=lambda x: x[1]["best"], reverse=True)[:10]
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = ["🏆 *TOP 10 LIDERLAR*\n"]
    for i, (_, d) in enumerate(items):
        avg = d["total"] / d["games"] if d["games"] else 0
        lines.append(
            f"{medals[i]} *{d['name']}*\n"
            f"   🎯 Eng yaxshi: {d['best']}/{QUIZ_LENGTH} | "
            f"O'yinlar: {d['games']} | O'rtacha: {avg:.1f}\n"
        )
    return "\n".join(lines)

# ── KLAVIATURA ─────────────────────────────────────────────────────────────────
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ O'yinni boshlash", callback_data="start_quiz")],
        [InlineKeyboardButton("🏆 Liderlar jadvali", callback_data="leaderboard")],
        [InlineKeyboardButton("📊 Statistika",        callback_data="stats")],
    ])

# ── SAVOL KO'RSATISH ───────────────────────────────────────────────────────────
async def show_question(query_or_msg, uid, edit=True):
    session = user_sessions[uid]
    idx = session["current"]
    qobj = session["questions"][idx]

    options = qobj["options"][:]
    random.shuffle(options)
    session["shuffled_options"] = options  # keyingi foydalanish uchun saqla

    keyboard = [
        [InlineKeyboardButton(f"{chr(65+i)}) {opt}", callback_data=f"ans|{idx}|{opt}")]
        for i, opt in enumerate(options)
    ]

    text = (
        f"⏱ *{TIME_LIMIT} sekund*  |  "
        f"❓ Savol *{idx+1}/{QUIZ_LENGTH}*  |  "
        f"✅ Ball: *{session['score']}*\n\n"
        f"{qobj['q']}"
    )

    if edit:
        msg = await query_or_msg.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        msg = await query_or_msg.reply_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    session["message_id"] = msg.message_id
    session["chat_id"] = msg.chat.id

    # Eski taymerni bekor qil, yangi boshlat
    cancel_timer(uid)
    task = asyncio.create_task(time_is_up(uid, idx, query_or_msg))
    timer_tasks[uid] = task

# ── TAYMER ─────────────────────────────────────────────────────────────────────
def cancel_timer(uid):
    if uid in timer_tasks:
        timer_tasks[uid].cancel()
        del timer_tasks[uid]

async def time_is_up(uid, idx, ctx_obj):
    await asyncio.sleep(TIME_LIMIT)
    if uid not in user_sessions:
        return
    session = user_sessions[uid]
    if session["current"] != idx:
        return

    qobj = session["questions"][idx]
    correct = qobj["correct"]
    session["current"] += 1

    feedback = f"⏰ *Vaqt tugadi!*\n\nTo'g'ri javob: ✅ _{correct}_"

    try:
        bot = ctx_obj._application.bot if hasattr(ctx_obj, '_application') else ctx_obj.get_bot()
    except Exception:
        return

    if session["current"] < QUIZ_LENGTH:
        try:
            await bot.edit_message_text(
                chat_id=session["chat_id"],
                message_id=session["message_id"],
                text=f"❓ Savol {idx+1}/{QUIZ_LENGTH}  ✅ Ball: {session['score']}\n\n{feedback}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("➡️ Keyingi savol", callback_data=f"next|{session['current']}")
                ]])
            )
        except Exception as e:
            logger.warning(f"Timer edit error: {e}")
    else:
        await finish_by_timer(bot, uid)

async def finish_by_timer(bot, uid):
    if uid not in user_sessions:
        return
    session = user_sessions.pop(uid)
    score = session["score"]
    pct = score / QUIZ_LENGTH * 100
    grade = get_grade(pct)
    name = session.get("name", "Foydalanuvchi")
    save_score(uid, name, score)
    try:
        await bot.edit_message_text(
            chat_id=session["chat_id"],
            message_id=session["message_id"],
            text=(
                f"🎉 *O'yin tugadi!*\n\n"
                f"👤 {name}\n"
                f"🎯 Natija: *{score}/{QUIZ_LENGTH}* ({pct:.0f}%)\n"
                f"{grade}\n\n"
                f"🏆 Eng yaxshi natijangiz: {leaderboard[uid]['best']}/{QUIZ_LENGTH}"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Yana o'ynash", callback_data="start_quiz")],
                [InlineKeyboardButton("🏆 Liderlar",     callback_data="leaderboard")],
                [InlineKeyboardButton("🏠 Menyu",        callback_data="menu")],
            ])
        )
    except Exception as e:
        logger.warning(f"Finish timer error: {e}")

# ── BAHO ───────────────────────────────────────────────────────────────────────
def get_grade(pct):
    if pct == 100:  return "🏆 Mukammal! Barcha savollar to'g'ri!"
    if pct >= 85:   return "🌟 A'lo natija!"
    if pct >= 70:   return "👍 Yaxshi!"
    if pct >= 50:   return "📚 Qoniqarli. Ko'proq o'qing!"
    return "😅 Qiyin bo'ldi. Yana urinib ko'ring!"

# ── /start ─────────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"👋 Salom, *{name}*!\n\n"
        f"📚 *Lexicology Quiz*\n\n"
        f"📌 {len(ALL_QUESTIONS)} ta savol mavjud\n"
        f"🎯 Har o'yinda *{QUIZ_LENGTH} ta* tasodifiy savol\n"
        f"⏱ Har bir savolga *{TIME_LIMIT} sekund* vaqt\n"
        f"🔀 Javob variantlari har safar aralashtirilib beriladi\n\n"
        f"Boshlaylik! 👇",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ── TUGMALAR ───────────────────────────────────────────────────────────────────
async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data

    # ── Bosh menyu ──
    if data == "menu":
        cancel_timer(uid)
        await q.edit_message_text(
            "📚 *Lexicology Quiz*\n\nNimani tanlaysiz?",
            parse_mode="Markdown", reply_markup=main_keyboard()
        )

    # ── O'yin boshlash ──
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
        }
        # ctx ni task uchun saqlash
        user_sessions[uid]["app"] = ctx.application
        await show_question(q, uid, edit=True)

    # ── Liderlar ──
    elif data == "leaderboard":
        await q.edit_message_text(
            top10_text(), parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Ortga", callback_data="menu")
            ]])
        )

    # ── Statistika ──
    elif data == "stats":
        if uid in leaderboard:
            d = leaderboard[uid]
            avg = d["total"] / d["games"] if d["games"] else 0
            text = (
                f"📊 *Sizning statistikangiz*\n\n"
                f"🎮 O'yinlar: {d['games']}\n"
                f"🏆 Eng yaxshi: {d['best']}/{QUIZ_LENGTH}\n"
                f"📈 O'rtacha ball: {avg:.1f}\n"
                f"🎯 Jami to'g'ri: {d['total']}"
            )
        else:
            text = "📊 Siz hali o'ynamagansiz! Boshlang 🎮"
        await q.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ O'ynash", callback_data="start_quiz")],
                [InlineKeyboardButton("🔙 Ortga",   callback_data="menu")],
            ])
        )

    # ── Javob ──
    elif data.startswith("ans|"):
        parts = data.split("|", 2)
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
            feedback = f"✅ *To'g'ri!*\n\n_{correct}_"
        else:
            feedback = (
                f"❌ *Noto'g'ri!*\n\n"
                f"Sizning javobingiz: _{chosen}_\n"
                f"To'g'ri javob: ✅ _{correct}_"
            )

        session["current"] += 1

        if session["current"] < QUIZ_LENGTH:
            await q.edit_message_text(
                f"❓ Savol {idx+1}/{QUIZ_LENGTH}  ✅ Ball: {session['score']}\n\n{feedback}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("➡️ Keyingi savol", callback_data=f"next|{session['current']}")
                ]])
            )
        else:
            await finish(q, uid)

    # ── Keyingi savol ──
    elif data.startswith("next|"):
        idx = int(data.split("|")[1])
        if uid not in user_sessions:
            return
        if user_sessions[uid]["current"] != idx:
            return
        await show_question(q, uid, edit=True)

# ── O'YIN TUGADI ───────────────────────────────────────────────────────────────
async def finish(q, uid):
    cancel_timer(uid)
    session = user_sessions.pop(uid)
    score = session["score"]
    pct = score / QUIZ_LENGTH * 100
    grade = get_grade(pct)
    name = q.from_user.full_name
    save_score(uid, name, score)

    await q.edit_message_text(
        f"🎉 *O'yin tugadi!*\n\n"
        f"👤 {name}\n"
        f"🎯 Natija: *{score}/{QUIZ_LENGTH}* ({pct:.0f}%)\n"
        f"{grade}\n\n"
        f"🏆 Eng yaxshi natijangiz: {leaderboard[uid]['best']}/{QUIZ_LENGTH}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Yana o'ynash", callback_data="start_quiz")],
            [InlineKeyboardButton("🏆 Liderlar",     callback_data="leaderboard")],
            [InlineKeyboardButton("🏠 Menyu",        callback_data="menu")],
        ])
    )

# ── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    logger.info("Bot ishga tushdi! 20 savol | 15 sekund taymer")
    app.run_polling()

if __name__ == "__main__":
    main()
