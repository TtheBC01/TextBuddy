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

from telegram import ForceReply, Update, Chat, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler

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

    message = (
        update.message or
        (update.callback_query.message if update.callback_query else None)
    )

    if not message:
        return False  # fallback

    if message.chat.type != Chat.PRIVATE:
        await message.reply_text("This command is only available in private chat.")
        return False

    return True

async def set_model_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a list of available models as inline buttons."""
    if not await private_chat_only(update):
        return

    response = ollama_client.list()
    models = response.models

    # Get the active model for the user
    user_id = update.effective_user.id
    active_model = user_active_models.get(user_id)

    # Create a button for each model
    keyboard = [
        [InlineKeyboardButton(
            f"{model.model} {'✅' if model.model == active_model else ''}",
            callback_data=f"setmodel:{model.model}"
        )]
        for model in models
    ]

    # Add "Load a new model" button
    keyboard.append([InlineKeyboardButton("Load a new model", callback_data="pullmodel")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Select a model to use for chat:", reply_markup=reply_markup)

async def handle_model_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the model selection button click."""
    query = update.callback_query
    await query.answer()

    if query.data.startswith("setmodel:"):
        model = query.data.split("setmodel:")[1]
        user_id = query.from_user.id
        user_active_models[user_id] = model
        await query.edit_message_text(text=f"✅ Active model set to: *{model}*", parse_mode="Markdown")

async def pull_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await private_chat_only(update):
        return ConversationHandler.END

    message = update.message or update.callback_query.message

    response = ollama_client.list()
    models = response.models

    if models:
        models_list = "\n".join(f"- {model.model}" for model in models)
        text = f"Downloaded Models:\n{models_list}"
    else:
        text = "There are currently no loaded models."

    await message.reply_text(text)
    await message.reply_text("Tell me what new model you want to load into Ollama (type /cancel to quit).")

    return ASKING_MODEL

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

MAX_MESSAGE_LENGTH = 4096

def chunk_message(text: str, chunk_size: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Break a long message into chunks that fit within Telegram's limit."""
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the user message to Ollama and return the response using the active model."""
    user_message = update.message.text
    user_id = update.effective_user.id
    model = user_active_models.get(user_id, "llama3")  # Default if none selected

    try:
        response = ollama_client.chat(
            model=model,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        reply = response['message']['content']
    except Exception as e:
        logger.error("Error talking to Ollama: %s", str(e))
        reply = "Sorry, I couldn't get a response from the model."

    for chunk in chunk_message(reply):
        # Send each chunk separately to avoid Telegram's message length limit
        await update.message.reply_text(chunk)  

# Define states for the conversation
ASKING_MODEL = 1

# Store active model per user
user_active_models = {}

def main() -> None:
    """Start the bot."""
    # Replace 'YOUR_BOT_TOKEN' with your actual bot token or set DISCORD_BOT_TOKEN as an environment variable
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # Define conversation handler for setting an external address
    model_loader_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("pullmodel", pull_model),
            CallbackQueryHandler(pull_model, pattern="^pullmodel$")
        ],
        states={ASKING_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, store_model)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(model_loader_conv_handler)  # Add conversation handler
    application.add_handler(CommandHandler("setmodel", set_model_command))
    application.add_handler(CallbackQueryHandler(handle_model_selection, pattern="^setmodel:"))


    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()