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
    await update.message.reply_text("send a message and it'll appear on your something page. don't have a page? sign up at smth.fyi")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    date_str = datetime.now().strftime("%m/%d/%y, %I:%M%p")

    headers = {
        "Authorization": f"Bearer {WORKER_SECRET}",
        "Content-Type": "application/json"
    }
    payload = {
        "content": message_text,
        "date": date_str
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                WORKER_URL,
                json=payload,
                headers=headers,
                timeout=10.0
            )

        if response.status_code == 200:
            await update.message.reply_text("posted!")
        else:
            await update.message.reply_text(f"failed :( error ({response.status_code})")

    except Exception as e:
        await update.message.reply_text(f"error: {e}")


def main():
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()


if __name__ == "__main__":
    main()
