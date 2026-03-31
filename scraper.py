"""
江西公共资源交易平台数据抓取模块
使用官方API直接获取数据，无需浏览器自动化
"""

# 首先配置OpenSSL支持legacy renegotiation（必须在导入requests之前）
import os
import ssl
import tempfile

def setup_openssl_legacy():
    """配置OpenSSL支持legacy renegotiation"""
    conf_content = """openssl_conf = openssl_init

[openssl_init]
ssl_conf = ssl_sect

[ssl_sect]
system_default = system_default_sect

[system_default_sect]
CipherString = DEFAULT:@SECLEVEL=1
Options = UnsafeLegacyRenegotiation
"""
    conf_file = tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False)
    conf_file.write(conf_content)
    conf_file.close()
    os.environ['OPENSSL_CONF'] = conf_file.name

setup_openssl_legacy()

# 然后才导入其他模块
import requests
import json
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from config import (
    API_BASE_URL, API_ENDPOINT,
    INDUSTRY_TYPES, INFO_TYPES, MONITOR_INFO_TYPES,
    get_scraper_config,
)

logger = logging.getLogger(__name__)


class JiangxiBidScraper:
    """江西公共资源交易平台数据抓取器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"{API_BASE_URL}/jyxx/trade.html",
            "Origin": API_BASE_URL,
        })
        # 初始化时获取token
        self._init_session()

    def _init_session(self):
        """初始化会话，获取必要的token"""
        try:
            # 获取OAuth信息
            app_info_url = f"{API_BASE_URL}/XZEWB-FRONT/rest/getOauthInfoAction/getAppInfo"
            self.session.post(app_info_url, json={}, timeout=10)

            # 获取匿名访问token
            token_url = f"{API_BASE_URL}/XZEWB-FRONT/rest/getOauthInfoAction/getNoUserAccessToken"
            response = self.session.post(token_url, json={}, timeout=10)

            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    data = result.get("data", {})
                    access_token = data.get("noOauthAccessToken")
                    refresh_token = data.get("noOauthRefreshToken")
                    if access_token:
                        self.session.cookies.set("noOauthAccessToken", access_token)
                        logger.info("成功获取访问token")
                    if refresh_token:
                        self.session.cookies.set("noOauthRefreshToken", refresh_token)
        except Exception as e:
            logger.warning(f"获取token失败（可能不影响使用）: {e}")

    def _build_request_body(
        self,
        industry_code: str,
        info_type_code: Optional[str] = None,
        page_num: int = 0,
        page_size: int = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """构建API请求体"""

        # 动态获取配置 - 每次请求固定10条
        if page_size is None:
            page_size = get_scraper_config().get("page_size", 10)

        # 时间范围：默认查询最近3个月
        if not start_date:
            start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d 00:00:00")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d 23:59:59")

        # 构建条件 - 与网页请求保持一致，始终使用模糊匹配
        conditions = [
            {
                "fieldName": "categorynum",
                "equal": info_type_code if info_type_code else industry_code,
                "notEqual": None,
                "equalList": None,
                "notEqualList": None,
                "isLike": True,
                "likeType": 2
            }
        ]

        request_body = {
            "token": "",
            "pn": page_num * page_size,  # offset: 从第几条开始
            "rn": page_size,              # limit: 返回多少条
            "sdt": "",
            "edt": "",
            "wd": "",
            "inc_wd": "",
            "exc_wd": "",
            "fields": "",
            "cnum": "",
            "sort": "{\"webdate\":\"0\",\"id\":\"0\"}",  # 按发布时间降序
            "ssort": "",
            "cl": 500,
            "terminal": "",
            "condition": conditions,
            "time": [
                {
                    "fieldName": "webdate",
                    "startTime": start_date,
                    "endTime": end_date
                }
            ],
            "highlights": "",
            "statistics": None,
            "unionCondition": [],
            "accuracy": "",
            "noParticiple": "1",
            "searchRange": None,
            "noWd": True
        }

        return request_body

    def _make_request(self, request_body: Dict) -> Optional[Dict]:
        """发送API请求"""

        url = f"{API_BASE_URL}{API_ENDPOINT}"
        request_timeout = get_scraper_config().get("request_timeout", 60)

        try:
            # 尝试两种请求方式
            # 方式1: 作为JSON body发送
            response = self.session.post(
                url,
                json=request_body,
                timeout=request_timeout
            )

            if response.status_code != 200:
                # 方式2: 作为form data发送
                response = self.session.post(
                    url,
                    data={"param": json.dumps(request_body)},
                    timeout=request_timeout
                )

            response.raise_for_status()

            result = response.json()
            if result.get("success") or result.get("result"):
                return result.get("result", result)
            else:
                logger.error(f"API返回错误: {result}")
                return None

        except requests.exceptions.Timeout:
            logger.error("请求超时")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"请求异常: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {e}")
            return None

    def fetch_by_info_type(
        self,
        info_type_name: str,
        page_num: int = 0,
        page_size: int = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """按信息类型抓取数据"""

        # 动态获取页大小配置（每次请求固定10条）
        if page_size is None:
            page_size = get_scraper_config().get("page_size", 10)

        industry_code = INDUSTRY_TYPES["房建及市政工程"]
        info_type_code = INFO_TYPES.get(info_type_name)

        if not info_type_code:
            logger.error(f"未知的信息类型: {info_type_name}")
            return {"total": 0, "records": []}

        request_body = self._build_request_body(
            industry_code=industry_code,
            info_type_code=info_type_code,
            page_num=page_num,
            page_size=page_size,
            start_date=start_date,
            end_date=end_date
        )

        logger.info(f"正在抓取: {info_type_name}, 第{page_num + 1}页 (从第{page_num * page_size + 1}条开始)")

        result = self._make_request(request_body)

        if result:
            records = result.get("records", [])
            total = result.get("totalcount", 0)

            # 标准化记录格式
            normalized_records = []
            for record in records:
                normalized_records.append({
                    "id": record.get("infoid", ""),
                    "title": record.get("titlenew", record.get("title", "")),
                    "link": f"{API_BASE_URL}{record.get('linkurl', '')}",
                    "publish_time": record.get("webdate", ""),
                    "info_type": record.get("categoryname", info_type_name),
                    "region": record.get("xiaquname", ""),
                    "region_code": record.get("xiaqucode", ""),
                    "bid_type": record.get("kaibiaotype", ""),
                    "content": record.get("content", ""),
                    "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })

            logger.info(f"获取到 {len(normalized_records)} 条记录, 总计 {total} 条")
            return {"total": total, "records": normalized_records}

        return {"total": 0, "records": []}

    def fetch_all_info_types(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_pages_per_type: int = None  # 每种类型最多抓取几页，从配置读取
    ) -> Dict[str, List[Dict]]:
        """抓取所有监控的信息类型"""

        # 从配置获取页数（2页 = 20条数据）
        if max_pages_per_type is None:
            max_pages_per_type = get_scraper_config().get("max_pages_per_type", 2)

        # 每次请求的条数
        page_size = get_scraper_config().get("page_size", 10)

        all_records = {}

        for info_type in MONITOR_INFO_TYPES:
            records = []
            page_num = 0

            while page_num < max_pages_per_type:
                result = self.fetch_by_info_type(
                    info_type_name=info_type,
                    page_num=page_num,
                    page_size=page_size,
                    start_date=start_date,
                    end_date=end_date
                )

                if result["records"]:
                    records.extend(result["records"])

                    # 如果返回记录数小于请求的页大小，说明已经获取完毕
                    if len(result["records"]) < page_size:
                        break
                else:
                    break

                page_num += 1
                time.sleep(get_scraper_config().get("request_delay", 5))  # 避免请求过快

            all_records[info_type] = records

        return all_records

    def fetch_latest(
        self,
        hours: int = 1  # 获取最近几小时的数据
    ) -> Dict[str, List[Dict]]:
        """获取最新数据（增量抓取）"""

        start_date = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:00")
        end_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"增量抓取: {start_date} ~ {end_date}")

        return self.fetch_all_info_types(
            start_date=start_date,
            end_date=end_date,
            max_pages_per_type=3  # 增量抓取只需要少量页面
        )


def test_scraper():
    """测试抓取功能"""

    scraper = JiangxiBidScraper()

    # 测试抓取招标计划
    print("=" * 10)
    print("测试抓取: 招标计划")
    print("=" * 10)
    result = scraper.fetch_by_info_type("招标计划", page_size=5)
    for record in result["records"]:
        print(f"\n标题: {record['title']}")
        print(f"发布时间: {record['publish_time']}")
        print(f"辖区: {record['region']}")
        print(f"链接: {record['link']}")

    print("\n" + "=" * 10)
    print("测试增量抓取（最近1小时）")
    print("=" * 10)
    latest = scraper.fetch_latest(hours=24)  # 测试时扩大范围
    for info_type, records in latest.items():
        print(f"\n{info_type}: {len(records)} 条新记录")


if __name__ == "__main__":
    test_scraper()