import logging
import os
import aiohttp
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters
)
from dotenv import load_dotenv
import database

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
ADMIN_CHAT_ID = 838476401

# Логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Состояния
ADDING_TASK, REMOVING_TASK, COMPLETING_TASK, CONFIRM_REMOVE, CONFIRM_COMPLETE = range(5)

# Буфер для задач
user_task_buffer = {}

# Главное меню
def main_keyboard(chat_id):
    keyboard = [
        [KeyboardButton("🌦️ Погода"), KeyboardButton("📋 Мои задачи")],
        [KeyboardButton("➕ Добавить задачу"), KeyboardButton("🗑️ Удалить задачу")],
        [KeyboardButton("✅ Завершить задачу"), KeyboardButton("📄 Завершённые задачи")],
        [KeyboardButton("📈 Моя статистика")]
    ]
    if chat_id == ADMIN_CHAT_ID:
        keyboard.append([KeyboardButton("👑 Админка")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Да/Нет меню
def yes_no_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("Да"), KeyboardButton("Нет")]], resize_keyboard=True)

# Погода
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

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await database.init_db()
    chat_id = update.message.chat_id
    username = update.message.from_user.username or "NoName"
    await database.add_user(chat_id, username)
    await update.message.reply_text("✅ Бот запущен!", reply_markup=main_keyboard(chat_id))

# Обработка главного меню
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)

    if text == "🌦️ Погода":
        weather = await get_weather()
        await update.message.reply_text(weather, reply_markup=main_keyboard(chat_id))
        await context.bot.send_photo(chat_id=chat_id, photo="https://upload.wikimedia.org/wikipedia/commons/e/e0/Saint_Petersburg_on_the_world_map.png")

    elif text == "📋 Мои задачи":
        tasks = await database.get_active_tasks(user_id)
        if not tasks:
            await update.message.reply_text("🎉 Нет активных задач!", reply_markup=main_keyboard(chat_id))
        else:
            buttons = [[KeyboardButton(task)] for task in tasks]
            buttons.append([KeyboardButton("🔙 Назад")])
            await update.message.reply_text("📋 Ваши задачи:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))

    elif text == "➕ Добавить задачу":
        await update.message.reply_text("✏️ Напишите задачу (или список задач через перенос строки):")
        return ADDING_TASK

    elif text == "🗑️ Удалить задачу":
        tasks = await database.get_active_tasks(user_id)
        if not tasks:
            await update.message.reply_text("❗ Нет задач для удаления.", reply_markup=main_keyboard(chat_id))
        else:
            buttons = [[KeyboardButton(task)] for task in tasks]
            buttons.append([KeyboardButton("🔙 Назад")])
            await update.message.reply_text("🗑️ Выберите задачу для удаления:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
            return REMOVING_TASK

    elif text == "✅ Завершить задачу":
        tasks = await database.get_active_tasks(user_id)
        if not tasks:
            await update.message.reply_text("❗ Нет задач для завершения.", reply_markup=main_keyboard(chat_id))
        else:
            buttons = [[KeyboardButton(task)] for task in tasks]
            buttons.append([KeyboardButton("🔙 Назад")])
            await update.message.reply_text("✅ Выберите задачу для завершения:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
            return COMPLETING_TASK

    elif text == "📄 Завершённые задачи":
        tasks = await database.get_completed_tasks(user_id)
        if not tasks:
            await update.message.reply_text("📭 Нет завершённых задач.", reply_markup=main_keyboard(chat_id))
        else:
            msg = "\n".join(f"✅ {task}" for task in tasks)
            await update.message.reply_text(f"📄 Завершённые задачи:\n{msg}", reply_markup=main_keyboard(chat_id))

    elif text == "📈 Моя статистика":
        total, completed = await database.get_weekly_stats(user_id)
        await update.message.reply_text(f"📊 Статистика:\nСоздано: {total}\nВыполнено: {completed}", reply_markup=main_keyboard(chat_id))

    elif text == "👑 Админка" and chat_id == ADMIN_CHAT_ID:
        users = await database.get_all_users()
        if users:
            msg = "👑 Зарегистрированные пользователи:\n\n"
            for u in users:
                msg += f"• @{u['username']} (ID: {u['chat_id']})\n"
            await update.message.reply_text(msg, reply_markup=main_keyboard(chat_id))
        else:
            await update.message.reply_text("⛔ Нет зарегистрированных пользователей.", reply_markup=main_keyboard(chat_id))

    elif text == "🔙 Назад":
        await update.message.reply_text("🔙 Главное меню.", reply_markup=main_keyboard(chat_id))
        return ConversationHandler.END

    else:
        await update.message.reply_text("❓ Нажмите кнопку в меню.", reply_markup=main_keyboard(chat_id))

# Добавление задач
async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)
    tasks = update.message.text.split('\n')
    for t in tasks:
        t = t.strip()
        if t:
            await database.add_task(user_id, t)
    await update.message.reply_text("✅ Задача(и) добавлена(ы)!", reply_markup=main_keyboard(chat_id))
    return ConversationHandler.END

# Удаление задач
async def remove_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    task_text = update.message.text
    if task_text == "🔙 Назад":
        await update.message.reply_text("🔙 Отмена удаления.", reply_markup=main_keyboard(chat_id))
        return ConversationHandler.END
    user_task_buffer[chat_id] = task_text
    await update.message.reply_text(f"❓ Удалить задачу '{task_text}'?", reply_markup=yes_no_keyboard())
    return CONFIRM_REMOVE

# Завершение задач
async def complete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    task_text = update.message.text
    if task_text == "🔙 Назад":
        await update.message.reply_text("🔙 Отмена завершения.", reply_markup=main_keyboard(chat_id))
        return ConversationHandler.END
    user_task_buffer[chat_id] = task_text
    await update.message.reply_text(f"❓ Завершить задачу '{task_text}'?", reply_markup=yes_no_keyboard())
    return CONFIRM_COMPLETE

# Подтверждение удаления
async def confirm_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)
    if update.message.text == "Да":
        await database.remove_task(user_id, user_task_buffer[chat_id])
        await update.message.reply_text("🗑️ Задача удалена.", reply_markup=main_keyboard(chat_id))
    else:
        await update.message.reply_text("❌ Удаление отменено.", reply_markup=main_keyboard(chat_id))
    return ConversationHandler.END

# Подтверждение завершения
async def confirm_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)
    if update.message.text == "Да":
        await database.complete_task(user_id, user_task_buffer[chat_id])
        await update.message.reply_text("✅ Задача завершена.", reply_markup=main_keyboard(chat_id))
    else:
        await update.message.reply_text("❌ Завершение отменено.", reply_markup=main_keyboard(chat_id))
    return ConversationHandler.END

# Запуск
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
