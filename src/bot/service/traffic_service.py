import logging

from src.bot.api.traffic_api import TrafficAPI


class TrafficService:
    def __init__(self, api: TrafficAPI, library_codes, db=None):
        self.api = api
        self.library_codes = library_codes
        self.db = db

    def fetch_and_parse_daily_flow(self):
        """调用接口并解析当日人流数据"""
        logging.info("开始获取人流数据...")

        data = self.api.fetch_flow_data(use_backup=False)
        if not data:
            logging.warning("主接口失败，尝试备用接口...")
            data = self.api.fetch_flow_data(use_backup=True)

        if not data:
            logging.error("所有接口都无法访问，本次任务失败")
            return None

        flow_data = self.parse_daily_flow(data)

        if not flow_data:
            logging.error("解析人流数据失败，不进行后续处理")
            return None

        logging.info("人流数据获取和解析完成")
        return flow_data

    def parse_daily_flow(self, data):
        """解析当日人流数据"""
        if not data or not data.get("isSuccess"):
            logging.error("API返回数据异常或未成功")
            return None

        flow_summary = {}

        for library in data.get("data", []):
            org_location = library.get("orgLocation")
            org_name = library.get("orgLocationName")

            if org_location not in self.library_codes:
                continue

            # 查找当日数据：仅使用进馆，出馆固定为0
            daily_in = 0
            daily_out = 0

            for count_data in library.get("fCount", []):
                if count_data.get("countType") == "日":
                    if count_data.get("dateType") == 0:  # 进馆
                        daily_in = count_data.get("personCount", 0)

            flow_summary[org_location] = {
                "name": org_name,
                "daily_in": daily_in,
                "daily_out": daily_out,
            }

        return flow_summary

    def save_daily_flow(self, flow_data, date_str=None):
        """保存当日人流数据到数据库"""
        if not self.db or not flow_data:
            return

        if date_str is None:
            from datetime import datetime

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
    ):
        # API接口地址
        primary_url = primary_url or (
            "https://pfs.zjlib.cn/zhejiangshengtsg/alvarainflow/"
            "api/WwStatisticsLog/GetBigFlowByLocations"
        )
        backup_url = backup_url or (
            "https://shujia.alva.com.cn/zhejiangshengtsg/alvarainflow/"
            "api/WwStatisticsLog/GetBigFlowByLocations"
        )

        # 馆区代码和名称映射
        self.library_codes = library_codes or {
            "CN-ZJLIB_ZJ": "之江馆",
            "CN-ZJLIB_BSGL": "曙光馆",
            "CN-ZJLIB_BSL": "大学路馆",
        }

        # 请求参数
        payload = {
            "orgLocations": org_locations
            or ["CN-ZJLIB_ZJ", "CN-ZJLIB_BSGL", "CN-ZJLIB_BSL"]
        }

        # 请求头
        headers = {
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36"
            ),
        }

        api = TrafficAPI(
            primary_url=primary_url,
            backup_url=backup_url,
            payload=payload,
            headers=headers,
        )
        self.service = TrafficService(
            api=api,
            library_codes=self.library_codes,
            db=db,
        )

        # 保存钉钉机器人实例
        self.dingtalk_bot = dingtalk_bot

    def format_output_for_dingtalk(self, flow_data):
        """格式化输出为钉钉Markdown格式"""
        if not flow_data:
            return "无法获取人流数据"

        from datetime import datetime

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output_lines = [
            f"#### 浙江图书馆人流统计 ({current_time})",
            "---",
        ]

        total_in = 0
        total_out = 0

        for info in flow_data.values():
            output_lines.extend(
                [
                    f"**📍 {info['name']}**",
                    f"- **进馆人次**: {info['daily_in']:,}",
                    "",
                ]
            )
            total_in += info["daily_in"]
            total_out += info["daily_out"]

        output_lines.extend(
            [
                "---",
                "**📊 总计:**",
                f"- **总进馆人次**: {total_in:,}",
            ]
        )

        return "\n".join(output_lines)

    def format_output(self, flow_data):
        """控制台输出"""
        return self.format_output_for_dingtalk(flow_data)

    def get_daily_flow(self):
        """获取、解析、输出并推送到钉钉"""
        flow_data = self.service.fetch_and_parse_daily_flow()
        if not flow_data:
            return None

        self.service.save_daily_flow(flow_data)

        # 格式化消息并推送到钉钉
        if self.dingtalk_bot:
            from datetime import datetime

            title = f"浙图人流速报 {datetime.now().strftime('%Y-%m-%d')}"
            markdown_text = self.format_output_for_dingtalk(flow_data)
            self.dingtalk_bot.send_markdown(
                title=title, text=markdown_text, is_at_all=False
            )
            logging.info("成功推送到钉钉群")
            # 也在控制台打印一份，方便本地查看
            print(
                "\n--- 推送到钉钉的消息预览 ---\n"
                + markdown_text
                + "\n---------------------------\n"
            )
        else:
            logging.warning("未配置钉钉机器人，跳过推送")
            # 如果没有机器人，则在控制台打印原始格式
            print(self.format_output(flow_data))

        return flow_data
