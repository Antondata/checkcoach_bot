import logging
import os
import aiohttp
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, filters, ContextTypes
)
from dotenv import load_dotenv
import database
from datetime import datetime, timedelta

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
CITY = "Saint Petersburg"
ADMIN_CHAT_ID = 838476401

# Логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Состояния
ADDING_TEXT, SELECTING_DATE, CONFIRM_FILE, WAITING_FILE = range(4)

# Главная клавиатура
def main_keyboard():
    keyboard = [
        [KeyboardButton("➕ Добавить задачу"), KeyboardButton("🎤 Голосовая задача")],
        [KeyboardButton("📋 Мои задачи"), KeyboardButton("📄 Завершённые задачи")],
        [KeyboardButton("🌦️ Погода"), KeyboardButton("📈 Статистика"), KeyboardButton("👑 Админка")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Клавиатура выбора даты
def date_keyboard():
    dates = ["Сегодня", "Завтра", "Указать дату вручную"]
    return ReplyKeyboardMarkup([[KeyboardButton(d)] for d in dates], resize_keyboard=True)

# Да/Нет клавиатура
def yes_no_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("Да"), KeyboardButton("Нет")]], resize_keyboard=True)

# Получение погоды
async def get_weather():
    try:
        async with aiohttp.ClientSession() as session:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
            async with session.get(url) as response:
                data = await response.json()
                temp = data['main']['temp']
                description = data['weather'][0]['description']
                wind = data['wind']['speed']
                return f"🌍 Погода в {CITY}:\n🌡️ Температура: {temp}°C\n🌥️ Описание: {description}\n🌬️ Ветер: {wind} м/с"
    except Exception as e:
        logging.error(f"Ошибка погоды: {e}")
        return "❗ Ошибка получения погоды."

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await database.init_db()
    chat_id = update.message.chat_id
    username = update.message.from_user.username or "NoName"
    await database.add_user(chat_id, username)
    await update.message.reply_text("✅ Бот готов к работе!", reply_markup=main_keyboard())

# Главное меню
async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)

    if text == "🌦️ Погода":
        weather = await get_weather()
        await update.message.reply_text(weather, reply_markup=main_keyboard())

    elif text == "➕ Добавить задачу":
        await update.message.reply_text("✏️ Напишите одну или несколько задач (каждую с новой строки):")
        return ADDING_TEXT

    elif text == "🎤 Голосовая задача":
        await update.message.reply_text("🎙️ Отправьте голосовое сообщение:")
        return WAITING_FILE

    elif text == "📋 Мои задачи":
        tasks = await database.get_active_tasks(user_id)
        if not tasks:
            await update.message.reply_text("🎉 Нет активных задач!", reply_markup=main_keyboard())
        else:
            msg = "\n".join([f"📝 {task[0]}" for task in tasks])
            await update.message.reply_text(f"📋 Ваши задачи:\n{msg}", reply_markup=main_keyboard())

    elif text == "📄 Завершённые задачи":
        tasks = await database.get_completed_tasks(user_id)
        if not tasks:
            await update.message.reply_text("📭 Нет завершённых задач.", reply_markup=main_keyboard())
        else:
            msg = "\n".join([f"✅ {task[0]}" for task in tasks])
            await update.message.reply_text(f"📄 Завершённые задачи:\n{msg}", reply_markup=main_keyboard())

    elif text == "📈 Статистика":
        total, completed = 10, 5  # Псевдостатистика
        await update.message.reply_text(f"📊 Статистика:\nСоздано: {total}\nЗавершено: {completed}", reply_markup=main_keyboard())

    elif text == "👑 Админка":
        if chat_id == ADMIN_CHAT_ID:
            users = await database.get_all_users()
            msg = "👑 Пользователи:\n" + "\n".join([f"{u['username']} ({u['chat_id']})" for u in users])
            await update.message.reply_text(msg, reply_markup=main_keyboard())
        else:
            await update.message.reply_text("⛔ Доступ запрещён.", reply_markup=main_keyboard())

    else:
        await update.message.reply_text("❓ Выберите действие через меню.", reply_markup=main_keyboard())

# Добавление текста задачи
async def add_task_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['task_text'] = update.message.text
    await update.message.reply_text("📅 Выберите дату выполнения:", reply_markup=date_keyboard())
    return SELECTING_DATE

# Выбор даты
async def select_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Сегодня":
        context.user_data['due_date'] = datetime.now().strftime('%Y-%m-%d')
    elif text == "Завтра":
        context.user_data['due_date'] = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        context.user_data['due_date'] = None
    await update.message.reply_text("📎 Хотите прикрепить файл?", reply_markup=yes_no_keyboard())
    return CONFIRM_FILE

# Подтверждение файла
async def confirm_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "Да":
        await update.message.reply_text("📎 Отправьте файл:")
        return WAITING_FILE
    else:
        return await save_task(update, context)

# Сохраняем задачу
async def save_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)
    task_text = context.user_data.get('task_text')

    tasks = task_text.split('\n')
    for t in tasks:
        t = t.strip()
        if t:
            await database.add_task(
                user_id,
                t,
                due_date=context.user_data.get('due_date')
            )

    await update.message.reply_text("✅ Задача(и) добавлена(ы)!", reply_markup=main_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

# Обработка голосового сообщения
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)
    file_id = update.message.voice.file_id
    voice_task = f"🎤 Голосовая задача (ID: {file_id})"
    await database.add_task(user_id, voice_task, due_date=None)
    await update.message.reply_text("🎤 Голосовая задача добавлена!", reply_markup=main_keyboard())
    return ConversationHandler.END

# Отмена добавления
async def cancel_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❗ Добавление отменено.", reply_markup=main_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

# Конфиг бота
conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Добавить задачу$"), main_menu_handler)],
    states={
        ADDING_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_text)],
        SELECTING_DATE: [MessageHandler(filters.Regex("^(Сегодня|Завтра|Указать дату вручную)$"), select_date)],
        CONFIRM_FILE: [MessageHandler(filters.Regex("^(Да|Нет)$"), confirm_file)],
        WAITING_FILE: [
            MessageHandler(filters.Document.ALL | filters.PHOTO, save_task),
            MessageHandler(filters.VOICE, handle_voice)
        ],
    },
    fallbacks=[MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_task)],
)

# Запуск
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler))

    app.run_webhook(
        listen="127.0.0.1",
        port=8443,
        url_path=TOKEN,
        webhook_url=f"https://pitg.online/{TOKEN}",
        allowed_updates=Update.ALL_TYPES
    )
