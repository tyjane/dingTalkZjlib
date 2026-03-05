import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from src.bot.api.traffic_api import TrafficAPI


class TrafficService:
    def __init__(self, api: TrafficAPI, library_codes, db=None):
        self.api = api
        self.library_codes = library_codes
        self.db = db

    def fetch_and_parse_daily_flow(self):
        logging.info("开始获取人流数据")

        data = self.api.fetch_flow_data(use_backup=False)
        if not data:
            logging.warning("主接口失败，尝试备用接口")
            data = self.api.fetch_flow_data(use_backup=True)

        if not data:
            logging.error("所有接口均失败")
            return None

        flow_data = self.parse_daily_flow(data)
        if not flow_data:
            logging.error("解析人流数据失败")
            return None

        logging.info("人流数据获取完成")
        return flow_data

    def parse_daily_flow(self, data):
        if not data or not data.get("isSuccess"):
            logging.error("API 返回异常")
            return None

        flow_summary = {}
        for library in data.get("data", []):
            org_location = library.get("orgLocation")
            org_name = library.get("orgLocationName")
            if org_location not in self.library_codes:
                continue

            daily_in = 0
            for count_data in library.get("fCount", []):
                if count_data.get("countType") == "日" and count_data.get("dateType") == 0:
                    daily_in = int(count_data.get("personCount", 0))

            flow_summary[org_location] = {
                "name": org_name,
                "daily_in": daily_in,
                "daily_out": 0,
            }

        return flow_summary

    def save_daily_flow(self, flow_data, date_str=None):
        if not self.db or not flow_data:
            return

        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        try:
            self.db.insert_daily_flow(date_str, flow_data)
        except Exception as exc:
            logging.error("保存人流数据失败: %s", exc)


class LibraryFlowMonitor:
    def __init__(
        self,
        dingtalk_bot=None,
        db=None,
        primary_url=None,
        backup_url=None,
        org_locations=None,
        library_codes=None,
        holiday_config_path=None,
    ):
        primary_url = primary_url or (
            "https://pfs.zjlib.cn/zhejiangshengtsg/alvarainflow/"
            "api/WwStatisticsLog/GetBigFlowByLocations"
        )
        backup_url = backup_url or (
            "https://shujia.alva.com.cn/zhejiangshengtsg/alvarainflow/"
            "api/WwStatisticsLog/GetBigFlowByLocations"
        )

        self.library_codes = library_codes or {
            "CN-ZJLIB_ZJ": "之江馆",
            "CN-ZJLIB_BSGL": "曙光馆",
            "CN-ZJLIB_BSL": "大学路馆",
        }

        payload = {
            "orgLocations": org_locations
            or ["CN-ZJLIB_ZJ", "CN-ZJLIB_BSGL", "CN-ZJLIB_BSL"]
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " "AppleWebKit/537.36"
            ),
        }

        api = TrafficAPI(
            primary_url=primary_url,
            backup_url=backup_url,
            payload=payload,
            headers=headers,
        )
        self.service = TrafficService(api=api, library_codes=self.library_codes, db=db)

        self.dingtalk_bot = dingtalk_bot
        self.db = db
        self.holiday_config_path = Path(holiday_config_path or "config/holiday_ranges.json")

    def _send_markdown(self, title, markdown_text):
        if self.dingtalk_bot:
            self.dingtalk_bot.send_markdown(title=title, text=markdown_text, is_at_all=False)
            logging.info("发送钉钉消息成功: %s", title)
        else:
            logging.warning("未配置钉钉机器人，输出到控制台: %s", title)
            print(f"\n[{title}]\n{markdown_text}\n")

    def format_output_for_dingtalk(self, flow_data):
        if not flow_data:
            return "无法获取人流数据"

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output_lines = [f"#### 浙江图书馆人流统计 ({current_time})", "---"]

        total_in = 0
        for info in flow_data.values():
            output_lines.extend(
                [
                    f"**{info['name']}**",
                    f"- **进馆人次**: {info['daily_in']:,}",
                    "",
                ]
            )
            total_in += int(info["daily_in"])

        output_lines.extend(["---", "**总计:**", f"- **总进馆人次**: {total_in:,}"])
        return "\n".join(output_lines)

    def _build_title(self, report_type, start_date, end_date):
        if report_type == "daily":
            return f"浙图人流速报 {end_date}"
        if report_type == "weekly":
            return f"浙图人流周报 {start_date}~{end_date}"
        if report_type == "holiday":
            return f"浙图人流节假日报 {start_date}~{end_date}"
        return f"浙图人流播报 {start_date}~{end_date}"

    def _send_aggregated_report(self, report_type, start_date, end_date, force=False):
        if not self.db:
            logging.warning("数据库未初始化，跳过 %s 报告", report_type)
            return

        if not force and self.db.has_report_sent(report_type, start_date, end_date):
            logging.info("%s 报告已发送，跳过: %s ~ %s", report_type, start_date, end_date)
            return

        flow_data = self.db.get_flow_between(start_date, end_date)
        if not flow_data:
            logging.warning("%s 区间无数据，跳过发送: %s ~ %s", report_type, start_date, end_date)
            return

        title = self._build_title(report_type, start_date, end_date)
        markdown_text = self.format_output_for_dingtalk(flow_data)
        self._send_markdown(title=title, markdown_text=markdown_text)

        if self.dingtalk_bot:
            self.db.mark_report_sent(report_type, start_date, end_date)

    def _week_range(self, today):
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start, end

    def _is_week_end(self, today):
        return today.weekday() == 6

    def _load_holiday_ranges(self):
        if not self.holiday_config_path.exists():
            return []

        try:
            payload = json.loads(self.holiday_config_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logging.error("读取节假日配置失败: %s", exc)
            return []

        ranges = payload.get("ranges", []) if isinstance(payload, dict) else []
        valid = []
        for item in ranges:
            if not isinstance(item, dict):
                continue
            start_date = item.get("start_date")
            end_date = item.get("end_date")
            if not start_date or not end_date:
                continue
            valid.append(
                {
                    "start_date": start_date,
                    "end_date": end_date,
                    "name": item.get("name", ""),
                }
            )
        return valid

    def _holiday_ranges_ending_today(self, today):
        today_str = today.strftime("%Y-%m-%d")
        return [x for x in self._load_holiday_ranges() if x.get("end_date") == today_str]

    def run_once(self):
        daily_flow = self.service.fetch_and_parse_daily_flow()
        if not daily_flow:
            return None

        today = datetime.now().date()
        today_str = today.strftime("%Y-%m-%d")
        self.service.save_daily_flow(daily_flow, date_str=today_str)

        daily_title = self._build_title("daily", today_str, today_str)
        self._send_markdown(daily_title, self.format_output_for_dingtalk(daily_flow))

        if self._is_week_end(today):
            week_start, week_end = self._week_range(today)
            self._send_aggregated_report(
                report_type="weekly",
                start_date=week_start.strftime("%Y-%m-%d"),
                end_date=week_end.strftime("%Y-%m-%d"),
            )

        for holiday in self._holiday_ranges_ending_today(today):
            self._send_aggregated_report(
                report_type="holiday",
                start_date=holiday["start_date"],
                end_date=holiday["end_date"],
            )

        return daily_flow

    def get_daily_flow(self):
        return self.run_once()
