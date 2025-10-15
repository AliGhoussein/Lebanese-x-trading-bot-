from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# 🔹 ضع توكن البوت الخاص بك من BotFather هون
TOKEN = "8452093321:AAEI16NcAIFTHRt1ieKYKe1CQ1qhUfcMgjs"

# 🔹 ضع رقم الـ Chat ID الخاص بك لتستقبل الطلبات
ADMIN_CHAT_ID = 1530145001

# الخطوات بالتسلسل الجديد
STEPS = [
    {"key": "full_name", "prompt": "📝 اكتب اسمك الثلاثي:", "type": "text"},
    {"key": "email", "prompt": "📧 اكتب بريدك الالكتروني:", "type": "text"},
    {"key": "phone", "prompt": "📱 اكتب رقم هاتفك مع رمز بلدك:", "type": "text"},
    {"key": "telegram_user", "prompt": "💬 اكتب المعرّف الخاص بك على تلغرام (username):", "type": "text"},
    {"key": "info1", "prompt": "🔗 للانضمام للقناة الخاصة، افتح حسابك تحت وكالتنا عبر الرابط التالي:\nhttps://my.oxshare.com/register?referral=01973820-6aaa-7313-bda5-2ffe0ade1490", "type": "info"},
    {"key": "account_number", "prompt": "💳 اكتب رقم حسابك الذي أنشأته لدى شركة Oxshare:", "type": "text"},
    {"key": "deposit_proof", "prompt": "📸 أرفق صورة لرسالة البريد الإلكتروني التي تم إرسالها إليك من قبل الشركة بنجاح الإيداع في حسابك:", "type": "photo"},
    {"key": "done", "prompt": "🎉 أهلاً وسهلاً بك في عائلة Lebanese X Trading!\nيرجى الانتظار للتدقيق لإضافتك للقناة الخاصة.\n📞 يمكنك التواصل معنا على واتساب: +96171204714", "type": "info"}
]

# 🔹 ذاكرة لحفظ إجابات المستخدمين
user_flows = {}

# إرسال أول سؤال
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    user_flows[user_id] = {"step": 0, "answers": {}}
    await update.message.reply_text("أهلاً وسهلاً 👋! لنبدأ التسجيل...")
    await ask_next_question(update, context)

# وظيفة لطرح السؤال التالي
async def ask_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    flow = user_flows.get(user_id)

    if not flow:
        return await update.message.reply_text("حدث خطأ، أرسل /start لإعادة المحاولة.")

    if flow["step"] >= len(STEPS):
        await update.message.reply_text("✅ تم استلام جميع البيانات. شكراً!")
        return

    step = STEPS[flow["step"]]
    if step["type"] == "info":
        await update.message.reply_text(step["prompt"])
        flow["step"] += 1
        await ask_next_question(update, context)
    else:
        await update.message.reply_text(step["prompt"])

# التعامل مع النصوص
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if user_id not in user_flows:
        return await update.message.reply_text("اكتب /start لتبدأ.")

    flow = user_flows[user_id]
    step = STEPS[flow["step"]]
    flow["answers"][step["key"]] = update.message.text
    flow["step"] += 1

    # بعد آخر إدخال، إرسال النتائج للإدارة
    if flow["step"] >= len(STEPS):
        await send_to_admin(update, context)
    else:
        await ask_next_question(update, context)

# التعامل مع الصور
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if user_id not in user_flows:
        return await update.message.reply_text("اكتب /start لتبدأ.")

    flow = user_flows[user_id]
    step = STEPS[flow["step"]]

    if step["type"] != "photo":
        return await update.message.reply_text("📎 الرجاء إرسال النص المطلوب وليس صورة.")

    photo = update.message.photo[-1]
    flow["answers"][step["key"]] = photo.file_id
    flow["step"] += 1

    if flow["step"] >= len(STEPS):
        await send_to_admin(update, context)
    else:
        await ask_next_question(update, context)

# إرسال البيانات للإدارة
async def send_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    flow = user_flows[user_id]
    answers = flow["answers"]

    text = "📩 تم استلام طلب جديد:\n\n"
    for s in STEPS:
        if s["type"] == "info":
            continue
        val = answers.get(s["key"], "")
        if s["type"] == "photo":
            val = "(📸 صورة مرفقة)"
        text += f"{s['prompt']}\n➡ {val}\n\n"

    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text)

    if "deposit_proof" in answers:
        await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=answers["deposit_proof"],
            caption="📎 إثبات الإيداع"
        )

    await update.message.reply_text("✅ شكراً! تم إرسال بياناتك إلى الإدارة.")

# اختبار للإدارة فقط
async def pingadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="✅ Test to admin: البوت شغال تمام!")
    await update.message.reply_text("📨 تم إرسال تنبيه للإدارة.")

# ----------------------------
# 🔹 MAIN FUNCTION
# ----------------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pingadmin", pingadmin))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("✅ البوت جاهز ويعمل الآن (Lebanese X Trading)")
    app.run_polling()

if __name__ == "__main__":
    main()


