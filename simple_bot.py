import os
import json
import logging
from flask import Flask, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не задан в переменных окружения!")

# Функция для отправки ответов в Telegram
def send_message(chat_id, text):
    """Отправляет сообщение пользователю через Telegram API"""
    import requests
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, json=payload)
        logger.info(f"Ответ отправлен в чат {chat_id}: {r.status_code}")
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")

@app.route('/')
def index():
    return "🤖 Бот Спортик друн работает! Сервер активен."

@app.route('/health')
def health():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обрабатывает входящие обновления от Telegram"""
    logger.info("🔥 Получен запрос на вебхук")
    
    try:
        # Получаем данные от Telegram
        data = request.get_json()
        logger.info(f"Данные: {data}")
        
        # Проверяем, есть ли сообщение
        if "message" in data:
            msg = data["message"]
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "")
            
            # Обрабатываем команду /start
            if text == "/start":
                user = msg.get("from", {})
                first_name = user.get("first_name", "друг")
                reply_text = f"Привет, {first_name}! 🤗\n\nЯ бот Спортик друн. Я работаю!"
                send_message(chat_id, reply_text)
            else:
                # Ответ на любое другое сообщение
                send_message(chat_id, f"Ты написал: {text}")
        
        # Всегда отвечаем Telegram, что запрос принят
        return {"ok": True}, 200
        
    except Exception as e:
        logger.error(f"❌ Ошибка в webhook: {e}")
        return {"error": str(e)}, 500

@app.errorhandler(Exception)
def handle_error(error):
    logger.error(f"Необработанная ошибка: {error}")
    return "Internal Server Error", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🚀 Запуск на порту {port}")
    app.run(host="0.0.0.0", port=port)
