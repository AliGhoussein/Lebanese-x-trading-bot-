import re
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# 🧩 معلومات البوت
TOKEN = "8452093321:AAEI16NcAIFTHRt1ieKYKe1CQ1qhUfcMgjs"
ADMIN_CHAT_ID = 1530145001

# 🔹 الخطوات بالتسلسل الاحترافي
STEPS = [
    {"key": "full_name", "prompt": "👤 يرجى إدخال اسمك الثلاثي كما هو في بطاقتك الرسمية:", "type": "text"},
    {"key": "email", "prompt": "📧 أدخل بريدك الإلكتروني الصحيح للتواصل الرسمي:", "type": "email"},
    {"key": "phone", "prompt": "📱 اكتب رقم هاتفك مع رمز البلد (مثال: +96171234567):", "type": "phone"},
    {"key": "username", "prompt": "💬 اكتب المعرّف الخاص بك على تلغرام (username) ويبدأ بـ @:", "type": "username"},
    {"key": "info", "prompt": "🔗 للانضمام للقناة الخاصة افتح حسابك تحت وكالتنا عبر الرابط التالي:\nhttps://my.oxshare.com/register?referral=01973820-6aaa-7313-bda5-2ffe0ade1490\n\nإذا كان لديك حساب فعلاً لدينا أو عند أحد وكلائنا، اكتب فقط رقم حسابك واسم وكيلك.", "type": "info"},
    {"key": "account_number", "prompt": "🏦 اكتب رقم حسابك الذي أنشأته لدى شركة Oxshare:", "type": "text"},
    {"key": "deposit_proof", "prompt": "📸 أرسل صورة لرسالة البريد الإلكتروني التي تم إرسالها إليك من قبل الشركة بنجاح الإيداع في حسابك:", "type": "photo"},
    {"key": "done", "prompt": "🎉 أهلاً وسهلاً بك في عائلة Lebanese X Trading!\nيرجى الانتظار للتدقيق لإضافتك للقناة الخاصة.\n📞 يمكنك التواصل معنا عبر واتساب: +96171204714", "type": "info"},
]

# 🔹 لتخزين بيانات المستخدم مؤقتاً
user_flows = {}

# 🟢 دالة بدء البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    user_flows[user_id] = {"step": 0, "answers": {}}
    welcome = (
        "مرحباً 👋\n\n"
        "أنا روبوت خدمة العملاء في فريق Lebanese X Trading.\n"
        "الرجاء الإجابة على *كافة الأسئلة بدقة وبالشكل الصحيح* لضمان خدمتكم بشكل أسرع وأفضل.\n\n"
        "لنبدأ 👇"
    )
    await update.message.reply_text(welcome)
    await ask_next(update, context)

# 🟡 طرح السؤال التالي
async def ask_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    flow = user_flows.get(user_id)
    if not flow:
        return await update.message.reply_text("حدث خطأ، أرسل /start لإعادة المحاولة.")

    step_index = flow["step"]
    if step_index >= len(STEPS):
        return

    step = STEPS[step_index]
    if step["type"] == "info":
        await update.message.reply_text(step["prompt"])
        flow["step"] += 1
        await ask_next(update, context)
    else:
        await update.message.reply_text(step["prompt"])

# 🔍 التحقق من صحة الإجابات
def validate_answer(answer, step_type):
    if step_type == "text":
        # الاسم لازم يحتوي على حروف فقط
        return bool(re.match(r"^[A-Za-z\u0600-\u06FF\s]{3,}$", answer))
    elif step_type == "email":
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", answer))
    elif step_type == "phone":
        return bool(re.match(r"^\+\d{6,15}$", answer))
    elif step_type == "username":
        return bool(re.match(r"^@[A-Za-z0-9_]{3,}$", answer))
    return True

# ✉ معالجة الردود النصية
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if user_id not in user_flows:
        return await update.message.reply_text("اكتب /start للبدء.")

    flow = user_flows[user_id]
    step = STEPS[flow["step"]]
    step_type = step["type"]

    if step_type == "photo":
        return await update.message.reply_text("📎 يرجى إرسال صورة وليس نصاً.")

    answer = update.message.text.strip()

    # تحقق من صحة الجواب
    if not validate_answer(answer, step_type):
        return await update.message.reply_text("❌ الإجابة غير صحيحة، يرجى المحاولة مجدداً بالشكل المطلوب.")

    flow["answers"][step["key"]] = answer
    flow["step"] += 1

    if flow["step"] >= len(STEPS):
        await send_to_admin(update, context)
    else:
        await ask_next(update, context)

# 🖼 معالجة الصور
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if user_id not in user_flows:
        return await update.message.reply_text("اكتب /start للبدء.")

    flow = user_flows[user_id]
    step = STEPS[flow["step"]]
    if step["type"] != "photo":
        return await update.message.reply_text("❌ هذه الخطوة تتطلب كتابة نص، وليس صورة.")

    photo = update.message.photo[-1]
    flow["answers"][step["key"]] = photo.file_id
    flow["step"] += 1

    if flow["step"] >= len(STEPS):
        await send_to_admin(update, context)
    else:
        await ask_next(update, context)

# 📤 إرسال البيانات إلى الأدمن
async def send_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    answers = user_flows[user_id]["answers"]

    formatted = (
        "📩 *طلب تسجيل جديد:*\n\n"
        f"👤 الاسم: {answers.get('full_name','غير محدد')}\n"
        f"📧 البريد: {answers.get('email','غير محدد')}\n"
        f"📱 الهاتف: {answers.get('phone','غير محدد')}\n"
        f"💬 يوزر تلغرام: {answers.get('username','غير محدد')}\n"
        f"🏦 رقم الحساب: {answers.get('account_number','غير محدد')}\n"
    )

    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=formatted)

    if "deposit_proof" in answers:
        await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=answers["deposit_proof"],
            caption="📎 إثبات الإيداع"
        )

    # إرسال رسالة الختام للمستخدم
    await update.message.reply_text(STEPS[-1]["prompt"])

# 🧭 تشغيل البوت
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("✅ البوت يعمل الآن (Lebanese X Trading)")
    app.run_polling()

if __name__ == "__main__":
    main()
