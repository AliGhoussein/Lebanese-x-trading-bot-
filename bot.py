# bot.py — Lebanese X Trading (Stable + Retry + Relaxed Validation)
# Requirements: python-telegram-bot==20.x
# Usage: paste as-is, then Commit & Deploy. (You can replace TOKEN/ADMIN_CHAT_ID if تريد)

import re
import asyncio
import logging
from typing import Dict, Any, Tuple, Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ------------------ CONFIG ------------------
# إذا حابب تستخدم environment variables بدل الثوابت، بدّل هنا.
TOKEN = "8452093321:AAEI16NcAIFTHRt1ieKYKe1CQ1qhUfcMgjs"
ADMIN_CHAT_ID = 1530145001
WHATSAPP_URL = "https://wa.me/96171204714"
# عدد محاولات الإرسال للإدمن لو فشل أول مرة
ADMIN_SEND_RETRIES = 3
# -------------------------------------------

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(_name_)

# Steps (one-by-one)
STEPS = [
    {"key": "full_name", "prompt": "1) 👤 الرجاء إدخال اسمك الثلاثي كما في بطاقتك الرسمية:", "type": "text"},
    {"key": "email", "prompt": "2) 📧 الرجاء إدخال بريدك الإلكتروني الصحيح (مثال: name@example.com):", "type": "email"},
    {"key": "phone", "prompt": "3) 📱 الرجاء كتابة رقم هاتفك مع رمز البلد (مثال: +96171234567 أو 96171234567):", "type": "phone"},
    {"key": "username", "prompt": "4) 💬 اكتب معرفك على Telegram (username) — مع أو بدون @:", "type": "username"},
    {
        "key": "info",
        "prompt": (
            "5) 🔗 للانضمام للقناة الخاصة افتح حسابك عبر:\n"
            "https://my.oxshare.com/register?referral=01973820-6aaa-7313-bda5-2ffe0ade1490\n\n"
            "إذا عندك حساب مسبقاً مع وكيلنا، اكتب *رقم الحساب واسم الوكيل* في الرد التالي (يمكنك كتابتهم في سطر واحد أو سطرين)."
        ),
        "type": "info",
    },
    {"key": "account_combo", "prompt": "6) 🏦 اكتب رقم حسابك لدى Oxshare (ويمكن إضافة اسم الوكيل بعد الرقم أو في سطر جديد):", "type": "account"},
    {"key": "deposit_proof", "prompt": "7) 📸 أرسل صورة لرسالة تأكيد الإيداع (يجب أن تكون صورة — لا نقبل نصاً هنا).", "type": "photo"},
    {"key": "done", "prompt": "8) 🎉 شكراً! سترى زر التواصل مع فريقنا في الرسالة التالية.", "type": "info"},
]

# In-memory flows: chat_id -> {"step": int, "answers": {...}}
FLOWS: Dict[int, Dict[str, Any]] = {}


# ------------------ Validators & Helpers ------------------

def merge_multiline(text: str) -> str:
    if "\n" in text:
        parts = [p.strip() for p in text.split("\n") if p.strip()]
        return " ".join(parts)
    return text.strip()


def normalize_phone(s: str) -> str:
    s = s.strip()
    s = re.sub(r"[^\d+]", "", s)  # remove spaces and non-digit except '+'
    if s.startswith("00"):
        s = "+" + s[2:]
    if not s.startswith("+"):
        # assume missing plus — add plus
        s = "+" + s
    return s


def valid_email(s: str) -> bool:
    s = s.strip()
    # permissive regex — practical for most emails
    return bool(re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", s))


def valid_phone(s: str) -> bool:
    s = s.strip()
    s_norm = re.sub(r"[^\d]", "", s)
    return 7 <= len(s_norm) <= 15


def valid_fullname(s: str) -> bool:
    parts = [p for p in s.strip().split() if p]
    return len(parts) >= 2 and any(re.search(r"[A-Za-z\u0600-\u06FF]", p) for p in parts)


def valid_username(s: str) -> bool:
    s = s.strip()
    if s.startswith("@"):
        s = s[1:]
    return bool(re.fullmatch(r"[A-Za-z0-9_]{2,32}", s))


def parse_account_combo(text: str) -> Tuple[str, str]:
    """
    Extract account number (first 4+ digits) and agent name (rest).
    Accepts single or multiline.
    """
    text = merge_multiline(text)
    m = re.search(r"(\d{4,})", text)
    acc = m.group(1) if m else ""
    agent = ""
    if acc:
        after = text.split(acc, 1)[1].strip()
        after = re.sub(r"^(?:[-:,\.]|\s)(?:الوكيل|اسم الوكيل|وكيل|و)?\s", "", after, flags=re.IGNORECASE)
        agent = after.strip()
    return acc, agent


def validate_answer(answer: str, step_type: str, key: str = "") -> bool:
    ans = answer.strip()
    if step_type == "text" and key == "full_name":
        return valid_fullname(ans)
    if step_type == "email":
        return valid_email(ans)
    if step_type == "phone":
        return valid_phone(ans)
    if step_type == "username":
        return valid_username(ans)
    if step_type == "account":
        acc, _ = parse_account_combo(ans)
        return bool(acc)
    if step_type == "photo":
        return True
    return len(ans) > 0


# ------------------ Bot Handlers ------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    FLOWS[chat_id] = {"step": 0, "answers": {}}
    welcome = (
        "مرحباً 👋\n\n"
        "أنا روبوت خدمة العملاء في فريق Lebanese X Trading.\n"
        "الرجاء الإجابة على كامل الأسئلة بدقة لضمان خدمتك بشكل أسرع.\n\n"
        "سنبدأ الآن 👇"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")

    # small admin connectivity test (non-blocking)
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="🔔 [نوت] بوت Lebanese X Trading: تم تشغيل جلسة جديدة.")
    except Exception as e:
        # print to logs — لا نوقف المستخدم
        logger.warning("Admin test message failed: %s", e)

    # send first question
    await ask_next(update, context)


async def ask_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    flow = FLOWS.get(chat_id)
    if not flow:
        await update.message.reply_text("حدث خطأ — الرجاء كتابة /start للبدء.")
        return
    i = flow["step"]
    if i >= len(STEPS):
        return
    step = STEPS[i]
    if step["type"] == "info":
        await update.message.reply_text(step["prompt"], parse_mode="Markdown")
        flow["step"] += 1
        # immediately advance to next (info is just informational)
        await ask_next(update, context)
        return
    await update.message.reply_text(step["prompt"], parse_mode="Markdown")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in FLOWS:
        await update.message.reply_text("اضغط /start للبدء.")
        return

    flow = FLOWS[chat_id]
    i = flow["step"]
    if i >= len(STEPS):
        await update.message.reply_text("انتهت الخطوات، ارسل /start لبدء جديد.")
        return

    step = STEPS[i]
    key = step["key"]
    step_type = step["type"]

    if step_type == "photo":
        await update.message.reply_text("📎 هذه الخطوة تحتاج صورة — الرجاء إرسال الصورة بدل النص.")
        return

    raw = update.message.text or ""
    answer = merge_multiline(raw)

    # special normalize for phone and username
    if step_type == "phone":
        # allow missing plus, we'll normalize if valid
        if raw.strip().startswith("+"):
            normalized = normalize_phone(raw)
        else:
            normalized = normalize_phone(raw)  # add + if missing
        # validate on digits
        if not validate_answer(normalized, step_type, key):
            await update.message.reply_text("❌ رقم هاتف غير صالح. مثال صحيح: +96171234567")
            return
        answer = normalized
    elif step_type == "username":
        # store username with leading @
        u = raw.strip()
        if not u.startswith("@"):
            u = "@" + u
        if not validate_answer(u, step_type, key):
            await update.message.reply_text("❌ اسم المستخدم غير صالح. مثال: @AliGhsein")
            return
        answer = u
    else:
        if not validate_answer(answer, step_type, key):
            # custom messages for clarity
            if step_type == "email":
                await update.message.reply_text("❌ البريد غير صحيح. مثال: name@example.com")
            elif step_type == "text" and key == "full_name":
                await update.message.reply_text("❌ اكتب اسمك الثلاثي (اسم ولقب على الأقل).")
            elif step_type == "account":
                await update.message.reply_text("❌ رقم الحساب غير واضح. اكتب رقم الحساب (4 أرقام فما فوق) ويمكنك إضافة اسم الوكيل.")
            else:
                await update.message.reply_text("❌ الإجابة غير مقبولة — حاول مجدداً.")
            return

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
        # finished -> send to admin
        await send_to_admin(update, context)
    else:
        await ask_next(update, context)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in FLOWS:
        await update.message.reply_text("اضغط /start للبدء.")
        return

    flow = FLOWS[chat_id]
    i = flow["step"]
    if i >= len(STEPS):
        await update.message.reply_text("انتهت الخطوات، ارسل /start لبدء جديد.")
        return

    step = STEPS[i]
    if step["type"] != "photo":
        await update.message.reply_text("❌ الآن كان مطلوباً نصًّا، ليس صورة.")
        return

    photo = update.message.photo[-1]
    file_id = photo.file_id
    flow["answers"][step["key"]] = file_id

    flow["step"] += 1
    if flow["step"] >= len(STEPS):
        await send_to_admin(update, context)
    else:
        await ask_next(update, context)


# send to admin with retries and logging
async def send_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    flow = FLOWS.get(chat_id, {})
    answers = flow.get("answers", {})

    if not answers:
        await update.message.reply_text("⚠ حدث خطأ أثناء معالجة إجاباتك. الرجاء إعادة المحاولة بـ /start.")
        return

    admin_text = (
        "📩 طلب تسجيل جديد\n\n"
        f"👤 الاسم: {answers.get('full_name', 'غير مذكور')}\n"
        f"📧 البريد: {answers.get('email', 'غير مذكور')}\n"
        f"📱 الهاتف: {answers.get('phone', 'غير مذكور')}\n"
        f"💬 يوزر تلغرام: {answers.get('username', 'غير مذكور')}\n"
        f"🏦 رقم الحساب: {answers.get('account_number', 'غير مذكور')}\n"
        f"🧑‍💼 اسم الوكيل: {answers.get('agent_name', 'غير مذكور')}\n"
    )

    sent = False
    last_exception: Optional[Exception] = None
    for attempt in range(1, ADMIN_SEND_RETRIES + 1):
        try:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text, parse_mode="Markdown")
            # send photo if exists
            photo_id = answers.get("deposit_proof") or answers.get("deposit_proof_file_id") or answers.get("deposit_proof_id")
            if photo_id:
                await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=photo_id, caption="🧾 إثبات الإيداع")
            sent = True
            logger.info("تم إرسال الطلب للإدمن (attempt %s).", attempt)
            break
        except Exception as e:
            last_exception = e
            logger.warning("فشل إرسال الطلب للإدمن (attempt %s): %s", attempt, e)
            # backoff small delay
            await asyncio.sleep(1 * attempt)

    if not sent:
        # أخبر المستخدم أن هناك تأخير في الإرسال واطبع السبب في اللوج
        logger.error("لم يتمكن البوت من إرسال الطلب للإدمن بعد %s محاولات. آخر خطأ: %s", ADMIN_SEND_RETRIES, last_exception)
        await update.message.reply_text("✅ تم استقبال بياناتك، لكن واجهتنا مشكلة فنية أثناء إرسالها للإدارة — سيتم المحاولة وإبلاغك لاحقاً.")
    else:
        # reply to user with final message and WhatsApp button (send in two messages to ensure button shows)
        final_text = (
            "🎉 شكراً! تم استلام معلوماتك بنجاح.\n"
            "⏳ يرجى الانتظار ريثما يتم التحقق من بياناتك، وسنوافيك بالتحديث."
        )
        await update.message.reply_text(final_text, parse_mode="Markdown")
        # send WhatsApp button as separate message (more reliable display)
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📲 تواصل عبر واتساب", url=WHATSAPP_URL)]])
        await context.bot.send_message(chat_id=chat_id, text="يمكنك التواصل معنا عبر الزر أدناه 👇", reply_markup=keyboard)

    # cleanup
    FLOWS.pop(chat_id, None)


# small ping command for testing admin delivery
async def pingadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="📣 اختبار: البوت يرسل رسائل إلى الإدمن ✅")
        await update.message.reply_text("تم إرسال اختبار إلى الإدمن.")
    except Exception as e:
        logger.exception("فشل إرسال اختبار للإدمن: %s", e)
        await update.message.reply_text(f"فشل إرسال الاختبار: {e}")


# ------------------ App bootstrap ------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pingadmin", pingadmin))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("بدء تشغيل البوت — Lebanese X Trading")
    app.run_polling()


if __name__ == "__main__":
    main()
