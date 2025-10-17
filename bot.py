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

# ---------------- CONFIG (ضع التوكن والآدمن كما تفضّل) ----------------
ADMIN_CHAT_ID = 1530145001
TOKEN = "8452093321:AAEI16NcAIFTHRt1ieKYKe1CQ1qhUfcMgjs"
WHATSAPP_NUMBER = "+96171204714"
# --------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# In-memory flows: { user_id: {"step": int, "answers": {}} }
FLOWS = {}

# ---- خطوات الأسئلة (معدّلة: أمثلة وهمية، السؤال 5+6 مدموجان) ----
STEPS = [
    {"key": "name", "type": "text", "prompt": "1️⃣ اكتب اسمك الثلاثي\nمثال (وهمي): محمد حمزة خلف 🎯"},
    {"key": "email", "type": "email", "prompt": "2️⃣ اكتب بريدك الإلكتروني\nمثال (وهمي): example.user@mail.com ✉"},
    {"key": "phone", "type": "phone", "prompt": "3️⃣ اكتب رقم هاتفك مع رمز بلدك\nمثال (وهمي): +96171200000 📱"},
    {"key": "username", "type": "username", "prompt": "4️⃣ اكتب المعرّف الخاص بك على تلغرام (username)\nمثال (وهمي): @example_user 🔗"},
    {
        "key": "oxshare_info",
        "type": "text",
        "prompt": (
            "5️⃣ فتح حساب / معلومات الوكيل 🔔\n\n"
            "للانضمام افتح حسابك تحت وكالتنا عبر الرابط:\n"
            "🔗 https://my.oxshare.com/register?referral=01973820-6aaa-7313-bda5-2ffe0ade1490\n\n"
            "إذا عندك حساب مسبقاً: اكتب رقم الحساب واسم الوكيل.\n"
            "مثال (وهمي): 6409074 - الوكيل: علي غصين ✅\n\n"
            "ملاحظة: إن لم تفتح حساب الآن، فقط اكتب: ليس لدي حساب أو اترك info قصيرة."
        ),
    },
    {"key": "deposit_proof", "type": "photo", "prompt": "6️⃣ أرفق صورة لرسالة البريد الإلكتروني التي تُثبت نجاح الإيداع 🖼\n(مطلوبة صورة — إذا أرسلت نصًا سنطلب إعادة الصورة)"},
]
# -------------------------------------------------------------------

# لسهولة التحقق: نمط بسيط (متساهل)
EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")
PHONE_RE = re.compile(r"^\+?\d{6,15}$")  # قبول + و 6-15 رقم

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    FLOWS[uid] = {"step": 0, "answers": {}}

    welcome_text = (
        "👋 مرحباً! أنا روبوت خدمة العملاء - فريق Lebanese X Trading.\n\n"
        "➡ الرجاء الإجابة على كامل الأسئلة بالشكل الصحيح لضمان خدمتكم بشكل أسرع وأفضل.\n"
        "لن يأخذ الأمر أكثر من دقيقة واحدة 🕒\n"
    )
    await update.message.reply_text(welcome_text)
    # أرسل أول سؤال
    await update.message.reply_markdown(STEPS[0]["prompt"])

def lenient_validate(step_type, text):
    text = text.strip()
    if step_type == "text":
        # متساهل: اسم مقبول إن كان يحتوي على حروف أو مسافات (أقل من 2 حرف => رفض)
        if len(text) < 2:
            return False
        # قبول أرقام إن كانت مصحوبة بنص
        return True
    if step_type == "email":
        # متساهل: إذا فيه شكل بسيط @ و . نقبله، وإلا نقبل كـ 'unverified' بدل كره
        return bool(EMAIL_RE.search(text)) or len(text) >= 5
    if step_type == "phone":
        # متساهل: نقبل إذا فيه + أو أرقام بطول منطقي
        return bool(PHONE_RE.match(text)) or (len(re.sub(r"\D", "", text)) >= 6)
    if step_type == "username":
        # متساهل: قبول لو يبدأ بـ@ أو مجرد كلمة
        return text.startswith("@") or (len(text) >= 3)
    return True

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in FLOWS:
        FLOWS[uid] = {"step": 0, "answers": {}}

    flow = FLOWS[uid]
    step_idx = flow["step"]
    step = STEPS[step_idx]

    # إذا الانتظار في خطوة صورة وليس نص
    if step["type"] == "photo":
        await update.message.reply_text("❌ في هذه الخطوة نحتاج صورة (إثبات الإيداع). الرجاء إرسال صورة الآن.")
        return

    text = update.message.text.strip()

    # تحقق متساهل
    ok = lenient_validate(step["type"], text)
    if not ok:
        await update.message.reply_text("❌ الإجابة غير مقبولة، حاول بطريقة أوضح من فضلك.")
        return

    flow["answers"][step["key"]] = text
    flow["step"] += 1

    # إذا اكتمل
    if flow["step"] >= len(STEPS):
        await finalize(update, context)
        return

    # أرسل السؤال التالي مع إيموجي تحفيزي
    next_prompt = STEPS[flow["step"]]["prompt"]
    await update.message.reply_markdown("✅ ممتاز! الآن:\n\n" + next_prompt)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in FLOWS:
        FLOWS[uid] = {"step": 0, "answers": {}}

    flow = FLOWS[uid]
    step_idx = flow["step"]
    step = STEPS[step_idx]

    if step["type"] != "photo":
        await update.message.reply_text("❌ لم نطلب صورة في هذه الخطوة، رجاءً أرسل نصاً.")
        return

    # استلم آخر صورة (أفضل جودة)
    photo = update.message.photo[-1]
    file_id = photo.file_id
    flow["answers"][step["key"]] = file_id
    flow["step"] += 1

    if flow["step"] >= len(STEPS):
        await finalize(update, context)
        return

    next_prompt = STEPS[flow["step"]]["prompt"]
    await update.message.reply_markdown("✅ تم استلام الصورة!\n\n" + next_prompt)

async def finalize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    flow = FLOWS.get(uid, {"answers": {}, "step": 0})
    answers = flow["answers"]

    # رساله للإدمن — فقط الإجابات (بدون نص الأسئلة)
    admin_msg_lines = [
        "📥 جديد: إجابات مستخدم",
        f"🆔 user_id: {uid}",
    ]
    # المخرجات تظهر فقط الإجابات المتوفرة
    fields = [
        ("الاسم", "name"),
        ("البريد الإلكتروني", "email"),
        ("الهاتف", "phone"),
        ("اليوزرنيم", "username"),
        ("معلومات Oxshare/الوكيل", "oxshare_info"),
    ]
    for label, key in fields:
        val = answers.get(key, "— لم يُقدّم —")
        admin_msg_lines.append(f"{label}: {val}")

    # رقم الحساب إن وُجد في نفس الحقل أو منفصل
    # صورة الإثبات يتم إرسالها منفصلة
    admin_text = "\n".join(admin_msg_lines)
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text)

    # إذا فيه صورة إثبات، نرسلها كـ photo للادمن
    if "deposit_proof" in answers:
        try:
            await context.bot.send_photo(
                chat_id=ADMIN_CHAT_ID, photo=answers["deposit_proof"], caption="🧾 إثبات الإيداع"
            )
        except Exception as e:
            logger.exception("Failed to send proof photo to admin: %s", e)

    # رسالة للمستخدم: تأكيد مع زر واتساب
    wa_url = f"https://wa.me/{WHATSAPP_NUMBER.replace('+', '')}"
    keyboard = InlineKeyboardMarkup.from_button(
        InlineKeyboardButton(text="📲 تواصل عبر واتساب الآن", url=wa_url)
    )

    confirmation = (
        "🎉 شكرًا! تم استلام معلوماتك بنجاح ✅\n\n"
        "⏳ سيتم التحقق من بياناتك لإضافتك إلى القناة الخاصة.\n"
        "إذا رغبت بالتواصل الفوري، اضغط زر واتساب أدناه للتواصل معنا الآن."
    )
    await update.message.reply_markdown(confirmation, reply_markup=keyboard)

    # لا نحذف البيانات من الذاكرة (يمكن تعديل لاحقاً لحفظ دائم)
    # نحتفظ بتسجيل بسيط في اللوج
    logger.info("Collected answers for user %s: %s", uid, answers)

def run():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    # شغل polling (واحد فقط)
    app.run_polling()

if __name__ == "__main__":
    run()
