import os
import httpx
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

load_dotenv()

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
WORKER_URL = os.getenv("WORKER_URL")
WORKER_SECRET = os.getenv("WORKER_SECRET")
PORT = int(os.getenv("PORT", 10000))


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, formatt, *args):
        pass


def run_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    server.serve_forever()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "welcome to smth!\n\n"
        "/register <handle> - create your page\n"
        "/me - see your page link\n"
        "just send a message to post it!"
    )


async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.chat_id)
    username = update.message.chat.username
    display_name = update.message.chat.first_name

    if not context.args or len(context.args) == 0:
        await update.message.reply_text("usage: /register <handle>\ne.g. /register raster")
        return

    handle = context.args[0].lower()

    headers = {
        "Authorization": f"Bearer {WORKER_SECRET}",
        "Content-Type": "application/json"
    }

    payload = {
        "telegram_id": user_id,
        "handle": handle,
        "telegram_username": username,
        "display_name": display_name
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{WORKER_URL}/register",
                json=payload,
                headers=headers,
                timeout=10.0
            )

        if response.status_code == 200:
            data = response.json()
            handle = data.get("handle", handle)
            await update.message.reply_text(
                f"registered! your page is live at:\n"
                f"{WORKER_URL}/{handle}"
            )
        elif response.status_code == 409:
            await update.message.reply_text("handle already taken, try another one")
        else:
            await update.message.reply_text(f"error: {response.status_code}")

    except Exception as e:
        await update.message.reply_text(f"error: {e}")


async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.chat_id)

    headers = {
        "Authorization": f"Bearer {WORKER_SECRET}",
        "Content-Type": "application/json"
    }

    payload = {"telegram_id": user_id}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{WORKER_URL}/lookup",
                json=payload,
                headers=headers,
                timeout=10.0
            )

        if response.status_code == 200:
            data = response.json()
            handle = data.get("handle")
            if handle:
                await update.message.reply_text(f"your page: {WORKER_URL}/{handle}")
            else:
                await update.message.reply_text("you haven't registered yet. use /register <handle>")
        else:
            await update.message.reply_text("error looking up your page")

    except Exception as e:
        await update.message.reply_text(f"error: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.chat_id)

    headers = {
        "Authorization": f"Bearer {WORKER_SECRET}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            lookup_response = await client.post(
                f"{WORKER_URL}/lookup",
                json={"telegram_id": user_id},
                headers=headers,
                timeout=10.0
            )

        if lookup_response.status_code != 200:
            await update.message.reply_text("something went wrong, try again later")
            return

        data = lookup_response.json()
        handle = data.get("handle")

        if not handle:
            await update.message.reply_text(
                "you need to register first!\n"
                "use /register <handle> to create your page\n"
                "e.g. /register raster"
            )
            return

        message_text = update.message.text
        date_str = datetime.now().strftime("%m/%d/%y, %I:%M%p")

        payload = {
            "content": message_text,
            "date": date_str
        }

        async with httpx.AsyncClient() as client:
            post_response = await client.post(
                f"{WORKER_URL}/{handle}",
                json=payload,
                headers=headers,
                timeout=10.0
            )

        if post_response.status_code == 200:
            await update.message.reply_text(f"posted! view at: {WORKER_URL}/{handle}")
        else:
            await update.message.reply_text(f"failed: {post_response.status_code}")

    except Exception as e:
        await update.message.reply_text(f"error: {e}")


def main():
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("me", me))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()


if __name__ == "__main__":
    main()
