import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dingtalkchatbot.chatbot import DingtalkChatbot

from src.bot.service.traffic_service import LibraryFlowMonitor
from src.bot.storage.database import Database


LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "library_flow.log"


def setup_logging():
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    rotating_file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    rotating_file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(rotating_file_handler)
    root_logger.addHandler(stream_handler)


setup_logging()


def main():
    webhook = (
        "https://openplatform-pro.ding.zj.gov.cn/robot/send?"
        "access_token=1bb3c90d0d1e1855e4851b9d30080bbb5763e173433512ebd6a66722d55625c9"
    )
    secret = "SEC3c2e7e293180ba69854687a1b639fbd9fa3a8550f085fc0ea2cb9070930cd308"

    try:
        if "YOUR_REAL_WEBHOOK_URL" in webhook:
            print("\u9519\u8bef\uff1a\u8bf7\u5c06 webhook \u66ff\u6362\u4e3a\u771f\u5b9e\u9489\u9489\u673a\u5668\u4eba\u5730\u5740")
            chatbot = None
        else:
            chatbot = DingtalkChatbot(webhook, secret=secret)
    except Exception as exc:
        logging.error("\u521d\u59cb\u5316\u9489\u9489\u673a\u5668\u4eba\u5931\u8d25: %s", exc)
        chatbot = None

    db = Database()
    monitor = LibraryFlowMonitor(dingtalk_bot=chatbot, db=db)

    try:
        monitor.run_once()
    finally:
        db.close()


if __name__ == "__main__":
    main()
