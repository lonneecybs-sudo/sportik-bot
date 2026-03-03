import os
import logging
from flask import Flask, request

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def index():
    logger.info("Главная страница открыта")
    return "Бот работает!"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Простой вебхук"""
    logger.info("🔥 ПОЛУЧЕН ЗАПРОС НА ВЕБХУК")
    
    # Логируем всё подряд
    logger.info(f"Заголовки: {dict(request.headers)}")
    logger.info(f"Данные: {request.get_data(as_text=True)}")
    
    # Всегда возвращаем успех
    return "OK", 200

@app.errorhandler(500)
def handle_500(error):
    logger.error(f"ОШИБКА 500: {error}")
    return "Internal Server Error", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Запуск на порту {port}")
    app.run(host="0.0.0.0", port=port)
