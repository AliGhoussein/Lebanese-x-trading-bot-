# bot.py — Modified final script
# Requirements: python-telegram-bot==20.x
# Paste this file as-is (replace existing bot.py), then Commit & Deploy.

import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ========== CONFIG ==========
TOKEN = "8452093321:AAEI16NcAIFTHRt1ieKYKe1CQ1qhUfcMgjs"
ADMIN_CHAT_ID = 1530145001
WHATSAPP_URL = "https://wa.me/96171204714"
# ============================

# Steps definition (order + type)
STEPS = [
    {"key": "full_name", "prompt": "1) 👤 اكتب اسمك الثلاثي كما هو في بطاقتك الرسمية:", "type": "text"},
    {"key": "email", "prompt": "2) 📧 اكتب بريدك الإلكتروني (example@example.com):", "type": "email"},
    {"key": "phone", "prompt": "3) 📱 اكتب رقم هاتفك مع رمز البلد (مثال: +96171234567):", "type": "phone"},
    {"key": "username", "prompt": "4) 💬 اكتب المعرّف الخاص بك على تلغرام (username) مع @:", "type": "username"},
    {
        "key": "info",
        "prompt": (
            "5) 🔗 للانضمام للقناة الخاصة افتح حسابك عبر الرابط التالي:\n"
            "https://my.oxshare.com/register?referral=01973820-6aaa-7313-bda5-2ffe0ade1490\n\n"
            "إذا كان لديك حساب فعلاً لدينا أو عند أحد وكلائنا، اكتب فقط رقم حسابك واسم وكيلك في الرد التالي."
        ),
        "type": "info",
    },
    {"key": "account_combo", "prompt": "6) 🏦 اكتب رقم حسابك لدى Oxshare (ويمكن إضافة اسم الوكيل بعد الرقم أو في سطر جديد):", "type": "account"},
    {"key": "deposit_proof", "prompt": "7) 📸 أرفق صورة لرسالة تأكيد نجاح الإيداع في حسابك (يجب أن تكون صورة):", "type": "photo"},
    {"key": "done", "prompt": "8) 🎉 أهلاً وسهلاً! سيتم الآن إرسال بياناتك للمراجعة.\nيمكنك التواصل عبر واتساب إن رغبت.", "type": "info"},
]

# In-memory flows: chat_id -> {"step": int, "answers": dict}
user_flows = {}

# ---- utilities ----
def merge_multiline(text: str) -> str:
    if "\n" in text:
        parts = [p.strip() for p in text.split("\n") if p.strip()]
        return " ".join(parts)
    return text.strip()

def valid_email(s: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", s.strip()))

def valid_phone(s: str) -> bool:
    return bool(re.fullmatch(r"\+\d{6,15}", s.strip()))

def valid_fullname(s: str) -> bool:
    # at least two words, letters/Arabic letters
    parts = [p for p in s.strip().split() if p]
    if len(parts) < 2:
        return False
    return any(re.search(r"[A-Za-z\u0600-\u06FF]", p) for p in parts)

def valid_username(s: str) -> bool:
    return bool(re.fullmatch(r"@[A-Za-z0-9_]{2,32}", s.strip()))

def parse_account_combo(text: str):
    """
    Return (account_number, agent_name)
    Accepts: "6409074", "6409074 Ali", "6409074\nAli", "رقم 6409074 و الوكيل علي"
    """
    text = merge_multiline(text)
    m = re.search(r"(\d{4,})", text)
    acc = m.group(1) if m else ""
    agent = ""
    if acc:
        after = text.split(acc, 1)[1].strip()
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
        return bool(acc)
    if step_type == "photo":
        return True
    return len(answer.strip()) > 0

# ---- Handlers ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_flows[chat_id] = {"step": 0, "answers": {}}
    welcome = (
        "مرحباً 👋\n"
        "أنا روبوت خدمة العملاء في فريق Lebanese x trading.\n"
        "الرجاء الإجابة على كامل الأسئلة بدقة لضمان خدمتك بسرعة.\n\n"
        f"{STEPS[0]['prompt']}"
    )
    await update.message.reply_text(welcome)
    return

async def ask_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    flow = user_flows.get(chat_id)
    if not flow:
        return await update.message.reply_text("اكتب /start للبدء.")
    i = flow["step"]
    if i >= len(STEPS):
        return
    step = STEPS[i]
    if step["type"] == "info":
        await update.message.reply_text(step["prompt"])
        flow["step"] += 1
        return await ask_next(update, context)
    else:
        return await update.message.reply_text(step["prompt"])

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_flows:
        return await update.message.reply_text("اكتب /start للبدء.")
    flow = user_flows[chat_id]
    i = flow["step"]
    if i >= len(STEPS):
        return await update.message.reply_text("انتهت الخطوات، اكتب /start لبدء جديد.")
    step = STEPS[i]
    key = step["key"]
    step_type = step["type"]

    if step_type == "photo":
        return await update.message.reply_text("❌ هذه الخطوة تتطلب صورة. الرجاء إرسال الصورة بدلاً من نص.")
    raw = update.message.text or ""
    answer = raw.strip()
    if step_type == "account":
        answer = merge_multiline(answer)

    if not validate_answer(answer, step_type, key):
        # custom error messages
        if step_type == "email":
            return await update.message.reply_text("❌ البريد غير صالح. مثال صحيح: name@example.com")
        if step_type == "phone":
            return await update.message.reply_text("❌ رقم الهاتف غير صالح. استخدم الصيغة الدولية مثل: +96171234567")
        if step_type == "username":
            return await update.message.reply_text("❌ اسم المستخدم غير صالح. اكتب username مع @ مثل: @AliGhsein")
        if step_type == "account":
            return await update.message.reply_text("❌ رقم الحساب غير واضح. اكتب رقم حساب مكوّن من 4 أرقام فما فوق، ويمكن إضافة اسم الوكيل بعده.")
        if key == "full_name":
            return await update.message.reply_text("❌ الرجاء كتابة اسمك الثلاثي (اسم ولقب على الأقل).")
        return await update.message.reply_text("❌ الإجابة غير مقبولة. حاول مجدداً.")

    # store answer
    if step_type == "account":
        acc, agent = parse_account_combo(answer)
        flow["answers"]["account_number"] = acc
        if agent:
            flow["answers"]["agent_name"] = agent
    else:
        flow["answers"][key] = answer

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
    i = flow["step"]
    if i >= len(STEPS):
        return await update.message.reply_text("انتهت الخطوات، اكتب /start لبدء جديد.")
    step = STEPS[i]
    if step["type"] != "photo":
        return await update.message.reply_text("❌ في هذه الخطوة نحتاج نصاً، ليست صورة.")
    photo = update.message.photo[-1]
    file_id = photo.file_id
    flow["answers"][step["key"]] = file_id
    flow["step"] += 1
    if flow["step"] >= len(STEPS):
        await send_to_admin(update, context)
    else:
        await ask_next(update, context)

# robust send_to_admin
async def send_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    flow = user_flows.get(chat_id, {})
    answers = flow.get("answers", {})

    if not answers:
        await update.message.reply_text("⚠ حدث خطأ أثناء تجهيز البيانات. الرجاء المحاولة مرة أخرى بـ /start")
        return

    # Compose admin message (answers only, nicely formatted)
    admin_msg = (
        "📩 طلب تسجيل جديد\n\n"
        f"👤 الاسم: {answers.get('full_name', 'غير مذكور')}\n"
        f"📧 البريد: {answers.get('email', 'غير مذكور')}\n"
        f"📱 الهاتف: {answers.get('phone', 'غير مذكور')}\n"
        f"💬 يوزر تلغرام: {answers.get('username', 'غير مذكور')}\n"
        f"🏦 رقم الحساب: {answers.get('account_number', 'غير مذكور')}\n"
        f"🧑‍💼 اسم الوكيل: {answers.get('agent_name', 'غير مذكور')}\n"
    )

    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg)
        # send photo if exists (photo stored under key 'deposit_proof')
        photo_id = answers.get("deposit_proof")
        # previous versions may have used other key names; check alternatives:
        if not photo_id:
            # check common alternative keys:
            photo_id = answers.get("deposit_proof_file_id") or answers.get("deposit_proof_id")
        if photo_id:
            await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=photo_id, caption="🧾 إثبات الإيداع")
    except Exception as e:
        # log and continue
        print(f"Error sending to admin: {e}")

    # Send final message to user with WhatsApp button
    final_prompt = STEPS[-1]["prompt"]
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("تواصل عبر واتساب 📲", url=WHATSAPP_URL)]])
    await update.message.reply_text(final_prompt, reply_markup=keyboard)

    # clear flow
    user_flows.pop(chat_id, None)

# start pingadmin for testing
async def pingadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="📣 Test to admin: البوت يرسل رسائل ✅")
    await update.message.reply_text("تم إرسال رسالة اختبار للإدمن.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pingadmin", pingadmin))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("✅ Bot is running (Lebanese X Trading)")
    app.run_polling()

if __name__ == "__main__":
    main()


