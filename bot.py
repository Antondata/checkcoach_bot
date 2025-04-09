import logging
import os
import aiohttp
import aiosqlite
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler
from datetime import time
from dotenv import load_dotenv
import database

load_dotenv()
API_KEY = os.getenv("OPENWEATHER_API_KEY")
CITY = "Saint Petersburg"
TOKEN = os.getenv("TOKEN")
ADMIN_CHAT_ID = 838476401

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

ADDING_TASK, REMOVING_TASK, COMPLETING_TASK, CONFIRMING_REMOVE, CONFIRMING_COMPLETE = range(5)

# Глобальные переменные для хранения выбранной задачи
user_task_buffer = {}

def main_keyboard():
    keyboard = [
        [KeyboardButton("🌦️ Погода"), KeyboardButton("📋 Мои задачи")],
        [KeyboardButton("➕ Добавить задачу"), KeyboardButton("🗑️ Удалить задачу")],
        [KeyboardButton("✅ Завершить задачу"), KeyboardButton("📈 Моя статистика")],
        [KeyboardButton("👑 Админка")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def yes_no_keyboard():
    keyboard = [
        [KeyboardButton("Да"), KeyboardButton("Нет")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await database.init_db()
    chat_id = update.message.chat_id
    username = update.message.from_user.username or "NoName"
    await database.add_user(chat_id, username)

    await update.message.reply_text("✅ Бот запущен!", reply_markup=main_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)

    if text == "🌦️ Погода":
        await update.message.reply_text("🌤️ Погода в Санкт-Петербурге:", reply_markup=main_keyboard())

    elif text == "📋 Мои задачи":
        tasks = await database.get_active_tasks(user_id)
        if not tasks:
            await update.message.reply_text("🎉 У вас нет активных задач!", reply_markup=main_keyboard())
        else:
            task_buttons = [[KeyboardButton(task)] for task in tasks]
            task_buttons.append([KeyboardButton("🔙 Назад")])
            reply_markup = ReplyKeyboardMarkup(task_buttons, resize_keyboard=True)
            await update.message.reply_text("📋 Ваши задачи:", reply_markup=reply_markup)

    elif text == "➕ Добавить задачу":
        await update.message.reply_text("✏️ Напишите одну или несколько задач (каждая с новой строки):")
        return ADDING_TASK

    elif text == "🗑️ Удалить задачу":
        tasks = await database.get_active_tasks(user_id)
        if not tasks:
            await update.message.reply_text("❗ Нет задач для удаления.", reply_markup=main_keyboard())
        else:
            task_buttons = [[KeyboardButton(task)] for task in tasks]
            task_buttons.append([KeyboardButton("🔙 Назад")])
            reply_markup = ReplyKeyboardMarkup(task_buttons, resize_keyboard=True)
            await update.message.reply_text("🗑️ Выберите задачу для удаления:", reply_markup=reply_markup)
            return REMOVING_TASK

    elif text == "✅ Завершить задачу":
        tasks = await database.get_active_tasks(user_id)
        if not tasks:
            await update.message.reply_text("❗ Нет задач для завершения.", reply_markup=main_keyboard())
        else:
            task_buttons = [[KeyboardButton(task)] for task in tasks]
            task_buttons.append([KeyboardButton("🔙 Назад")])
            reply_markup = ReplyKeyboardMarkup(task_buttons, resize_keyboard=True)
            await update.message.reply_text("✅ Выберите задачу для завершения:", reply_markup=reply_markup)
            return COMPLETING_TASK

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

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks_text = update.message.text.strip().split("\n")
    chat_id = update.message.chat_id
    user_id = await database.get_user_id(chat_id)
    for task in tasks_text:
        if task.strip():
            await database.add_task(user_id, task.strip())
    await update.message.reply_text("✅ Задачи добавлены!", reply_markup=main_keyboard())
    return ConversationHandler.END

async def remove_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_task_buffer[chat_id] = update.message.text
    await update.message.reply_text(f"❓ Удалить задачу '{update.message.text}'?", reply_markup=yes_no_keyboard())
    return CONFIRMING_REMOVE

async def complete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_task_buffer[chat_id] = update.message.text
    await update.message.reply_text(f"❓ Завершить задачу '{update.message.text}'?", reply_markup=yes_no_keyboard())
    return CONFIRMING_COMPLETE

async def confirm_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if update.message.text == "Да":
        user_id = await database.get_user_id(chat_id)
        await database.remove_task(user_id, user_task_buffer[chat_id])
        await update.message.reply_text(f"🗑️ Задача удалена: {user_task_buffer[chat_id]}", reply_markup=main_keyboard())
    else:
        await update.message.reply_text("❌ Отмена удаления.", reply_markup=main_keyboard())
    return ConversationHandler.END

async def confirm_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if update.message.text == "Да":
        user_id = await database.get_user_id(chat_id)
        await database.complete_task(user_id, user_task_buffer[chat_id])
        await update.message.reply_text(f"✅ Задача завершена: {user_task_buffer[chat_id]}", reply_markup=main_keyboard())
    else:
        await update.message.reply_text("❌ Отмена завершения.", reply_markup=main_keyboard())
    return ConversationHandler.END

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        states={
            ADDING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task)],
            REMOVING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_task)],
            COMPLETING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, complete_task)],
            CONFIRMING_REMOVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_remove)],
            CONFIRMING_COMPLETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_complete)],
        },
        fallbacks=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
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