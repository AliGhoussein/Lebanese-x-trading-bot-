# bot.py
import re
import time
import logging
from typing import Dict, Any, Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

# ----------------- CONFIG -----------------
# استخدمت القيم اللي اعطيتني ياها
TOKEN = "8452093321:AAEI16NcAIFTHRt1ieKYKe1CQ1qhUfcMgjs"
ADMIN_CHAT_ID = 1530145001  # as integer

# WhatsApp contact link (زر الواتساب)
WHATSAPP_NUMBER = "+96171204714"
WHATSAPP_LINK = f"https://wa.me/{WHATSAPP_NUMBER.lstrip('+')}"

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
# ------------------------------------------

# In-memory storage for users' flows (session). لا يتم مسحها إلا بإعادة تشغيل البوت.
USER_FLOWS: Dict[int, Dict[str, Any]] = {}

# Steps definition (do not change ordering unless intentional)
STEPS = [
    {"key": "full_name", "type": "text", "prompt": "1️⃣ اكتب اسمك الثلاثي\nمثال: Ali Gh Hssein\n"},
    {"key": "email", "type": "email", "prompt": "2️⃣ اكتب بريدك الإلكتروني\nمثال: example.user@mail.com\n"},
    {"key": "phone", "type": "phone", "prompt": "3️⃣ اكتب رقم هاتفك مع رمز بلدك\nمثال: +96171200000\n"},
    {"key": "tg_username", "type": "text", "prompt": "4️⃣ اكتب المعرّف الخاص بك على تلغرام (username)\nمثال: @AliGh\n"},
    # Step 5 & 6: combined prompt flow (we'll ask link + then request account number)
    {"key": "oxshare_account", "type": "text", "prompt": (
        "5️⃣🔗 للانضمام للقناة الخاصة افتح حسابك تحت وكالتنا عن طريق الرابط التالي:\n"
        "https://my.oxshare.com/register?referral=01973820-6aaa-7313-bda5-2ffe0ade1490\n\n"
        "6️⃣ اكتب رقم حسابك الذي أنشأته لدى شركة Oxshare\nمثال: 75775455\n"
    )},
    {"key": "deposit_proof_photo_id", "type": "photo", "prompt": "7️⃣ أرفق صورة لرسالة البريد الإلكتروني (إثبات الإيداع) 📎\n(أجب بإرفاق صورة — لا نقبل كتابات بدل الصورة)\n"},
    {"key": "final_note", "type": "final", "prompt": (
        "8️⃣ أهلاً و سهلاً بك في عائلة Lebanese X Trading،\n"
        "يرجى الانتظار للتدقيق لإضافتك للقناة الخاصة.\n"
        "يمكنك التواصل معنا مباشرة على واتساب للاستفسار:"
        f" {WHATSAPP_NUMBER}\n"
    )},
]

# ---------------- Utility validators ----------------

EMAIL_RE = re.compile(r"^[^@ \t\r\n]+@[^@ \t\r\n]+\.[^@ \t\r\n]+$", re.IGNORECASE)
PHONE_DIGITS_RE = re.compile(r"[0-9]")

def validate_email_simple(email: str) -> bool:
    return bool(EMAIL_RE.match(email.strip()))

def validate_phone_lenient(phone: str) -> bool:
    # Accept + and digits and spaces and parentheses, require at least 6 digits
    digits = "".join(ch for ch in phone if ch.isdigit())
    return len(digits) >= 6

# -------------- Duplicate / Lock handling --------------
# Prevent repeated immediate messages / spamming; auto-release stale locks.
def _is_duplicate_or_locked(user_flow: Dict[str, Any], update_msg_text: str, message_id: Optional[int], dup_window=1.5, lock_timeout=6.0):
    now = time.time()

    # auto-release stale lock
    locked_at = user_flow.get("_locked_at")
    if user_flow.get("locked") and locked_at:
        if now - locked_at > lock_timeout:
            user_flow["locked"] = False
            user_flow["_locked_at"] = None

    if not user_flow.get("locked"):
        return "ok"   # proceed

    # locked == True -> check duplication
    last = user_flow.get("_last_msg", {})
    last_id = last.get("id")
    last_text = last.get("text", "")
    last_ts = last.get("ts", 0)

    if message_id is not None and last_id == message_id:
        return "ignore"

    if last_text == (update_msg_text or "") and (now - last_ts < dup_window):
        return "ignore"

    # otherwise, update last and ask user to wait once
    user_flow["_last_msg"] = {"id": message_id, "ts": now, "text": update_msg_text}
    return "wait"

# ---------------- Flow helpers ----------------
def _start_flow_for_user(user_id: int):
    USER_FLOWS[user_id] = {
        "step_index": 0,
        "answers": {},
        "locked": False,
        "_locked_at": None,
        "_last_msg": None,
    }
    return USER_FLOWS[user_id]

def _get_flow(user_id: int):
    return USER_FLOWS.get(user_id)

def _set_lock(user_flow: Dict[str, Any], locked=True):
    user_flow["locked"] = locked
    user_flow["_locked_at"] = time.time() if locked else None

def _advance_step(user_flow: Dict[str, Any]):
    user_flow["step_index"] = user_flow.get("step_index", 0) + 1

def _current_step(user_flow: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    idx = user_flow.get("step_index", 0)
    if idx < len(STEPS):
        return STEPS[idx]
    return None

# -------------- Core handlers --------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    flow = _start_flow_for_user(user_id)
    # greet user and present first prompt
    welcome = (
        "👋 مرحباً! أنا روبوت خدمة العملاء في فريق Lebanese x trading.\n\n"
        "الرجاء الإجابة على كامل الأسئلة بالشكل الصحيح لضمان خدمتكن بشكل أسرع و أفضل.\n\n"
        "سنبدأ الآن — فقط أجب بحسب المطلوب تحت كل سؤال.\n"
    )
    await update.message.reply_text(welcome)
    # send first prompt
    cur = _current_step(flow)
    if cur:
        await update.message.reply_text(cur["prompt"])
        # set short lock while we wait for user response
        _set_lock(flow, locked=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.effective_user.id
    text = (update.message.text or "").strip()
    message_id = getattr(update.message, "message_id", None)

    flow = _get_flow(user_id)
    if not flow:
        # if no flow started, start automatically
        flow = _start_flow_for_user(user_id)
        await update.message.reply_text("بدّك تبدأ؟ اكتب /start لتشغيل النموذج.")
        return

    # Duplicate/locking control
    lock_check = _is_duplicate_or_locked(flow, text, message_id)
    if lock_check == "ignore":
        # quiet ignore duplicate
        return
    elif lock_check == "wait":
        await update.message.reply_text("⏳ يرجى الانتظار قليلاً...")
        return
    # else ok -> proceed and set lock for processing
    _set_lock(flow, True)

    step = _current_step(flow)
    if not step:
        # finished all steps already
        await update.message.reply_text("✅ تم إنهاء النموذج مسبقاً. شكراً لك.")
        _set_lock(flow, False)
        return

    # If current expected type is photo but user sent text -> reject and ask again
    expected_type = step["type"]
    # Photo handling (user must send a photo object)
    if expected_type == "photo":
        if not update.message.photo:
            # reject
            await update.message.reply_text(
                "❌ الإجابة غير صحيحة: مطلوب إرفاق صورة. الرجاء إرسال الصورة (صورة واحدة واضحة لإثبات الإيداع)."
            )
            # don't advance; release lock after sending rejection
            _set_lock(flow, False)
            return
        # accept photo: take highest-res file_id
        photo_file = update.message.photo[-1]
        file_id = photo_file.file_id
        flow["answers"][step["key"]] = file_id
        _advance_step(flow)
        # proceed to next step immediately
        next_step = _current_step(flow)
        if next_step:
            await update.message.reply_text(next_step["prompt"])
        else:
            # finish flow
            await _finish_flow_for_user(update, context, flow)
        _set_lock(flow, False)
        return

    # For text / email / phone
    if expected_type == "email":
        if not text or not validate_email_simple(text):
            await update.message.reply_text("❌ البريد الإلكتروني غير صحيح. الرجاء إدخال بريد صالح مثل: example.user@mail.com")
            _set_lock(flow, False)
            return
        flow["answers"][step["key"]] = text
        _advance_step(flow)
        next_step = _current_step(flow)
        if next_step:
            await update.message.reply_text(next_step["prompt"])
        else:
            await _finish_flow_for_user(update, context, flow)
        _set_lock(flow, False)
        return

    if expected_type == "phone":
        if not text or not validate_phone_lenient(text):
            await update.message.reply_text("❌ رقم الهاتف غير مقبول. الرجاء إدخال رقم يحتوي على رمز البلد و لا يقل عن 6 أرقام. مثال: +96171200000")
            _set_lock(flow, False)
            return
        flow["answers"][step["key"]] = text
        _advance_step(flow)
        next_step = _current_step(flow)
        if next_step:
            await update.message.reply_text(next_step["prompt"])
        else:
            await _finish_flow_for_user(update, context, flow)
        _set_lock(flow, False)
        return

    # generic text acceptance (with mild leniency)
    if expected_type == "text":
        if not text:
            await update.message.reply_text("❌ الإجابة فارغة، الرجاء إدخال قيمة صحيحة.")
            _set_lock(flow, False)
            return
        flow["answers"][step["key"]] = text
        _advance_step(flow)
        next_step = _current_step(flow)
        if next_step:
            await update.message.reply_text(next_step["prompt"])
        else:
            await _finish_flow_for_user(update, context, flow)
        _set_lock(flow, False)
        return

    # final step handling (type 'final' just sends confirmation)
    if expected_type == "final":
        # store final note if needed
        flow["answers"][step["key"]] = "requested"
        _advance_step(flow)
        await _finish_flow_for_user(update, context, flow)
        _set_lock(flow, False)
        return

async def _finish_flow_for_user(update: Update, context: ContextTypes.DEFAULT_TYPE, flow: Dict[str, Any]):
    """Compile answers and send to admin (only answers), then confirm to user with WhatsApp button."""
    user = update.effective_user
    answers = flow.get("answers", {})

    # prepare admin message: only values (not questions)
    lines = []
    # keep same sequence as STEPS
    for step in STEPS:
        key = step["key"]
        val = answers.get(key)
        if val is None:
            display_val = "(لم يُقدّم)"
        else:
            # if it's a photo file_id, we'll note below and send photo separately
            display_val = val if step["type"] != "photo" else "(مرفق صورة إثبات الإيداع)"
        lines.append(f"{key}: {display_val}")

    admin_text = "📥 طلب تسجيل جديد — الإجابات (قيم فقط):\n\n" + "\n".join(lines) + f"\n\nFrom user: @{user.username or user.id} ({user.id})"

    # send text to admin
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text)
    except Exception as e:
        logger.exception("Failed to send to admin: %s", e)

    # if photo provided, send the photo to admin with a short caption
    photo_id = answers.get("deposit_proof_photo_id")
    if photo_id:
        try:
            await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=photo_id, caption="صورة إثبات الإيداع")
        except Exception as e:
            logger.exception("Failed to send photo to admin: %s", e)

    # final message to user with WhatsApp button
    final_text = (
        "✅ شكراً! تم استلام طلبك بنجاح.\n"
        "سنقوم بالتدقيق وإضافتك للقناة الخاصة قريباً.\n\n"
        "للتواصل السريع اضغط زر الواتساب أدناه:"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📞 تواصل عبر واتساب", url=WHATSAPP_LINK)]])
    await update.message.reply_text(final_text, reply_markup=keyboard)

    # Note: Do NOT delete the flow unless you want to reset it
    # (you requested data not to be erased). Keep it for reference.

# -------------- Command to show current status (admin or user) --------------
async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    flow = _get_flow(user_id)
    if not flow:
        await update.message.reply_text("لم تبدأ أي نموذج بعد. اكتب /start للبدء.")
        return
    step_idx = flow.get("step_index", 0)
    await update.message.reply_text(f"أنت في خطوة رقم {step_idx}/{len(STEPS)}. إجابات حالياً: {list(flow.get('answers', {}).keys())}")

# -------------- Main --------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", my_status))
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_message))

    # Start the Bot
    logger.info("Bot starting (polling)...")
    app.run_polling()

if __name__ == "__main__":
    main()
