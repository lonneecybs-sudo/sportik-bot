import os
import json
import logging
import random
from flask import Flask, request
import telegram

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
TOKEN = os.environ.get("BOT_TOKEN")
URL = os.environ.get("RENDER_EXTERNAL_URL", "")
bot = telegram.Bot(token=TOKEN)

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

def update_user_stats(user_id, user_name, game, points=1):
    users_data = load_users()
    uid = str(user_id)
    if uid not in users_data:
        users_data[uid] = {"name": user_name, "stats": {"cities": 0, "rps": 0, "dice": 0}}
    users_data[uid]["stats"][game] = users_data[uid]["stats"].get(game, 0) + points
    save_users(users_data)

def get_last_letter(city):
    name = city.lower()
    for i in range(len(name)-1, -1, -1):
        if name[i] not in 'ьъы':
            return name[i]
    return name[-1]

user_cities = {}

@app.route('/')
def index():
    return "Бот Спортик работает!"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    text = update.message.text

    if text == "/start":
        bot.send_message(chat_id=chat_id, text=f"Привет, {user_name}! Я Спортик бот.\nКоманды: /help")

    elif text == "/help":
        bot.send_message(chat_id=chat_id, text="/games - игры\n/top - рейтинг")

    elif text == "/games":
        keyboard = [[telegram.KeyboardButton("🎮 Города")], [telegram.KeyboardButton("🧮 КМБ")], [telegram.KeyboardButton("🎲 Кубик")]]
        reply_markup = telegram.ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        bot.send_message(chat_id=chat_id, text="Выбери игру:", reply_markup=reply_markup)

    elif text == "/top":
        users = load_users()
        top = sorted(users.items(), key=lambda x: sum(x[1]["stats"].values()), reverse=True)[:5]
        msg = "🏆 ТОП-5:\n"
        for i, (uid, data) in enumerate(top, 1):
            total = sum(data["stats"].values())
            msg += f"{i}. {data['name']} - {total} очков\n"
        bot.send_message(chat_id=chat_id, text=msg)

    elif text == "🎮 Города":
        start_city = random.choice(cities_db)
        last = get_last_letter(start_city)
        user_cities[user_id] = {"last": last, "used": [start_city.lower()]}
        bot.send_message(chat_id=chat_id, text=f"Я: {start_city}\nТебе на {last.upper()}")

    elif text == "🧮 КМБ":
        keyboard = [[telegram.InlineKeyboardButton("🪨", callback_data="rock"),
                     telegram.InlineKeyboardButton("✂️", callback_data="scissors"),
                     telegram.InlineKeyboardButton("📄", callback_data="paper")]]
        reply_markup = telegram.InlineKeyboardMarkup(keyboard)
        bot.send_message(chat_id=chat_id, text="Выбирай:", reply_markup=reply_markup)

    elif text == "🎲 Кубик":
        d1, d2 = random.randint(1,6), random.randint(1,6)
        total = d1 + d2
        update_user_stats(user_id, user_name, "dice", total)
        bot.send_message(chat_id=chat_id, text=f"🎲 {d1} и {d2}\nСумма: {total}")

    elif user_id in user_cities:
        game = user_cities[user_id]
        city = text.lower()
        if city in game["used"]:
            bot.send_message(chat_id=chat_id, text="Уже было! Ты проиграл")
            del user_cities[user_id]
        elif city not in cities_dict:
            bot.send_message(chat_id=chat_id, text="Нет такого города")
        elif city[0] != game["last"]:
            bot.send_message(chat_id=chat_id, text=f"Нужно на {game['last'].upper()}")
            del user_cities[user_id]
        else:
            game["used"].append(city)
            last = get_last_letter(city)
            possible = [c for c in cities_db if c[0].lower() == last and c.lower() not in game["used"]]
            if not possible:
                bot.send_message(chat_id=chat_id, text="Ты выиграл! +3 очка")
                update_user_stats(user_id, user_name, "cities", 3)
                del user_cities[user_id]
            else:
                bot_city = random.choice(possible)
                game["used"].append(bot_city.lower())
                game["last"] = get_last_letter(bot_city)
                bot.send_message(chat_id=chat_id, text=f"{bot_city}\nТебе на {game['last'].upper()}")

    else:
        bot.send_message(chat_id=chat_id, text="Используй /help")

    return "OK", 200

@app.route('/callback', methods=['POST'])
def callback():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    user_name = query.from_user.first_name
    chat_id = query.message.chat.id
    choice = query.data

    choices = {"rock": "🪨", "scissors": "✂️", "paper": "📄"}
    bot_choice = random.choice(["rock", "scissors", "paper"])
    
    if choice == bot_choice:
        result = "Ничья"
        points = 1
    elif (choice == "rock" and bot_choice == "scissors") or \
         (choice == "scissors" and bot_choice == "paper") or \
         (choice == "paper" and bot_choice == "rock"):
        result = "Ты выиграл!"
        points = 3
    else:
        result = "Бот выиграл"
        points = 0
    
    update_user_stats(user_id, user_name, "rps", points)
    query.edit_message_text(text=f"{choices[choice]} vs {choices[bot_choice]}\n{result}")

    return "OK", 200

if __name__ == "__main__":
    if URL:
        bot.set_webhook(url=f"{URL.rstrip('/')}/webhook")
        logger.info(f"Вебхук: {URL}/webhook")
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
