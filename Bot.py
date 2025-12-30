import random
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

BOT_TOKEN = "8583192474:AAESPvmGIcu8iRLjrqRlgSFL7DsqrWzZ-Rk"

tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-small")
model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-small")

async def reply_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # Group: reply only on mention
    if update.message.chat.type in ["group", "supergroup"]:
        if context.bot.username.lower() not in text.lower():
            return

    await asyncio.sleep(random.randint(1, 3))  # human delay

    input_ids = tokenizer.encode(text + tokenizer.eos_token, return_tensors="pt")

    output = model.generate(
        input_ids,
        max_length=120,
        do_sample=True,
        top_k=50,
        top_p=0.95,
        pad_token_id=tokenizer.eos_token_id
    )

    reply = tokenizer.decode(
        output[:, input_ids.shape[-1]:][0],
        skip_special_tokens=True
    )

    if not reply.strip():
        reply = random.choice([
            "Haha 😄",
            "Interesting 👀",
            "Arre bhai 😂",
            "Samajh raha hoon 😌"
        ])

    await update.message.reply_text(reply)

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_ai))

print("Human AI bot running on Railway...")
app.run_polling()
