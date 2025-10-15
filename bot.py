from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 🔑 حط التوكن الخاص فيك يلي عطاك ياه BotFather هون بين علامات التنصيص
TOKEN = "8452093321:AAEkKLqr5FP_7TAwWwaKyMUdQDcD_mIMBUE"
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلا وسهلا 👋! أنا Lebanese X Trading Bot، كيف فيني ساعدك اليوم؟")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))

print("✅ البوت شغال... روح جرّب /start على التلغرام")
app.run_polling()