import logging
import os
import aiohttp
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters
)
from dotenv import load_dotenv
import database

# Загрузка настроек
load_dotenv()
TOKEN = os.getenv("TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
ADMIN_CHAT_ID = 838476401

# Логирование
logging.basicConfig(
    filename='bot.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Состояния
SELF_TASK, OTHER_USER_CHOOSE, OTHER_USER_TASK, COMPLETE_TASK, DELETE_TASK = range(5)

# Главное меню
def main_keyboard(is_admin=False):
    keyboard = [
        [KeyboardButton("📝 Поставить себе задачу"), KeyboardButton("📤 Поставить другому")],
        [KeyboardButton("📋 Мои задачи"), KeyboardButton("📄 Поставленные задачи")],
        [KeyboardButton("✅ Завершить задачу"), KeyboardButton("🗑️ Удалить задачу")],
        [KeyboardButton("📈 Моя статистика"), KeyboardButton("🌦️ Погода")],
        [KeyboardButton("📞 Поделиться контактом")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton("👑 Админка")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Принять/Отклонить задача
def yes_no_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("✅ Принять"), KeyboardButton("❌ Отклонить")]],
        resize_keyboard=True
    )

# Погода
async def get_weather():
    try:
        async with aiohttp.ClientSession() as session:
            url = f"http://api.openweathermap.org/data/2.5/weather?q=Saint Petersburg&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
            async with session.get(url) as response:
                data = await response.json()
                temp = data['main']['temp']
                desc = data['weather'][0]['description']
                wind = data['wind']['speed']
                return f"🌍 Санкт-Петербург\n🌡️ {temp}°C\n☁️ {desc}\n🌬️ {wind} м/с"
    except Exception as e:
        logging.error(f"Ошибка погоды: {e}")
        return "❗ Ошибка получения погоды."

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await database.init_db()
    chat_id = update.message.chat_id
    username = update.message.from_user.username or "NoName"

    await database.add_user(chat_id, username, None)
    await update.message.reply_text(
        "✅ Добро пожаловать! Поделитесь контактом для работы:",
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
        "📞 Контакт получен! Теперь доступны все функции.",
        reply_markup=main_keyboard(is_admin=(chat_id == ADMIN_CHAT_ID))
    )
    return ConversationHandler.END

# Главное меню
async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id
    is_admin = (chat_id == ADMIN_CHAT_ID)

    if text == "📝 Поставить себе задачу":
        await update.message.reply_text("✏️ Напишите задачу для себя:")
        return SELF_TASK

    elif text == "📤 Поставить другому":
        contacts = await database.get_all_contacts()
        contacts = [user for user in contacts if user['chat_id'] != chat_id]
        if not contacts:
            await update.message.reply_text("❗ Нет других пользователей.", reply_markup=main_keyboard(is_admin=is_admin))
            return ConversationHandler.END

        buttons = [[KeyboardButton(user['username'])] for user in contacts]
        context.user_data['contacts'] = {user['username']: user['chat_id'] for user in contacts}
        await update.message.reply_text("👥 Кому поставить задачу?", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return OTHER_USER_CHOOSE

    elif text == "📋 Мои задачи":
        tasks = await database.get_tasks_for_user(chat_id)
        if not tasks:
            await update.message.reply_text("🎯 Нет активных задач.", reply_markup=main_keyboard(is_admin=is_admin))
        else:
            msg = "\n".join([f"📝 {task['task_text']} ({task['status']})" for task in tasks])
            await update.message.reply_text(f"📋 Ваши задачи:\n{msg}", reply_markup=main_keyboard(is_admin=is_admin))

    elif text == "📄 Поставленные задачи":
        tasks = await database.get_assigned_tasks(chat_id)
        if not tasks:
            await update.message.reply_text("📭 Вы пока никому не ставили задач.", reply_markup=main_keyboard(is_admin=is_admin))
        else:
            msg = "\n".join([f"📤 {task['task_text']} → @{task['receiver_username']} ({task['status']})" for task in tasks])
            await update.message.reply_text(f"📄 Поставленные задачи:\n{msg}", reply_markup=main_keyboard(is_admin=is_admin))

    elif text == "✅ Завершить задачу":
        await update.message.reply_text("✏️ Напишите текст задачи для завершения:")
        return COMPLETE_TASK

    elif text == "🗑️ Удалить задачу":
        await update.message.reply_text("✏️ Напишите текст задачи для удаления:")
        return DELETE_TASK

    elif text == "📈 Моя статистика":
        count = await database.get_task_count(chat_id)
        await update.message.reply_text(f"📊 Вы поставили {count} задач(и).", reply_markup=main_keyboard(is_admin=is_admin))

    elif text == "🌦️ Погода":
        weather = await get_weather()
        await update.message.reply_text(weather, reply_markup=main_keyboard(is_admin=is_admin))

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
        await update.message.reply_text("❓ Пожалуйста, выберите действие через меню.", reply_markup=main_keyboard(is_admin=is_admin))

# Поставить задачу себе
async def self_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id

    await database.add_task(chat_id, chat_id, text)
    await update.message.reply_text("✅ Задача добавлена себе!", reply_markup=main_keyboard(is_admin=(chat_id == ADMIN_CHAT_ID)))
    return ConversationHandler.END

# Выбрать другого пользователя
async def choose_other_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected_username = update.message.text
    receiver_id = context.user_data['contacts'].get(selected_username)

    if receiver_id:
        context.user_data['receiver_id'] = receiver_id
        await update.message.reply_text(f"✏️ Напишите задачу для @{selected_username}:")
        return OTHER_USER_TASK
    else:
        await update.message.reply_text("❗ Пользователь не найден.", reply_markup=main_keyboard())

# Поставить задачу другому
async def other_user_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    sender_id = update.message.chat_id
    receiver_id = context.user_data['receiver_id']

    await database.add_task(sender_id, receiver_id, text)
    await context.bot.send_message(
        chat_id=receiver_id,
        text=f"📩 Вам поставили новую задачу:\n\n{text}",
        reply_markup=yes_no_keyboard()
    )
    await update.message.reply_text("✅ Задача отправлена!", reply_markup=main_keyboard(is_admin=(sender_id == ADMIN_CHAT_ID)))
    return ConversationHandler.END

# Завершить задачу
async def complete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id

    await database.update_task_status_by_text(chat_id, text, "completed")
    await update.message.reply_text("✅ Задача завершена!", reply_markup=main_keyboard(is_admin=(chat_id == ADMIN_CHAT_ID)))
    return ConversationHandler.END

# Удалить задачу
async def delete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id

    await database.delete_task_by_text(chat_id, text)
    await update.message.reply_text("🗑️ Задача удалена!", reply_markup=main_keyboard(is_admin=(chat_id == ADMIN_CHAT_ID)))
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
            SELF_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, self_task)],
            OTHER_USER_CHOOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_other_user)],
            OTHER_USER_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, other_user_task)],
            COMPLETE_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, complete_task)],
            DELETE_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_task)],
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
