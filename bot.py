import logging
import os
import aiohttp
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, filters, ContextTypes
)
from dotenv import load_dotenv
import database
from datetime import datetime

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
CITY = "Saint Petersburg"
ADMIN_CHAT_ID = 838476401

# Логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Состояния для ConversationHandler
ADDING_TEXT, SELECTING_CATEGORY, SELECTING_DATE, SELECTING_PRIORITY, CONFIRM_FILE, REMOVING_TASK, COMPLETING_TASK, CONFIRMING_REMOVE, CONFIRMING_COMPLETE = range(9)

user_task_buffer = {}

# Главная клавиатура
def main_keyboard():
    keyboard = [
        [KeyboardButton("➕ Добавить задачу"), KeyboardButton("🎤 Голосовая задача")],
        [KeyboardButton("📋 Мои задачи"), KeyboardButton("📄 Завершённые задачи")],
        [KeyboardButton("✅ Завершить задачу"), KeyboardButton("🗑️ Удалить задачу")],
        [KeyboardButton("🌦️ Погода"), KeyboardButton("📈 Статистика"), KeyboardButton("👑 Админка")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Клавиатура категорий
def category_keyboard():
    categories = ["Работа", "Личное", "Учёба", "Проекты", "Спорт"]
    return ReplyKeyboardMarkup([[KeyboardButton(cat)] for cat in categories], resize_keyboard=True)

# Клавиатура выбора даты
def date_keyboard():
    dates = ["Сегодня", "Завтра", "Выбрать дату вручную"]
    return ReplyKeyboardMarkup([[KeyboardButton(d)] for d in dates], resize_keyboard=True)

# Клавиатура приоритета
def priority_keyboard():
    priorities = ["🔥 Срочно", "⚡ Обычное", "🐢 Потом"]
    return ReplyKeyboardMarkup([[KeyboardButton(p)] for p in priorities], resize_keyboard=True)

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
                return f"🌍 Погода в {CITY}:\n🌡️ {temp}°C, {description}, 🌬️ {wind} м/с"
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

# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)

    if text == "🌦️ Погода":
        weather = await get_weather()
        await update.message.reply_text(weather, reply_markup=main_keyboard())

    elif text == "➕ Добавить задачу":
        await update.message.reply_text("✏️ Введите текст задачи:")
        return ADDING_TEXT

    elif text == "🎤 Голосовая задача":
        await update.message.reply_text("🎙️ Надиктуйте задачу голосом (отправьте аудиосообщение):")
        return ADDING_TEXT

    elif text == "📋 Мои задачи":
        tasks = await database.get_active_tasks(user_id)
        if not tasks:
            await update.message.reply_text("🎉 Нет активных задач!", reply_markup=main_keyboard())
        else:
            msg = "\n".join([f"📝 {task[0]} ({task[1] or 'Без категории'})" for task in tasks])
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
            msg = "👑 Пользователи:\n" + "\n".join(
                [f"{'⭐' if u['is_favorite'] else ''} {u['username']} ({u['chat_id']})" for u in users]
            )
            await update.message.reply_text(msg, reply_markup=main_keyboard())
        else:
            await update.message.reply_text("⛔ Доступ запрещён.", reply_markup=main_keyboard())

    else:
        await update.message.reply_text("❓ Нажмите на кнопку меню.", reply_markup=main_keyboard())
# Добавление текстовой задачи
async def add_task_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['task_text'] = update.message.text
    await update.message.reply_text("🏷️ Выберите категорию:", reply_markup=category_keyboard())
    return SELECTING_CATEGORY

async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['category'] = update.message.text
    await update.message.reply_text("📅 Укажите срок выполнения:", reply_markup=date_keyboard())
    return SELECTING_DATE

async def select_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Сегодня":
        context.user_data['due_date'] = datetime.now().strftime('%Y-%m-%d')
    elif text == "Завтра":
        context.user_data['due_date'] = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        context.user_data['due_date'] = None
    await update.message.reply_text("⚡ Установите приоритет:", reply_markup=priority_keyboard())
    return SELECTING_PRIORITY

async def select_priority(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['priority'] = update.message.text
    await update.message.reply_text("📎 Хотите прикрепить файл?", reply_markup=yes_no_keyboard())
    return CONFIRM_FILE

async def confirm_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "Да":
        await update.message.reply_text("📎 Отправьте файл (документ или фото):")
        return CONFIRM_FILE
    else:
        # Завершаем добавление задачи
        return await save_task(update, context)

async def save_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)
    await database.add_task(
        user_id,
        context.user_data.get('task_text'),
        context.user_data.get('category'),
        context.user_data.get('due_date'),
        context.user_data.get('priority'),
        context.user_data.get('file_id')  # может быть None
    )
    await update.message.reply_text("✅ Задача добавлена!", reply_markup=main_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Неверная команда во время добавления задачи.\nДобавление отменено, возвращаю в главное меню.",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)
    file_id = update.message.voice.file_id
    file = await context.bot.get_file(file_id)
    voice_text = f"🎤 Голосовая задача (ID: {file_id})"  # Можно будет добавить распознавание позже
    await database.add_task(user_id, voice_text, category="Быстрая", due_date=None, priority="Обычная", file_id=file_id)
    await update.message.reply_text("🎤 Голосовая задача добавлена!", reply_markup=main_keyboard())
    return ConversationHandler.END

# Настройка ConversationHandler
conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Добавить задачу$"), add_task_text)],
    states={
        ADDING_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_text)],
        SELECTING_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_category)],
        SELECTING_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_date)],
        SELECTING_PRIORITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_priority)],
        CONFIRM_FILE: [
            MessageHandler(filters.Document.ALL | filters.PHOTO, save_task),
            MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_file)
        ],
    },
    fallbacks=[MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_task)],
)

# Запуск приложения
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    app.run_webhook(
        listen="127.0.0.1",
        port=8443,
        url_path=TOKEN,
        webhook_url=f"https://pitg.online/{TOKEN}",
        allowed_updates=Update.ALL_TYPES
    )
