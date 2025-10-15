from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8452093321:AAEI16NcAIFTHRt1ieKYKe1CQ1qhUfcMgjs"
ADMIN_CHAT_ID = 1530145001

# خطوات الأسئلة
STEPS = [
    {"key": "full_name", "prompt": "📝 اكتب اسمك الثلاثي"},
    {"key": "email", "prompt": "📧 اكتب بريدك الإلكتروني"},
    {"key": "phone", "prompt": "📱 اكتب رقم هاتفك مع رمز بلدك"},
    {"key": "username", "prompt": "👤 اكتب المعرّف الخاص بك على تلغرام (username)"},
    {"key": "info", "prompt": "🔗 للانضمام للقناة الخاصة افتح حسابك تحت وكالتنا عن طريق الرابط التالي:\nhttps://my.oxshare.com/register?referral=01973820-6aaa-7313-bda5-2ffe0ade1490"},
    {"key": "account_number", "prompt": "💳 اكتب رقم حسابك الذي أنشأته لدى شركة Oxshare"},
    {"key": "deposit_proof", "prompt": "📸 أرفق صورة لرسالة البريد الإلكتروني التي تم إرسالها إليك من قبل الشركة بنجاح الإيداع في حسابك", "type": "photo"},
    {"key": "done", "prompt": "🎉 أهلاً وسهلاً بك في عائلة Lebanese X Trading.\nيرجى الانتظار للتدقيق لإضافتك للقناة الخاصة.\nيمكنك التواصل معنا على واتساب: +96171204714", "type": "info"}
]

# لتخزين بيانات المستخدم
user_flows = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    user_flows[user_id] = {"step": 0, "answers": {}}
    await update.message.reply_text("👋 أهلاً فيك! خلينا نبدأ.")
    await ask_next(update, context)

async def ask_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    flow = user_flows.get(user_id)
    if not flow:
        await update.message.reply_text("❗ اكتب /start للبدء من جديد.")
        return

    i = flow["step"]
    if i >= len(STEPS):
        await update.message.reply_text("✅ شكراً! تم إرسال بياناتك للمراجعة.")
        return

    step = STEPS[i]
    if step.get("type") == "info":
        await update.message.reply_text(step["prompt"])
        flow["step"] += 1
        await ask_next(update, context)
        return

    await update.message.reply_text(step["prompt"])

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    flow = user_flows.get(user_id)
    if not flow:
        return await update.message.reply_text("❗ اكتب /start للبدء من جديد.")

    step = STEPS[flow["step"]]
    flow["answers"][step["key"]] = update.message.text
    flow["step"] += 1
    await ask_next(update, context)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    flow = user_flows.get(user_id)
    if not flow:
        return await update.message.reply_text("❗ اكتب /start للبدء من جديد.")

    photo = update.message.photo[-1]
    flow["answers"][STEPS[flow["step"]]["key"]] = photo.file_id
    flow["step"] += 1

    await ask_next(update, context)

    # إرسال البيانات للإدمن
    lines = ["📋 *بيانات جديدة من مستخدم:*"]
    for s in STEPS:
        key = s["key"]
        if key in flow["answers"] and s.get("type") != "photo":
            lines.append(f"{s['prompt']}: {flow['answers'][key]}")

    text_summary = "\n".join(lines)
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text_summary)

    if "deposit_proof" in flow["answers"]:
        await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=flow["answers"]["deposit_proof"], caption="📎 إثبات الإيداع")

async def pingadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="📬 Test to admin: البوت شغال ✅")
    await update.message.reply_text("📩 تم إرسال رسالة للإدمن بنجاح!")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pingadmin", pingadmin))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("✅ البوت يعمل الآن (Lebanese X Trading)")
    app.run_polling()

if __name__ == "__main__":
    main()


