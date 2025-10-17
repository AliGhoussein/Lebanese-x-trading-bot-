import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ---------------- CONFIG ----------------
ADMIN_CHAT_ID = 1530145001
TOKEN = "8452093321:AAEI16NcAIFTHRt1ieKYKe1CQ1qhUfcMgjs"
WHATSAPP_NUMBER = "+96171204714"
# ----------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

FLOWS = {}

STEPS = [
    {"key": "name", "type": "text", "prompt": "١- اكتب اسمك الثلاثي\n🧩 مثال: علي غصين"},
    {"key": "email", "type": "email", "prompt": "٢- اكتب بريدك الإلكتروني\n🧩 مثال: ali@gmail.com"},
    {"key": "phone", "type": "phone", "prompt": "٣- اكتب رقم هاتفك مع رمز بلدك\n🧩 مثال: +96171204714"},
    {"key": "username", "type": "username", "prompt": "٤- اكتب المعرّف الخاص بك على تلغرام (username)\n🧩 مثال: @aligh"},
    {
        "key": "oxshare",
        "type": "text",
        "prompt": (
            "٥- للانضمام للقناة الخاصة افتح حسابك تحت وكالتنا عن طريق الرابط التالي:\n"
            "🔗 https://my.oxshare.com/register?referral=01973820-6aaa-7313-bda5-2ffe0ade1490\n\n"
            "إذا كان لديك حساب فعلاً لدينا أو عند أحد وكلائنا، اكتب فقط رقم حسابك واسم وكيلك.\n"
            "🧩 مثال: 6409074 - الوكيل علي غصين"
        ),
    },
    {"key": "account", "type": "text", "prompt": "٦- اكتب رقم حسابك الذي أنشأته لدى شركة Oxshare\n🧩 مثال: 75775455"},
    {"key": "deposit_proof", "type": "photo", "prompt": "٧- أرفق صورة لرسالة البريد الإلكتروني التي تم إرسالها إليك من قبل الشركة بنجاح الإيداع في حسابك."},
]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?\d{6,15}$")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    FLOWS[uid] = {"answers": {}, "step": 0}

    welcome_text = (
        "مرحباً 👋\n\n"
        "أنا روبوت خدمة العملاء في فريق Lebanese X Trading.\n"
        "الرجاء الإجابة على كامل الأسئلة بالشكل الصحيح لضمان خدمتكن بشكل أسرع وأفضل."
    )
    await update.message.reply_text(welcome_text)
    await update.message.reply_text(STEPS[0]["prompt"])

def validate_answer(step_type, text):
    if step_type == "text":
        return len(text.strip()) >= 2 and not text.strip().isdigit()
    elif step_type == "email":
        return EMAIL_RE.match(text.strip())
    elif step_type == "phone":
        return PHONE_RE.match(text.strip())
    elif step_type == "username":
        return text.strip().startswith("@")
    return True

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in FLOWS:
        FLOWS[uid] = {"answers": {}, "step": 0}

    flow = FLOWS[uid]
    step = STEPS[flow["step"]]

    if step["type"] == "photo":
        await update.message.reply_text("❌ الرجاء إرسال صورة كما هو مطلوب.")
        return

    text = update.message.text.strip()

    if not validate_answer(step["type"], text):
        await update.message.reply_text("❌ الإجابة غير صحيحة، يرجى المحاولة مجددًا بالشكل المطلوب.")
        return

    flow["answers"][step["key"]] = text
    flow["step"] += 1

    if flow["step"] >= len(STEPS):
        await finalize(update, context)
        return

    next_step = STEPS[flow["step"]]
    await update.message.reply_text(next_step["prompt"])

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in FLOWS:
        FLOWS[uid] = {"answers": {}, "step": 0}

    flow = FLOWS[uid]
    step = STEPS[flow["step"]]

    if step["type"] != "photo":
        await update.message.reply_text("❌ ليست مطلوبة صورة في هذا السؤال.")
        return

    file_id = update.message.photo[-1].file_id
    flow["answers"][step["key"]] = file_id
    flow["step"] += 1

    if flow["step"] >= len(STEPS):
        await finalize(update, context)
        return

    next_step = STEPS[flow["step"]]
    await update.message.reply_text(next_step["prompt"])

async def finalize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    flow = FLOWS[uid]
    answers = flow["answers"]

    admin_msg = (
        f"👤 الاسم: {answers.get('name')}\n"
        f"📧 البريد الإلكتروني: {answers.get('email')}\n"
        f"📱 الهاتف: {answers.get('phone')}\n"
        f"💬 المعرف على تلغرام: {answers.get('username')}\n"
        f"🧾 حساب Oxshare: {answers.get('oxshare')}\n"
        f"🏦 رقم الحساب: {answers.get('account')}"
    )

    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg)

    if "deposit_proof" in answers:
        await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=answers["deposit_proof"],
            caption="🧾 إثبات الإيداع"
        )

    wa_url = f"https://wa.me/{WHATSAPP_NUMBER.replace('+', '')}"
    keyboard = InlineKeyboardMarkup.from_button(
        InlineKeyboardButton("📲 تواصل عبر واتساب", url=wa_url)
    )

    await update.message.reply_text(
        "🎉 شكراً! تم استلام معلوماتك بنجاح.\n⏳ يرجى الانتظار للتدقيق.",
        reply_markup=keyboard
    )

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.run_polling()

if __name__ == "__main__":
    main()
