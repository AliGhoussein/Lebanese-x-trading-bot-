# bot.py
import re
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ---------------- CONFIGURATION ----------------
ADMIN_CHAT_ID = 1530145001
TOKEN = "8452093321:AAEI16NcAIFTHRt1ieKYKe1CQ1qhUfcMgjs"
WHATSAPP_NUMBER = "+96171204714"
# ------------------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

FLOWS = {}  # {user_id: {"step": int, "answers": {}, "locked": False}}

# -------- تسلسل الأسئلة الصحيح --------
STEPS = [
    {"key": "name", "type": "text", "prompt": "1️⃣ اكتب اسمك الثلاثي 🎯\n🧩 مثال: محمد حمزة خلف"},
    {"key": "email", "type": "email", "prompt": "2️⃣ اكتب بريدك الإلكتروني ✉\n🧩 مثال: example.user@mail.com"},
    {"key": "phone", "type": "phone", "prompt": "3️⃣ اكتب رقم هاتفك مع رمز بلدك 📱\n🧩 مثال: +96171200000"},
    {"key": "username", "type": "username", "prompt": "4️⃣ اكتب المعرّف الخاص بك على تلغرام (username) 🔗\n🧩 مثال: @example_user"},
    {
        "key": "oxshare_info",
        "type": "text",
        "prompt": (
            "5️⃣ افتح حسابك عبر الرابط تحت وكالتنا أو اكتب معلومات وكيلك إن كنت تملك حسابًا مسبقًا 💼\n\n"
            "🔗 https://my.oxshare.com/register?referral=01973820-6aaa-7313-bda5-2ffe0ade1490\n\n"
            "🧩 مثال: 6409074 - الوكيل: علي غصين"
        ),
    },
    {"key": "deposit_proof", "type": "photo", "prompt": "6️⃣ أرفق صورة لرسالة البريد الإلكتروني التي تُثبت نجاح الإيداع 🖼"},
]
# ---------------------------------------

EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")
PHONE_RE = re.compile(r"^\+?\d{6,15}$")

def validate_answer(step_type, text):
    text = text.strip()
    if step_type == "text":
        return len(text) >= 2
    elif step_type == "email":
        return bool(EMAIL_RE.search(text))
    elif step_type == "phone":
        return bool(PHONE_RE.match(text)) or len(re.sub(r"\D", "", text)) >= 6
    elif step_type == "username":
        return text.startswith("@") or len(text) >= 3
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    FLOWS[user.id] = {"step": 0, "answers": {}, "locked": False}

    welcome_msg = (
        "👋 مرحباً!\n\n"
        "أنا روبوت خدمة العملاء لفريق Lebanese X Trading.\n"
        "💬 الرجاء الإجابة على الأسئلة خطوة بخطوة لضمان خدمتكم بشكل أسرع وأفضل.\n\n"
        "لنبدأ الآن 🚀"
    )
    await update.message.reply_markdown(welcome_msg)
    await asyncio.sleep(1)
    await update.message.reply_markdown(STEPS[0]["prompt"])

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # تحقق أن المستخدم عنده جلسة
    if user_id not in FLOWS:
        FLOWS[user_id] = {"step": 0, "answers": {}, "locked": False}

    flow = FLOWS[user_id]

    # منع التداخل
    if flow.get("locked"):
        await update.message.reply_text("⏳ يرجى الانتظار قليلاً...")
        return

    flow["locked"] = True

    step_index = flow["step"]
    step = STEPS[step_index]

    # لو المستخدم أرسل نص بدل صورة المطلوبة
    if step["type"] == "photo":
        await update.message.reply_text("❌ في هذه الخطوة مطلوب صورة، رجاءً أرسل صورة.")
        flow["locked"] = False
        return

    # تحقق من الإجابة
    if not validate_answer(step["type"], text):
        await update.message.reply_text("⚠ الإجابة غير صحيحة، حاول مجدداً بالشكل المطلوب.")
        flow["locked"] = False
        return

    # حفظ الإجابة
    flow["answers"][step["key"]] = text
    flow["step"] += 1

    # الانتقال للخطوة التالية أو إنهاء
    if flow["step"] >= len(STEPS):
        await finalize(update, context)
    else:
        next_step = STEPS[flow["step"]]
        await asyncio.sleep(0.7)
        await update.message.reply_markdown(f"✅ ممتاز! الآن:\n\n{next_step['prompt']}")

    flow["locked"] = False

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo = update.message.photo[-1]
    file_id = photo.file_id

    if user_id not in FLOWS:
        FLOWS[user_id] = {"step": 0, "answers": {}, "locked": False}

    flow = FLOWS[user_id]

    if flow["locked"]:
        await update.message.reply_text("⏳ يرجى الانتظار قليلاً...")
        return

    step = STEPS[flow["step"]]

    if step["type"] != "photo":
        await update.message.reply_text("❌ لم نطلب صورة في هذه المرحلة.")
        return

    flow["answers"][step["key"]] = file_id
    flow["step"] += 1

    if flow["step"] >= len(STEPS):
        await finalize(update, context)
    else:
        next_step = STEPS[flow["step"]]
        await asyncio.sleep(0.7)
        await update.message.reply_markdown(f"✅ تم استلام الصورة!\n\n{next_step['prompt']}")

async def finalize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    flow = FLOWS[user_id]
    answers = flow["answers"]

    # إرسال النتائج للإدمن
    summary = (
        f"👤 الاسم: {answers.get('name')}\n"
        f"📧 البريد: {answers.get('email')}\n"
        f"📱 الهاتف: {answers.get('phone')}\n"
        f"💬 المعرّف: {answers.get('username')}\n"
        f"🧾 معلومات الحساب/الوكيل: {answers.get('oxshare_info')}"
    )
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=summary)

    if "deposit_proof" in answers:
        await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=answers["deposit_proof"], caption="📎 إثبات الإيداع")

    # زر واتساب
    wa_url = f"https://wa.me/{WHATSAPP_NUMBER.replace('+', '')}"
    keyboard = InlineKeyboardMarkup.from_button(
        InlineKeyboardButton("📲 تواصل معنا عبر واتساب", url=wa_url)
    )

    # رسالة ختامية
    confirmation = (
        "🎉 شكرًا لك! تم استلام جميع معلوماتك بنجاح ✅\n\n"
        "⏳ يرجى الانتظار قليلاً لحين مراجعة بياناتك.\n\n"
        "📞 اضغط الزر أدناه للتواصل معنا مباشرة عبر واتساب إذا رغبت بالمساعدة الفورية 👇"
    )
    await update.message.reply_markdown(confirmation, reply_markup=keyboard)

    logger.info(f"✅ User {user_id} completed flow successfully.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()
