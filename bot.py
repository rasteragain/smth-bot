import os
import asyncio
import httpx
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

load_dotenv()

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
AUTH_URL = os.getenv("AUTH_URL")  # e.g., https://auth.smth.fyi
WORKER_URL = os.getenv("WORKER_URL")  # e.g., https://api.smth.fyi
AUTH_SECRET = os.getenv("AUTH_SECRET")
PORT = int(os.getenv("PORT", 10000))


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(("OK"))

    def log_message(self, formatt, *args):
        pass


def run_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    server.serve_forever()


async def delete_after(msg, seconds):
    await asyncio.sleep(seconds)
    try:
        await msg.delete()
    except:
        pass

async def reply_and_delete(update, text, seconds=10):
    msg = await update.message.reply_text(text)
    asyncio.create_task(delete_after(msg, seconds))
    return msg


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply_and_delete(update,
        "welcome to smth!\n\n"
        "/link - link your telegram to your account\n"
        "/me - see your page link\n\n"
        "just send a message to post it!"
    )


async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.message.chat_id)

    headers = {
        "Authorization": f"Bearer {AUTH_SECRET}",
        "Content-Type": "application/json"
    }

    payload = {
        "telegram_id": telegram_id
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{AUTH_URL}/api/telegram/lookup",
                json=payload,
                headers=headers,
                timeout=10.0
            )

        if response.status_code == 200:
            data = response.json()
            handle = data.get("handle")

            if handle:
                await reply_and_delete(update,
                    f"your telegram is already linked to @{handle}\n\n"
                    f"view your page at: {WORKER_URL}/{handle}"
                )
            else:
                await reply_and_delete(update,
                    "your telegram isn't linked to any account yet.\n\n"
                    "go to your dashboard at smth.fyi/{handle}/dashboard\n"
                    "and set your telegram handle/id to link it."
                )
        else:
            await reply_and_delete(update, "error looking up your account")

    except Exception as e:
        await reply_and_delete(update, f"error: {e}")


async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.message.chat_id)

    headers = {
        "Authorization": f"Bearer {AUTH_SECRET}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{AUTH_URL}/api/telegram/lookup",
                json={"telegram_id": telegram_id},
                headers=headers,
                timeout=10.0
            )

        if response.status_code == 200:
            data = response.json()
            handle = data.get("handle")
            if handle:
                await reply_and_delete(update, f"your page: {WORKER_URL}/{handle}")
            else:
                await reply_and_delete(update, "you haven't linked your telegram yet. use /link")
        else:
            await reply_and_delete(update, "error looking up your page")

    except Exception as e:
        await reply_and_delete(update, f"error: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.message.chat_id)

    headers = {
        "Authorization": f"Bearer {AUTH_SECRET}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            lookup_response = await client.post(
                f"{AUTH_URL}/api/telegram/lookup",
                json={"telegram_id": telegram_id},
                headers=headers,
                timeout=10.0
            )

        if lookup_response.status_code != 200:
            await reply_and_delete(update, "something went wrong, try again later")
            return

        data = lookup_response.json()
        handle = data.get("handle")

        if not handle:
            await reply_and_delete(update,
                "you need to link your telegram first!\n\n"
                "1. Go to smth.fyi\n"
                "2. Sign up / Login\n"
                "3. Go to Dashboard\n"
                "4. Set your Telegram Handle/ID\n"
                "5. Come back and message again"
            )
            return

        message_text = update.message.text
        date_str = datetime.now().strftime("%m/%d/%y, %I:%M%p")

        payload = {
            "content": message_text,
            "date": date_str,
            "source": "telegram"
        }

        async with httpx.AsyncClient() as client:
            post_response = await client.post(
                f"{WORKER_URL}/api/post",
                json=payload,
                headers=headers,
                timeout=10.0
            )

        if post_response.status_code == 200:
            await reply_and_delete(update, f"posted! view at: {WORKER_URL}/{handle}")
        else:
            await reply_and_delete(update, f"failed: {post_response.status_code}")

    except Exception as e:
        await reply_and_delete(update, f"error: {e}")


def main():
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("link", link))
    app.add_handler(CommandHandler("me", me))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()


if __name__ == "__main__":
    main()
