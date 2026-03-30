"""
配置加载模块 - 动态从 config.json 加载所有配置
每次调用获取配置函数时都会重新读取文件，支持热更新
"""

import json
import os

# 配置文件路径
CONFIG_FILE = "config.json"

# 默认配置
DEFAULT_CONFIG = {
    "ai": {
        "api_url": "",
        "api_key": "",
        "model": "qwen3.5-plus",
        "timeout": 300,
        "max_records_per_request": 3
    },
    "feishu": {
        "webhook_url": "",
        "app_id": "",
        "app_secret": "",
        "receive_id": ""
    },
    "scraper": {
        "max_records_per_type": 20,
        "request_delay": 5,
        "request_timeout": 60
    },
    "schedule": {
        "start_hour": 8,
        "end_hour": 22,
        "interval_hours": 2,
        "startup_task": True
    },
    "database": {
        "path": "data/bid_info.db",
        "records_json_path": "data/records.json"
    },
    "dashboard": {
        "url": ""
    }
}

# 平台静态常量（不可配置）
API_BASE_URL = "https://ggzy.jiangxi.gov.cn"
API_ENDPOINT = "/XZinterface/rest/esinteligentsearch/getFullTextDataNew"

INDUSTRY_TYPES = {
    "房建及市政工程": "002001",
}

INFO_TYPES = {
    "招标计划": "002001006",
    "招标公告": "002001001",
    "中标候选人公示": "002001004",
}

MONITOR_INFO_TYPES = ["招标计划", "招标公告", "中标候选人公示"]

# 提示词文件路径
PROMPT_FILES = {
    "招标计划": "prompts/zhaobiao_jihua.txt",
    "招标公告": "prompts/zhaobiao_gonggao.txt",
    "中标候选人公示": "prompts/zhongbiao_houxuanren.txt",
}


def load_config() -> dict:
    """动态加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_CONFIG


def get_ai_config() -> dict:
    """获取AI配置（每次调用重新读取）"""
    config = load_config()
    return config.get("ai", DEFAULT_CONFIG["ai"])


def get_feishu_config() -> dict:
    """获取飞书配置（每次调用重新读取）"""
    config = load_config()
    return config.get("feishu", DEFAULT_CONFIG["feishu"])


def get_scraper_config() -> dict:
    """获取抓取配置（每次调用重新读取）"""
    config = load_config()
    return config.get("scraper", DEFAULT_CONFIG["scraper"])


def get_schedule_config() -> dict:
    """获取调度配置（每次调用重新读取）"""
    config = load_config()
    return config.get("schedule", DEFAULT_CONFIG["schedule"])


def get_database_config() -> dict:
    """获取数据库配置（每次调用重新读取）"""
    config = load_config()
    return config.get("database", DEFAULT_CONFIG["database"])


def get_dashboard_config() -> dict:
    """获取仪表盘配置（每次调用重新读取）"""
    config = load_config()
    return config.get("dashboard", DEFAULT_CONFIG["dashboard"])