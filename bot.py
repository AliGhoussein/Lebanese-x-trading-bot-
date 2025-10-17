# bot.py
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

# ---------------------------
# CONFIGURATION
# ---------------------------
ADMIN_CHAT_ID = 1530145001
TOKEN = "8452093321:AAEI16NcAIFTHRt1ieKYKe1CQ1qhUfcMgjs"
WHATSAPP_NUMBER = "+96171204714"
# ---------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

FLOWS = {}

STEPS = [
    {"key": "name", "type": "text", "prompt": "١- اكتب اسمك الثلاثي"},
    {"key": "email", "type": "email", "prompt": "٢ - اكتب بريدك الالكتروني"},
    {"key": "phone", "type": "phone", "prompt": "٣- اكتب رقم هاتفك و رمز بلدك"},
    {"key": "username", "type": "username", "prompt": "٤-اكتب المعرّف الخاص بك على تلغرام username"},
    {
        "key": "oxshare",
        "type": "text",
        "prompt": (
            "٥-للانضمام للقناة الخاصة افتح حسابك تحت وكالتنا عن طريق الرابط التالي : "
            "https://my.oxshare.com/register?referral=01973820-6aaa-7313-bda5-2ffe0ade1490\n\n"
            "اذا كان لديك حساب فعلاً لدينا او عند أحد وكلائنا ، اكتب فقط رقم حسابك و اسم وكيلك"
        ),
    },
    {"key": "account", "type": "text", "prompt": "٦-اكتب رقم حسابك الذي أنشأته لدى شركة Oxshare"},
    {
        "key": "deposit_proof",
        "type": "photo",
        "prompt": "٧- أرفق صورة لرسالة البريد الإلكتروني التي تم إرسالها إليك من قبل الشركة بنجاح الإيداع في حسابك",
    },
    {
        "key": "final",
        "type": "final",
        "prompt": (
            "٨-أهلا و سهلاً بك في عائلة Lebanese x trading , يرجى الانتظار للتدقيق لإضافتك للقناة الخاصة ، "
            "يمكنك التواصل معنا مباشرة على تطبيق واتساب للاستفسار +96171204714"
        ),
    },
]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?\d{6,15}$")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    FLOWS[uid] = {"answers": {}, "step": 0}

    welcome_text = (
        "مرحباً 👋\n\n"
        "أنا روبوت خدمة العملاء في فريق Lebanese x trading.\n"
        "الرجاء الإجابة على كامل الأسئلة بالشكل الصحيح لضمان خدمتكن بشكل اسرع و افضل."
    )
    await update.message.reply_text(welcome_text)
    await update.message.reply_text(STEPS[0]["prompt"])


def validate_answer(step_type, text):
    if step_type == "text":
        if not text or len(text.strip()) < 2:
            return False
        return True
    elif step_type == "email":
        return EMAIL_RE.match(text.strip())
    elif step_type == "phone":
        t = text.strip()
        if t.isdigit():
            t = "+" + t
        return PHONE_RE.match(t)
    elif step_type == "username":
        return len(text.strip()) >= 3
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
        await update.message.reply_text("❌ الإجابة غير صحيحة، الرجاء إعادة المحاولة.")
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
        f"💬 المعرّف على تلغرام: {answers.get('username')}\n"
        f"🧾 حساب Oxshare: {answers.get('oxshare')}\n"
        f"🏦 رقم الحساب: {answers.get('account')}"
    )

    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg)

    if "deposit_proof" in answers:
        await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=answers["deposit_proof"],
            caption="🧾 إثبات الإيداع",
        )

    wa_url = f"https://wa.me/{WHATSAPP_NUMBER.replace('+', '')}"
    keyboard = InlineKeyboardMarkup.from_button(
        InlineKeyboardButton("📲 تواصل عبر واتساب", url=wa_url)
    )

    await update.message.reply_text(
        "🎉 شكراً! تم استلام معلوماتك بنجاح.\n⏳ يرجى الانتظار للتدقيق.",
        reply_markup=keyboard,
    )


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.run_polling()


if __name__ == "__main__":
    main()
