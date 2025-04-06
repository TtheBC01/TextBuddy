#!/usr/bin/env python
# pylint: disable=unused-argument
# This program is dedicated to the public domain under the CC0 license.

"""
Simple Bot to reply to use Telegram as an interface to Ollama.

First, a few handler functions are defined. Then, those functions are passed to
the Application and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Basic Echobot example, repeats messages.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging
import os

from telegram import ForceReply, Update, Chat
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler

from ollama import Client

ollama_client = Client(host='http://ollama-service:11434')

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

async def private_chat_only(update: Update) -> bool:
    """Helper function to check if the command is used in a private chat."""
    if update.message.chat.type != Chat.PRIVATE:
        await update.message.reply_text("This command is only available in private chat.")
        return False
    return True

async def pull_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Initiate conversation and ask for a model to load into Ollama."""
    if not await private_chat_only(update):
        message = "only available in private chats."
        return ConversationHandler.END  # Exit if not in private chat
    
    response = ollama_client.list()
    models = response.models
    # Format the models into a nice string
    if models:
        models_list = "\n".join(f"- {model.model}" for model in models)
        message = f"Available Models:\n{models_list}"
    else:
        message = "There are currently no loaded models."

    await update.message.reply_text(message)
    await update.message.reply_text(rf"Tell me what new model you want to load into Ollama (type /cancel to quit).")
    return ASKING_MODEL  # Move to the next state

async def store_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the Ethereum wallet address if valid, otherwise ask again."""
    user_id = update.effective_user.id
    model = update.message.text.strip()

    try: 
        await update.message.reply_text(f"⬇️ {model} model is now being downloaded.")
        ollama_client.pull(model)
        await update.message.reply_text(f"✅ The model is now available in Ollama.")
    except Exception as e:
        logger.error("Error pulling model: %s", str(e))
        await update.message.reply_text(f"❌ Failed to pull model: {model}. Please check the model name and try again.")
        return ASKING_MODEL  # Ask again if there was an error

    return ConversationHandler.END  # End the conversation

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text("Action canceled.")
    return ConversationHandler.END


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the user message to Ollama and return the response."""
    user_message = update.message.text

    try:
        response = ollama_client.chat(
            model="llama3.2:1b",  # Change this to the default model you want to use
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        reply = response['message']['content']
    except Exception as e:
        logger.error("Error talking to Ollama: %s", str(e))
        reply = "Sorry, I couldn't get a response from the model."

    await update.message.reply_text(reply)

# Define states for the conversation
ASKING_MODEL = 1

def main() -> None:
    """Start the bot."""
    # Replace 'YOUR_BOT_TOKEN' with your actual bot token or set DISCORD_BOT_TOKEN as an environment variable
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # Define conversation handler for setting an external address
    model_loader_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("pullmodel", pull_model)],
        states={ASKING_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, store_model)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(model_loader_conv_handler)  # Add conversation handler

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()