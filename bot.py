import logging
import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Чек-лист
CHECKLIST_ITEMS = [
    "🥗 Завтрак: Овсянка + 2 яйца + банан",
    "🥜 Перекус 1: Йогурт + орехи",
    "🍗 Обед: Курица + гречка + овощи",
    "🧀 Перекус 2: Творог 150г",
    "🐟 Ужин: Рыба + овощи",
    "💧 Вода: 1.5-2 литра",
    "🧘 Растяжка: Наклоны, кобра, спина, плечи"
]

# Функция старта
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[item] for item in CHECKLIST_ITEMS]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
    await update.message.reply_text(
        "📝 Чек-лист на сегодня:\n\nНажимай на задание, чтобы отметить выполнение!",
        reply_markup=reply_markup
    )

# Функция обработки нажатия на кнопку
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"✅ Выполнено: {update.message.text}")

# Основной запуск бота
def main():
    TOKEN = os.getenv("TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_click))
    app.run_polling()

if __name__ == "__main__":
    main()
