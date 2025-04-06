
import logging
import os
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

API_KEY = "1ecccdc989505c1ca2d3d75b74e98f49"
CITY = "Saint Petersburg"
URL = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}&units=metric&lang=en"

WEBHOOK_URL = "https://checkcoach-bot.onrender.com"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("🌦️ Check Weather")],
        [KeyboardButton("📋 Check Schedule Loaded")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        text="✅ Bot is running! Here are your buttons:",
        reply_markup=reply_markup
    )

async def main():
    TOKEN = os.getenv("TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    await app.initialize()
    await app.bot.set_webhook(WEBHOOK_URL)
    await app.start()
    await asyncio.Event().wait()

    # Устанавливаем webhook
    await app.bot.set_webhook(WEBHOOK_URL)

    # Запускаем сервер на Render
    await app.start_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8443)),
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
