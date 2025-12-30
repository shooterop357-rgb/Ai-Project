import os
import asyncio
import random
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from groq import Groq

# ENV variables (Railway)
BOT_TOKEN = os.getenv("8583192474:AAESPvmGIcu8iRLjrqRlgSFL7DsqrWzZ-Rk")
GROQ_API_KEY = os.getenv("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")

client = Groq(api_key=GROQ_API_KEY)

async def reply_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return

    text = msg.text.strip()

    # Group: reply only on mention
    if msg.chat.type in ["group", "supergroup"]:
        if context.bot.username.lower() not in text.lower():
            return

    await asyncio.sleep(random.randint(1, 2))  # human delay

    completion = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {
                "role": "system",
                "content": "You are a chill, funny, human-like friend. Keep replies short and natural."
            },
            {
                "role": "user",
                "content": text
            }
        ],
        temperature=0.8,
        max_tokens=80
    )

    reply = completion.choices[0].message.content.strip()
    await msg.reply_text(reply)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_ai))
    print("Groq AI bot running on Railway...")
    app.run_polling()

if __name__ == "__main__":
    main()
