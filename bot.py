import logging
import os
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)

API_KEY = "1ecccdc989505c1ca2d3d75b74e98f49"
CITY = "Saint Petersburg"
URL = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}&units=metric&lang=en"

user_tasks = {}
scheduler_started = False

def get_weather():
    try:
        response = requests.get(URL)
        data = response.json()
        temp = data['main']['temp']
        description = data['weather'][0]['description']
        wind = data['wind']['speed']
        weather_message = f"Temperature: {temp}°C\nWeather: {description}\nWind: {wind} m/s"
        return weather_message
    except Exception as e:
        logging.error(f"Error getting weather: {e}")
        return "Failed to fetch weather."

def read_checklist():
    try:
        with open("checklist.txt", "r", encoding="utf-8") as file:
            tasks = [line.strip() for line in file if line.strip()]
        return tasks
    except Exception as e:
        logging.error(f"Error reading checklist.txt: {e}")
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("Button 1")],
        [KeyboardButton("Button 2")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        text="Test buttons",
        reply_markup=reply_markup
    )

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎉 Great job! I'm proud of you!")

async def miss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💪 No worries! Tomorrow will be better!")

async def morning_task(context: ContextTypes.DEFAULT_TYPE):
    weather = get_weather()
    checklist = read_checklist()
    message = f"🌞 Good morning, champion! 💪\n\n📍 Weather in Saint Petersburg:\n{weather}\n\n📋 Today's plan:"
    chat_id = context.job.chat_id
    user_tasks[chat_id] = checklist
    keyboard = [[task] for task in checklist]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
    await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup)

async def task_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text

    if text == "🌦️ Check Weather":
        weather = get_weather()
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

async def evening_task(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=context.job.chat_id, text="🌙 How was your day? Type /done if you completed everything or /miss if not.")

async def main():
    global scheduler_started

    TOKEN = os.getenv("TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("miss", miss))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, task_done))

    if not scheduler_started:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(morning_task, 'cron', hour=7, minute=0, args=[app.bot])
        scheduler.add_job(evening_task, 'cron', hour=20, minute=0, args=[app.bot])
        scheduler.start()
        scheduler_started = True

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
