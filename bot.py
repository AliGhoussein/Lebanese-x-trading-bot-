# Lebanese X Trading - Final Bot Script (Updated: WhatsApp group link + join text)
import re
import time
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# ===== إعدادات البوت =====
TOKEN = "8452093321:AAEI16NcAIFTHRt1ieKYKe1CQ1qhUfcMgjs"
ADMIN_CHAT_ID = 1530145001

# 🔗 رابط مجموعة واتساب الجديد
WHATSAPP_GROUP_LINK = "https://chat.whatsapp.com/IrGq4wC3Z7w5juCMI1YtSz?mode=wwt"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== تخزين المستخدمين في الذاكرة =====
users = {}

# ===== خطوات الأسئلة =====
steps = [
    ("full_name", "1️⃣ اكتب اسمك الثلاثي ✍\nمثال: Ahmad Example User"),
    ("email", "2️⃣ اكتب بريدك الإلكتروني ✉\nمثال: example.user@mail.com"),
    ("phone", "3️⃣ اكتب رقم هاتفك مع رمز بلدك 📱\nمثال: +123456789"),
    ("telegram", "4️⃣ اكتب المعرّف الخاص بك على تلغرام 👤\nمثال: @ExampleUser"),
    ("account_info", "5️⃣ للانضمام للقناة الخاصة افتح حسابك تحت وكالتنا عبر الرابط التالي:\n"
                     "🔗 https://my.oxshare.com/register?referral=01973820-6aaa-7313-bda5-2ffe0ade1490\n\n"
                     "إذا كان لديك حساب فعلاً لدينا أو عند أحد وكلائنا، اكتب رقم حسابك واسم وكيلك.\n"
                     "مثال: 78965412 - ExampleAgent"),
    ("deposit_proof", "6️⃣ أرفق صورة البريد الإلكتروني التي تثبت نجاح الإيداع 📎\n(مطلوب إرسال صورة فقط)"),
]

# ===== أدوات التحقق =====
def valid_email(text): return bool(re.match(r"[^@]+@[^@]+\.[^@]+", text))
def valid_phone(text): return bool(re.match(r"^\+?\d{6,}$", text))
def contains_digit(text): return any(ch.isdigit() for ch in text)

# ===== قفل ذكي لتفادي التكرار =====
def is_locked(user):
    now = time.time()
    if user.get("locked") and now - user["locked"] < 2:
        return True
    user["locked"] = now
    return False

# ===== البداية =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    users[user_id] = {"step": 0, "answers": {}, "locked": 0}

    await update.message.reply_text(
        "👋 مرحباً! أنا روبوت خدمة العملاء في فريق Lebanese X Trading.\n"
        "الرجاء الإجابة على كامل الأسئلة بالشكل الصحيح لضمان خدمتكن بشكل أسرع وأفضل 🚀"
    )
    await update.message.reply_text(steps[0][1])

# ===== استقبال الرسائل =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    user = users.get(user_id)

    if not user:
        await msg.reply_text("اكتب /start للبدء 🙌")
        return

    if is_locked(user):
        await msg.reply_text("⏳ يرجى الانتظار قليلاً...")
        return

    step_key, step_text = steps[user["step"]]
    text = (msg.text or "").strip()

    # تحقق حسب الخطوة الحالية
    if step_key == "full_name":
        if not text or contains_digit(text):
            return await msg.reply_text("❌ الاسم غير صالح. أعد المحاولة واكتب اسمك الثلاثي من دون أرقام.")
    elif step_key == "email":
        if not valid_email(text):
            return await msg.reply_text("❌ البريد الإلكتروني غير صحيح. مثال: example.user@mail.com")
    elif step_key == "phone":
        if not valid_phone(text):
            return await msg.reply_text("❌ رقم الهاتف غير صالح. مثال: +123456789")
    elif step_key == "telegram":
        if not text.startswith("@"):
            return await msg.reply_text("❌ اسم المستخدم يجب أن يبدأ بـ @")
    elif step_key == "deposit_proof":
        if not msg.photo:
            return await msg.reply_text("❌ مطلوب صورة فقط. أعد الإرسال بصورة.")
        photo_id = msg.photo[-1].file_id
        user["answers"][step_key] = photo_id
        user["step"] += 1
        return await next_question(update, context, user)

    # حفظ الإجابة النصية
    user["answers"][step_key] = text
    user["step"] += 1
    await next_question(update, context, user)

# ===== السؤال التالي =====
async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    if user["step"] >= len(steps):
        await finish_form(update, context, user)
        return
    _, question = steps[user["step"]]
    await update.message.reply_text(question)

# ===== عند الانتهاء =====
async def finish_form(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    answers = user["answers"]
    txt = "\n".join(
        f"{k}: {'(مرفقة صورة)' if k == 'deposit_proof' else v}"
        for k, v in answers.items()
    )

    # إرسال للأدمن
    await context.bot.send_message(
        ADMIN_CHAT_ID,
        f"📩 طلب جديد من {update.effective_user.full_name}:\n\n{txt}"
    )

    if "deposit_proof" in answers:
        await context.bot.send_photo(ADMIN_CHAT_ID, answers["deposit_proof"], caption="📎 إثبات الإيداع")

    # إرسال رسالة الختام + زر مجموعة الواتساب
    join_text = "اضغط على الرابط للانضمام إلى مجموعة التوصيات 👇"
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📢 انضم إلى مجموعة التوصيات", url=WHATSAPP_GROUP_LINK)]]
    )
    await update.message.reply_text(join_text, reply_markup=keyboard)

    await update.message.reply_text(
        "✅ شكراً لك! تم استلام بياناتك بنجاح.\n"
        "سيتم التواصل معك قريباً بعد مراجعة المعلومات 🔍"
    )

# ===== تشغيل البوت =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
