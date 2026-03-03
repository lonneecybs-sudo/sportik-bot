import os,json,logging,random,asyncio
from flask import Flask,request
from telegram import Update,InlineKeyboardButton,InlineKeyboardMarkup,KeyboardButton,ReplyKeyboardMarkup
from telegram.ext import Application,CommandHandler,ContextTypes,MessageHandler,filters,CallbackQueryHandler

logging.basicConfig(level=logging.INFO)
app=Flask(__name__)
BOT_TOKEN="8710055657:AAEWkUYdJdv6FxNpuWi2ikZI0vRF4P8rygk"
ADMIN_ID=8259326703
RENDER_URL="https://sportik-bot.onrender.com"

telegram_app=Application.builder().token(BOT_TOKEN).build()

def load_json(f,d=None):
 try:
  with open(f,'r',encoding='utf-8') as x:return json.load(x)
 except:return d if d else{}if f=='users.json'else[]

cities=load_json('cities.json',['Москва','Париж','Лондон','Токио','Нью-Йорк','Сидней'])
if not load_json('cities.json'):json.dump(cities,open('cities.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

def upd_stats(user,game,p=1):
 d=load_json('users.json',{})
 uid=str(user.id)
 if uid not in d:d[uid]={'first_name':user.first_name,'username':user.username,'stats':{'cities':0,'rps':0,'dice':0}}
 d[uid]['stats'][game]=d[uid]['stats'].get(game,0)+p
 json.dump(d,open('users.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

async def start(u,c):await u.message.reply_text(f"Привет, {u.effective_user.first_name}! Я Спортик друн! Напиши /help")
async def help(u,c):await u.message.reply_text("/start\n/help\n/games\n/top\n/gift")
async def games(u,c):await u.message.reply_text("Выбери:",reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🎮 Города"),KeyboardButton("🧮 КМБ")],[KeyboardButton("🎲 Кубик"),KeyboardButton("💣 Сапер")]],resize_keyboard=True))
async def top(u,c):
 d=load_json('users.json',{});p=[]
 for uid,data in d.items():
  s=sum(data.get('stats',{}).values())
  if s>0:p.append((data.get('first_name','Unknown'),s))
 p.sort(key=lambda x:x[1],reverse=True)
 t="🏆 ТОП:\n"
 for i,(n,s)in enumerate(p[:10],1):t+=f"{i}.{n}-{s}\n"
 await u.message.reply_text(t)

games_data={}
def key(u):return f"{u.effective_chat.id}:{u.effective_user.id}"

async def cities_start(u,c):
 k=key(u);city=random.choice(cities);last=city[-1].lower()
 if last in'ьъы':last=city[-2].lower()
 games_data[k]={'last':last,'used':{city.lower()}}
 await u.message.reply_text(f"🎮{city}\nТебе на {last.upper()}")

async def cities_handle(u,c):
 k=key(u)
 if k not in games_data:return False
 g=games_data[k];city=u.message.text.strip()
 if city.lower()=='/cancel':del games_data[k];await u.message.reply_text("Выход");return True
 cl=city.lower()
 if cl not in[c.lower()for c in cities]:await u.message.reply_text("❌Нет такого!");return True
 if cl in g['used']:del games_data[k];await u.message.reply_text("❌Был! Ты проиграл!");return True
 if city[0].lower()!=g['last']:del games_data[k];await u.message.reply_text(f"❌Нужно на {g['last'].upper()}!");return True
 g['used'].add(cl);upd_stats(u.effective_user,'cities',1)
 last=city[-1].lower()
 if last in'ьъы':last=city[-2].lower()
 possible=[c for c in cities if c[0].lower()==last and c.lower()not in g['used']]
 if not possible:del games_data[k];await u.message.reply_text("✅Ты победил!+3");upd_stats(u.effective_user,'cities',3);return True
 bot=random.choice(possible);g['used'].add(bot.lower())
 nlast=bot[-1].lower()
 if nlast in'ьъы':nlast=bot[-2].lower()
 g['last']=nlast
 await u.message.reply_text(f"{bot}\nТебе на {nlast.upper()}")
 return True

rps_games={}
async def rps_start(u,c):
 k=key(u);rps_games[k]={'u':0,'b':0}
 kb=[[InlineKeyboardButton("🪨",callback_data="rps:r"),InlineKeyboardButton("✂️",callback_data="rps:s"),InlineKeyboardButton("📄",callback_data="rps:p")],[InlineKeyboardButton("❌",callback_data="rps:e")]]
 await u.message.reply_text("КМБ!",reply_markup=InlineKeyboardMarkup(kb))

async def rps_cb(q,c):
 await q.answer()
 k=f"{q.message.chat.id}:{q.from_user.id}"
 if k not in rps_games:return
 d=q.data.split(':')
 if d[1]=='e':del rps_games[k];await q.edit_message_text("Выход");return
 g=rps_games[k];ch={'r':'🪨','s':'✂️','p':'📄'};uc=d[1];bc=random.choice(['r','s','p'])
 if uc==bc:res='🤝';p=1
 elif(uc=='r'and bc=='s')or(uc=='s'and bc=='p')or(uc=='p'and bc=='r'):res='✅';g['u']+=1;p=3
 else:res='❌';g['b']+=1;p=0
 upd_stats(q.from_user,'rps',p)
 kb=[[InlineKeyboardButton("🪨",callback_data="rps:r"),InlineKeyboardButton("✂️",callback_data="rps:s"),InlineKeyboardButton("📄",callback_data="rps:p")],[InlineKeyboardButton("❌",callback_data="rps:e")]]
 await q.edit_message_text(f"{ch[uc]}vs{ch[bc]}\n{res}\n{g['u']}:{g['b']}",reply_markup=InlineKeyboardMarkup(kb))

async def dice_start(u,c):
 await u.message.reply_text("🎲",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Бросить",callback_data="dice")]]))

async def dice_cb(q,c):
 await q.answer()
 d1,d2=random.randint(1,6),random.randint(1,6)
 upd_stats(q.from_user,'dice',d1+d2)
 await q.edit_message_text(f"{d1}+{d2}={d1+d2}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ещё",callback_data="dice")]]))

async def msg_h(u,c):
 t=u.message.text
 if t=="🎮 Города":await cities_start(u,c)
 elif t=="🧮 КМБ":await rps_start(u,c)
 elif t=="🎲 Кубик":await dice_start(u,c)
 elif t=="💣 Сапер":await u.message.reply_text("🚧")
 elif await cities_handle(u,c):pass
 else:await u.message.reply_text("❓/help")

telegram_app.add_handler(CommandHandler("start",start))
telegram_app.add_handler(CommandHandler("help",help))
telegram_app.add_handler(CommandHandler("games",games))
telegram_app.add_handler(CommandHandler("top",top))
telegram_app.add_handler(CallbackQueryHandler(rps_cb,pattern="^rps:"))
telegram_app.add_handler(CallbackQueryHandler(dice_cb,pattern="^dice"))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,msg_h))

@app.route('/')
def index():return "Бот работает!"
@app.route('/health')
def health():return "OK",200
@app.route('/webhook',methods=['POST'])
def webhook():
 try:asyncio.create_task(telegram_app.process_update(Update.de_json(request.get_json(),telegram_app.bot)))
 except Exception as e:logging.error(e)
 return "OK",200

async def setup():await telegram_app.bot.set_webhook(url=f"{RENDER_URL}/webhook");logging.info("Вебхук готов")

if __name__=="__main__":
 loop=asyncio.new_event_loop();asyncio.set_event_loop(loop);loop.run_until_complete(setup())
 app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
