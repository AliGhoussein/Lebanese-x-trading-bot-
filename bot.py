# bot.py
import re
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

# ---------------------------
# CONFIGURATION (You provided)
# ---------------------------
ADMIN_CHAT_ID = 1530145001
TOKEN = "8452093321:AAEI16NcAIFTHRt1ieKYKe1CQ1qhUfcMgjs"
WHATSAPP_NUMBER = "+96171204714"  # button link will use wa.me
OXSHARE_LINK = "https://my.oxshare.com/register?referral=01973820-6aaa-7313-bda5-2ffe0ade1490"
# ---------------------------

# logger basic config (no admin startup notifications)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# In-memory storage for flows. We will NOT auto-delete data (per request).
FLOWS: Dict[int, Dict[str, Any]] = {}

# Steps definition: key, type, prompt
STEPS = [
    {"key": "full_name", "type": "text", "prompt": "1️⃣ الرجاء كتابة اسمك الثلاثي:"},
    {"key": "email", "type": "email", "prompt": "2️⃣ من فضلك اكتب بريدك الإلكتروني (مثال: example@gmail.com):"},
    {"key": "phone", "type": "phone", "prompt": "3️⃣ اكتب رقم هاتفك مع رمز بلدك (مثال: +96171... أو 96171...):"},
    {"key": "username", "type": "username", "prompt": "4️⃣ اكتب المعرف الخاص بك على تلغرام (username):"},
    {"key": "oxshare_instruction", "type": "info", "prompt": (
        "5️⃣ للانضمام للقناة الخاصة افتح حسابك تحت وكالتنا عبر الرابط:\n"
        f"{OXSHARE_LINK}\n\n"
        "إذا لديك حساب فعلاً لدينا أو عند أحد وكلائنا، اكتب فقط رقم حسابك واسم وكيلك."
    )},
    {"key": "oxshare_account", "type": "text", "prompt": "6️⃣ اكتب رقم حسابك الذي أنشأته لدى شركة Oxshare (وأضف اسم الوكيل إن وُجد):"},
    {"key": "deposit_proof", "type": "photo", "prompt": "7️⃣ أرفق صورة رسالة البريد الإلكتروني التي تثبت نجاح الإيداع (أرسل صورة، لا تكتب نصًا):"},
    {"key": "done_msg", "type": "final", "prompt": (
        "8️⃣ شكراً! ستصلك رسالة تثبيت وإن شاء الله بنضيفك للقناة قريباً.\n"
        f"للتواصل الفوري عبر واتساب: {WHATSAPP_NUMBER}"
    )},
]

# Validators
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?\d{6,15}$")  # basic check


def get_step_index(user_flow: Dict[str, Any]) -> int:
    return user_flow.get("step", 0)


def set_next_step(user_flow: Dict[str, Any]) -> None:
    user_flow["step"] = get_step_index(user_flow) + 1


def format_admin_message(flow: Dict[str, Any]) -> str:
    lines = []
    # Order by STEPS sequence but include only answers keys
    for s in STEPS:
        k = s["key"]
        if k in ("oxshare_instruction", "done_msg"):
            continue
        val = flow.get("answers", {}).get(k)
        label = {
            "full_name": "👤 الاسم",
            "email": "📧 البريد",
            "phone": "📱 الهاتف",
            "username": "💬 يوزر تلغرام",
            "oxshare_account": "🏦 رقم حساب (Oxshare)",
            "deposit_proof": "🧾 إثبات الإيداع (photo)",
        }.get(k, k)
        # For photo, we will send the file separately; show placeholder text
        if val is None:
            display = "—"
        else:
            display = str(val)
        lines.append(f"{label}: {display}")
    return "📩 طلب تسجيل جديد\n\n" + "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    uid = user.id
    # Initialize flow if not exist
    if uid not in FLOWS:
        FLOWS[uid] = {"answers": {}, "step": 0}
    flow = FLOWS[uid]

    # Welcome message (as requested)
    welcome_text = (
        "مرحباً 👋\n\n"
        "أنا روبوت خدمة العملاء في فريق Lebanese X Trading.\n"
        "الرجاء الإجابة على كامل الأسئلة بالشكل الصحيح لضمان خدمتكم بشكل أسرع و أفضل.\n\n"
        "نبدأ الآن:"
    )
    await update.message.reply_markdown(welcome_text)
    # Ask first prompt
    await ask_current_question(update, context)


async def ask_current_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    flow = FLOWS.get(uid)
    if flow is None:
        FLOWS[uid] = {"answers": {}, "step": 0}
        flow = FLOWS[uid]
    idx = get_step_index(flow)
    # skip info steps if needed (but we present them as normal)
    if idx >= len(STEPS):
        # All done
        await finalize_flow_for_user(update, context, uid)
        return
    step = STEPS[idx]
    # If asking for photo, prompt user to send photo
    await update.message.reply_text(step["prompt"])


def normalize_username(val: str) -> str:
    val = val.strip()
    if not val.startswith("@"):
        val = "@" + val
    return val


def validate_answer(step_type: str, text: Optional[str], update: Update) -> (bool, Optional[str]):
    # returns (is_valid, normalized_value or None)
    if step_type == "text":
        if not text or text.strip() == "":
            return False, None
        # simple name validation allowed (for account numbers etc this function used elsewhere)
        return True, text.strip()
    if step_type == "email":
        if not text:
            return False, None
        t = text.strip()
        if EMAIL_RE.match(t):
            return True, t
        return False, None
    if step_type == "phone":
        if not text:
            return False, None
        t = text.strip()
        # add + if starts with country code without plus (common)
        if t.isdigit() and len(t) >= 6:
            t2 = "+" + t
        else:
            t2 = t
        # basic check
        if PHONE_RE.match(t2):
            # normalize to + format
            if not t2.startswith("+"):
                t2 = "+" + t2
            return True, t2
        return False, None
    if step_type == "username":
        if not text:
            return False, None
        t = text.strip()
        t = t.replace(" ", "")
        # minimal check: should be 5-32 chars roughly
        if len(t.replace("@", "")) < 2:
            return False, None
        return True, normalize_username(t)
    if step_type == "info":
        # info step doesn't require user input; we'll accept empty and proceed
        return True, None
    if step_type == "final":
        return True, None
    return False, None


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if uid not in FLOWS:
        # if user didn't start properly, start a flow
        FLOWS[uid] = {"answers": {}, "step": 0}
    flow = FLOWS[uid]
    idx = get_step_index(flow)
    if idx >= len(STEPS):
        # already done
        await update.message.reply_text("شكراً — لمزيد من المساعدة أرسل /start")
        return
    step = STEPS[idx]
    stype = step["type"]

    # If current step expects photo, tell user they must send a photo
    if stype == "photo":
        await update.message.reply_text("❌ هذا السؤال يتطلب إرسال صورة. الرجاء إرسال صورة فحسب.")
        return

    text = update.message.text
    valid, value = validate_answer(stype, text, update)
    if not valid:
        # prepare nice message
        if stype == "email":
            await update.message.reply_text("❌ البريد غير صحيح. حاول مرة أخرى بالشكل: example@gmail.com")
        elif stype == "phone":
            await update.message.reply_text("❌ رقم الهاتف غير صحيح. أرسل رقمك مع رمز الدولة مثلاً: +96171xxxxxxx")
        elif stype == "username":
            await update.message.reply_text("❌ اسم المستخدم غير صالح. اكتب اليوزر بدون مسافات، مثال: @AliGhsein")
        else:
            await update.message.reply_text("❌ الإجابة غير صحيحة أو فارغة، حاول مجدداً.")
        return

    # store answer
    if "answers" not in flow:
        flow["answers"] = {}
    if value is not None:
        flow["answers"][step["key"]] = value
    else:
        # info or final, no value
        flow["answers"][step["key"]] = None

    # move to next step
    set_next_step(flow)

    # if next step is final info, we should prompt (final prompt or photo)
    # Ask next question or finalize
    next_idx = get_step_index(flow)
    if next_idx >= len(STEPS):
        await finalize_flow_for_user(update, context, uid)
        return
    next_step = STEPS[next_idx]
    await update.message.reply_text(next_step["prompt"])


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if uid not in FLOWS:
        FLOWS[uid] = {"answers": {}, "step": 0}
    flow = FLOWS[uid]
    idx = get_step_index(flow)
    if idx >= len(STEPS):
        await update.message.reply_text("تم إنهاء النموذج. لإعادة التقديم أرسل /start")
        return
    step = STEPS[idx]
    if step["type"] != "photo":
        await update.message.reply_text("ليست مطلوبة صورة الآن. الرجاء متابعة التسلسل.")
        return

    # accept the largest photo
    photo = update.message.photo
    if not photo:
        await update.message.reply_text("❌ لم يتم العثور على صورة. الرجاء إرسال صورة (jpg/png) فقط.")
        return
    file_id = photo[-1].file_id
    # store the file_id
    flow["answers"][step["key"]] = file_id

    # increment step
    set_next_step(flow)

    # proceed to finalize or next prompt
    next_idx = get_step_index(flow)
    if next_idx >= len(STEPS):
        await finalize_flow_for_user(update, context, uid)
        return
    next_step = STEPS[next_idx]
    await update.message.reply_text(next_step["prompt"])


async def finalize_flow_for_user(update: Update, context: ContextTypes.DEFAULT_TYPE, uid: int) -> None:
    """
    Send collected answers to admin (ONLY answers, no full question dumps).
    Do not delete flow from memory.
    """
    flow = FLOWS.get(uid)
    if not flow:
        await update.message.reply_text("لم يتم العثور على بيانات لتقديمها.")
        return

    # Format admin text
    admin_text = format_admin_message(flow)
    # send message to admin (retry safe)
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text)
    except Exception as e:
        logger.exception("Failed to send admin message: %s", e)
        # Don't crash; we continue

    # send photo if provided
    photo_id = flow.get("answers", {}).get("deposit_proof")
    if photo_id:
        try:
            await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=photo_id, caption="🧾 إثبات الإيداع")
        except Exception:
            logger.exception("Failed to send deposit photo to admin")

    # Reply to user: final message + whatsapp button
    final_text = (
        "🎉 شكراً! تم استلام معلوماتك بنجاح.\n"
        "⏳ يرجى الانتظار ريثما يتم التحقق من بياناتك. يمكنك التواصل مباشرة عبر واتساب:"
    )
    wa_url = f"https://wa.me/{WHATSAPP_NUMBER.replace('+','')}"
    keyboard = InlineKeyboardMarkup.from_button(
        InlineKeyboardButton(text="📲 تواصل عبر واتساب", url=wa_url)
    )
    # send final text with button
    try:
        await context.bot.send_message(chat_id=uid, text=final_text, reply_markup=keyboard)
    except Exception:
        # fallback; user may be in privacy mode
        try:
            await context.bot.send_message(chat_id=uid, text=final_text)
        except Exception:
            logger.exception("Failed to send final message to user %s", uid)

    # IMPORTANT: per your request, DO NOT delete the flow from memory.
    # So we keep FLOWS[uid] as-is. If you later want to clear it use separate admin command.


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    # do not delete flow, only mark canceled
    if uid in FLOWS:
        FLOWS[uid]["canceled"] = True
    await update.message.reply_text("تم إلغاء العملية. لإعادة التقديم أرسل /start")


def main() -> None:
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))

    # Text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    # Photo messages
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Run polling
    app.run_polling()


if __name__ == "__main__":
    main()
