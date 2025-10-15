import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

TOKEN = os.environ["BOT_TOKEN"]

# غيّرها لرقم الشات تبعك إذا بدك توصلك نسخة من الطلب (اختياري)
ADMIN_CHAT_ID = 0

# تعريف الخطوات: type = text/email/info/photo
STEPS = [
    {"key": "full_name", "prompt": "١) اكتب اسمك الثلاثي:", "type": "text"},
    {"key": "email", "prompt": "٢) اكتب بريدك الإلكتروني:", "type": "email"},
    {
        "key": "ox_link",
        "prompt": (
            "٣) للانضمام للقناة الخاصة افتح حساب تحت وكالتنا عبر الرابط:\n"
            "https://my.oxshare.com/register?referral=01973820-6aaa-7313-bda5-2ffe0ade1490\n\n"
            "بعد التسجيل منتابع ✌"
        ),
        "type": "info"  # معلومة فقط، منتابع تلقائياً
    },
    {"key": "account_number", "prompt": "٤) اكتب رقم حسابك الذي أنشأته لدى شركة OXShare:", "type": "text"},
    {"key": "deposit_proof", "prompt": "٥) أرفق صورة لرسالة الإيميل من الشركة بتأكيد نجاح الإيداع (ارفع صورة):", "type": "photo"},
]

def _init_flow(context):
    context.user_data["flow"] = {"step": 0, "answers": {}}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _init_flow(context)
    await update.message.reply_text("أهلاً فيك 👋 رح نمشي خطوة بخطوة. فيك تكتب /cancel بأي وقت للإلغاء.")
    await _ask_next(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("flow", None)
    await update.message.reply_text("تم الإلغاء ✅. فيك تبلّش من جديد بـ /start")

async def _ask_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    flow = context.user_data["flow"]
    i = flow["step"]
    if i >= len(STEPS):
        # ملخّص + رسالة الترحيب الأخيرة
        lines = []
        for s in STEPS:
            key, ptype = s["key"], s["type"]
            if ptype == "info":  # ما منخزّن شي لهاي
                continue
            val = flow["answers"].get(key, "")
            label = s["prompt"].split(") ", 1)[-1]
            lines.append(f"• {label} {('[صورة]' if ptype=='photo' else val)}")
        summary = "✅ تم استلام طلبك:\n" + "\n".join(lines)

        await update.message.reply_text(summary)
        await update.message.reply_text(
            "٦) أهلاً و سهلاً بك في عائلة Lebanese X Trading 🙌\n"
            "يرجى الانتظار للتدقيق لإضافتك للقناة الخاصة."
        )

        # إرسال نسخة للإدارة (اختياري)
        if ADMIN_CHAT_ID and ADMIN_CHAT_ID != 0:
            user = update.effective_user
            who = f"@{user.username}" if user and user.username else f"UserID:{user.id if user else 'unknown'}"
            await context.bot.send_message(ADMIN_CHAT_ID, f"📥 طلب جديد من {who}:\n\n{summary}")
            # إذا فيه صورة إثبات إيداع، جرّب نبعثها كمان
            photo_id = flow["answers"].get("deposit_proof_photo_id")
            if photo_id:
                await context.bot.send_photo(ADMIN_CHAT_ID, photo=photo_id, caption="🧾 إثبات الإيداع")

        context.user_data.pop("flow", None)  # صفّر الفلو
        return

    step = STEPS[i]
    await update.message.reply_text(step["prompt"])

    # إذا الخطوة معلومات فقط، مننتقل فوراً للي بعدها
    if step["type"] == "info":
        flow["step"] += 1
        await _ask_next(update, context)

def _basic_email_ok(s: str) -> bool:
    return ("@" in s) and ("." in s) and (" " not in s)

async def _handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "flow" not in context.user_data:
        return await start(update, context)

    flow = context.user_data["flow"]
    i = flow["step"]
    if i >= len(STEPS):
        return await start(update, context)

    step = STEPS[i]
    text = (update.message.text or "").strip()

    # خطوات نص/إيميل
    if step["type"] in ("text", "email"):
        if step["type"] == "email" and not _basic_email_ok(text):
            return await update.message.reply_text("📧 البريد غير واضح. جرّب تكتب هيك: name@example.com")
        flow["answers"][step["key"]] = text
        flow["step"] += 1
        return await _ask_next(update, context)

    # إذا المطلوب صورة والمستخدم بعث نص
    if step["type"] == "photo":
        return await update.message.reply_text("الرجاء رفع *صورة* لرسالة تأكيد الإيداع 📸.")

async def _handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "flow" not in context.user_data:
        return await start(update, context)

    flow = context.user_data["flow"]
    i = flow["step"]
    if i >= len(STEPS):
        return await start(update, context)

    step = STEPS[i]
    if step["type"] != "photo":
        # إذا مش وقت الصورة، اعتبرها مرفق عابر
        return await update.message.reply_text("تلقيت الصورة 👍 (رح نطلبها بوقتها).")

    # خُذ أكبر دقة من الصور المرسلة
    photo = update.message.photo[-1]
    flow["answers"][step["key"]] = "مرفق"
    flow["answers"]["deposit_proof_photo_id"] = photo.file_id
    flow["step"] += 1
    await _ask_next(update, context)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("cancel", cancel))
app.add_handler(MessageHandler(filters.PHOTO, _handle_photo))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text))

print("✅ البوت شغال (فلو متسلسل)…")
app.run_polling()
