import logging
import schedule
import time
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
    """主函数"""
    # --- 钉钉机器人配置 ---
    # 请将下面的地址和密钥替换为你的实际信息
    # Webhook地址, 从钉钉群机器人设置中获取
    prod_webhook = (
        "https://openplatform-pro.ding.zj.gov.cn/robot/send?"
        "access_token=1bb3c90d0d1e1855e4851b9d30080bbb5763e173433512ebd6a66722d55625c9"
    )
    # 可选：加签密钥(Secret), 从机器人安全设置中获取。如果未设置则留空或设为None
    prod_secret = "SEC3c2e7e293180ba69854687a1b639fbd9fa3a8550f085fc0ea2cb9070930cd308"

    dingtalk_webhook = prod_webhook
    dingtalk_secret = prod_secret

    # 初始化钉钉机器人
    # 注意：如果你的webhook或secret是无效的占位符，这里会报错，请务必修改
    try:
        if "YOUR_REAL_WEBHOOK_URL" in dingtalk_webhook:
            print("错误：请在代码中替换'dingtalk_webhook'为你的实际钉钉机器人Webhook地址。")
            chatbot = None
        else:
            chatbot = DingtalkChatbot(dingtalk_webhook, secret=dingtalk_secret)
    except Exception as exc:
        logging.error("初始化钉钉机器人失败: %s", exc)
        chatbot = None

    # 初始化监控器，并传入机器人实例
    db = Database()
    monitor = LibraryFlowMonitor(dingtalk_bot=chatbot, db=db)

    # --- 定时任务设置 ---
    # 每天指定时间执行
    def run_daily():
        if datetime.now().weekday() == 6:
            return
        monitor.get_daily_flow(include_weekly=False)

    def run_weekly():
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        weekly_range_text = (
            f"{week_start.strftime('%Y-%m-%d')}至{week_end.strftime('%Y-%m-%d')}"
        )
        monitor.get_daily_flow(include_weekly=True, weekly_range_text=weekly_range_text)

    schedule.every().day.at("21:00").do(run_daily)
    schedule.every().sunday.at("21:00").do(run_weekly)
    # 你可以根据需要添加更多时间点
    # schedule.every().day.at("21:00").do(monitor.get_daily_flow)

    print("浙江图书馆人流监控脚本已启动...")
    print("定时任务将在每天21:00执行推送")
    print("按 Ctrl+C 停止程序")

    # 启动定时任务循环
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次是否有任务需要运行
    except KeyboardInterrupt:
        print("\n程序已手动停止")
        logging.info("程序手动停止")
    finally:
        db.close()


if __name__ == "__main__":
    main()
