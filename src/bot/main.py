import logging
from pathlib import Path

from dingtalkchatbot.chatbot import DingtalkChatbot

from src.bot.service.traffic_service import LibraryFlowMonitor
from src.bot.storage.database import Database


LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "library_flow.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def main():
    webhook = (
        "https://openplatform-pro.ding.zj.gov.cn/robot/send?"
        "access_token=1bb3c90d0d1e1855e4851b9d30080bbb5763e173433512ebd6a66722d55625c9"
    )
    secret = "SEC3c2e7e293180ba69854687a1b639fbd9fa3a8550f085fc0ea2cb9070930cd308"

    try:
        if "YOUR_REAL_WEBHOOK_URL" in webhook:
            print("错误：请将 webhook 替换为真实钉钉机器人地址")
            chatbot = None
        else:
            chatbot = DingtalkChatbot(webhook, secret=secret)
    except Exception as exc:
        logging.error("初始化钉钉机器人失败: %s", exc)
        chatbot = None

    db = Database()
    monitor = LibraryFlowMonitor(dingtalk_bot=chatbot, db=db)

    try:
        monitor.run_once()
    finally:
        db.close()


if __name__ == "__main__":
    main()
