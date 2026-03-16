# 浙江图书馆人流数据监控机器人

一个用于自动获取浙江图书馆各馆区人流数据，并通过钉钉机器人推送日报、周报和节假日报的 Python 应用。

## 功能特性

- **自动数据采集**：每日自动从浙江图书馆 API 获取三个馆区的人流数据
  - 之江馆
  - 曙光馆
  - 大学路馆

- **智能报告推送**：
  - **日报**：每日推送当日各馆区进馆人次
  - **周报**：每周日自动推送本周累计人流统计
  - **节假日报**：节假日最后一天自动推送假期期间累计人流

- **双链路容错**：主接口故障时自动切换至备用接口，确保数据获取稳定性

- **数据持久化**：使用 SQLite 数据库存储历史数据，支持数据查询和报告去重

- **智能去重**：周报和节假日报通过数据库记录避免重复发送

## 技术栈

- Python 3.8+
- SQLite3
- requests - HTTP 请求
- dingtalkchatbot - 钉钉机器人 SDK

## 项目结构

```
dingTalkZjlib/
├── config/
│   └── holiday_ranges.json    # 节假日配置文件
├── data/
│   └── bot.db                 # SQLite 数据库文件
├── logs/
│   └── library_flow.log       # 应用日志文件
├── src/
│   └── bot/
│       ├── api/
│       │   └── traffic_api.py     # API 接口调用模块
│       ├── service/
│       │   └── traffic_service.py # 业务逻辑与报告生成
│       ├── storage/
│       │   ├── database.py        # 数据库操作
│       │   └── models.py          # 数据模型
│       └── main.py                # 程序入口
├── requirements.txt           # Python 依赖
└── README.md                  # 项目说明文档
```

## 安装部署

### 1. 克隆仓库

```bash
cd dingTalkZjlib
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置钉钉机器人

编辑 `src/bot/main.py`，替换以下配置：

```python
webhook = "https://openplatform-pro.ding.zj.gov.cn/robot/send?access_token=YOUR_TOKEN"
secret = "YOUR_SECRET"
```

> **获取方式**：在钉钉群中添加自定义机器人，选择"加签"安全设置，复制 Webhook 地址和密钥。

## 使用方法

### 手动运行

```bash
# 从项目根目录运行
python -m src.bot.main
```

### 定时任务配置（推荐）

使用 **Windows 任务计划程序** 或 **Linux crontab** 设置每日定时执行。

#### Windows 任务计划程序配置建议：

1. 创建基本任务，设置每日触发
2. 操作：启动程序
3. 程序/脚本：`python` 或 `python.exe` 的完整路径
4. 添加参数：`-m src.bot.main`
5. 起始于：项目根目录的完整路径

#### Linux Crontab 示例：

```bash
# 每天 21:00 执行
0 21 * * * cd /path/to/dingTalkZjlib && /path/to/venv/bin/python -m src.bot.main >> /path/to/dingTalkZjlib/logs/cron.log 2>&1
```

## 配置说明

### 节假日配置

编辑 `config/holiday_ranges.json` 添加或修改节假日：

```json
{
  "ranges": [
    {
      "name": "元旦",
      "start_date": "2026-01-01",
      "end_date": "2026-01-03"
    }
  ]
}
```

### 日志配置

日志文件位于 `logs/library_flow.log`，默认配置：
- 单个文件最大：10MB
- 保留备份数量：10 个
- 日志级别：INFO

## 数据库说明

SQLite 数据库自动创建在 `data/bot.db`，包含以下表：

| 表名 | 说明 |
|------|------|
| `traffic_raw_snapshots` | 原始数据快照 |
| `traffic_daily_by_location` | 按馆区汇总的每日数据 |
| `traffic_daily_summary` | 每日总人流汇总 |
| `report_send_log` | 报告发送记录（用于去重）|

## 报告示例

### 日报
```
#### 浙图人流日报
- 统计日期：2026-03-13
---
**之江馆**
- 进馆人次：1,234

**曙光馆**
- 进馆人次：567

**大学路馆**
- 进馆人次：345

---
**总计**
- 总进馆人次：2,146
```

### 周报
```
#### 浙图人流周报
- 统计区间：2026-03-09 ~ 2026-03-15
---
...
```

## 注意事项

1. **网络环境**：确保运行环境能够访问浙江图书馆内网 API（10.18.222.30）或外网备用接口
2. **钉钉机器人**：确保机器人没有被禁言，且 Webhook 地址和密钥正确
3. **时区设置**：服务器时区建议设置为北京时间（Asia/Shanghai）
4. **节假日更新**：每年初更新 `holiday_ranges.json` 中的节假日配置

## 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 无数据返回 | 网络问题或 API 故障 | 检查网络连接，查看日志确认主备接口状态 |
| 钉钉消息未收到 | Webhook 或密钥错误 | 核对钉钉机器人配置信息 |
| 数据库错误 | 文件权限问题 | 检查 `data` 目录的读写权限 |

## 许可证

MIT License

## 维护者

- 项目维护：浙江图书馆技术团队

---

如有问题或建议，请通过钉钉或邮件联系维护团队。
