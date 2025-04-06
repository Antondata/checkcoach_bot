from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import asyncio

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("🌦️ Check Weather")],
        [KeyboardButton("📋 Check Schedule Loaded")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "✅ Bot is running! Choose an option:",
        reply_markup=reply_markup
    )

async def main():
    app = ApplicationBuilder().token("YOUR_BOT_TOKEN_HERE").build()
    app.add_handler(MessageHandler(filters.Regex('^/start$'), start))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())