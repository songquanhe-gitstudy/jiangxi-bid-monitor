"""
江西公共资源交易平台招标信息监控系统配置文件
"""

# API配置
API_BASE_URL = "https://ggzy.jiangxi.gov.cn"
API_ENDPOINT = "/XZinterface/rest/esinteligentsearch/getFullTextDataNew"

# 行业类型编码
INDUSTRY_TYPES = {
    "房建及市政工程": "002001",
    # 其他行业类型（备用）
    #"政府采购": "002006",
    #"交通工程": "002002",
    #"水利工程": "002003",
}

# 信息类型编码（房建及市政工程下的子类型）
INFO_TYPES = {
    "招标计划": "002001006",
    "招标公告": "002001001",
    "中标候选人公示": "002001004",
    # 其他类型（备用）
    #"中标结果公示": "002001005",
    #"文件下载": "002001003",
    #"答疑澄清": "002001002",
}

# 监控配置 - 关注的信息类型
MONITOR_INFO_TYPES = ["招标计划", "招标公告", "中标候选人公示"]

# 抓取配置
MAX_RECORDS_PER_REQUEST = 10  # 每次请求最大记录数（API可能有限制）
REQUEST_TIMEOUT = 60  # 请求超时时间（秒）
REQUEST_DELAY = 5  # 每次请求间隔时间（秒），避免请求过快

# 定时任务配置
SCHEDULE_CONFIG = {
    "start_hour": 8,   # 早上8点开始
    "end_hour": 23,    # 晚上11点结束
    "interval_hours": 2,  # 每2小时执行一次
}

# 数据库配置
DATABASE_PATH = "data/bid_info.db"
RECORDS_JSON_PATH = "data/records.json"  # 用于快速检查已抓取记录

# 飞书通知配置（需要用户自行配置）
FEISHU_CONFIG = {
    "webhook_url": "",  # 飞书机器人webhook地址，需要用户填写
    # 或者使用飞书API
    "app_id": "",       # 飞书应用ID
    "app_secret": "",   # 飞书应用密钥
    "receive_id": "",   # 接收消息的用户/群ID
}

# 日志配置
LOG_PATH = "logs/monitor.log"
LOG_LEVEL = "INFO"