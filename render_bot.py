"""
Telegram Bot для Render.com
"""

import os
import json
import logging
import random
import asyncio
from typing import Dict, List, Tuple

from flask import Flask, request, abort
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# ======================== НАСТРОЙКИ ========================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Не задана переменная окружения BOT_TOKEN")

ADMIN_ID = 8259326703

# Render автоматически выдает публичный URL
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

# ======================== ИНИЦИАЛИЗАЦИЯ ========================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask приложение
app = Flask(__name__)

# ======================== РАБОТА С JSON ========================
USERS_FILE = "users.json"
CITIES_FILE = "cities.json"

def load_json(file_path: str, default=None):
    if default is None:
        default = {} if file_path == USERS_FILE else []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default

def save_json(file_path: str, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ======================== ГОРОДА ========================
DEFAULT_CITIES = [
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань",
    "Лондон", "Париж", "Берлин", "Мадрид", "Рим", "Токио", "Пекин",
    "Нью-Йорк", "Лос-Анджелес", "Чикаго", "Сидней", "Мельбурн"
]

cities_db = load_json(CITIES_FILE, default=DEFAULT_CITIES)
cities_lower_set = {city.lower() for city in cities_db}
cities_dict = {city.lower(): city for city in cities_db}

if not load_json(CITIES_FILE):
    save_json(CITIES_FILE, cities_db)

# ======================== ПОЛЬЗОВАТЕЛИ И СТАТИСТИКА ========================
def load_users() -> Dict[str, Dict]:
    return load_json(USERS_FILE, default={})

def save_users(users_data: Dict):
    save_json(USERS_FILE, users_data)

def update_user_stats(user_id: int, user_name: str, username: str, game: str, points: int = 1):
    users_data = load_users()
    user_id_str = str(user_id)
    
    if user_id_str not in users_data:
        users_data[user_id_str] = {
            "first_name": user_name,
            "username": username,
            "stats": {"cities": 0, "rps": 0, "dice": 0, "sapper": 0}
        }
    
    users_data[user_id_str]["first_name"] = user_name
    users_data[user_id_str]["username"] = username
    users_data[user_id_str]["stats"][game] = users_data[user_id_str]["stats"].get(game, 0) + points
    save_users(users_data)
    return users_data[user_id_str]["stats"][game]

# ======================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ========================
def get_user_mention(user) -> str:
    return f"@{user.username}" if user.username else user.first_name

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# ======================== СОЗДАЕМ ПРИЛОЖЕНИЕ БОТА ========================
telegram_app = Application.builder().token(BOT_TOKEN).updater(None).build()

# ======================== ОБРАБОТЧИКИ КОМАНД ========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    update_user_stats(user.id, user.first_name, user.username, "cities", 0)
    
    await update.message.reply_text(
        f"Приветствую, {user.first_name}! 🤗\n\n"
        f"Я развлекательный бот Спортик друн😝\n\n"
        f"Напиши /help что бы узнать подробнее!😁"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🎮 **Доступные команды:**\n\n"
        "/start - Приветствие\n"
        "/help - Это сообщение\n"
        "/games - Меню со всеми играми\n"
        "/top - Топ игроков\n"
        "/mystats - Твоя статистика"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def games_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["🎮 Города", "🧮 КМБ"],
        ["🎲 Кубик", "💣 Сапер"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Выбери игру:", reply_markup=reply_markup)

async def echo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Временный обработчик для теста"""
    text = update.message.text
    await update.message.reply_text(f"Ты написал: {text}")

# ======================== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ ========================
telegram_app.add_handler(CommandHandler("start", start_command))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(CommandHandler("games", games_command))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_handler))

# ======================== НАСТРОЙКА ВЕБХУКА ========================
async def setup_webhook():
    """Устанавливает вебхук при старте"""
    if not RENDER_EXTERNAL_URL:
        logger.warning("RENDER_EXTERNAL_URL не найден. Вебхук не установлен.")
        return
    
    webhook_url = f"{RENDER_EXTERNAL_URL.rstrip('/')}/webhook"
    
    await telegram_app.bot.delete_webhook()
    await asyncio.sleep(0.5)
    
    ok = await telegram_app.bot.set_webhook(
        url=webhook_url,
        allowed_updates=Update.ALL_TYPES
    )
    
    if ok:
        logger.info(f"✅ Вебхук установлен: {webhook_url}")
    else:
        logger.error("❌ Не удалось установить вебхук")

# ======================== FLASK МАРШРУТЫ ========================
@app.route('/')
def index():
    return "Бот Спортик друн работает! 🤖", 200

@app.route('/health')
def health():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Принимает обновления от Telegram"""
    if request.headers.get('content-type') != 'application/json':
        abort(403)
    
    json_str = request.get_data(as_text=True)
    update = Update.de_json(json_str, telegram_app.bot)
    
    asyncio.run_coroutine_threadsafe(
        telegram_app.process_update(update),
        telegram_app.loop
    )
    
    return '', 200

# ======================== ЗАПУСК ========================
@app.before_first_request
async def before_first_request():
    """Выполняется перед первым запросом"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    await setup_webhook()

if __name__ == "__main__":
    # Render сам задает порт через переменную окружения PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
