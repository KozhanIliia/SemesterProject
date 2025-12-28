import os
import asyncio
import threading
from flask import Flask
from interface import run_bot
from dotenv import load_dotenv
import nest_asyncio

load_dotenv()
nest_asyncio.apply()  # Allow nested event loops

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive! (Ця сторінка потрібна, щоб Render не вимикав сервіс)"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Запуск Telegram бота...")
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("Бот зупинений.")