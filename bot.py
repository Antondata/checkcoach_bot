import logging 
import os
import aiohttp
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters
from dotenv import load_dotenv
import database

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
ADMIN_CHAT_ID = 838476401

# Проверка переменных
if not TOKEN or not OPENWEATHER_API_KEY:
    raise ValueError("❗ Переменные окружения TOKEN или OPENWEATHER_API_KEY не установлены.")

# Логирование
logging.basicConfig(level=logging.INFO)

# Состояния для ConversationHandler
(WRITING_SELF_TASK, CHOOSING_USER, WRITING_USER_TASK,
 CHOOSING_TASK_TO_COMPLETE, CONFIRM_COMPLETION,
 CHOOSING_TASK_TO_DELETE, CONFIRM_DELETION) = range(7)

user_data_buffer = {}

# Главное меню
def main_keyboard(is_admin=False):
    keyboard = [
        [KeyboardButton("➕ Поставить себе"), KeyboardButton("📤 Поставить другому")],
        [KeyboardButton("📋 Мои задачи"), KeyboardButton("📄 Отправленные задачи")],
        [KeyboardButton("✅ Завершить задачу"), KeyboardButton("🗑️ Удалить задачу")],
        [KeyboardButton("📈 Моя статистика"), KeyboardButton("🌦️ Погода")],
        [KeyboardButton("📞 Поделиться контактом")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton("👑 Админка")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Да/Нет клавиатура
def yes_no_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("✅ Да"), KeyboardButton("❌ Нет")]],
        resize_keyboard=True
    )

# Погода
async def get_weather():
    try:
        async with aiohttp.ClientSession() as session:
            url = f"http://api.openweathermap.org/data/2.5/weather?q=Saint Petersburg&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Ошибка погоды: код {response.status}")
                data = await response.json()
                temp = data['main']['temp']
                description = data['weather'][0]['description']
                wind = data['wind']['speed']
                return f"🌍 Санкт-Петербург\n🌡️ {temp}°C\n☁️ {description}\n🌬️ {wind} м/с"
    except Exception as e:
        logging.error(f"Ошибка получения погоды: {e}")
        return "❗ Ошибка получения погоды."

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await database.init_db()
    chat_id = update.message.chat_id
    username = update.message.from_user.username or "NoName"
    await database.add_user(chat_id, username, None)
    await update.message.reply_text(
        "✅ Привет! Чтобы работать с ботом, поделитесь контактом:",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📞 Поделиться контактом", request_contact=True)]],
            resize_keyboard=True
        )
    )

# Контакт
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    chat_id = update.message.chat_id
    username = update.message.from_user.username or "NoName"
    phone_number = contact.phone_number
    await database.add_user(chat_id, username, phone_number)

    await update.message.reply_text(
        "📞 Контакт получен!",
        reply_markup=main_keyboard(is_admin=(chat_id == ADMIN_CHAT_ID))
    )

# Главное меню
async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id
    is_admin = (chat_id == ADMIN_CHAT_ID)

    if text == "➕ Поставить себе":
        await update.message.reply_text("✏️ Напишите текст задачи для себя:")
        return WRITING_SELF_TASK

    elif text == "📤 Поставить другому":
        contacts = await database.get_all_contacts()
        buttons = [[KeyboardButton(user['username'])] for user in contacts if user['chat_id'] != chat_id]
        context.user_data['contacts'] = {user['username']: user['chat_id'] for user in contacts}
        if buttons:
            await update.message.reply_text("👥 Выберите пользователя:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
            return CHOOSING_USER
        else:
            await update.message.reply_text("❗ Нет других пользователей.", reply_markup=main_keyboard(is_admin))

    elif text == "📋 Мои задачи":
        tasks = await database.get_tasks_for_user(chat_id)
        tasks = [t for t in tasks if t['status'] != 'completed']
        if not tasks:
            await update.message.reply_text("🎯 Нет задач.", reply_markup=main_keyboard(is_admin))
        else:
            msg = "\n".join([f"📝 {task['task_text']} ({task['status']})" for task in tasks])
            await update.message.reply_text(f"📋 Ваши задачи:\n{msg}", reply_markup=main_keyboard(is_admin))

    elif text == "📄 Отправленные задачи":
        tasks = await database.get_assigned_tasks(chat_id)
        if not tasks:
            await update.message.reply_text("📭 Вы никому не поставили задачи.", reply_markup=main_keyboard(is_admin))
        else:
            msg = "\n".join([f"📤 {task['task_text']} → @{task['receiver_username']} ({task['status']})" for task in tasks])
            await update.message.reply_text(f"📄 Отправленные задачи:\n{msg}", reply_markup=main_keyboard(is_admin))

    elif text == "✅ Завершить задачу":
        tasks = await database.get_tasks_for_user(chat_id)
        tasks = [t for t in tasks if t['status'] == 'accepted']
        if not tasks:
            await update.message.reply_text("❗ Нет задач для завершения.", reply_markup=main_keyboard(is_admin))
            return ConversationHandler.END
        context.user_data['completion_tasks'] = tasks
        buttons = [[KeyboardButton(task['task_text'])] for task in tasks]
        await update.message.reply_text("✅ Выберите задачу для завершения:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return CHOOSING_TASK_TO_COMPLETE

    elif text == "🗑️ Удалить задачу":
        tasks = await database.get_tasks_for_user(chat_id)
        if not tasks:
            await update.message.reply_text("❗ Нет задач для удаления.", reply_markup=main_keyboard(is_admin))
            return ConversationHandler.END
        context.user_data['deletion_tasks'] = tasks
        buttons = [[KeyboardButton(task['task_text'])] for task in tasks]
        await update.message.reply_text("🗑️ Выберите задачу для удаления:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return CHOOSING_TASK_TO_DELETE

    elif text == "📈 Моя статистика":
        count = await database.get_task_count(chat_id)
        await update.message.reply_text(f"📊 Всего задач: {count}", reply_markup=main_keyboard(is_admin))

    elif text == "🌦️ Погода":
        weather = await get_weather()
        await update.message.reply_text(weather, reply_markup=main_keyboard(is_admin))

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
        await update.message.reply_text(msg, reply_markup=main_keyboard(is_admin))

    else:
        await update.message.reply_text("❓ Команда не распознана. Используйте кнопки меню.", reply_markup=main_keyboard(is_admin))


async def write_self_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_text = update.message.text
    chat_id = update.message.chat_id
    await database.add_task(chat_id, chat_id, task_text, status="accepted")
    await update.message.reply_text("✅ Задача добавлена!", reply_markup=main_keyboard(is_admin=(chat_id == ADMIN_CHAT_ID)))
    return ConversationHandler.END

# Выбираем пользователя
async def choose_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected_username = update.message.text
    receiver_id = context.user_data.get('contacts', {}).get(selected_username)
    if not receiver_id:
        await update.message.reply_text("❗ Пользователь не найден.", reply_markup=main_keyboard())
        return ConversationHandler.END
    context.user_data['receiver_id'] = receiver_id
    await update.message.reply_text(f"✏️ Напишите текст задачи для @{selected_username}:")
    return WRITING_USER_TASK

# Пишем задачу другому
async def write_user_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_text = update.message.text
    sender_id = update.message.chat_id
    receiver_id = context.user_data.get('receiver_id')

    if not receiver_id:
        await update.message.reply_text("❗ Ошибка: не выбран получатель задачи.", reply_markup=main_keyboard())
        return ConversationHandler.END

    await database.add_task(sender_id, receiver_id, task_text, status="pending")
    context.user_data.clear()

    await update.message.reply_text("✅ Задача отправлена!", reply_markup=main_keyboard(is_admin=(sender_id == ADMIN_CHAT_ID)))

    await context.bot.send_message(
    chat_id=receiver_id,
    text=f"📩 Вам поставили новую задачу:\n\n{task_text}",
    reply_markup=ReplyKeyboardMarkup(
        [[KeyboardButton("✅ Принять"), KeyboardButton("❌ Отклонить")]],
        resize_keyboard=True
    )
)
context.application.user_data.setdefault(receiver_id, {})['pending_task_text'] = task_text

return ConversationHandler.END


# Выбор задачи для завершения
async def choose_task_to_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_text = update.message.text
    chat_id = update.message.chat_id
    user_data_buffer[chat_id] = task_text
    await update.message.reply_text(f"✅ Подтвердите завершение задачи:\n\n{task_text}", reply_markup=yes_no_keyboard())
    return CONFIRM_COMPLETION

# Подтверждение завершения
async def confirm_completion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    answer = update.message.text
    task_text = user_data_buffer.get(chat_id)

    if not task_text:
        await update.message.reply_text("❗ Ошибка: задача не найдена.", reply_markup=main_keyboard())
        return ConversationHandler.END

    if answer == "✅ Да":
        await database.update_task_status_by_text(chat_id, task_text, "completed")
        await update.message.reply_text("✅ Задача завершена!", reply_markup=main_keyboard(is_admin=(chat_id == ADMIN_CHAT_ID)))
    else:
        await update.message.reply_text("❌ Завершение отменено.", reply_markup=main_keyboard(is_admin=(chat_id == ADMIN_CHAT_ID)))
    user_data_buffer.pop(chat_id, None)
    return ConversationHandler.END

# Выбор задачи для удаления
async def choose_task_to_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_text = update.message.text
    chat_id = update.message.chat_id
    user_data_buffer[chat_id] = task_text
    await update.message.reply_text(f"🗑️ Подтвердите удаление задачи:\n\n{task_text}", reply_markup=yes_no_keyboard())
    return CONFIRM_DELETION

# Подтверждение удаления
async def confirm_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    answer = update.message.text
    task_text = user_data_buffer.get(chat_id)

    if not task_text:
        await update.message.reply_text("❗ Ошибка: задача не найдена.", reply_markup=main_keyboard())
        return ConversationHandler.END

    if answer == "✅ Да":
        await database.delete_task_by_text(chat_id, task_text)
        await update.message.reply_text("🗑️ Задача удалена!", reply_markup=main_keyboard(is_admin=(chat_id == ADMIN_CHAT_ID)))
    else:
        await update.message.reply_text("❌ Удаление отменено.", reply_markup=main_keyboard(is_admin=(chat_id == ADMIN_CHAT_ID)))
    user_data_buffer.pop(chat_id, None)
    return ConversationHandler.END

# Принятие или отклонение задачи
async def handle_accept_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id

    # Забираем текст задачи, который был сохранен
    pending_task = context.application.user_data.get(chat_id, {}).get('pending_task_text')

    if not pending_task:
        await update.message.reply_text("❗ Нет задачи для принятия или отклонения.", reply_markup=main_keyboard(is_admin=(chat_id == ADMIN_CHAT_ID)))
        return ConversationHandler.END

    if text == "✅ Принять":
        await database.update_task_status_by_text(chat_id, pending_task, "accepted")
        await update.message.reply_text("✅ Задача принята!", reply_markup=main_keyboard(is_admin=(chat_id == ADMIN_CHAT_ID)))
    elif text == "❌ Отклонить":
        await database.update_task_status_by_text(chat_id, pending_task, "rejected")
        await update.message.reply_text("❌ Задача отклонена.", reply_markup=main_keyboard(is_admin=(chat_id == ADMIN_CHAT_ID)))
    else:
        await update.message.reply_text("❓ Неверная команда.", reply_markup=main_keyboard(is_admin=(chat_id == ADMIN_CHAT_ID)))

    # Очищаем после обработки
    context.application.user_data.pop(chat_id, None)

    return ConversationHandler.END

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    # Основной обработчик состояний задач
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler),
            MessageHandler(filters.CONTACT, contact_handler),
        ],
        states={
            WRITING_SELF_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, write_self_task)],
            CHOOSING_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_user)],
            WRITING_USER_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, write_user_task)],
            CHOOSING_TASK_TO_COMPLETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_task_to_complete)],
            CONFIRM_COMPLETION: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_completion)],
            CHOOSING_TASK_TO_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_task_to_delete)],
            CONFIRM_DELETION: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_deletion)],
        },
        fallbacks=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler)
        ],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    # Отдельная обработка принятия/отклонения задач
    app.add_handler(MessageHandler(filters.Regex("^(✅ Принять|❌ Отклонить)$"), handle_accept_reject))

    # Стартуем через Webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=8443,
        url_path=TOKEN,
        webhook_url=f"https://pitg.online/{TOKEN}",
        allowed_updates=Update.ALL_TYPES
    )
