# bot.py
# Requirements:
# pip install python-telegram-bot==20.4 email-validator

import re
import logging
from email_validator import validate_email, EmailNotValidError

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(_name_)

# ------------------------------------------
# YOUR CONFIG - غيّر فقط هالقيم إذا لزم:
TOKEN = "8452093321:AAEI16NcAIFTHRt1ieKYKe1CQ1qhUfcMgjs"
ADMIN_CHAT_ID = 1530145001
# ------------------------------------------

# Conversation steps keys
(
    STEP_FULLNAME,
    STEP_EMAIL,
    STEP_PHONE,
    STEP_USERNAME,
    STEP_SIGNUP,
    STEP_ACCOUNT,
    STEP_PROOF,
    STEP_FINAL,
) = range(8)

# The questions/prompts (professional Arabic)
PROMPTS = {
    STEP_FULLNAME: "١) اكتب اسمك الثلاثي (الاسم واللقب والجد إن وُجد):",
    STEP_EMAIL: "٢) اكتب بريدك الإلكتروني (Email):",
    STEP_PHONE: "٣) اكتب رقم هاتفك مع رمز البلد (مثال: +96171234567):",
    STEP_USERNAME: "٤) اكتب المعرّف الخاص بك على تلغرام (username) بدون @ :",
    STEP_SIGNUP: (
        "٥) للانضمام للقناة الخاصة افتح حسابك تحت وكالتنا عن طريق الرابط التالي:\n"
        "🔗 https://my.oxshare.com/register?referral=01973820-6aaa-7313-bda5-2ffe0ade1490\n\n"
        "إذا كان لديك حساب فعلاً لدى أحد وكلائنا، اكتب فقط رقم حسابك واسم وكيلك (أو اكتفِ بكتابة رقم الحساب إذا فتحته بنفسك)."
    ),
    STEP_ACCOUNT: "٦) اكتب رقم حسابك الذي أنشأته لدى شركة Oxshare (ورقم الوكيل إذا كان موجودًا):",
    STEP_PROOF: "٧) أرفق صورة لرسالة البريد الإلكتروني التي تؤكد الإيداع (*يجب أن تكون صورة* - لا نقبل كتابة نص بدلاً عنها). الرجاء إرسال صورة واحدة هنا.",
    STEP_FINAL: (
        "٨) شكرًا. هذه آخر رسالة تصل للعميل: أهلاً وسهلاً بك في عائلة Lebanese X Trading،\n"
        "يرجى الانتظار للتدقيق لإضافتك للقناة الخاصة. يمكنك التواصل معنا مباشرة على واتساب للاستفسار:\n"
        "📞 +96171204714\n\n"
        "اضغط /done للانتهاء أو /cancel لإلغاء العملية."
    ),
}

# utility validators
def is_name_valid(text: str) -> bool:
    # simple: must contain letters (Arabic or Latin) and at least 2 words
    parts = [p for p in text.strip().split() if p]
    if len(parts) < 2:
        return False
    return any(re.search(r"[A-Za-z\u0600-\u06FF]", p) for p in parts)

def is_email_valid(text: str) -> bool:
    try:
        validate_email(text)
        return True
    except EmailNotValidError:
        return False

def is_phone_valid(text: str) -> bool:
    # simple check: digits and +, length between 7 and 16
    s = text.strip()
    return bool(re.fullmatch(r"\+?\d{7,16}", s))

def is_account_valid(text: str) -> bool:
    # account should contain digits; allow letters for agent name appended
    # Accept if there is at least one digit of length >= 5
    digits = re.findall(r"\d+", text)
    return any(len(d) >= 5 for d in digits)

def normalize_multiline_answer(ans: str) -> str:
    # merge multiple lines into one space-separated string
    if "\n" in ans:
        parts = [p.strip() for p in ans.split("\n") if p.strip()]
        return " ".join(parts)
    return ans.strip()

# store per-user flow in-memory
# structure: {user_id: {"step": int, "answers": {key: value}}}
FLOWS = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # initialize flow
    FLOWS[user.id] = {"step": STEP_FULLNAME, "answers": {}}

    welcome = (
        "مرحباً 👋\n"
        "أنا روبوت خدمة العملاء في فريق Lebanese x trading.\n"
        "الرجاء الإجابة على كامل الأسئلة التالية بالشكل الصحيح لضمان خدمتكم بشكل أسرع وأفضل.\n\n"
        f"{PROMPTS[STEP_FULLNAME]}"
    )
    await update.message.reply_text(welcome)
    return STEP_FULLNAME

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    FLOWS.pop(user.id, None)
    await update.message.reply_text("تم إلغاء العملية. إذا رغبت أعد ارسال /start للبدء من جديد.")
    return ConversationHandler.END

# generic handler for text responses
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    text = update.message.text or ""
    if uid not in FLOWS:
        # not in flow, invite to start
        await update.message.reply_text("اضغط /start للبدء بملء البيانات.")
        return

    flow = FLOWS[uid]
    step = flow["step"]
    text = normalize_multiline_answer(text)

    # STEP handlers
    if step == STEP_FULLNAME:
        if not is_name_valid(text):
            await update.message.reply_text("❌ الاسم غير صحيح. اكتب الاسم الثلاثي (مثال: علي حسن غصين).")
            return
        flow["answers"]["full_name"] = text
        flow["step"] = STEP_EMAIL
        await update.message.reply_text(PROMPTS[STEP_EMAIL])
        return

    if step == STEP_EMAIL:
        if not is_email_valid(text):
            await update.message.reply_text("❌ البريد الإلكتروني غير صحيح. يرجى إدخال بريد صالح (مثال: name@example.com).")
            return
        flow["answers"]["email"] = text
        flow["step"] = STEP_PHONE
        await update.message.reply_text(PROMPTS[STEP_PHONE])
        return

    if step == STEP_PHONE:
        if not is_phone_valid(text):
            await update.message.reply_text("❌ رقم الهاتف غير صحيح. أعد كتابة رقم مثل: +96171234567")
            return
        flow["answers"]["phone"] = text
        flow["step"] = STEP_USERNAME
        await update.message.reply_text(PROMPTS[STEP_USERNAME])
        return

    if step == STEP_USERNAME:
        username = text.lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9_]{2,32}", username):
            await update.message.reply_text("❌ اسم المستخدم غير صالح. اكتب username بدون @، فقط أحرف وأرقام و_ طول بين 2 و32.")
            return
        flow["answers"]["username"] = username
        flow["step"] = STEP_SIGNUP
        await update.message.reply_text(PROMPTS[STEP_SIGNUP])
        # proceed to account step after user reads link
        flow["step"] = STEP_ACCOUNT
        await update.message.reply_text(PROMPTS[STEP_ACCOUNT])
        return

    if step == STEP_SIGNUP:
        # shouldn't happen because we immediately moved to STEP_ACCOUNT after showing link
        flow["step"] = STEP_ACCOUNT
        await update.message.reply_text(PROMPTS[STEP_ACCOUNT])
        return

    if step == STEP_ACCOUNT:
        # allow merged multiline: e.g. "6409074\nAli Ghsein" -> merged
        text = normalize_multiline_answer(text)
        if not is_account_valid(text):
            await update.message.reply_text("❌ الإجابة غير صحيحة. اكتب رقم الحساب (5 أرقام أو أكثر) ويمكنك إضافة اسم الوكيل بنفس السطر أو بعده.")
            return
        flow["answers"]["account"] = text
        flow["step"] = STEP_PROOF
        await update.message.reply_text(PROMPTS[STEP_PROOF])
        return

    if step == STEP_FINAL:
        # shouldn't reach here via text normally
        await update.message.reply_text("اضغط /done لإرسال المعلومات أو /cancel للإلغاء.")
        return

    # if we reach here, unknown step
    await update.message.reply_text("حصل خطأ غير متوقع — أعد تشغيل البوت بكتابة /start.")
    return

# handler for receiving photos (deposit proof)
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    if uid not in FLOWS:
        await update.message.reply_text("اضغط /start للبدء بملء البيانات.")
        return

    flow = FLOWS[uid]
    step = flow["step"]

    if step != STEP_PROOF:
        await update.message.reply_text("لم يُطلب منك صورة الآن. اتبع التعليمات أو اضغط /start للبدء من جديد.")
        return

    # get highest quality photo
    photo = update.message.photo[-1]
    file_id = photo.file_id
    flow["answers"]["deposit_proof_file_id"] = file_id

    # go to final message
    flow["step"] = STEP_FINAL
    # final "closing" message to user as requested
    await update.message.reply_text(PROMPTS[STEP_FINAL])
    return

# if user sends text where photo required -> re-ask
async def handle_text_when_photo_needed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    if uid not in FLOWS:
        await update.message.reply_text("اضغط /start للبدء.")
        return

    flow = FLOWS[uid]
    if flow["step"] == STEP_PROOF:
        await update.message.reply_text("❌ نحتاج صورة (Proof) وليس نصًّا. الرجاء إرسال صورة لرسالة التأكيد فقط.")
        return
    await handle_text(update, context)

# done -> send to admin only answers
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    if uid not in FLOWS:
        await update.message.reply_text("ما في عملية جارية. ارسل /start للبدء.")
        return ConversationHandler.END

    flow = FLOWS[uid]
    # make sure all steps completed
    missing = []
    needed_keys = ["full_name", "email", "phone", "username", "account", "deposit_proof_file_id"]
    for k in needed_keys:
        if k not in flow["answers"]:
            missing.append(k)
    if missing:
        await update.message.reply_text("❌ لاتمام العملية يجب الإجابة على كل الأسئلة وإرفاق الصورة المطلوبة. الرجاء إكمال الخطوات.")
        # re-send prompt of current step
        await update.message.reply_text(PROMPTS.get(flow["step"], "أكمل المعلومات المطلوبة."))
        return

    # send to admin: only answers, nicely formatted
    ans = flow["answers"]
    admin_text = (
        "🆕 طلب جديد من بوت الدعم - Lebanese X Trading\n\n"
        f"📛 الإسم الثلاثي: {ans.get('full_name')}\n"
        f"📧 البريد الإلكتروني: {ans.get('email')}\n"
        f"📱 الهاتف: {ans.get('phone')}\n"
        f"🔹 Telegram username: @{ans.get('username')}\n"
        f"🏦 رقم الحساب و/أو وكيل: {ans.get('account')}\n"
    )
    # send admin text
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text)

    # send photo to admin (caption optional)
    file_id = ans.get("deposit_proof_file_id")
    if file_id:
        await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=file_id, caption="🔔 صورة إثبات الإيداع")

    # reply to user final confirmation
    await update.message.reply_text("✅ تم استلام معلوماتك بنجاح. شكراً لك، سيتم التواصل معك عند الانضمام للقناة.")
    # clear flow
    FLOWS.pop(uid, None)
    return ConversationHandler.END

# error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Exception while handling an update:")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            STEP_FULLNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
            STEP_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
            STEP_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
            STEP_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
            STEP_SIGNUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
            STEP_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
            STEP_PROOF: [
                MessageHandler(filters.PHOTO, handle_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_when_photo_needed),
            ],
            STEP_FINAL: [CommandHandler("done", done), CommandHandler("cancel", cancel)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("done", done))
    app.add_error_handler(error_handler)

    # Run the bot (polling). Ensure only one instance runs to avoid getUpdates conflicts.
    logger.info("Starting bot (polling). Make sure only one instance is deployed.")
    app.run_polling()

if __name__ == "__main__":
    main()
