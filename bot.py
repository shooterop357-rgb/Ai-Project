import os, time, json, threading
from datetime import datetime, timedelta
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

MAIN_ADMIN = "5436530930"
MAX_ATTACK_TIME = 300     # 5 minutes
COOLDOWN_TIME = 1200      # 20 minutes
USERS_FILE = "users.json"

# Pricing (edit later)
PLANS = {
    1: 100,
    3: 150,
    7: 300
}

# ================= STATE =================
running = {}        # uid -> end_time
cooldown = {}       # uid -> last_end
awaiting = set()    # uid waiting for params
admin_chat = set()  # uid chatting with admin
lock = threading.Lock()

# ================= USERS =================
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    return json.load(open(USERS_FILE))

def save_users(d):
    json.dump(d, open(USERS_FILE, "w"), indent=2)

users = load_users()

def role(uid):
    if uid == MAIN_ADMIN:
        return "main"
    return users.get(uid, {}).get("role")

def expired(uid):
    if uid == MAIN_ADMIN:
        return False
    u = users.get(uid)
    if not u:
        return True
    return datetime.now() > datetime.fromisoformat(u["expires_at"])

def remaining_days(uid):
    if uid == MAIN_ADMIN:
        return "Unlimited"
    u = users.get(uid)
    if not u:
        return "Expired"
    delta = datetime.fromisoformat(u["expires_at"]) - datetime.now()
    return max(delta.days, 0)

# ================= UI =================
def user_menu(uid):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🚀 Attack", callback_data="attack"),
        InlineKeyboardButton("📞 Contact Admin", callback_data="contact"),
        InlineKeyboardButton("👤 User Panel", callback_data="panel"),
        InlineKeyboardButton("💳 Plans", callback_data="plans"),
    )
    if uid in running:
        kb.add(InlineKeyboardButton("🛑 Stop Attack", callback_data="stop"))
    return kb

def admin_menu(uid):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🚀 Attack", callback_data="attack"),
        InlineKeyboardButton("📞 Contact Admin", callback_data="contact"),
        InlineKeyboardButton("👤 User Panel", callback_data="panel"),
        InlineKeyboardButton("💳 Plans", callback_data="plans"),
        InlineKeyboardButton("➕ Add User", callback_data="adduser"),
        InlineKeyboardButton("➕ Add Admin", callback_data="addadmin"),
        InlineKeyboardButton("➖ Remove User", callback_data="remove"),
    )
    if uid in running:
        kb.add(InlineKeyboardButton("🛑 Stop Attack", callback_data="stop"))
    return kb

def end_chat_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("❌ End Admin Chat", callback_data="endchat"))
    return kb

# ================= CALLBACKS =================
@bot.callback_query_handler(func=lambda c: True)
def callbacks(c):
    uid = str(c.message.chat.id)
    r = role(uid)
    menu = admin_menu(uid) if r == "main" else user_menu(uid)

    if c.data == "attack":
        if expired(uid):
            bot.answer_callback_query(c.id, "Plan expired. Contact admin.", show_alert=True)
            return
        awaiting.add(uid)
        bot.send_message(uid, "📝 Enter:\n<code>IP PORT SECONDS</code>\nExample:\n<code>1.1.1.1 80 120</code>")
        bot.send_message(uid, " ", reply_markup=menu)

    elif c.data == "contact":
        admin_chat.add(uid)
        bot.send_message(uid, "💬 <b>Admin chat enabled</b>\nType your message.")
        bot.send_message(uid, " ", reply_markup=end_chat_kb())

    elif c.data == "endchat":
        admin_chat.discard(uid)
        bot.send_message(uid, "✅ <b>Admin chat closed</b>")
        bot.send_message(uid, " ", reply_markup=menu)

    elif c.data == "panel":
        bot.send_message(
            uid,
            f"👤 <b>User Panel</b>\n\n"
            f"Role: <b>{r}</b>\n"
            f"Remaining Days: <b>{remaining_days(uid)}</b>"
        )
        bot.send_message(uid, " ", reply_markup=menu)

    elif c.data == "plans":
        text = "💳 <b>Available Plans</b>\n\n"
        for d, p in PLANS.items():
            text += f"{d} Day(s) – ₹{p}\n"
        text += "\nContact admin to purchase."
        bot.send_message(uid, text)
        bot.send_message(uid, " ", reply_markup=menu)

    elif c.data == "stop":
        stop_attack(uid)
        bot.send_message(uid, "🛑 <b>Attack stopped</b>\n⏳ Cooldown started (20 min)")
        bot.send_message(uid, " ", reply_markup=menu)

    elif c.data in ("adduser", "addadmin", "remove"):
        if uid != MAIN_ADMIN:
            return
        if c.data == "adduser":
            bot.send_message(uid, "Usage:\n<code>/adduser USERID DAYS</code>\nDays: 1 / 3 / 7")
        elif c.data == "addadmin":
            bot.send_message(uid, "Usage:\n<code>/addadmin USERID DAYS</code>\nDays: 1 / 3 / 7")
        elif c.data == "remove":
            bot.send_message(uid, "Usage:\n<code>/remove USERID</code>")

# ================= ADMIN CHAT =================
@bot.message_handler(func=lambda m: str(m.chat.id) in admin_chat and str(m.chat.id) != MAIN_ADMIN)
def user_to_admin(m):
    bot.send_message(MAIN_ADMIN, f"👤 User <code>{m.chat.id}</code>:\n{m.text}")

@bot.message_handler(func=lambda m: str(m.chat.id) == MAIN_ADMIN and m.reply_to_message)
def admin_to_user(m):
    try:
        uid = m.reply_to_message.text.split("<code>")[1].split("</code>")[0]
        bot.send_message(uid, m.text)
    except:
        pass

# ================= ATTACK (SIMULATED) =================
def stop_attack(uid):
    with lock:
        if uid in running:
            running.pop(uid)
            cooldown[uid] = time.time()

@bot.message_handler(func=lambda m: str(m.chat.id) in awaiting)
def receive_attack(m):
    uid = str(m.chat.id)
    awaiting.discard(uid)

    if expired(uid):
        bot.send_message(uid, "Plan expired.")
        return

    if uid != MAIN_ADMIN:
        last = cooldown.get(uid)
        if last and time.time() - last < COOLDOWN_TIME:
            bot.send_message(uid, "Next attack after 20 minutes.")
            return

    try:
        _, _, sec = m.text.split()
        sec = int(sec)
        if sec > MAX_ATTACK_TIME:
            raise ValueError
    except:
        bot.send_message(uid, "Invalid format.")
        return

    end_time = time.time() + sec
    running[uid] = end_time

    bot.send_message(uid, f"✅ <b>Attack started</b>\nTime: {sec}s")

    def finish():
        while time.time() < end_time:
            time.sleep(1)
        if uid in running:
            running.pop(uid)
            cooldown[uid] = time.time()
            bot.send_message(uid, "✅ <b>Attack completed</b>\n⏳ Cooldown: 20 minutes")

    threading.Thread(target=finish, daemon=True).start()

# ================= ADMIN COMMANDS =================
@bot.message_handler(commands=["adduser", "addadmin"])
def add_user(m):
    if str(m.chat.id) != MAIN_ADMIN:
        return
    try:
        _, uid, days = m.text.split()
        days = int(days)
        r = "admin" if m.text.startswith("/addadmin") else "user"
        exp = datetime.now() + timedelta(days=days)
        users[uid] = {"role": r, "expires_at": exp.isoformat()}
        save_users(users)
        bot.reply_to(m, f"✅ {r} {uid} added for {days} days")
    except:
        bot.reply_to(m, "Usage: /adduser <id> <days>")

@bot.message_handler(commands=["remove"])
def remove_user(m):
    if str(m.chat.id) != MAIN_ADMIN:
        return
    try:
        _, uid = m.text.split()
        users.pop(uid, None)
        save_users(users)
        bot.reply_to(m, f"Removed {uid}")
    except:
        bot.reply_to(m, "Usage: /remove <id>")

# ================= START =================
@bot.message_handler(commands=["start"])
def start(m):
    uid = str(m.chat.id)
    r = role(uid)
    if uid == MAIN_ADMIN:
        bot.send_message(uid, "👑 <b>Main Admin Detected</b>\nFull control enabled.")
        bot.send_message(uid, " ", reply_markup=admin_menu(uid))
    else:
        bot.send_message(uid, "👋 <b>Welcome</b>\nChoose an option below")
        bot.send_message(uid, " ", reply_markup=user_menu(uid))

# ================= EXPIRY REMINDER =================
def expiry_reminder():
    while True:
        for uid, u in users.items():
            try:
                exp = datetime.fromisoformat(u["expires_at"])
                if 0 < (exp - datetime.now()).days == 1:
                    bot.send_message(uid, "⏰ Your plan expires tomorrow. Contact admin for renewal.")
            except:
                pass
        time.sleep(86400)

threading.Thread(target=expiry_reminder, daemon=True).start()

# ================= RUN =================
while True:
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(e)
        time.sleep(3)
