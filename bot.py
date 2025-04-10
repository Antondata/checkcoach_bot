import logging
import os
import aiohttp
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters
)
from dotenv import load_dotenv
import database

load_dotenv()
TOKEN = os.getenv("TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
ADMIN_CHAT_ID = 838476401

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

ADDING_TASK, REMOVING_TASK, COMPLETING_TASK, CONFIRM_REMOVE, CONFIRM_COMPLETE = range(5)

user_task_buffer = {}

# Основное меню
def main_keyboard():
    keyboard = [
        [KeyboardButton("🌦️ Погода"), KeyboardButton("📋 Мои задачи")],
        [KeyboardButton("➕ Добавить задачу"), KeyboardButton("🗑️ Удалить задачу")],
        [KeyboardButton("✅ Завершить задачу"), KeyboardButton("📄 Завершённые задачи")],
        [KeyboardButton("📈 Моя статистика"), KeyboardButton("👑 Админка")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Да/Нет
def yes_no_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("Да"), KeyboardButton("Нет")]], resize_keyboard=True)

# Погода + Карта
async def get_weather():
    try:
        async with aiohttp.ClientSession() as session:
            url = f"http://api.openweathermap.org/data/2.5/weather?q=Saint Petersburg&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
            async with session.get(url) as response:
                data = await response.json()
                temp = data['main']['temp']
                description = data['weather'][0]['description']
                wind = data['wind']['speed']
                return f"🌍 Санкт-Петербург\n🌡️ {temp}°C\n☁️ {description}\n🌬️ {wind} м/с"
    except Exception as e:
        logging.error(f"Ошибка погоды: {e}")
        return "❗ Ошибка получения погоды."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await database.init_db()
    chat_id = update.message.chat_id
    username = update.message.from_user.username or "NoName"
    await database.add_user(chat_id, username)
    await update.message.reply_text("✅ Бот запущен!", reply_markup=main_keyboard())

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)

    if text == "🌦️ Погода":
        weather = await get_weather()
        await update.message.reply_text(weather, reply_markup=main_keyboard())
        await context.bot.send_photo(chat_id=chat_id, photo="https://upload.wikimedia.org/wikipedia/commons/e/e0/Saint_Petersburg_on_the_world_map.png")

    elif text == "📋 Мои задачи":
        tasks = await database.get_active_tasks(user_id)
        if not tasks:
            await update.message.reply_text("🎉 Нет активных задач!", reply_markup=main_keyboard())
        else:
            buttons = [[KeyboardButton(task)] for task in tasks]
            buttons.append([KeyboardButton("🔙 Назад")])
            await update.message.reply_text("📋 Ваши задачи:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))

    elif text == "➕ Добавить задачу":
        await update.message.reply_text("✏️ Напишите задачу (или несколько задач построчно):")
        return ADDING_TASK

    elif text == "🗑️ Удалить задачу":
        tasks = await database.get_active_tasks(user_id)
        if not tasks:
            await update.message.reply_text("❗ Нет задач для удаления.", reply_markup=main_keyboard())
        else:
            buttons = [[KeyboardButton(task)] for task in tasks]
            buttons.append([KeyboardButton("🔙 Назад")])
            await update.message.reply_text("🗑️ Выберите задачу для удаления:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
            return REMOVING_TASK

    elif text == "✅ Завершить задачу":
        tasks = await database.get_active_tasks(user_id)
        if not tasks:
            await update.message.reply_text("❗ Нет задач для завершения.", reply_markup=main_keyboard())
        else:
            buttons = [[KeyboardButton(task)] for task in tasks]
            buttons.append([KeyboardButton("🔙 Назад")])
            await update.message.reply_text("✅ Выберите задачу для завершения:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
            return COMPLETING_TASK

    elif text == "📄 Завершённые задачи":
        tasks = await database.get_completed_tasks(user_id)
        if not tasks:
            await update.message.reply_text("📭 Нет завершённых задач.", reply_markup=main_keyboard())
        else:
            msg = "\n".join(f"✅ {task}" for task in tasks)
            await update.message.reply_text(f"📄 Завершённые задачи:\n{msg}", reply_markup=main_keyboard())

    elif text == "📈 Моя статистика":
        total, completed = await database.get_weekly_stats(user_id)
        await update.message.reply_text(f"📊 Статистика:\nСоздано задач: {total}\nВыполнено: {completed}", reply_markup=main_keyboard())

    elif text == "👑 Админка":
        if chat_id == ADMIN_CHAT_ID:
            users = await database.get_all_users()
            if users:
                msg = "👑 Зарегистрированные пользователи:\n\n"
                for u in users:
                    msg += f"• @{u['username']} (ID: {u['chat_id']})\n"
                await update.message.reply_text(msg, reply_markup=main_keyboard())
            else:
                await update.message.reply_text("⛔ Нет зарегистрированных пользователей.", reply_markup=main_keyboard())
        else:
            await update.message.reply_text("⛔ Доступ запрещён.", reply_markup=main_keyboard())

    else:
        await update.message.reply_text("❓ Пожалуйста, выберите кнопку в меню.", reply_markup=main_keyboard())

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)
    tasks = update.message.text.split('\n')
    for t in tasks:
        t = t.strip()
        if t:
            await database.add_task(user_id, t)
    await update.message.reply_text("✅ Задачи добавлены!", reply_markup=main_keyboard())
    return ConversationHandler.END

async def remove_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_task_buffer[chat_id] = update.message.text
    await update.message.reply_text(f"❓ Удалить задачу '{update.message.text}'?", reply_markup=yes_no_keyboard())
    return CONFIRM_REMOVE

async def complete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_task_buffer[chat_id] = update.message.text
    await update.message.reply_text(f"❓ Завершить задачу '{update.message.text}'?", reply_markup=yes_no_keyboard())
    return CONFIRM_COMPLETE

async def confirm_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)
    if update.message.text == "Да":
        await database.remove_task(user_id, user_task_buffer[chat_id])
        await update.message.reply_text("🗑️ Задача удалена.", reply_markup=main_keyboard())
    else:
        await update.message.reply_text("❌ Отмена удаления.", reply_markup=main_keyboard())
    return ConversationHandler.END

async def confirm_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)
    if update.message.text == "Да":
        await database.complete_task(user_id, user_task_buffer[chat_id])
        await update.message.reply_text("✅ Задача завершена.", reply_markup=main_keyboard())
    else:
        await update.message.reply_text("❌ Отмена завершения.", reply_markup=main_keyboard())
    return ConversationHandler.END

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu)],
        states={
            ADDING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task)],
            REMOVING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_task)],
            COMPLETING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, complete_task)],
            CONFIRM_REMOVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_remove)],
            CONFIRM_COMPLETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_complete)],
        },
        fallbacks=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    app.run_webhook(
        listen="127.0.0.1",
        port=8443,
        url_path=TOKEN,
        webhook_url=f"https://pitg.online/{TOKEN}",
        allowed_updates=Update.ALL_TYPES
    )
