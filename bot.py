import os
import asyncio
import random
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from groq import Groq

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY missing")

client = Groq(api_key=GROQ_API_KEY)

async def reply_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return

    text = msg.text.strip()

    if msg.chat.type in ["group", "supergroup"]:
        if context.bot.username.lower() not in text.lower():
            return

    await asyncio.sleep(random.randint(1, 2))

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",   # ✅ FIXED MODEL
        messages=[
            {"role": "system", "content": "You are a chill, human-like friend. Short replies."},
            {"role": "user", "content": text}
        ],
        temperature=0.8,
        max_tokens=80
    )

    await msg.reply_text(response.choices[0].message.content.strip())

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_ai))
    print("✅ Groq AI bot running on Railway...")
    app.run_polling()

if __name__ == "__main__":
    main()
