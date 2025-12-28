import sqlite3
from datetime import datetime

# На Render (Free Tier) цей файл буде видалятися при кожному перезапуску (deploy).
# Для курсової роботи це нормально. Для реального продукту потрібен PostgreSQL.
DB_NAME = "emails.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gmail_id TEXT UNIQUE,
            sender TEXT,
            recipient TEXT,
            subject TEXT,
            body TEXT,
            folder TEXT,
            received_date TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_email(gmail_id, sender, subject, snippet, folder='INBOX'):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO emails (gmail_id, sender, subject, body, folder, received_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (gmail_id, sender, subject, snippet, folder, datetime.now()))
        conn.commit()
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        conn.close()