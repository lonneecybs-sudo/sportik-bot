import os
import json
import logging
import random
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, CallbackQueryHandler, Filters

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 8259326703
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

bot = Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)

USERS_FILE = "users.json"
CITIES_FILE = "cities.json"

def load_json(file_path, default=None):
    if default is None:
        default = {} if file_path == USERS_FILE else []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

DEFAULT_CITIES = [
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань",
    "Лондон", "Париж", "Берлин", "Мадрид", "Рим", "Токио", "Пекин",
    "Нью-Йорк", "Лос-Анджелес", "Чикаго", "Сидней", "Мельбурн"
]

cities_db = load_json(CITIES_FILE, default=DEFAULT_CITIES)
cities_dict = {city.lower(): city for city in cities_db}

if not load_json(CITIES_FILE):
    save_json(CITIES_FILE, cities_db)

def load_users():
    return load_json(USERS_FILE, default={})

def save_users(users_data):
    save_json(USERS_FILE, users_data)

def update_user_stats(user, game, points=1):
    users_data = load_users()
    user_id = str(user.id)
    
    if user_id not in users_data:
        users_data[user_id] = {
            "first_name": user.first_name,
            "username": user.username,
            "stats": {"cities": 0, "rps": 0, "dice": 0, "sapper": 0}
        }
    
    users_data[user_id]["stats"][game] = users_data[user_id]["stats"].get(game, 0) + points
    save_users(users_data)
    return users_data[user_id]["stats"][game]

def get_top_players(limit=10):
    users_data = load_users()
    players = []
    for user_id, data in users_data.items():
        name = data.get("first_name", "Unknown")
        total = sum(data.get("stats", {}).values())
        if total > 0:
            players.append((name, total))
    players.sort(key=lambda x: x[1], reverse=True)
    return players[:limit]

def get_game_key(update):
    return f"{update.effective_chat.id}:{update.effective_user.id}"

def get_last_letter(city):
    name = city.lower()
    for i in range(len(name) - 1, -1, -1):
        if name[i] not in 'ьъы':
            return name[i]
    return name[-1]

user_cities_games = {}
user_rps_games = {}

def start(update, context):
    user = update.effective_user
    update_user_stats(user, "cities", 0)
    update.message.reply_text(
        f"Привет, {user.first_name}! 🤗\n\n"
        f"Я бот Спортик друн!\n"
        f"Напиши /help для списка команд"
    )

def help(update, context):
    update.message.reply_text(
        "📋 **Доступные команды:**\n\n"
        "/start - Приветствие\n"
        "/help - Это меню\n"
        "/games - Игры 🎮\n"
        "/top - Топ игроков 🏆\n"
        "/gift [текст] - Отправить подарок 🎁",
        parse_mode="Markdown"
    )

def games(update, context):
    keyboard = [
        [KeyboardButton("🎮 Города"), KeyboardButton("🧮 КМБ")],
        [KeyboardButton("🎲 Кубик"), KeyboardButton("💣 Сапер")]
    ]
    update.message.reply_text(
        "Выбери игру:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

def top(update, context):
    players = get_top_players(10)
    if not players:
        update.message.reply_text("🏆 Рейтинг пуст!")
        return
    
    text = "🏆 **ТОП ИГРОКОВ:**\n\n"
    for i, (name, score) in enumerate(players, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
        text += f"{medal} {i}. {name} — {score} очков\n"
    
    update.message.reply_text(text, parse_mode="Markdown")

def gift(update, context):
    if not context.args:
        update.message.reply_text("🎁 Напиши текст подарка. Пример:\n/gift Привет!")
        return
    
    gift_text = " ".join(context.args)
    user = update.effective_user
    
    context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🎁 Подарок от {user.first_name} (ID: {user.id}):\n\n{gift_text}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Выбрать получателя 🔀", callback_data=f"gift:{user.id}:{gift_text}")
        ]])
    )
    
    update.message.reply_text("✅ Подарок отправлен!")

def gift_callback(update, context):
    query = update.callback_query
    query.answer()
    
    if query.from_user.id != ADMIN_ID:
        query.edit_message_text("❌ Только админ может выбирать!")
        return
    
    data = query.data.split(":", 2)
    if len(data) != 3:
        return
    
    sender_id = int(data[1])
    gift_text = data[2]
    
    users_data = load_users()
    candidates = [uid for uid in users_data.keys() if int(uid) not in (sender_id, ADMIN_ID)]
    
    if not candidates:
        query.edit_message_text("❌ Нет получателей!")
        return
    
    receiver_id = random.choice(candidates)
    try:
        receiver = context.bot.get_chat(int(receiver_id))
        context.bot.send_message(
            chat_id=receiver_id,
            text=f"🎁 Тебе подарок!\n\n{gift_text}"
        )
        query.edit_message_text(f"✅ Подарок отправлен {receiver.first_name}")
    except:
        query.edit_message_text("❌ Ошибка отправки")

def cities_start(update, context):
    key = get_game_key(update)
    start_city = random.choice(cities_db)
    last_letter = get_last_letter(start_city)
    
    user_cities_games[key] = {
        "last_letter": last_letter,
        "used": {start_city.lower()}
    }
    
    update.message.reply_text(
        f"🎮 **Города!**\n\nЯ: {start_city}\nТебе на **{last_letter.upper()}**",
        parse_mode="Markdown"
    )

def cities_handle(update, context):
    key = get_game_key(update)
    if key not in user_cities_games:
        return False
    
    user = update.effective_user
    game = user_cities_games[key]
    city = update.message.text.strip()
    
    if city.lower() == "/cancel":
        del user_cities_games[key]
        update.message.reply_text("Игра завершена")
        return True
    
    city_lower = city.lower()
    if city_lower not in cities_dict:
        update.message.reply_text("❌ Нет такого города!")
        return True
    
    if city_lower in game["used"]:
        update.message.reply_text("❌ Уже был! Ты проиграл!")
        del user_cities_games[key]
        return True
    
    if city[0].lower() != game["last_letter"]:
        update.message.reply_text(f"❌ Нужно на '{game['last_letter'].upper()}'!")
        del user_cities_games[key]
        return True
    
    game["used"].add(city_lower)
    update_user_stats(user, "cities", 1)
    
    last = get_last_letter(city)
    possible = [c for c in cities_db if c[0].lower() == last and c.lower() not in game["used"]]
    
    if not possible:
        update.message.reply_text("✅ Ты победил! +3 очка")
        update_user_stats(user, "cities", 3)
        del user_cities_games[key]
        return True
    
    bot_city = random.choice(possible)
    game["used"].add(bot_city.lower())
    new_last = get_last_letter(bot_city)
    game["last_letter"] = new_last
    
    update.message.reply_text(f"{bot_city}\nТебе на **{new_last.upper()}**", parse_mode="Markdown")
    return True

def rps_start(update, context):
    key = get_game_key(update)
    user_rps_games[key] = {"user": 0, "bot": 0}
    
    keyboard = [
        [InlineKeyboardButton("🪨", callback_data="rps:rock"),
         InlineKeyboardButton("✂️", callback_data="rps:scissors"),
         InlineKeyboardButton("📄", callback_data="rps:paper")],
        [InlineKeyboardButton("❌ Выйти", callback_data="rps:end")]
    ]
    
    update.message.reply_text("КМБ! Выбирай:", reply_markup=InlineKeyboardMarkup(keyboard))

def rps_callback(update, context):
    query = update.callback_query
    query.answer()
    
    key = f"{query.message.chat.id}:{query.from_user.id}"
    if key not in user_rps_games:
        return
    
    data = query.data.split(":")
    if data[1] == "end":
        del user_rps_games[key]
        query.edit_message_text("Игра завершена")
        return
    
    game = user_rps_games[key]
    choices = {"rock": "🪨", "scissors": "✂️", "paper": "📄"}
    user_choice = data[1]
    bot_choice = random.choice(["rock", "scissors", "paper"])
    
    if user_choice == bot_choice:
        result = "🤝 Ничья"
        points = 1
    elif (
        (user_choice == "rock" and bot_choice == "scissors") or
        (user_choice == "scissors" and bot_choice == "paper") or
        (user_choice == "paper" and bot_choice == "rock")
    ):
        result = "✅ Ты выиграл!"
        game["user"] += 1
        points = 3
    else:
        result = "❌ Бот выиграл"
        game["bot"] += 1
        points = 0
    
    update_user_stats(query.from_user, "rps", points)
    
    keyboard = [
        [InlineKeyboardButton("🪨", callback_data="rps:rock"),
         InlineKeyboardButton("✂️", callback_data="rps:scissors"),
         InlineKeyboardButton("📄", callback_data="rps:paper")],
        [InlineKeyboardButton("❌ Выйти", callback_data="rps:end")]
    ]
    
    query.edit_message_text(
        f"{choices[user_choice]} vs {choices[bot_choice]}\n"
        f"{result}\n"
        f"Счет: {game['user']}:{game['bot']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def dice_start(update, context):
    keyboard = [[InlineKeyboardButton("🎲 Бросить", callback_data="dice:roll")]]
    update.message.reply_text("Нажми кнопку:", reply_markup=InlineKeyboardMarkup(keyboard))

def dice_callback(update, context):
    query = update.callback_query
    query.answer()
    
    d1, d2 = random.randint(1, 6), random.randint(1, 6)
    total = d1 + d2
    update_user_stats(query.from_user, "dice", total)
    
    keyboard = [[InlineKeyboardButton("🎲 Ещё", callback_data="dice:roll")]]
    query.edit_message_text(
        f"🎲 {d1} и {d2}\nСумма: {total}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def message_handler(update, context):
    text = update.message.text
    user = update.effective_user
    update_user_stats(user, "cities", 0)
    
    if text == "🎮 Города":
        cities_start(update, context)
    elif text == "🧮 КМБ":
        rps_start(update, context)
    elif text == "🎲 Кубик":
        dice_start(update, context)
    elif text == "💣 Сапер":
        update.message.reply_text("🚧 Сапер в разработке")
    elif cities_handle(update, context):
        pass
    else:
        update.message.reply_text("❓ Используй /help")

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help))
dispatcher.add_handler(CommandHandler("games", games))
dispatcher.add_handler(CommandHandler("top", top))
dispatcher.add_handler(CommandHandler("gift", gift))
dispatcher.add_handler(CallbackQueryHandler(gift_callback, pattern="^gift:"))
dispatcher.add_handler(CallbackQueryHandler(rps_callback, pattern="^rps:"))
dispatcher.add_handler(CallbackQueryHandler(dice_callback, pattern="^dice:"))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, message_handler))

@app.route('/')
def index():
    return "✅ Бот Спортик друн работает!"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') != 'application/json':
        return "OK", 200
    
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        return "OK", 200
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return "OK", 200

if __name__ == "__main__":
    logger.info("Запуск бота...")
    if RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL.rstrip('/')}/webhook"
        bot.set_webhook(url=webhook_url)
        logger.info(f"Вебхук: {webhook_url}")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
