import logging
from datetime import datetime, timedelta
from pathlib import Path

from dingtalkchatbot.chatbot import DingtalkChatbot

from src.bot.service.traffic_service import LibraryFlowMonitor
from src.bot.storage.database import Database


LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "library_flow.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def main():
    # 测试Webhook与Secret（用于测试入口）
    test_webhook = (
        "https://openplatform-pro.ding.zj.gov.cn/robot/send?"
        "access_token=1bb3c90d0d1e1855e4851b9d30080bbb5763e173433512ebd6a66722d55625c9"
    )
    test_secret = "SEC3c2e7e293180ba69854687a1b639fbd9fa3a8550f085fc0ea2cb9070930cd308"

    # 初始化钉钉机器人
    try:
        if "YOUR_REAL_WEBHOOK_URL" in test_webhook:
            print("错误：请在代码中替换'test_webhook'为你的测试钉钉机器人Webhook地址。")
            chatbot = None
        else:
            chatbot = DingtalkChatbot(test_webhook, secret=test_secret)
    except Exception as exc:
        logging.error("初始化钉钉机器人失败: %s", exc)
        chatbot = None

    db = Database()
    monitor = LibraryFlowMonitor(dingtalk_bot=chatbot, db=db)

    today = datetime.now()
    month_start = today.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    month_end = next_month - timedelta(days=1)
    monthly_range_text = (
        f"{month_start.strftime('%Y-%m-%d')}至{month_end.strftime('%Y-%m-%d')}"
    )
    monitor.get_daily_flow(include_monthly=True, monthly_range_text=monthly_range_text)
    db.close()


if __name__ == "__main__":
    main()
