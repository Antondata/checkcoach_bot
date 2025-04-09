import logging
import os
import aiohttp
import aiosqlite
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler
)
from datetime import time
from dotenv import load_dotenv
import database

# Load environment variables
load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")
CITY = "Saint Petersburg"
TOKEN = os.getenv("TOKEN")
ADMIN_CHAT_ID = 838476401

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

ADDING_TASK, REMOVING_TASK = range(2)

async def get_weather():
    try:
        async with aiohttp.ClientSession() as session:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}&units=metric&lang=en"
            async with session.get(url) as response:
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

def main_keyboard():
    keyboard = [
        [KeyboardButton("🌦️ Погода"), KeyboardButton("📋 Мои задачи")],
        [KeyboardButton("➕ Добавить задачу"), KeyboardButton("🗑️ Удалить задачу")],
        [KeyboardButton("📈 Моя статистика"), KeyboardButton("👑 Админка")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await database.init_db()
    chat_id = update.message.chat_id
    username = update.message.from_user.username or "NoName"
    await database.add_user(chat_id, username)

    await update.message.reply_text(
        "✅ Бот запущен! Готов помочь с задачами!",
        reply_markup=main_keyboard()
    )

    context.job_queue.run_daily(morning_task, time=time(hour=7, minute=0), chat_id=chat_id)
    context.job_queue.run_daily(evening_task, time=time(hour=20, minute=0), chat_id=chat_id)
    context.job_queue.run_daily(clear_old_tasks, time=time(hour=2, minute=0))
    context.job_queue.run_daily(weekly_statistics, time=time(hour=20, minute=0), days=(6,), chat_id=chat_id)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)

    if text == "🌦️ Погода":
        weather = await get_weather()
        await update.message.reply_text(f"🌤️ Погода в Санкт-Петербурге:\n{weather}", reply_markup=main_keyboard())

    elif text == "📋 Мои задачи":
        tasks = await database.get_tasks(user_id)
        if not tasks:
            await update.message.reply_text("🎉 У вас нет активных задач!", reply_markup=main_keyboard())
        else:
            task_buttons = [[KeyboardButton(task)] for task in tasks]
            task_buttons.append([KeyboardButton("🔙 Назад")])
            reply_markup = ReplyKeyboardMarkup(task_buttons, resize_keyboard=True)
            await update.message.reply_text("📋 Ваши задачи:", reply_markup=reply_markup)

    elif text == "➕ Добавить задачу":
        await update.message.reply_text("✏️ Напишите новую задачу:")
        return ADDING_TASK

    elif text == "🗑️ Удалить задачу":
        tasks = await database.get_tasks(user_id)
        if not tasks:
            await update.message.reply_text("❗ Нет задач для удаления.", reply_markup=main_keyboard())
        else:
            task_buttons = [[KeyboardButton(task)] for task in tasks]
            task_buttons.append([KeyboardButton("🔙 Назад")])
            reply_markup = ReplyKeyboardMarkup(task_buttons, resize_keyboard=True)
            await update.message.reply_text("🗑️ Выберите задачу для удаления:", reply_markup=reply_markup)
            return REMOVING_TASK

    elif text == "📈 Моя статистика":
        total, completed = await database.get_weekly_stats(user_id)
        await update.message.reply_text(f"📊 Статистика за неделю:\nСоздано задач: {total}\nВыполнено задач: {completed}", reply_markup=main_keyboard())

    elif text == "👑 Админка":
        if chat_id == ADMIN_CHAT_ID:
            users = await database.get_all_users()
            msg = "👑 Список пользователей:\n\n"
            for u in users:
                msg += f"ID: {u['chat_id']}, Username: {u['username']}\n"
            await update.message.reply_text(msg, reply_markup=main_keyboard())
        else:
            await update.message.reply_text("⛔ Доступ запрещён.", reply_markup=main_keyboard())

    elif text == "🔙 Назад":
        await update.message.reply_text("🔙 Возвращаемся в меню.", reply_markup=main_keyboard())

    else:
        await update.message.reply_text("❓ Пожалуйста, выберите кнопку.", reply_markup=main_keyboard())

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_text = update.message.text
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)
    await database.add_task(user_id, task_text)
    await update.message.reply_text(f"✅ Задача добавлена: {task_text}", reply_markup=main_keyboard())
    return ConversationHandler.END

async def remove_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_text = update.message.text
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)
    await database.remove_task(user_id, task_text)
    await update.message.reply_text(f"🗑️ Задача удалена: {task_text}", reply_markup=main_keyboard())
    return ConversationHandler.END

async def morning_task(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    user_id = await database.get_user_id(chat_id)
    tasks = await database.get_tasks(user_id)

    if tasks:
        message = "🌞 Доброе утро! Ваши задачи на сегодня:\n\n" + "\n".join(f"- {task}" for task in tasks)
    else:
        message = "🌞 Доброе утро! Сегодня у вас нет задач."

    await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=main_keyboard())

async def evening_task(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    user_id = await database.get_user_id(chat_id)
    tasks = await database.get_tasks(user_id)

    if tasks:
        message = "🌙 Ваши незавершенные задачи:\n\n" + "\n".join(f"- {task}" for task in tasks)
    else:
        message = "🌙 Все задачи на сегодня выполнены! Отличная работа!"

    await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=main_keyboard())

async def clear_old_tasks(context: ContextTypes.DEFAULT_TYPE):
    await database.clear_old_tasks()

async def weekly_statistics(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    user_id = await database.get_user_id(chat_id)
    total, completed = await database.get_weekly_stats(user_id)
    await context.bot.send_message(chat_id=chat_id, text=f"📊 Статистика за неделю:\nСоздано задач: {total}\nВыполнено задач: {completed}")

async def main():
    await database.init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        states={
            ADDING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task)],
            REMOVING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_task)],
        },
        fallbacks=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    await app.bot.set_webhook(url="https://pitg.online/webhook")

    await app.run_webhook(
        listen="0.0.0.0",
        port=443,
        url_path="webhook",
        webhook_url="https://pitg.online/webhook"
    )

if __name__ == "__main__":
    asyncio.run(main())
