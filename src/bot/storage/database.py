import sqlite3
from pathlib import Path

DB_PATH = Path("data/bot.db")

class Database:
    def __init__(self):
        DB_PATH.parent.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT UNIQUE,
            content TEXT,
            created_at TEXT
        )
        """)
        self.conn.commit()

    def insert_message(self, message_id, content, created_at):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
            INSERT INTO messages (message_id, content, created_at)
            VALUES (?, ?, ?)
            """, (message_id, content, created_at))
            self.conn.commit()
        except sqlite3.IntegrityError:
            # 已存在则忽略（防重复）
            pass

    def debug_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for table in tables:
            print(table["name"])



    def close(self):
        self.conn.close()
