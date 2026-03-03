"""
Telegram Bot для Render (Minesweeper, Gifts, Games)
Исправленная версия для работы с вебхуками
"""

import os
import json
import logging
import random
import re
import asyncio
from typing import Dict, List, Tuple
from flask import Flask, request, abort

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, User
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode

# ======================== НАСТРОЙКИ ========================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8710055657:AAEWkUYdJdv6FxNpuWi2ikZI0vRF4P8rygk")
ADMIN_ID = 8259326703
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

# ======================== ИНИЦИАЛИЗАЦИЯ ========================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask приложение
app = Flask(__name__)

USERS_FILE = "users.json"
CITIES_FILE = "cities.json"

# ======================== РАБОТА С JSON ========================
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

# ======================== БОЛЬШОЙ СПИСОК ГОРОДОВ ========================
DEFAULT_CITIES = [
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань", "Лондон", "Париж", "Берлин", 
    "Мадрид", "Рим", "Токио", "Пекин", "Нью-Йорк", "Лос-Анджелес", "Чикаго", "Сидней", "Мельбурн"
]

cities_db = load_json(CITIES_FILE, default=DEFAULT_CITIES)
cities_dict = {city.lower(): city for city in cities_db}

if not load_json(CITIES_FILE):
    save_json(CITIES_FILE, cities_db)

logger.info(f"✅ Загружено {len(cities_db)} городов для игры")

def find_city_in_db(city_name: str) -> str:
    city_clean = city_name.lower().strip()
    if city_clean in cities_dict:
        return cities_dict[city_clean]
    city_no_hyphen = city_clean.replace('-', ' ')
    if city_no_hyphen in cities_dict:
        return cities_dict[city_no_hyphen]
    return None

def get_last_letter(city_name: str) -> str:
    name = city_name.lower()
    for i in range(len(name) - 1, -1, -1):
        letter = name[i]
        if letter not in 'ьъы':
            return letter
    return name[-1]

# ======================== ПОЛЬЗОВАТЕЛИ И СТАТИСТИКА ========================
def load_users() -> Dict[str, Dict]:
    return load_json(USERS_FILE, default={})

def save_users(users_data: Dict):
    save_json(USERS_FILE, users_data)

def update_user_stats(user: User, game: str, points: int = 1):
    users_data = load_users()
    user_id = str(user.id)
    
    if user_id not in users_data:
        users_data[user_id] = {
            "first_name": user.first_name,
            "username": user.username,
            "stats": {"cities": 0, "rps": 0, "dice": 0, "sapper": 0}
        }
    
    users_data[user_id]["first_name"] = user.first_name
    users_data[user_id]["username"] = user.username
    users_data[user_id]["stats"][game] = users_data[user_id]["stats"].get(game, 0) + points
    
    save_users(users_data)
    return users_data[user_id]["stats"][game]

def get_top_players_total(limit: int = 10) -> List[Tuple[str, int]]:
    users_data = load_users()
    players = []
    for user_id, data in users_data.items():
        name = data.get("first_name", "Unknown")
        stats = data.get("stats", {})
        total = sum(stats.values())
        if total > 0:
            players.append((name, total))
    players.sort(key=lambda x: x[1], reverse=True)
    return players[:limit]

# ======================== ИГРЫ ========================
def get_game_key(update: Update) -> str:
    return f"{update.effective_chat.id}:{update.effective_user.id}"

user_cities_games = {}
user_rps_games = {}
user_sapper_games = {}

MINES_COUNT = 6
TOTAL_CELLS = 18
SAFE_CELLS = TOTAL_CELLS - MINES_COUNT
BOARD_LAYOUT = [(0, 1, 2, 3, 4, 5), (6, 7, 8, 9, 10, 11), (12, 13, 14, 15, 16, 17)]

class SapperGame:
    def __init__(self):
        self.mines = set(random.sample(range(TOTAL_CELLS), MINES_COUNT))
        self.opened = set()
        self.game_over = False
        self.won = False

    def open_cell(self, index: int):
        if self.game_over or index in self.opened:
            return False, False, 0
        if index in self.mines:
            self.game_over = True
            return True, False, 0
        self.opened.add(index)
        if len(self.opened) == SAFE_CELLS:
            self.game_over = True
            self.won = True
        return False, self.won, 1

    def get_board_text(self):
        if self.game_over and not self.won:
            return "💥 Игра окончена! Ты взорвался."
        elif self.won:
            return f"🎉 Победа! Открыто {len(self.opened)}/{SAFE_CELLS} клеток."
        else:
            return f"Открыто безопасных клеток: {len(self.opened)}/{SAFE_CELLS}"

def get_user_mention(user: User) -> str:
    return f"@{user.username}" if user.username else user.first_name

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# ======================== СОЗДАЕМ ПРИЛОЖЕНИЕ TELEGRAM ========================
telegram_app = Application.builder().token(BOT_TOKEN).build()

# ======================== КОМАНДЫ ========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    update_user_stats(user, "cities", 0)
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
        "/top - Топ игроков\n\n"
        f"Всего городов: {len(cities_db)} 🌍"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def games_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("🎮 Города"), KeyboardButton("🧮 КМБ")],
        [KeyboardButton("🎲 Кубик"), KeyboardButton("💣 Сапер")]
    ]
    await update.message.reply_text(
        "🎯 Выбери игру:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_players = get_top_players_total(5)
    if not top_players:
        await update.message.reply_text("🏆 Рейтинг пуст!")
        return
    text = "🏆 **ТОП ИГРОКОВ:**\n\n"
    for i, (name, score) in enumerate(top_players, 1):
        text += f"{i}. {name} — {score} очков\n"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# ======================== ИГРА ГОРОДА ========================
async def cities_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = get_game_key(update)
    start_city = random.choice(cities_db)
    last_letter = get_last_letter(start_city)
    
    user_cities_games[key] = {
        "last_letter": last_letter,
        "used_cities": {start_city.lower()}
    }
    
    await update.message.reply_text(
        f"🎮 **Игра в города!**\n\n"
        f"Я называю: **{start_city}**\n"
        f"Тебе на букву: **'{last_letter.upper()}'**",
        parse_mode=ParseMode.MARKDOWN
    )

async def cities_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = get_game_key(update)
    if key not in user_cities_games:
        return False
    
    user = update.effective_user
    game = user_cities_games[key]
    city_input = update.message.text.strip()
    
    if city_input.lower() == "/cancel":
        del user_cities_games[key]
        await update.message.reply_text("Игра завершена.")
        return True
    
    found_city = find_city_in_db(city_input)
    if not found_city:
        await update.message.reply_text(f"❌ Город '{city_input}' не найден!")
        return True
    
    city_lower = found_city.lower()
    
    if city_lower in game["used_cities"]:
        await update.message.reply_text(f"❌ Город уже был! Ты проиграл!")
        del user_cities_games[key]
        return True
    
    if found_city[0].lower() != game["last_letter"]:
        await update.message.reply_text(f"❌ Нужно на букву '{game['last_letter'].upper()}'!")
        del user_cities_games[key]
        return True
    
    game["used_cities"].add(city_lower)
    update_user_stats(user, "cities", 1)
    
    last_letter = get_last_letter(found_city)
    possible = [c for c in cities_db if c[0].lower() == last_letter and c.lower() not in game["used_cities"]]
    
    if not possible:
        await update.message.reply_text(f"✅ Ты победил! +3 очка")
        update_user_stats(user, "cities", 3)
        del user_cities_games[key]
        return True
    
    bot_city = random.choice(possible)
    game["used_cities"].add(bot_city.lower())
    new_last = get_last_letter(bot_city)
    game["last_letter"] = new_last
    
    await update.message.reply_text(f"{bot_city}\nТебе на букву '{new_last.upper()}'")
    return True

# ======================== КМБ ========================
async def rps_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = get_game_key(update)
    user_rps_games[key] = {"user_score": 0, "bot_score": 0}
    keyboard = [
        [InlineKeyboardButton("🪨", callback_data="rps:rock"),
         InlineKeyboardButton("✂️", callback_data="rps:scissors"),
         InlineKeyboardButton("📄", callback_data="rps:paper")],
        [InlineKeyboardButton("❌ Выйти", callback_data="rps:end")]
    ]
    await update.message.reply_text("КМБ! Выбери:", reply_markup=InlineKeyboardMarkup(keyboard))

async def rps_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    key = f"{query.message.chat.id}:{query.from_user.id}"
    if key not in user_rps_games:
        return
    
    data = query.data.split(":")
    if data[1] == "end":
        del user_rps_games[key]
        await query.edit_message_text("Игра завершена.")
        return
    
    game = user_rps_games[key]
    choices = {"rock": "🪨", "scissors": "✂️", "paper": "📄"}
    user_choice = data[1]
    bot_choice = random.choice(["rock", "scissors", "paper"])
    
    if user_choice == bot_choice:
        result = "🤝 Ничья"
        points = 1
    elif ((user_choice == "rock" and bot_choice == "scissors") or
          (user_choice == "scissors" and bot_choice == "paper") or
          (user_choice == "paper" and bot_choice == "rock")):
        result = "✅ Ты выиграл!"
        game["user_score"] += 1
        points = 3
    else:
        result = "❌ Бот выиграл"
        game["bot_score"] += 1
        points = 0
    
    update_user_stats(query.from_user, "rps", points)
    
    keyboard = [[InlineKeyboardButton("🪨", callback_data="rps:rock"),
                 InlineKeyboardButton("✂️", callback_data="rps:scissors"),
                 InlineKeyboardButton("📄", callback_data="rps:paper")],
                [InlineKeyboardButton("❌ Выйти", callback_data="rps:end")]]
    
    await query.edit_message_text(
        f"{choices[user_choice]} vs {choices[bot_choice]}\n{result}\nСчет: {game['user_score']}:{game['bot_score']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ======================== КУБИК ========================
async def dice_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🎲 Бросить", callback_data="dice:roll")]]
    await update.message.reply_text("Нажми кнопку:", reply_markup=InlineKeyboardMarkup(keyboard))

async def dice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    d1, d2 = random.randint(1, 6), random.randint(1, 6)
    total = d1 + d2
    update_user_stats(query.from_user, "dice", total)
    
    keyboard = [[InlineKeyboardButton("🎲 Ещё", callback_data="dice:roll")]]
    await query.edit_message_text(f"🎲 {d1} и {d2}\nСумма: {total}", reply_markup=InlineKeyboardMarkup(keyboard))

# ======================== САПЁР ========================
async def sapper_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = get_game_key(update)
    user_sapper_games[key] = SapperGame()
    await show_sapper(update, context, key)

async def show_sapper(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    game = user_sapper_games.get(key)
    if not game:
        return
    
    keyboard = []
    for row in BOARD_LAYOUT:
        row_buttons = []
        for idx in row:
            if idx in game.opened:
                row_buttons.append(InlineKeyboardButton("1️⃣", callback_data="skip"))
            elif game.game_over:
                row_buttons.append(InlineKeyboardButton("💣" if idx in game.mines else "⬜", callback_data="skip"))
            else:
                row_buttons.append(InlineKeyboardButton("⬜", callback_data=f"sapper:{idx}"))
        keyboard.append(row_buttons)
    
    keyboard.append([InlineKeyboardButton("🔄 Новая", callback_data="sapper:new")])
    
    if update.callback_query:
        await update.callback_query.edit_message_text(game.get_board_text(), reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(game.get_board_text(), reply_markup=InlineKeyboardMarkup(keyboard))

async def sapper_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    key = f"{query.message.chat.id}:{query.from_user.id}"
    data = query.data.split(":")
    
    if data[1] == "new":
        user_sapper_games[key] = SapperGame()
        await show_sapper(update, context, key)
        return
    
    if len(data) == 2 and data[1].isdigit():
        if key not in user_sapper_games:
            return
        game = user_sapper_games[key]
        idx = int(data[1])
        exploded, won, points = game.open_cell(idx)
        if points > 0:
            update_user_stats(query.from_user, "sapper", points)
        if won:
            update_user_stats(query.from_user, "sapper", 12)
        await show_sapper(update, context, key)

# ======================== ОБЩИЙ ОБРАБОТЧИК ========================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    
    update_user_stats(user, "cities", 0)
    
    if text == "🎮 Города":
        await cities_start(update, context)
    elif text == "🧮 КМБ":
        await rps_start(update, context)
    elif text == "🎲 Кубик":
        await dice_start(update, context)
    elif text == "💣 Сапер":
        await sapper_start(update, context)
    elif await cities_handle(update, context):
        pass
    else:
        await update.message.reply_text("❓ Используй /help")

# ======================== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ ========================
telegram_app.add_handler(CommandHandler("start", start_command))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(CommandHandler("games", games_command))
telegram_app.add_handler(CommandHandler("top", top_command))
telegram_app.add_handler(CallbackQueryHandler(rps_callback, pattern="^rps:"))
telegram_app.add_handler(CallbackQueryHandler(dice_callback, pattern="^dice:"))
telegram_app.add_handler(CallbackQueryHandler(sapper_callback, pattern="^sapper:"))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

# ======================== FLASK МАРШРУТЫ ========================
@app.route('/')
def index():
    return "Бот Спортик друн работает! 🚀"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Принимает обновления от Telegram"""
    if request.headers.get('content-type') != 'application/json':
        return 'OK', 200
    
    try:
        json_str = request.get_data(as_text=True)
        update = Update.de_json(json.loads(json_str), telegram_app.bot)
        
        # Создаём задачу для обработки обновления
        asyncio.create_task(telegram_app.process_update(update))
        return 'OK', 200
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return 'OK', 200  # Всегда возвращаем 200

# ======================== НАСТРОЙКА ВЕБХУКА ========================
async def setup_webhook():
    """Устанавливает вебхук"""
    if RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL.rstrip('/')}/webhook"
        await telegram_app.bot.set_webhook(url=webhook_url)
        logger.info(f"✅ Вебхук установлен: {webhook_url}")

# ======================== ЗАПУСК ========================
if __name__ == "__main__":
    logger.info("🚀 Запуск бота...")
    
    # Запускаем Flask
    port = int(os.environ.get("PORT", 10000))
    
    # Создаём и запускаем event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Устанавливаем вебхук
    loop.run_until_complete(setup_webhook())
    
    # Запускаем Flask в отдельном потоке
    from threading import Thread
    flask_thread = Thread(target=lambda: app.run(host="0.0.0.0", port=port))
    flask_thread.start()
    
    # Запускаем event loop Telegram
    loop.run_forever()
