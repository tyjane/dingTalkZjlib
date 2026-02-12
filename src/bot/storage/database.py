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
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS traffic_daily_totals (
            date TEXT PRIMARY KEY,
            total_in INTEGER,
            total_out INTEGER,
            net_flow INTEGER,
            created_at TEXT
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS traffic_daily_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            org_location TEXT,
            org_name TEXT,
            daily_in INTEGER,
            daily_out INTEGER,
            net_flow INTEGER,
            created_at TEXT,
            UNIQUE(date, org_location)
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

    def insert_daily_flow(self, date_str, flow_summary):
        cursor = self.conn.cursor()

        total_in = 0
        total_out = 0
        for org_location, info in flow_summary.items():
            total_in += int(info.get("daily_in", 0))
            total_out += int(info.get("daily_out", 0))

            cursor.execute("""
            INSERT OR REPLACE INTO traffic_daily_locations
                (date, org_location, org_name, daily_in, daily_out, net_flow, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                date_str,
                org_location,
                info.get("name") or "",
                int(info.get("daily_in", 0)),
                int(info.get("daily_out", 0)),
                int(info.get("net_flow", 0)),
            ))

        cursor.execute("""
        INSERT OR REPLACE INTO traffic_daily_totals
            (date, total_in, total_out, net_flow, created_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        """, (date_str, total_in, total_out, total_in - total_out))

        self.conn.commit()

    def insert_daily_traffic(self, date_str, total_in):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT OR REPLACE INTO traffic_daily_totals
            (date, total_in, total_out, net_flow, created_at)
        VALUES (?, ?, 0, ?, datetime('now'))
        """, (date_str, int(total_in), int(total_in)))
        self.conn.commit()

    def get_total_between(self, start_date, end_date):
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT COALESCE(SUM(total_in), 0) AS total_in
        FROM traffic_daily_totals
        WHERE date >= ? AND date <= ?
        """, (start_date, end_date))
        row = cursor.fetchone()
        return row["total_in"] if row else 0

    def debug_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for table in tables:
            print(table["name"])



    def close(self):
        self.conn.close()
