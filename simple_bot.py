import os
import json
import logging
import asyncio
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes

# ======================== НАСТРОЙКИ ========================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не задан в переменных окружения!")

# ======================== ЛОГИРОВАНИЕ ========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ======================== FLASK ПРИЛОЖЕНИЕ ========================
app = Flask(__name__)

# ======================== TELEGRAM ПРИЛОЖЕНИЕ ========================
# Создаём Application без Updater (для вебхуков)
telegram_app = Application.builder().token(BOT_TOKEN).updater(None).build()

# ======================== ОБРАБОТЧИКИ КОМАНД ========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    logger.info(f"Получена команда /start от {user.first_name} (ID: {user.id})")
    
    await update.message.reply_text(
        f"Привет, {user.first_name}! 🤗\n\n"
        f"Я бот Спортик друн успешно запущен на Render! 🚀\n\n"
        f"Сервер работает, вебхук настроен."
    )

# Регистрируем обработчики
telegram_app.add_handler(CommandHandler("start", start_command))

# ======================== FLASK МАРШРУТЫ ========================
@app.route('/')
def index():
    """Главная страница для проверки"""
    return "🤖 Бот Спортик друн работает! Сервер активен."

@app.route('/health')
def health():
    """Health check для Render"""
    return "✅ OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Основной маршрут для приема обновлений от Telegram.
    Сюда Telegram отправляет все сообщения от пользователей.
    """
    # Проверяем, что запрос от Telegram
    if request.headers.get('content-type') != 'application/json':
        logger.warning("Получен запрос не в формате JSON")
        return '', 403
    
    try:
        # Получаем данные от Telegram
        json_str = request.get_data(as_text=True)
        logger.info(f"Получен webhook: {json_str[:100]}...")  # Логируем начало для отладки
        
        # Преобразуем JSON в объект Update
        update = Update.de_json(json.loads(json_str), telegram_app.bot)
        
        # Запускаем обработку в event loop'е Telegram
        asyncio.run_coroutine_threadsafe(
            telegram_app.process_update(update),
            telegram_app.loop
        )
        
        logger.info("✅ Webhook обработан успешно")
        return '', 200
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке webhook: {e}")
        return '', 500

@app.route('/test', methods=['GET'])
def test():
    """Тестовый маршрут для проверки"""
    return "✅ Тестовый маршрут работает!"

# ======================== ЗАПУСК ========================
if __name__ == "__main__":
    logger.info("🚀 Запуск бота на Render...")
    
    # Создаём event loop для Telegram
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Запускаем Flask
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🌐 Сервер запускается на порту {port}")
    
    # Важно: host='0.0.0.0' обязательно для Render
    app.run(host='0.0.0.0', port=port)
