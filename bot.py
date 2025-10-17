# bot.py
import re
import time
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# إعدادات عامة
TOKEN = "8452093321:AAEI16NcAIFTHRt1ieKYKe1CQ1qhUfcMgjs"
ADMIN_CHAT_ID = 1530145001
WHATSAPP_LINK = "https://wa.me/96171204714"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# حفظ بيانات المستخدمين في الذاكرة
users = {}

# خطوات الأسئلة
steps = [
    ("full_name", "1️⃣ اكتب اسمك الثلاثي (مثال: محمد علي حيدر) 🌟"),
    ("email", "2️⃣ اكتب بريدك الإلكتروني ✉ (مثال: example.user@mail.com)"),
    ("phone", "3️⃣ اكتب رقم هاتفك مع رمز بلدك 📱 (مثال: +96171200000)"),
    ("telegram", "4️⃣ اكتب المعرّف الخاص بك على تلغرام 👤 (مثال: @AliTrader)"),
    ("oxshare", "5️⃣ للانضمام للقناة الخاصة افتح حسابك تحت وكالتنا عبر الرابط:\n🔗 https://my.oxshare.com/register?referral=01973820-6aaa-7313-bda5-2ffe0ade1490\n\n"
                "6️⃣ اكتب رقم حسابك الذي أنشأته لدى شركة Oxshare 💳 (مثال: 64090974)"),
    ("deposit_proof", "7️⃣ أرفق صورة لإثبات الإيداع من الشركة 📎 (صورة مطلوبة، لا نقبل كتابة)"),
    ("final", "8️⃣ أهلاً وسهلاً بك في عائلة Lebanese X Trading 🤝\nيرجى الانتظار للتدقيق لإضافتك للقناة الخاصة.\n"
              "يمكنك التواصل معنا مباشرة على واتساب للاستفسار:")
]

# تحقق بسيط للبريد والهاتف
def is_valid_email(text): return re.match(r"[^@]+@[^@]+\.[^@]+", text)
def is_valid_phone(text): return bool(re.match(r"^\+?\d{6,}$", text))

# نظام قفل ذكي لتجنب التكرار
def lock_check(user):
    now = time.time()
    if user.get("locked") and now - user["locked"] < 2:
        return True
    user["locked"] = now
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    users[user_id] = {"step": 0, "answers": {}, "locked": 0}
    await update.message.reply_text(
        "👋 مرحباً! أنا روبوت خدمة العملاء في فريق Lebanese X Trading.\n"
        "الرجاء الإجابة على كامل الأسئلة بالشكل الصحيح لضمان خدمتكن بشكل أسرع وأفضل 🔥"
    )
    await update.message.reply_text(steps[0][1])

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = users.get(user_id)

    if not user:
        await update.message.reply_text("يرجى كتابة /start للبدء 🙌")
        return

    if lock_check(user):
        await update.message.reply_text("⏳ يرجى الانتظار قليلاً...")
        return

    step_key, step_text = steps[user["step"]]
    text = (update.message.text or "").strip()

    # تحقق من نوع الجواب حسب الخطوة
    if step_key == "full_name":
        if any(ch.isdigit() for ch in text):
            return await update.message.reply_text("❌ الاسم لا يجب أن يحتوي أرقام. أعد المحاولة.")
    elif step_key == "email":
        if not is_valid_email(text):
            return await update.message.reply_text("❌ البريد الإلكتروني غير صحيح. أعد المحاولة.")
    elif step_key == "phone":
        if not is_valid_phone(text):
            return await update.message.reply_text("❌ رقم الهاتف غير صالح. مثال: +96171200000")
    elif step_key == "deposit_proof":
        if not update.message.photo:
            return await update.message.reply_text("❌ مطلوب صورة فقط. أعد الإرسال بصورة.")
        photo_id = update.message.photo[-1].file_id
        user["answers"][step_key] = photo_id
        user["step"] += 1
        return await next_step(update, context, user)

    # حفظ الإجابة النصية
    if step_key != "deposit_proof":
        user["answers"][step_key] = text

    user["step"] += 1
    await next_step(update, context, user)

async def next_step(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    if user["step"] >= len(steps):
        return await finish_form(update, context, user)

    step_key, step_text = steps[user["step"]]
    await update.message.reply_text(step_text)

async def finish_form(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    answers = user["answers"]
    lines = []
    for k, v in answers.items():
        if k == "deposit_proof":
            v = "(مرفقة صورة)"
        lines.append(f"{k}: {v}")
    result = "\n".join(lines)

    await context.bot.send_message(ADMIN_CHAT_ID, f"📩 طلب جديد من {update.effective_user.full_name}:\n\n{result}")

    if "deposit_proof" in answers:
        await context.bot.send_photo(ADMIN_CHAT_ID, photo=answers["deposit_proof"], caption="📎 إثبات الإيداع")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📞 تواصل عبر واتساب", url=WHATSAPP_LINK)]])
    await update.message.reply_text(
        "✅ شكراً لك! تم استلام بياناتك بنجاح.\n"
        "سيتم التواصل معك قريباً بعد مراجعة المعلومات 🔍",
        reply_markup=keyboard
    )

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
