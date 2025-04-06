
import logging
import os
import aiohttp
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

async def get_weather():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(URL) as response:
                data = await response.json()
                temp = data['main']['temp']
                description = data['weather'][0]['description']
                wind = data['wind']['speed']
                weather_message = f"Temperature: {temp}°C\nWeather: {description}\nWind: {wind} m/s"
                return weather_message
    except Exception as e:
        logging.error(f"Error getting weather: {e}")
        return "Failed to fetch weather."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("Check Weather")],
        [KeyboardButton("Check Schedule Loaded")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        text="Bot is running! Here are your buttons:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "Check Weather":
        weather = await get_weather()
        await update.message.reply_text(f"Current weather in Saint Petersburg:\n{weather}")

    elif text == "Check Schedule Loaded":
        await update.message.reply_text("Schedule for today is loaded!")

async def main():
    TOKEN = os.getenv("TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("weather", button_handler))
    app.add_handler(CommandHandler("schedule", button_handler))
    app.add_handler(CommandHandler("check", button_handler))
    app.add_handler(CommandHandler("done", button_handler))
    app.add_handler(CommandHandler("miss", button_handler))
    app.add_handler(CommandHandler("cancel", button_handler))
    app.add_handler(CommandHandler("stop", button_handler))

    app.add_handler(CommandHandler("Check Weather", button_handler))
    app.add_handler(CommandHandler("Check Schedule Loaded", button_handler))

    app.add_handler(CommandHandler("Button 1", button_handler))
    app.add_handler(CommandHandler("Button 2", button_handler))

    await app.initialize()
    await app.bot.set_webhook(WEBHOOK_URL)
    await app.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
