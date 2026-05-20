import json
import random
import asyncio
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = "8863972910:AAFuZ1EpziBrBl8_7Wtg2_oHHdsRQQG4kVU"
QUESTIONS_PER_TEST = 20
TIME_PER_QUESTION = 15

with open("questions.json", "r", encoding="utf-8") as f:
    questions = json.load(f)

users = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected_questions = random.sample(
        questions,
        min(QUESTIONS_PER_TEST, len(questions))
    )

    users[update.effective_user.id] = {
        "score": 0,
        "index": 0,
        "questions": selected_questions,
        "answered": False
    }

    await update.message.reply_text(
        "📚 Test boshlandi!\n"
        f"📝 Savollar soni: {QUESTIONS_PER_TEST}\n"
        f"⏳ Har savol uchun vaqt: {TIME_PER_QUESTION} sekund"
    )

    await send_question(update, context)

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = users.get(update.effective_user.id)

    if not user:
        return

    if user["index"] >= len(user["questions"]):
        await update.message.reply_text(
            f"🏁 Test tugadi!\n\n"
            f"✅ Natija: {user['score']} / {len(user['questions'])}",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    user["answered"] = False

    q = user["questions"][user["index"]]
    options = q["options"][:]
    random.shuffle(options)

    keyboard = [[opt] for opt in options]

    await update.message.reply_text(
        f"❓ Savol {user['index'] + 1}/{len(user['questions'])}\n\n"
        f"{q['question']}\n\n"
        f"⏳ {TIME_PER_QUESTION} sekund vaqt",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

    asyncio.create_task(question_timeout(update, context))

async def question_timeout(update, context):
    await asyncio.sleep(TIME_PER_QUESTION)

    user = users.get(update.effective_user.id)

    if not user or user["answered"]:
        return

    q = user["questions"][user["index"]]

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "⏰ Vaqt tugadi!\n"
            f"✅ To'g'ri javob: {q['answer']}"
        )
    )

    user["index"] += 1
    user["answered"] = True

    await send_question(update, context)

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = users.get(update.effective_user.id)

    if not user:
        await update.message.reply_text("Avval /start bosing")
        return

    if user["answered"]:
        return

    q = user["questions"][user["index"]]
    user["answered"] = True

    if update.message.text == q["answer"]:
        user["score"] += 1
        await update.message.reply_text("✅ To'g'ri javob")
    else:
        await update.message.reply_text(
            f"❌ Noto'g'ri\n"
            f"✅ To'g'ri javob: {q['answer']}"
        )

    user["index"] += 1
    await send_question(update, context)

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer))

print("Bot ishga tushdi...")
app.run_polling()
