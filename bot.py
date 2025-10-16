# bot.py — Lebanese X Trading Bot (no email_validator)
# Requires: python-telegram-bot==20.5 (or 20.x)

import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ====== إعداداتك ======
TOKEN = "8452093321:AAEI16NcAIFTHRt1ieKYKe1CQ1qhUfcMgjs"
ADMIN_CHAT_ID = 1530145001
WHATSAPP_URL = "https://wa.me/96171204714"

# ====== تسلسل الخطوات ======
STEPS = [
    {"key": "full_name", "prompt": "👤 يرجى إدخال اسمك الثلاثي كما هو في بطاقتك الرسمية:", "type": "text"},
    {"key": "email", "prompt": "📧 أدخل بريدك الإلكتروني الصحيح للتواصل الرسمي:", "type": "email"},
    {"key": "phone", "prompt": "📱 اكتب رقم هاتفك مع رمز البلد (مثال: +96171234567):", "type": "phone"},
    {"key": "username", "prompt": "💬 اكتب المعرّف الخاص بك على تلغرام (username) ويبدأ بـ @:", "type": "username"},
    {
        "key": "info",
        "prompt": (
            "🔗 للانضمام للقناة الخاصة افتح حسابك تحت وكالتنا عبر الرابط التالي:\n"
            "https://my.oxshare.com/register?referral=01973820-6aaa-7313-bda5-2ffe0ade1490\n\n"
            "إذا كان لديك حساب فعلاً لدينا أو عند أحد وكلائنا، اكتب فقط رقم حسابك واسم وكيلك في الرد التالي."
        ),
        "type": "info",
    },
    {"key": "account_combo", "prompt": "🏦 اكتب رقم حسابك لدى شركة Oxshare (ويمكن إضافة اسم الوكيل بعد الرقم أو في سطر جديد):", "type": "account"},
    {"key": "deposit_proof", "prompt": "📸 أرسل *صورة* لرسالة البريد الإلكتروني التي تؤكد نجاح الإيداع في حسابك:", "type": "photo"},
    {"key": "done", "prompt": "🎉 أهلاً وسهلاً بك في عائلة Lebanese X Trading!\nيرجى الانتظار للتدقيق لإضافتك للقناة الخاصة.\n📞 يمكنك التواصل معنا مباشرة على واتساب بالزر أدناه.", "type": "info"},
]

# حالة المستخدمين
user_flows = {}  # chat_id -> {"step": int, "answers": dict}

# ====== أدوات تدقيق وتهيئة ======
def merge_multiline(text: str) -> str:
    if "\n" in text:
        parts = [p.strip() for p in text.split("\n") if p.strip()]
        return " ".join(parts)
    return text.strip()

def valid_email(s: str) -> bool:
    # Regex عملي وبسيط
    return bool(re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", s.strip()))

def valid_phone(s: str) -> bool:
    return bool(re.fullmatch(r"\+\d{6,15}", s.strip()))

def valid_fullname(s: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF\s]{2,}", s.strip()))

def valid_username(s: str) -> bool:
    return bool(re.fullmatch(r"@[A-Za-z0-9_]{3,32}", s.strip()))

def parse_account_combo(text: str):
    """
    يستخرج رقم الحساب (أول رقم بطول 4+ خانات) واسم الوكيل (إن وُجد) من نفس السطر أو من سطرين.
    أمثلة مقبولة:
      "6409074"
      "6409074 علي غصين"
      "رقمي 6409074 والوكيل علي غصين"
      "6409074\nعلي غصين"
    """
    text = merge_multiline(text)
    num_match = re.search(r"(\d{4,})", text)
    acc = num_match.group(1) if num_match else ""
    agent = ""
    if acc:
        after = text.split(acc, 1)[1].strip()
        # احذف كلمات ربط شائعة
        after = re.sub(r"^(?:[-:,\.]|\s)(?:والوكيل|الوكيل|اسم الوكيل|وكيل|و)?\s", "", after, flags=re.IGNORECASE)
        agent = after.strip()
    return acc, agent

def validate_answer(answer: str, step_type: str, key: str = "") -> bool:
    if step_type == "text" and key == "full_name":
        return valid_fullname(answer)
    if step_type == "email":
        return valid_email(answer)
    if step_type == "phone":
        return valid_phone(answer)
    if step_type == "username":
        return valid_username(answer)
    if step_type == "account":
        acc, _ = parse_account_combo(answer)
        return bool(acc)  # لازم يوجد رقم حساب
    if step_type == "photo":
        return True
    return len(answer.strip()) > 0

# ====== Handlers ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_flows[chat_id] = {"step": 0, "answers": {}}
    welcome = (
        "مرحباً 👋\n\n"
        "أنا روبوت خدمة العملاء في فريق Lebanese X Trading.\n"
        "الرجاء الإجابة على *كافة الأسئلة بدقة وبالشكل الصحيح* لضمان خدمتكم بشكل أسرع وأفضل.\n\n"
        "لنبدأ 👇"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")
    await ask_next(update, context)

async def ask_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    flow = user_flows.get(chat_id)
    if not flow:
        return await update.message.reply_text("حدث خطأ، أرسل /start لإعادة المحاولة.")

    i = flow["step"]
    if i >= len(STEPS):
        return

    step = STEPS[i]
    if step["type"] == "info":
        await update.message.reply_text(step["prompt"], parse_mode="Markdown")
        flow["step"] += 1
        return await ask_next(update, context)
    else:
        return await update.message.reply_text(step["prompt"], parse_mode="Markdown")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_flows:
        return await update.message.reply_text("اكتب /start للبدء.")

    flow = user_flows[chat_id]
    step = STEPS[flow["step"]]
    key, step_type = step["key"], step["type"]

    # إذا متوقع صورة ممنوع نص
    if step_type == "photo":
        return await update.message.reply_text("📎 هذه الخطوة تتطلب *صورة* وليست نصاً. الرجاء إرسال الصورة المطلوبة.")

    raw = update.message.text or ""
    answer = raw.strip()

    if step_type == "account":
        answer = merge_multiline(answer)

    if not validate_answer(answer, step_type, key):
        return await update.message.reply_text("❌ الإجابة غير صحيحة، يرجى المحاولة مجدداً بالشكل المطلوب.")

    # تخزين الإجابة
    if step_type == "account":
        acc, agent = parse_account_combo(answer)
        flow["answers"]["account_number"] = acc
        if agent:
            flow["answers"]["agent_name"] = agent
    else:
        flow["answers"][key] = answer

    # تقدم
    flow["step"] += 1
    if flow["step"] >= len(STEPS):
        await send_to_admin(update, context)
    else:
        await ask_next(update, context)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_flows:
        return await update.message.reply_text("اكتب /start للبدء.")

    flow = user_flows[chat_id]
    step = STEPS[flow["step"]]

    if step["type"] != "photo":
        return await update.message.reply_text("✍ هذه الخطوة تتطلب *كتابة نص* وليست صورة.")

    photo_id = update.message.photo[-1].file_id
    flow["answers"][step["key"]] = photo_id

    flow["step"] += 1
    if flow["step"] >= len(STEPS):
        await send_to_admin(update, context)
    else:
        await ask_next(update, context)

async def send_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    answers = user_flows.get(chat_id, {}).get("answers", {})

    # رسالة الإدمن — الأجوبة فقط
    msg = (
        "📩 طلب تسجيل جديد\n\n"
        f"👤 الاسم: {answers.get('full_name', 'غير مذكور')}\n"
        f"📧 البريد: {answers.get('email', 'غير مذكور')}\n"
        f"📱 الهاتف: {answers.get('phone', 'غير مذكور')}\n"
        f"💬 Username: {answers.get('username', 'غير مذكور')}\n"
        f"🏦 رقم الحساب: {answers.get('account_number', 'غير مذكور')}\n"
        f"🧑‍💼 اسم الوكيل: {answers.get('agent_name', 'غير مذكور')}\n"
    )
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg)

    if "deposit_proof" in answers:
        await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=answers["deposit_proof"],
            caption="🧾 إثبات الإيداع",
        )

    # رسالة الختام للمستخدم + زر واتساب
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("تواصل عبر واتساب 📲", url=WHATSAPP_URL)]]
    )
    await update.message.reply_text(STEPS[-1]["prompt"], reply_markup=keyboard)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("✅ البوت يعمل الآن (Lebanese X Trading)")
    app.run_polling()

if __name__ == "__main__":
    main()
