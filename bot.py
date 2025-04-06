
import logging
import os
import aiohttp
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)
from datetime import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")
CITY = "Saint Petersburg"
URL = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}&units=metric&lang=en"
TOKEN = os.getenv("TOKEN")

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

user_tasks = {}

async def get_weather():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(URL) as response:
                if response.status != 200:
                    return "❗ Failed to get weather data."
                data = await response.json()
                temp = data['main']['temp']
                description = data['weather'][0]['description']
                wind = data['wind']['speed']
                return f"Temperature: {temp}°C\nWeather: {description}\nWind: {wind} m/s"
    except Exception as e:
        logging.error(f"Weather API error: {e}")
        return "❗ Error fetching weather."

def read_checklist():
    try:
        if not os.path.exists("checklist.txt"):
            with open("checklist.txt", "w", encoding="utf-8") as f:
                f.write("Wake up\nExercise\nWork on project\nRead a book\nGo to sleep\n")
        with open("checklist.txt", "r", encoding="utf-8") as file:
            return [line.strip() for line in file if line.strip()]
    except Exception as e:
        logging.error(f"Error reading checklist.txt: {e}")
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("🌦️ Check Weather")],
        [KeyboardButton("📋 Check Schedule Loaded")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "✅ Bot is running! I will send you today's tasks at 7:00 AM and ask for your progress at 8:00 PM.",
        reply_markup=reply_markup
    )

    chat_id = update.message.chat_id

    # Schedule personal jobs
    context.job_queue.run_daily(morning_task, time=time(hour=7, minute=0), chat_id=chat_id)
    context.job_queue.run_daily(evening_task, time=time(hour=20, minute=0), chat_id=chat_id)

async def task_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text

    if text == "🌦️ Check Weather":
        weather = await get_weather()
        await update.message.reply_text(f"🌤️ Current weather in Saint Petersburg:\n{weather}")
        return

    if text == "📋 Check Schedule Loaded":
        await update.message.reply_text("✅ Schedule for today is loaded!")
        return

    if chat_id in user_tasks and text in user_tasks[chat_id]:
        user_tasks[chat_id].remove(text)
        if not user_tasks[chat_id]:
            await update.message.reply_text("🎉 All tasks completed! Well done!")
        else:
            keyboard = [[task] for task in user_tasks[chat_id]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
            await update.message.reply_text(f"✅ Done: {text}", reply_markup=reply_markup)
    else:
        await update.message.reply_text("❓ Task not found or already completed.")

async def morning_task(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    weather = await get_weather()
    checklist = read_checklist()
    user_tasks[chat_id] = checklist

    message = f"🌞 Good morning, champion! 💪\n\n📍 Weather in Saint Petersburg:\n{weather}\n\n📋 Today's plan:"
    keyboard = [[task] for task in checklist]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)

    await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup)

async def evening_task(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    await context.bot.send_message(chat_id=chat_id, text="🌙 How was your day? Type /done if you completed everything or /miss if not.")

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎉 Great job! I'm proud of you!")

async def miss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💪 No worries! Tomorrow will be better!")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("miss", miss))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, task_done))

    port = int(os.environ.get('PORT', 8443))
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url=f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/"
    )

if __name__ == "__main__":
    main()
