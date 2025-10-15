import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from datetime import datetime

# إعدادات البوت
TOKEN = "8452093321:AAEI16NcAIFTHRt1ieKYKe1CQ1qhUfcMgjs"
ADMIN_CHAT_ID = 1530145001

# إعداد نظام التسجيل
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# تسلسل الأسئلة الجديد
STEPS = [
    {"key": "name", "prompt": "1️⃣ اكتب اسمك الثلاثي", "type": "text"},
    {"key": "email", "prompt": "2️⃣ اكتب بريدك الإلكتروني", "type": "email"},
    {"key": "phone", "prompt": "3️⃣ اكتب رقم هاتفك مع رمز البلد", "type": "text"},
    {"key": "telegram_user", "prompt": "4️⃣ اكتب المعرّف الخاص بك على تلغرام (username)", "type": "text"},
    {
        "key": "info_link",
        "prompt": "5️⃣ للانضمام للقناة الخاصة افتح حسابك تحت وكالتنا عن طريق الرابط التالي:\nhttps://my.oxshare.com/register?referral=01973820-6aaa-7313-bda5-2ffe0ade1490",
        "type": "info",
    },
    {"key": "account_number", "prompt": "6️⃣ اكتب رقم حسابك الذي أنشأته لدى شركة Oxshare", "type": "text"},
    {
        "key": "deposit_proof_photo_id",
        "prompt": "7️⃣ أرفق صورة لرسالة البريد الإلكتروني التي تم إرسالها إليك من قبل الشركة بنجاح الإيداع في حسابك",
        "type": "photo",
    },
    {
        "key": "done",
        "prompt": "8️⃣ أهلاً وسهلاً بك في عائلة Lebanese X Trading، يرجى الانتظار للتدقيق لإضافتك للقناة الخاصة.\nيمكنك التواصل معنا مباشرة على تطبيق واتساب للاستفسار:\n📞 +96171204714",
        "type": "info",
    },
]

# ذاكرة مؤقتة لتتبع المحادثات
user_flows = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البدء"""
    user_id = update.message.chat_id
    user_flows[user_id] = {"step": 0, "answers": {}}
    await update.message.reply_text("👋 أهلاً بك! لنبدأ الطلب معك خطوة بخطوة:")
    await ask_next_question(update, context)


async def ask_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يسأل المستخدم السؤال التالي"""
    user_id = update.message.chat_id
    flow = user_flows[user_id]
    step = flow["step"]

    if step >= len(STEPS):
        await update.message.reply_text("✅ تم استلام جميع البيانات. شكراً لك!")
        return

    current = STEPS[step]
    if current["type"] == "info":
        await update.message.reply_text(current["prompt"])
        flow["step"] += 1
        await ask_next_question(update, context)
    else:
        await update.message.reply_text(current["prompt"])


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يتعامل مع إجابات المستخدم النصية"""
    user_id = update.message.chat_id
    if user_id not in user_flows:
        await update.message.reply_text("ابدأ بكتابة /start للبدء من جديد.")
        return

    flow = user_flows[user_id]
    step = flow["step"]
    if step >= len(STEPS):
        await update.message.reply_text("انتهيت من الأسئلة.")
        return

    current = STEPS[step]
    if current["type"] == "photo":
        await update.message.reply_text("يرجى إرسال صورة في هذه المرحلة.")
        return

    # حفظ الجواب
    flow["answers"][current["key"]] = update.message.text.strip()
    flow["step"] += 1
    await ask_next_question(update, context)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يتعامل مع الصور"""
    user_id = update.message.chat_id
    if user_id not in user_flows:
        await update.message.reply_text("ابدأ بكتابة /start للبدء من جديد.")
        return

    flow = user_flows[user_id]
    step = flow["step"]
    if step >= len(STEPS):
        return

    current = STEPS[step]
    if current["type"] != "photo":
        await update.message.reply_text("يرجى إرسال نص وليس صورة.")
        return

    # حفظ معرف الصورة
    photo_id = update.message.photo[-1].file_id
    flow["answers"][current["key"]] = photo_id
    flow["step"] += 1

    # إرسال ملخص للإدارة
    if ADMIN_CHAT_ID and ADMIN_CHAT_ID != 0:
        user = update.effective_user
        who = f"@{user.username}" if (user and user.username) else f"UserID:{user.id if user else 'unknown'}"
        lines = ["📥 طلب جديد"]
        lines.append(f"👤 العميل: {who}")
        lines.append("───")
        for s in STEPS:
            key, ptype = s["key"], s["type"]
            if ptype == "info":
                continue
            label = s["prompt"].split(') ', 1)[-1].strip().rstrip(':')
            val = flow["answers"].get(key, "")
            if ptype == "photo":
                val = "📎 صورة مرفقة"
            lines.append(f"• {label}: {val}")
        admin_text = "\n".join(lines)

        await context.bot.send_message(ADMIN_CHAT_ID, admin_text)

        # إرسال الصورة إذا موجودة
        photo_id = flow["answers"].get("deposit_proof_photo_id")
        if photo_id:
            await context.bot.send_photo(ADMIN_CHAT_ID, photo=photo_id, caption="🧾 إثبات الإيداع")

    # متابعة السؤال التالي (الختامي)
    await ask_next_question(update, context)


async def pingadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختبار الإرسال إلى الإدارة"""
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="📣 Test to admin: الإرسال شغّال ✅")
    await update.message.reply_text("تم إرسال رسالة تجريبية للإدارة.")


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pingadmin", pingadmin))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("✅ البوت شغال (Lebanese X Trading)...")
    app.run_polling()


if _name_ == "_main_":
    main()


