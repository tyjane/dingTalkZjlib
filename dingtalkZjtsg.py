import requests
import json
import schedule
import time
from datetime import datetime
import logging
from dingtalkchatbot.chatbot import DingtalkChatbot

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('library_flow.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class LibraryFlowMonitor:
    def __init__(self, dingtalk_bot=None):
        """
        初始化监控器
        :param dingtalk_bot: 传入配置好的DingtalkChatbot实例
        """
        # API接口地址
        self.primary_url = "https://pfs.zjlib.cn/zhejiangshengtsg/alvarainflow/api/WwStatisticsLog/GetBigFlowByLocations"
        self.backup_url = "https://shujia.alva.com.cn/zhejiangshengtsg/alvarainflow/api/WwStatisticsLog/GetBigFlowByLocations"
        
        # 馆区代码和名称映射
        self.library_codes = {
            "CN-ZJLIB_ZJ": "之江馆",
            "CN-ZJLIB_BSGL": "曙光馆", 
            "CN-ZJLIB_BSL": "大学路馆"
        }
        
        # 请求参数
        self.payload = {
            "orgLocations": ["CN-ZJLIB_ZJ", "CN-ZJLIB_BSGL", "CN-ZJLIB_BSL"]
        }
        
        # 请求头
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # 保存钉钉机器人实例
        self.dingtalk_bot = dingtalk_bot

    def fetch_flow_data(self, use_backup=False):
        """获取人流数据"""
        url = self.backup_url if use_backup else self.primary_url
        
        try:
            response = requests.post(
                url, 
                json=self.payload, 
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"请求失败 {'(备用接口)' if use_backup else '(主接口)'}: {e}")
            return None

    def parse_daily_flow(self, data):
        """解析当日人流数据"""
        if not data or not data.get('isSuccess'):
            logging.error("API返回数据异常或未成功")
            return None
            
        flow_summary = {}
        
        for library in data.get('data', []):
            org_location = library.get('orgLocation')
            org_name = library.get('orgLocationName')
            
            if org_location not in self.library_codes:
                continue
                
            # 查找当日数据 (countType="日" 且 dateType=0表示进馆, 1表示出馆)
            daily_in = 0
            daily_out = 0
            
            for count_data in library.get('fCount', []):
                if count_data.get('countType') == '日':
                    if count_data.get('dateType') == 0:  # 进馆
                        daily_in = count_data.get('personCount', 0)
                    elif count_data.get('dateType') == 1:  # 出馆
                        daily_out = count_data.get('personCount', 0)
            
            flow_summary[org_location] = {
                'name': org_name,
                'daily_in': daily_in,
                'daily_out': daily_out,
                'net_flow': daily_in - daily_out
            }
        
        return flow_summary

    def format_output_for_dingtalk(self, flow_data):
        """格式化输出为钉钉Markdown格式"""
        if not flow_data:
            return "无法获取人流数据"
            
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output_lines = [
            f"#### 浙江图书馆人流统计 ({current_time})",
            "---"
        ]
        
        total_in = 0
        total_out = 0
        
        for code, info in flow_data.items():
            output_lines.extend([
                f"**📍 {info['name']}**",
                f"- **进馆人次**: {info['daily_in']:,}",
               # f"- **出馆**: {info['daily_out']:,}",
               # f"- **在馆**: {info['net_flow']:,}",
                ""
            ])
            total_in += info['daily_in']
            total_out += info['daily_out']
        
        output_lines.extend([
            "---",
            f"**📊 总计:**",
            f"- **总进馆人次**: {total_in:,}",
         #   f"- **总出馆**: {total_out:,}",
         #   f"- **总在馆**: {total_in - total_out:,}"
        ])
        
        return "\n".join(output_lines)

    def get_daily_flow(self):
        """获取、解析、输出并推送到钉钉"""
        logging.info("开始获取人流数据...")
        
        data = self.fetch_flow_data(use_backup=False)
        if not data:
            logging.warning("主接口失败，尝试备用接口...")
            data = self.fetch_flow_data(use_backup=True)
        
        if not data:
            logging.error("所有接口都无法访问，本次任务失败")
            return
        
        flow_data = self.parse_daily_flow(data)
        
        if not flow_data:
            logging.error("解析人流数据失败，不进行推送")
            return
            
        logging.info("人流数据获取和解析完成")

        # 格式化消息并推送到钉钉
        if self.dingtalk_bot:
            title = f"浙图人流速报 {datetime.now().strftime('%Y-%m-%d')}"
            markdown_text = self.format_output_for_dingtalk(flow_data)
            self.dingtalk_bot.send_markdown(title=title, text=markdown_text, is_at_all=False)
            logging.info("成功推送到钉钉群")
            # 也在控制台打印一份，方便本地查看
            print("\n--- 推送到钉钉的消息预览 ---\n" + markdown_text + "\n---------------------------\n")
        else:
            logging.warning("未配置钉钉机器人，跳过推送")
            # 如果没有机器人，则在控制台打印原始格式
            output = self.format_output(flow_data)
            print(output)

        return flow_data

def main():
    """主函数"""
    # --- 钉钉机器人配置 ---
    # 请将下面的地址和密钥替换为你的实际信息
    # Webhook地址, 从钉钉群机器人设置中获取
    DINGTALK_WEBHOOK = "https://openplatform-pro.ding.zj.gov.cn/robot/send?access_token=8e30c6ee9f754d30e55561f80ed34eba24d70d6e25f8ec6f0fb3025819e5a6ed" 
    # 可选：加签密钥(Secret), 从机器人安全设置中获取。如果未设置则留空或设为None
    DINGTALK_SECRET = "SEC668ae0d326c49feaa840647042cfc30af257111521738bfec3abf8b6fa47b97c"  

    # 初始化钉钉机器人
    # 注意：如果你的webhook或secret是无效的占位符，这里会报错，请务必修改
    try:
        if "YOUR_REAL_WEBHOOK_URL" in DINGTALK_WEBHOOK:
             print("错误：请在代码中替换'DINGTALK_WEBHOOK'为你的实际钉钉机器人Webhook地址。")
             chatbot = None
        else:
             chatbot = DingtalkChatbot(DINGTALK_WEBHOOK, secret=DINGTALK_SECRET)
    except Exception as e:
        logging.error(f"初始化钉钉机器人失败: {e}")
        chatbot = None

    # 初始化监控器，并传入机器人实例
    monitor = LibraryFlowMonitor(dingtalk_bot=chatbot)
    
    # --- 定时任务设置 ---
    # 每天指定时间执行
    schedule.every().day.at("21:00").do(monitor.get_daily_flow)
    # 你可以根据需要添加更多时间点
    # schedule.every().day.at("21:00").do(monitor.get_daily_flow)

    print("浙江图书馆人流监控脚本已启动...")
    print(f"定时任务将在每天21:00执行推送")
    print("按 Ctrl+C 停止程序")
    
    # 启动定时任务循环
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次是否有任务需要运行
    except KeyboardInterrupt:
        print("\n程序已手动停止")
        logging.info("程序手动停止")

if __name__ == "__main__":
    main()