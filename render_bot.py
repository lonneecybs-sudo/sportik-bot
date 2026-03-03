"""
Telegram Bot для Render (Minesweeper, Gifts, Games)
Адаптировано для работы с вебхуками на Render.com
"""

import os
import json
import logging
import random
import re
import asyncio
from typing import Dict, List, Tuple
from collections import defaultdict
from flask import Flask, request, abort

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, Update, User
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

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
    # Россия и СНГ (40 городов)
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань", "Нижний Новгород", 
    "Челябинск", "Самара", "Омск", "Ростов-на-Дону", "Уфа", "Красноярск", "Воронеж", "Пермь", 
    "Волгоград", "Краснодар", "Саратов", "Тюмень", "Тольятти", "Ижевск", "Барнаул", "Ульяновск", 
    "Иркутск", "Хабаровск", "Ярославль", "Владивосток", "Махачкала", "Томск", "Оренбург", 
    "Кемерово", "Новокузнецк", "Рязань", "Астрахань", "Набережные Челны", "Пенза", "Липецк", 
    "Киров", "Чебоксары", "Калининград", "Балашиха",
    "Киев", "Харьков", "Одесса", "Днепр", "Донецк", "Запорожье", "Львов", "Кривой Рог", "Николаев",
    "Мариуполь", "Винница", "Херсон", "Полтава", "Чернигов", "Черкассы", "Житомир", "Сумы",
    "Минск", "Гомель", "Могилев", "Витебск", "Гродно", "Брест", "Бобруйск",
    "Астана", "Алматы", "Шымкент", "Караганда", "Актобе", "Тараз", "Павлодар", "Усть-Каменогорск",
    "Баку", "Тбилиси", "Ереван", "Кишинев", "Ташкент", "Самарканд", "Бишкек", "Душанбе",
    
    # Европа (60 городов)
    "Лондон", "Париж", "Берлин", "Мадрид", "Рим", "Амстердам", "Брюссель", "Вена", "Стокгольм", 
    "Осло", "Хельсинки", "Копенгаген", "Варшава", "Прага", "Будапешт", "Белград", "София", 
    "Бухарест", "Загреб", "Любляна", "Братислава", "Таллин", "Рига", "Вильнюс", "Дублин", 
    "Лиссабон", "Афины", "Стамбул", "Анкара", "Измир", "Барселона", "Милан", "Неаполь", "Турин", 
    "Мюнхен", "Гамбург", "Франкфурт", "Кёльн", "Штутгарт", "Лион", "Марсель", "Тулуза", "Ницца", 
    "Бордо", "Манчестер", "Бирмингем", "Глазго", "Ливерпуль", "Эдинбург", "Цюрих", "Женева", 
    "Берн", "Лозанна", "Краков", "Лодзь", "Вроцлав", "Познань", "Гданьск", "Бургас", "Варна",
    
    # Азия (50 городов)
    "Токио", "Осака", "Киото", "Иокогама", "Нагоя", "Саппоро", "Фукуока", "Сеул", "Пусан", 
    "Инчхон", "Пекин", "Шанхай", "Гонконг", "Тяньцзинь", "Чунцин", "Гуанчжоу", "Шэньчжэнь", 
    "Чэнду", "Ухань", "Сиань", "Нанкин", "Ханчжоу", "Тайбэй", "Бангкок", "Пхукет", "Чиангмай", 
    "Сингапур", "Куала-Лумпур", "Джохор-Бару", "Ипох", "Джакарта", "Сурабая", "Бандунг", "Бали", 
    "Манила", "Кесон-Сити", "Давао", "Ханой", "Хошимин", "Дананг", "Нячанг", "Дели", "Мумбаи", 
    "Бангалор", "Ченнаи", "Калькутта", "Коломбо", "Карачи", "Лахор", "Исламабад",
    
    # Ближний Восток (25 городов)
    "Дубай", "Абу-Даби", "Шарджа", "Доха", "Эр-Рияд", "Джидда", "Мекка", "Медина", "Кувейт", 
    "Манама", "Маскат", "Амман", "Бейрут", "Дамаск", "Алеппо", "Багдад", "Тегеран", "Мешхед", 
    "Исфахан", "Шираз", "Тель-Авив", "Иерусалим", "Хайфа", "Никосия", "Анкара",
    
    # Америка (50 городов)
    "Нью-Йорк", "Лос-Анджелес", "Чикаго", "Хьюстон", "Финикс", "Филадельфия", "Сан-Антонио", 
    "Сан-Диего", "Даллас", "Сан-Хосе", "Остин", "Джэксонвилл", "Форт-Уэрт", "Колумбус", 
    "Шарлотт", "Сан-Франциско", "Индианаполис", "Сиэтл", "Денвер", "Вашингтон", "Бостон", 
    "Эль-Пасо", "Нэшвилл", "Детройт", "Мемфис", "Портленд", "Оклахома-Сити", "Лас-Вегас", 
    "Луисвилл", "Балтимор", "Милуоки", "Альбукерке", "Тусон", "Фресно", "Сакраменто", 
    "Мехико", "Экатепек", "Гвадалахара", "Пуэбла", "Тихуана", "Сьюдад-Хуарес", "Леон", 
    "Торонто", "Монреаль", "Ванкувер", "Калгари", "Оттава", "Эдмонтон", "Квебек", "Галифакс",
    
    # Африка (25 городов)
    "Каир", "Александрия", "Гиза", "Лагос", "Кано", "Ибадан", "Кейптаун", "Йоханнесбург", 
    "Дурбан", "Претория", "Порт-Элизабет", "Найроби", "Момбаса", "Кисуму", "Аддис-Абеба", 
    "Дар-эс-Салам", "Додома", "Занзибар", "Касабланка", "Рабат", "Марракеш", "Фес", "Танжер", 
    "Алжир", "Тунис",
    
    # Австралия и Океания (15 городов)
    "Сидней", "Мельбурн", "Брисбен", "Перт", "Аделаида", "Голд-Кост", "Канберра", "Ньюкасл", 
    "Вуллонгонг", "Окленд", "Веллингтон", "Крайстчерч", "Гамильтон", "Тауранга", "Данидин"
]

# Загружаем или создаем список городов
cities_db = load_json(CITIES_FILE, default=DEFAULT_CITIES)

# СОЗДАЕМ НЕСКОЛЬКО ВАРИАНТОВ ДЛЯ ПОИСКА:
cities_lower_set = {city.lower() for city in cities_db}
cities_dict = {city.lower(): city for city in cities_db}

if not load_json(CITIES_FILE):
    save_json(CITIES_FILE, cities_db)

logger.info(f"✅ Загружено {len(cities_db)} городов для игры")

# Функция для нормализации города
def normalize_city_name(city_name: str) -> str:
    normalized = re.sub(r'[-\s]+', ' ', city_name.lower().strip())
    return normalized

def find_city_in_db(city_name: str) -> str:
    city_clean = city_name.lower().strip()
    
    if city_clean in cities_dict:
        return cities_dict[city_clean]
    
    city_no_hyphen = city_clean.replace('-', ' ')
    if city_no_hyphen in cities_dict:
        return cities_dict[city_no_hyphen]
    
    for db_city_lower, db_city_orig in cities_dict.items():
        if db_city_lower.replace('-', ' ') == city_no_hyphen:
            return db_city_orig
    
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
    
    if "stats" not in users_data[user_id]:
        users_data[user_id]["stats"] = {"cities": 0, "rps": 0, "dice": 0, "sapper": 0}
    
    users_data[user_id]["stats"][game] = users_data[user_id]["stats"].get(game, 0) + points
    
    save_users(users_data)
    return users_data[user_id]["stats"][game]

def get_user_total_score(user_id: str) -> int:
    users_data = load_users()
    if user_id not in users_data:
        return 0
    stats = users_data[user_id].get("stats", {})
    return sum(stats.values())

def get_top_players_total(limit: int = 10) -> List[Tuple[str, int, Dict]]:
    users_data = load_users()
    players = []
    
    for user_id, data in users_data.items():
        name = data.get("first_name", "Unknown")
        stats = data.get("stats", {"cities": 0, "rps": 0, "dice": 0, "sapper": 0})
        total = sum(stats.values())
        if total > 0:
            players.append((name, total, stats))
    
    players.sort(key=lambda x: x[1], reverse=True)
    return players[:limit]

def get_top_players_by_game(game: str, limit: int = 10) -> List[Tuple[str, int]]:
    users_data = load_users()
    players = []
    
    for user_id, data in users_data.items():
        name = data.get("first_name", "Unknown")
        stats = data.get("stats", {})
        score = stats.get(game, 0)
        if score > 0:
            players.append((name, score))
    
    players.sort(key=lambda x: x[1], reverse=True)
    return players[:limit]

# ======================== ИГРЫ ========================
def get_game_key(update: Update) -> str:
    return f"{update.effective_chat.id}:{update.effective_user.id}"

user_cities_games = {}
user_rps_games = {}

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

user_sapper_games: Dict[str, SapperGame] = {}

def get_user_mention(user: User) -> str:
    return f"@{user.username}" if user.username else user.first_name

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# ======================== СОЗДАЕМ ПРИЛОЖЕНИЕ TELEGRAM ========================
telegram_app = Application.builder().token(BOT_TOKEN).updater(None).build()

# ======================== КОМАНДЫ: START И HELP ========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = user.first_name
    
    update_user_stats(user, "cities", 0)
    
    welcome_text = (
        f"Приветствую, {user_name}! 🤗\n\n"
        f"Я развлекательный бот Спортик друн😝, у меня есть много разных навыков❤️‍🩹\n\n"
        f"Напиши /help что бы узнать подробнее!😁"
    )
    
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🎮 **Доступные команды:**\n\n"
        
        "📌 **Основные команды:**\n"
        "/start - Приветствие\n"
        "/help - Это сообщение\n"
        "/games - Меню со всеми играми\n"
        "/gift [текст] - Отправить подарок случайному пользователю\n"
        "/top - Общий топ игроков во всех играх\n"
        "/topcities - Топ игроков в города\n"
        "/toprps - Топ игроков в КМБ\n"
        "/topdice - Топ игроков в кубик\n"
        "/topsapper - Топ игроков в сапёра\n"
        "/mystats - Твоя личная статистика\n\n"
        
        "🎯 **Игры:**\n"
        "• 🎮 Города - Классическая игра в города\n"
        "• 🧮 КМБ - Камень, ножницы, бумага\n"
        "• 🎲 Кубик - Бросок двух кубиков\n"
        "• 💣 Сапёр - Найди все безопасные клетки\n\n"
        
        "🎁 **Система подарков:**\n"
        "Отправь /gift с текстом, и твой подарок будет передан случайному пользователю!\n\n"
        
        "🏆 **Таблица лидеров:**\n"
        "Играй в игры, зарабатывай очки и становись лучшим!\n\n"
        
        f"Всего в игре доступно **{len(cities_db)} городов** из разных стран мира! 🌍\n\n"
        
        "Приятного времяпровождения! 🌟"
    )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ======================== СТАТИСТИКА ========================
async def my_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users_data = load_users()
    user_id = str(user.id)
    
    if user_id not in users_data:
        await update.message.reply_text("У тебя пока нет статистики. Сыграй в игры!")
        return
    
    stats = users_data[user_id].get("stats", {"cities": 0, "rps": 0, "dice": 0, "sapper": 0})
    total = sum(stats.values())
    
    stats_text = (
        f"📊 **Твоя статистика, {user.first_name}:**\n\n"
        f"🎮 Города: {stats['cities']} очков\n"
        f"🧮 КМБ: {stats['rps']} очков\n"
        f"🎲 Кубик: {stats['dice']} очков\n"
        f"💣 Сапёр: {stats['sapper']} очков\n"
        f"━━━━━━━━━━━━━━\n"
        f"🏆 **Всего: {total} очков**"
    )
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_players = get_top_players_total(10)
    
    if not top_players:
        await update.message.reply_text("🏆 Рейтинг пуст. Сыграй в игры и стань первым!")
        return
    
    text = "🏆 **ОБЩИЙ ТОП ИГРОКОВ:**\n\n"
    for i, (name, total, stats) in enumerate(top_players, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🎮"
        text += f"{medal} {i}. {name} — **{total}** очков\n"
        text += f"   ├ Города: {stats['cities']} | КМБ: {stats['rps']}\n"
        text += f"   └ Кубик: {stats['dice']} | Сапёр: {stats['sapper']}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def top_cities_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = get_top_players_by_game("cities", 10)
    
    if not top:
        await update.message.reply_text("🏆 В города ещё никто не играл. Сыграй первым!")
        return
    
    text = "🏆 **ТОП ИГРОКОВ В ГОРОДА:**\n\n"
    for i, (name, score) in enumerate(top, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🎮"
        text += f"{medal} {i}. {name} — {score} очков\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def top_rps_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = get_top_players_by_game("rps", 10)
    
    if not top:
        await update.message.reply_text("🏆 В КМБ ещё никто не играл. Сыграй первым!")
        return
    
    text = "🏆 **ТОП ИГРОКОВ В КМБ:**\n\n"
    for i, (name, score) in enumerate(top, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🎮"
        text += f"{medal} {i}. {name} — {score} очков\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def top_dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = get_top_players_by_game("dice", 10)
    
    if not top:
        await update.message.reply_text("🏆 В кубик ещё никто не играл. Сыграй первым!")
        return
    
    text = "🏆 **ТОП ИГРОКОВ В КУБИК:**\n\n"
    for i, (name, score) in enumerate(top, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🎮"
        text += f"{medal} {i}. {name} — {score} очков\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def top_sapper_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = get_top_players_by_game("sapper", 10)
    
    if not top:
        await update.message.reply_text("🏆 В сапёра ещё никто не играл. Сыграй первым!")
        return
    
    text = "🏆 **ТОП ИГРОКОВ В САПЁРА:**\n\n"
    for i, (name, score) in enumerate(top, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "💣"
        text += f"{medal} {i}. {name} — {score} очков\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ======================== ПОДАРКИ ========================
async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("🎁 Напиши текст подарка. Пример:\n/gift С днем рождения!")
        return
    gift_text = " ".join(context.args)
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🎁 Новый подарок от {get_user_mention(user)} (ID: {user.id}):\n\n«{gift_text}»",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Выбрать случайного получателя 🔀", callback_data=f"gift_choose:{user.id}:{gift_text}")
        ]])
    )
    await update.message.reply_text("✅ Твой подарок отправлен на рассмотрение!")

async def gift_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только администратор может выбирать получателя.")
        return
    data = query.data.split(":", 2)
    if len(data) != 3:
        return
    _, sender_id_str, gift_text = data
    sender_id = int(sender_id_str)
    try:
        sender = await context.bot.get_chat(sender_id)
    except:
        await query.edit_message_text("Ошибка: не удалось найти отправителя.")
        return
    users_data = load_users()
    candidates = [uid for uid in users_data.keys() if int(uid) not in (sender_id, ADMIN_ID)]
    if not candidates:
        await query.edit_message_text("❌ Нет доступных получателей.")
        return
    receiver_id = random.choice(candidates)
    try:
        receiver = await context.bot.get_chat(int(receiver_id))
    except:
        await query.edit_message_text("Ошибка: не удалось найти получателя.")
        return
    await context.bot.send_message(
        chat_id=receiver_id,
        text=f"🎁 Тебе пришёл подарок от {get_user_mention(sender)}!\n\n«{gift_text}»"
    )
    await query.edit_message_text(f"✅ Подарок отправлен пользователю {get_user_mention(receiver)}.")

# ======================== ИГРЫ: МЕНЮ ========================
async def games_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("🎮 Города"), KeyboardButton("🧮 КМБ")],
        [KeyboardButton("🎲 Кубик"), KeyboardButton("💣 Сапер")]
    ]
    await update.message.reply_text(
        "🎯 **Выбери игру из меню ниже:**",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        parse_mode='Markdown'
    )

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
        f"Тебе нужно назвать город на букву: **'{last_letter.upper()}'**\n"
        f"Всего городов в базе: {len(cities_db)} 🌍\n\n"
        f"Правила:\n"
        f"• Город должен быть в моей базе\n"
        f"• Нельзя повторять города\n"
        f"• Название можно писать с большой или маленькой буквы\n"
        f"• Для выхода напиши /cancel",
        parse_mode='Markdown'
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
        await update.message.reply_text("Игра завершена. Возвращайся к /games")
        return True
    
    found_city = find_city_in_db(city_input)
    
    if not found_city:
        await update.message.reply_text(
            f"❌ Город '{city_input}' не найден в моей базе данных!\n"
            f"Попробуй другой город или напиши /cancel для выхода.",
            parse_mode='Markdown'
        )
        return True
    
    city_lower = found_city.lower()
    
    if city_lower in game["used_cities"]:
        await update.message.reply_text(
            f"❌ Город '{found_city}' уже был назван! Ты проиграл!\n"
            f"Сыграем еще? /games",
            parse_mode='Markdown'
        )
        del user_cities_games[key]
        return True
    
    first_letter = found_city[0].lower()
    if first_letter != game["last_letter"]:
        await update.message.reply_text(
            f"❌ Город должен начинаться на букву '{game['last_letter'].upper()}'!\n"
            f"Ты назвал '{found_city}' на букву '{first_letter.upper()}'. Ты проиграл!\n"
            f"Сыграем еще? /games",
            parse_mode='Markdown'
        )
        del user_cities_games[key]
        return True
    
    game["used_cities"].add(city_lower)
    update_user_stats(user, "cities", 1)
    
    last_letter = get_last_letter(found_city)
    
    possible_cities = []
    for city in cities_db:
        city_low = city.lower()
        if (city_low[0] == last_letter and 
            city_low not in game["used_cities"]):
            possible_cities.append(city)
    
    if not possible_cities:
        await update.message.reply_text(
            f"✅ Я не знаю больше городов на букву '{last_letter.upper()}'. Ты победил!\n"
            f"🏆 +3 очка за победу!\n"
            f"Сыграем еще? /games",
            parse_mode='Markdown'
        )
        update_user_stats(user, "cities", 3)
        del user_cities_games[key]
        return True
    
    bot_city = random.choice(possible_cities)
    game["used_cities"].add(bot_city.lower())
    
    new_last_letter = get_last_letter(bot_city)
    game["last_letter"] = new_last_letter
    
    await update.message.reply_text(
        f"**{bot_city}**\n"
        f"Тебе на букву: **'{new_last_letter.upper()}'**",
        parse_mode='Markdown'
    )
    return True

# ======================== КМБ ========================
async def rps_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = get_game_key(update)
    user_rps_games[key] = {"user_score": 0, "bot_score": 0}
    keyboard = [
        [InlineKeyboardButton("🪨 Камень", callback_data="rps:rock"),
         InlineKeyboardButton("✂️ Ножницы", callback_data="rps:scissors"),
         InlineKeyboardButton("📄 Бумага", callback_data="rps:paper")],
        [InlineKeyboardButton("❌ Выйти", callback_data="rps:end")]
    ]
    await update.message.reply_text(
        "🧮 **Камень-Ножницы-Бумага!**\n"
        "Счет: 0:0\n"
        "Выбери свой ход:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def rps_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    key = f"{query.message.chat.id}:{user.id}"
    
    if key not in user_rps_games:
        await query.edit_message_text("Игра не найдена. Начни новую через /games")
        return
    
    data = query.data.split(":")
    if data[1] == "end":
        del user_rps_games[key]
        await query.edit_message_text("Игра завершена. Возвращайся к /games")
        return
    
    game = user_rps_games[key]
    choices = {"rock": "🪨", "scissors": "✂️", "paper": "📄"}
    user_choice = data[1]
    bot_choice = random.choice(["rock", "scissors", "paper"])
    
    if user_choice == bot_choice:
        result = "🤝 Ничья"
        points = 1
        update_user_stats(user, "rps", points)
    elif (
        (user_choice == "rock" and bot_choice == "scissors") or
        (user_choice == "scissors" and bot_choice == "paper") or
        (user_choice == "paper" and bot_choice == "rock")
    ):
        result = "✅ Ты выиграл!"
        game["user_score"] += 1
        points = 3
        update_user_stats(user, "rps", points)
    else:
        result = "❌ Бот выиграл"
        game["bot_score"] += 1
        points = 0
    
    keyboard = [
        [InlineKeyboardButton("🪨", callback_data="rps:rock"),
         InlineKeyboardButton("✂️", callback_data="rps:scissors"),
         InlineKeyboardButton("📄", callback_data="rps:paper")],
        [InlineKeyboardButton("❌ Выйти", callback_data="rps:end")]
    ]
    
    points_text = f"✨ +{points} очков" if points > 0 else ""
    await query.edit_message_text(
        f"Ты: {choices[user_choice]} | Бот: {choices[bot_choice]}\n"
        f"{result}\n"
        f"Счет: {game['user_score']}:{game['bot_score']}\n"
        f"{points_text}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ======================== КУБИК ========================
async def dice_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🎲 Бросить кости", callback_data="dice:roll")]]
    await update.message.reply_text(
        "🎲 **Нажми кнопку, чтобы бросить два кубика:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def dice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    d1, d2 = random.randint(1, 6), random.randint(1, 6)
    total = d1 + d2
    
    update_user_stats(user, "dice", total)
    
    keyboard = [[InlineKeyboardButton("🎲 Бросить ещё", callback_data="dice:roll")]]
    
    await query.edit_message_text(
        f"🎲 **Тебе выпало:** {d1} и {d2}\n"
        f"**Сумма:** {total}\n"
        f"✨ +{total} очков!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

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
                if idx in game.mines:
                    row_buttons.append(InlineKeyboardButton("💣", callback_data="skip"))
                else:
                    row_buttons.append(InlineKeyboardButton("⬜", callback_data="skip"))
            else:
                row_buttons.append(InlineKeyboardButton("⬜", callback_data=f"sapper:{idx}"))
        keyboard.append(row_buttons)
    
    keyboard.append([InlineKeyboardButton("🔄 Новая игра", callback_data="sapper:new")])
    
    text = game.get_board_text()
    if game.game_over and game.won:
        text += "\n✨ +12 очков за победу!"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            text, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def sapper_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    key = f"{query.message.chat.id}:{user.id}"
    data = query.data.split(":")
    
    if data[0] == "sapper" and data[1] == "new":
        user_sapper_games[key] = SapperGame()
        await show_sapper(update, context, key)
        return
    
    if len(data) == 2 and data[0] == "sapper" and data[1].isdigit():
        if key not in user_sapper_games:
            return
        
        game = user_sapper_games[key]
        idx = int(data[1])
        exploded, won, points = game.open_cell(idx)
        
        if points > 0:
            update_user_stats(user, "sapper", points)
        
        if won:
            update_user_stats(user, "sapper", 12)
        
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
        await update.message.reply_text(
            "❓ Неизвестная команда.\n"
            "Используй /help для списка команд или /games для игр!"
        )

# ======================== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ ========================
telegram_app.add_handler(CommandHandler("start", start_command))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(CommandHandler("games", games_command))
telegram_app.add_handler(CommandHandler("gift", gift_command))
telegram_app.add_handler(CommandHandler("mystats", my_stats_command))
telegram_app.add_handler(CommandHandler("top", top_command))
telegram_app.add_handler(CommandHandler("topcities", top_cities_command))
telegram_app.add_handler(CommandHandler("toprps", top_rps_command))
telegram_app.add_handler(CommandHandler("topdice", top_dice_command))
telegram_app.add_handler(CommandHandler("topsapper", top_sapper_command))

telegram_app.add_handler(CallbackQueryHandler(gift_callback_handler, pattern="^gift_choose"))
telegram_app.add_handler(CallbackQueryHandler(rps_callback, pattern="^rps:"))
telegram_app.add_handler(CallbackQueryHandler(dice_callback, pattern="^dice:"))
telegram_app.add_handler(CallbackQueryHandler(sapper_callback, pattern="^sapper:"))

telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

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
    return "🤖 Бот Спортик друн работает на Render!", 200

@app.route('/health')
def health():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Принимает обновления от Telegram"""
    if request.headers.get('content-type') != 'application/json':
        abort(403)
    
    json_str = request.get_data(as_text=True)
    update = Update.de_json(json.loads(json_str), telegram_app.bot)
    
    asyncio.run_coroutine_threadsafe(
        telegram_app.process_update(update),
        telegram_app.loop
    )
    
    return '', 200

# ======================== ЗАПУСК ========================
if __name__ == "__main__":
    logger.info("🚀 Запуск бота на Render...")
    
    # Создаём event loop для Telegram
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Устанавливаем вебхук
    loop.run_until_complete(setup_webhook())
    
    # Запускаем Flask
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
