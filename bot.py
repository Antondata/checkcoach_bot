import logging
import os
import aiohttp
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters
from dotenv import load_dotenv
import database

# Загрузка настроек
load_dotenv()
TOKEN = os.getenv("TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
ADMIN_CHAT_ID = 838476401

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

ADDING_TASK, CHOOSING_USER, WRITING_TASK = range(3)

# Главное меню
def main_keyboard(is_admin=False):
    keyboard = [
        [KeyboardButton("➕ Поставить задачу"), KeyboardButton("📋 Мои задачи")],
        [KeyboardButton("📄 Принятые задачи"), KeyboardButton("📞 Поделиться контактом")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton("👑 Админка")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Клавиатура принять/отклонить
def yes_no_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("✅ Принять"), KeyboardButton("❌ Отклонить")]], resize_keyboard=True)

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
    await update.message.reply_text(
        "✅ Привет! Чтобы работать с ботом, поделитесь контактом:",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📞 Поделиться контактом", request_contact=True)]],
            resize_keyboard=True
        )
    )

# Обработка контакта
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    chat_id = update.message.chat_id
    username = update.message.from_user.username or "NoName"
    phone_number = contact.phone_number

    await database.add_user(chat_id, username, phone_number)

    await update.message.reply_text(
        "📞 Контакт получен! Можете начинать пользоваться ботом.",
        reply_markup=main_keyboard(is_admin=(chat_id == ADMIN_CHAT_ID))
    )

# Главное меню
async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id
    is_admin = (chat_id == ADMIN_CHAT_ID)

    # ⬇️ Если пользователь ожидает принятие задачи
    if context.application.chat_data.get(chat_id, {}).get('awaiting_accept'):
        return await accept_task(update, context)

    if text == "➕ Поставить задачу":
        contacts = await database.get_all_contacts()
        buttons = [[KeyboardButton(user['username'])] for user in contacts if user['chat_id'] != chat_id]
        context.user_data['contacts'] = {user['username']: user['chat_id'] for user in contacts}
        if buttons:
            await update.message.reply_text("👥 Выберите пользователя:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
            return CHOOSING_USER
        else:
            await update.message.reply_text("❗ Нет других пользователей.", reply_markup=main_keyboard(is_admin=is_admin))
            return ConversationHandler.END

    elif text == "📋 Мои задачи":
        tasks = await database.get_tasks_for_user(chat_id)
        if not tasks:
            await update.message.reply_text("🎯 Нет задач.", reply_markup=main_keyboard(is_admin=is_admin))
        else:
            message = "\n".join([f"📝 {task['task_text']} ({task['status']})" for task in tasks])
            await update.message.reply_text(f"📋 Ваши задачи:\n{message}", reply_markup=main_keyboard(is_admin=is_admin))

    elif text == "📄 Принятые задачи":
        tasks = await database.get_assigned_tasks(chat_id)
        if not tasks:
            await update.message.reply_text("📭 Вы пока никому не поставили задачи.", reply_markup=main_keyboard(is_admin=is_admin))
        else:
            message = "\n".join([f"📤 {task['task_text']} → @{task['receiver_username']} ({task['status']})" for task in tasks])
            await update.message.reply_text(f"📄 Отправленные задачи:\n{message}", reply_markup=main_keyboard(is_admin=is_admin))

    elif text == "📞 Поделиться контактом":
        await update.message.reply_text(
            "📞 Поделитесь своим контактом:",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📞 Поделиться контактом", request_contact=True)]],
                resize_keyboard=True
            )
        )

    elif text == "👑 Админка" and is_admin:
        users = await database.get_all_contacts()
        msg = "👑 Все пользователи:\n" + "\n".join(f"• @{u['username']} ({u['phone_number']})" for u in users)
        await update.message.reply_text(msg, reply_markup=main_keyboard(is_admin=True))

    else:
        await update.message.reply_text("❓ Пожалуйста, используйте меню.", reply_markup=main_keyboard(is_admin=is_admin))

# Выбор пользователя
async def choose_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected_username = update.message.text
    receiver_id = context.user_data['contacts'].get(selected_username)

    if receiver_id:
        context.user_data['receiver_id'] = receiver_id
        await update.message.reply_text(f"✏️ Напишите текст задачи для @{selected_username}:")
        return WRITING_TASK
    else:
        await update.message.reply_text("❗ Пользователь не найден.", reply_markup=main_keyboard(is_admin=(update.message.chat_id == ADMIN_CHAT_ID)))
        return ConversationHandler.END

# Написание задачи
async def write_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_text = update.message.text
    sender_id = update.message.chat_id
    receiver_id = context.user_data['receiver_id']

    await database.add_task(sender_id, receiver_id, task_text, status="pending")

    await update.message.reply_text("✅ Задача отправлена!", reply_markup=main_keyboard(is_admin=(sender_id == ADMIN_CHAT_ID)))

    await context.bot.send_message(
        chat_id=receiver_id,
        text=f"📩 Вам поставили новую задачу:\n\n{task_text}",
        reply_markup=yes_no_keyboard()
    )

    context.application.chat_data.setdefault(receiver_id, {})['awaiting_accept'] = True
    return ConversationHandler.END

# Принятие/отклонение задачи
async def accept_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id
    is_admin = (chat_id == ADMIN_CHAT_ID)

    if text == "✅ Принять":
        await database.update_task_status(chat_id, "accepted")
        await update.message.reply_text("✅ Задача принята.", reply_markup=main_keyboard(is_admin=is_admin))
    elif text == "❌ Отклонить":
        await database.update_task_status(chat_id, "rejected")
        await update.message.reply_text("❌ Задача отклонена.", reply_markup=main_keyboard(is_admin=is_admin))
    else:
        await update.message.reply_text("❓ Пожалуйста, используйте кнопки.", reply_markup=main_keyboard(is_admin=is_admin))

    context.application.chat_data.get(chat_id, {}).pop('awaiting_accept', None)
    return ConversationHandler.END

# Старт приложения
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler),
            MessageHandler(filters.CONTACT, contact_handler)
        ],
        states={
            CHOOSING_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_user)],
            WRITING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, write_task)],
        },
        fallbacks=[MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler)],
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
