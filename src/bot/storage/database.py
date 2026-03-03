import sqlite3
from datetime import datetime
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
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS traffic_daily_entries (
            stat_date TEXT NOT NULL,
            area TEXT NOT NULL,
            in_count INTEGER NOT NULL,
            fetched_at TEXT NOT NULL,
            PRIMARY KEY (stat_date, area)
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

    def insert_daily_flow(self, date_str, flow_summary, fetched_at=None):
        cursor = self.conn.cursor()
        fetched_at = fetched_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for org_location, info in flow_summary.items():
            area = (info.get("name") or org_location or "").strip() or "未知馆区"
            in_count = int(info.get("daily_in", 0))

            cursor.execute("""
            INSERT INTO traffic_daily_entries
                (stat_date, area, in_count, fetched_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(stat_date, area) DO UPDATE SET
                in_count = excluded.in_count,
                fetched_at = excluded.fetched_at
            """, (
                date_str,
                area,
                in_count,
                fetched_at,
            ))

        self.conn.commit()

    def insert_daily_traffic(self, date_str, total_in):
        # Deprecated: 保留接口兼容，当前仅存每日馆区进馆明细
        return None

    def get_total_between(self, start_date, end_date):
        # Deprecated: 保留接口兼容，当前不维护总计表
        return 0

    def debug_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for table in tables:
            print(table["name"])



    def close(self):
        self.conn.close()
