import logging
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

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE,
                content TEXT,
                created_at TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS traffic_raw_snapshots (
                stat_date TEXT NOT NULL,
                area_code TEXT NOT NULL,
                area_name TEXT NOT NULL,
                in_count INTEGER NOT NULL,
                out_count INTEGER NOT NULL,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (stat_date, area_code, fetched_at)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS traffic_daily_by_location (
                stat_date TEXT NOT NULL,
                area_code TEXT NOT NULL,
                area_name TEXT NOT NULL,
                in_count INTEGER NOT NULL,
                out_count INTEGER NOT NULL,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (stat_date, area_code)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS traffic_daily_summary (
                stat_date TEXT PRIMARY KEY,
                area_code TEXT NOT NULL,
                area_name TEXT NOT NULL,
                in_count INTEGER NOT NULL,
                out_count INTEGER NOT NULL,
                fetched_at TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS report_send_log (
                report_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                PRIMARY KEY (report_type, start_date, end_date)
            )
            """
        )

        self._migrate_legacy_tables()
        self.conn.commit()

    def _table_exists(self, table_name):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None

    def _table_columns(self, table_name):
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        return {row[1] for row in cursor.fetchall()}

    def _rename_legacy_table(self, table_name):
        legacy_name = f"{table_name}_legacy"
        if not self._table_exists(table_name):
            return
        if self._table_exists(legacy_name):
            return
        cursor = self.conn.cursor()
        cursor.execute(f"ALTER TABLE {table_name} RENAME TO {legacy_name}")

    def _migrate_legacy_tables(self):
        cursor = self.conn.cursor()

        if self._table_exists("traffic_daily_entries"):
            cols = self._table_columns("traffic_daily_entries")
            if {"stat_date", "area", "in_count", "fetched_at"}.issubset(cols):
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO traffic_raw_snapshots
                        (stat_date, area_code, area_name, in_count, out_count, fetched_at)
                    SELECT stat_date, area, area, COALESCE(in_count, 0), 0, fetched_at
                    FROM traffic_daily_entries
                    """
                )
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO traffic_daily_by_location
                        (stat_date, area_code, area_name, in_count, out_count, fetched_at)
                    SELECT stat_date, area, area, COALESCE(in_count, 0), 0, fetched_at
                    FROM traffic_daily_entries
                    """
                )
            self._rename_legacy_table("traffic_daily_entries")

        if self._table_exists("traffic_daily_locations"):
            cols = self._table_columns("traffic_daily_locations")
            required = {
                "date",
                "org_location",
                "org_name",
                "daily_in",
                "daily_out",
                "created_at",
            }
            if required.issubset(cols):
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO traffic_raw_snapshots
                        (stat_date, area_code, area_name, in_count, out_count, fetched_at)
                    SELECT
                        date,
                        org_location,
                        COALESCE(org_name, org_location),
                        COALESCE(daily_in, 0),
                        0,
                        COALESCE(created_at, datetime('now'))
                    FROM traffic_daily_locations
                    """
                )
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO traffic_daily_by_location
                        (stat_date, area_code, area_name, in_count, out_count, fetched_at)
                    SELECT
                        date,
                        org_location,
                        COALESCE(org_name, org_location),
                        COALESCE(daily_in, 0),
                        0,
                        COALESCE(created_at, datetime('now'))
                    FROM traffic_daily_locations
                    """
                )
            self._rename_legacy_table("traffic_daily_locations")

        if self._table_exists("traffic_daily_totals"):
            cols = self._table_columns("traffic_daily_totals")
            required = {"date", "total_in", "total_out", "created_at"}
            if required.issubset(cols):
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO traffic_daily_summary
                        (stat_date, area_code, area_name, in_count, out_count, fetched_at)
                    SELECT
                        date,
                        'ALL',
                        '??',
                        COALESCE(total_in, 0),
                        0,
                        COALESCE(created_at, datetime('now'))
                    FROM traffic_daily_totals
                    """
                )
            self._rename_legacy_table("traffic_daily_totals")

        cursor.execute(
            """
            INSERT INTO traffic_daily_summary
                (stat_date, area_code, area_name, in_count, out_count, fetched_at)
            SELECT
                l.stat_date,
                'ALL',
                '??',
                COALESCE(SUM(l.in_count), 0),
                0,
                COALESCE(MAX(l.fetched_at), datetime('now'))
            FROM traffic_daily_by_location l
            LEFT JOIN traffic_daily_summary s
                ON s.stat_date = l.stat_date
            WHERE s.stat_date IS NULL
            GROUP BY l.stat_date
            """
        )

    def insert_message(self, message_id, content, created_at):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO messages (message_id, content, created_at)
                VALUES (?, ?, ?)
                """,
                (message_id, content, created_at),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def insert_daily_flow(self, date_str, flow_summary, fetched_at=None):
        cursor = self.conn.cursor()
        fetched_at = fetched_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        total_in = 0
        location_rows = 0

        for org_location, info in flow_summary.items():
            area_code = (org_location or "").strip() or "UNKNOWN"
            area_name = (info.get("name") or area_code).strip()
            in_count = int(info.get("daily_in", 0))
            out_count = 0

            total_in += in_count

            cursor.execute(
                """
                INSERT OR REPLACE INTO traffic_raw_snapshots
                    (stat_date, area_code, area_name, in_count, out_count, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (date_str, area_code, area_name, in_count, out_count, fetched_at),
            )

            cursor.execute(
                """
                INSERT OR REPLACE INTO traffic_daily_by_location
                    (stat_date, area_code, area_name, in_count, out_count, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (date_str, area_code, area_name, in_count, out_count, fetched_at),
            )
            location_rows += 1

        cursor.execute(
            """
            INSERT OR REPLACE INTO traffic_daily_summary
                (stat_date, area_code, area_name, in_count, out_count, fetched_at)
            VALUES (?, 'ALL', '??', ?, 0, ?)
            """,
            (date_str, total_in, fetched_at),
        )

        self.conn.commit()
        logging.info(
            "DB write success action=insert_daily_flow date=%s locations=%s total_in=%s",
            date_str,
            location_rows,
            total_in,
        )

    def get_flow_between(self, start_date, end_date):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT
                area_code,
                area_name,
                COALESCE(SUM(in_count), 0) AS in_total
            FROM traffic_daily_by_location
            WHERE stat_date >= ? AND stat_date <= ?
            GROUP BY area_code, area_name
            ORDER BY
                CASE area_code
                    WHEN 'CN-ZJLIB_ZJ' THEN 1
                    WHEN 'CN-ZJLIB_BSGL' THEN 2
                    WHEN 'CN-ZJLIB_BSL' THEN 3
                    ELSE 4
                END
            """,
            (start_date, end_date),
        )
        rows = cursor.fetchall()

        flow_summary = {}
        for row in rows:
            flow_summary[row["area_code"]] = {
                "name": row["area_name"],
                "daily_in": int(row["in_total"]),
                "daily_out": 0,
            }

        logging.info(
            "DB query success action=get_flow_between range=%s~%s locations=%s",
            start_date,
            end_date,
            len(flow_summary),
        )
        return flow_summary

    def has_report_sent(self, report_type, start_date, end_date):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT 1
            FROM report_send_log
            WHERE report_type = ? AND start_date = ? AND end_date = ?
            LIMIT 1
            """,
            (report_type, start_date, end_date),
        )
        exists = cursor.fetchone() is not None
        logging.info(
            "DB dedupe check action=has_report_sent type=%s range=%s~%s exists=%s",
            report_type,
            start_date,
            end_date,
            exists,
        )
        return exists

    def mark_report_sent(self, report_type, start_date, end_date, sent_at=None):
        cursor = self.conn.cursor()
        sent_at = sent_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            INSERT OR REPLACE INTO report_send_log
                (report_type, start_date, end_date, sent_at)
            VALUES (?, ?, ?, ?)
            """,
            (report_type, start_date, end_date, sent_at),
        )
        self.conn.commit()
        logging.info(
            "DB write success action=mark_report_sent type=%s range=%s~%s",
            report_type,
            start_date,
            end_date,
        )

    def insert_daily_traffic(self, date_str, total_in):
        cursor = self.conn.cursor()
        fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            INSERT OR REPLACE INTO traffic_daily_summary
                (stat_date, area_code, area_name, in_count, out_count, fetched_at)
            VALUES (?, 'ALL', '??', ?, 0, ?)
            """,
            (date_str, int(total_in), fetched_at),
        )
        self.conn.commit()

    def get_total_between(self, start_date, end_date):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(in_count), 0) AS total_in
            FROM traffic_daily_summary
            WHERE stat_date >= ? AND stat_date <= ?
            """,
            (start_date, end_date),
        )
        row = cursor.fetchone()
        return row["total_in"] if row else 0

    def debug_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        for table in tables:
            print(table["name"])

    def close(self):
        self.conn.close()
