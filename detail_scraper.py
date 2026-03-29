"""
详情页面抓取模块 - 抓取原始HTML内容
"""

import requests
import json
import re
import time
from typing import Dict, Optional
from datetime import datetime
import logging

from config import REQUEST_TIMEOUT, REQUEST_DELAY

logger = logging.getLogger(__name__)


class DetailScraper:
    """详情页面抓取器 - 获取原始HTML内容"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })

    def fetch_detail(self, url: str, info_type: str, title: str = "", publish_time: str = "") -> Optional[Dict]:
        """
        抓取详情页面，返回文本内容

        Args:
            url: 详情页面URL
            info_type: 信息类型（招标计划/招标公告/中标候选人公示）
            title: 标题
            publish_time: 发布时间

        Returns:
            包含纯文本的字典（不包含HTML）
        """

        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.encoding = 'utf-8'
            html = response.text

            # 提取纯文本内容
            text = self._html_to_text(html)

            detail = {
                "title": title,
                "publish_time": publish_time,
                "info_type": info_type,
                "url": url,
                "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "text": text,
            }

            logger.info(f"成功抓取详情: {url[:60]}...")
            return detail

        except requests.exceptions.Timeout:
            logger.error(f"请求超时: {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败: {url}, 错误: {e}")
            return None
        except Exception as e:
            logger.error(f"抓取异常: {url}, 错误: {e}")
            return None

    def _html_to_text(self, html: str) -> str:
        """将HTML转换为纯文本"""

        # 移除script和style标签及其内容
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)

        # 将常见的块级标签替换为换行
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</tr>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</td>', ' | ', text, flags=re.IGNORECASE)
        text = re.sub(r'</th>', ' | ', text, flags=re.IGNORECASE)
        text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)

        # 移除所有剩余的HTML标签
        text = re.sub(r'<[^>]+>', '', text)

        # 清理HTML实体
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#34;', '"')
        text = text.replace('&#39;', "'")

        # 清理多余空白
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = text.strip()

        return text

    def fetch_batch(self, records: list, delay: float = REQUEST_DELAY) -> list:
        """
        批量抓取详情

        Args:
            records: 记录列表，每条记录需要包含 id, link, info_type, title, publish_time
            delay: 每次请求间隔时间

        Returns:
            抓取结果列表
        """

        results = []
        total = len(records)

        for i, record in enumerate(records):
            record_id = record.get('id')
            url = record.get('link')
            info_type = record.get('info_type')
            title = record.get('title', '')
            publish_time = record.get('publish_time', '')

            if not url:
                logger.warning(f"记录 {record_id} 没有链接")
                continue

            logger.info(f"抓取进度: {i+1}/{total}")

            detail = self.fetch_detail(url, info_type, title, publish_time)
            if detail:
                detail['record_id'] = record_id
                results.append(detail)

            # 间隔等待
            if i < total - 1:
                time.sleep(delay)

        return results


def test_detail_scraper():
    """测试详情抓取"""

    scraper = DetailScraper()

    # 测试URL
    test_urls = [
        ("招标计划", "https://ggzy.jiangxi.gov.cn/jyxx/002001/002001006/20260328/d96e1d7a-442b-4ebd-aacd-5d2fbac37aa4.html"),
        ("招标公告", "https://ggzy.jiangxi.gov.cn/jyxx/002001/002001001/20260328/058f0869-b43b-4c3d-849c-70ba333ea8b9.html"),
        ("中标候选人公示", "https://ggzy.jiangxi.gov.cn/jyxx/002001/002001004/20260328/da8dcf2c-17df-4a47-9196-ee3778eb505b.html"),
    ]

    for info_type, url in test_urls:
        print("=" * 60)
        print(f"测试: {info_type}")
        print("=" * 60)

        result = scraper.fetch_detail(url, info_type)

        if result:
            # 显示文本内容（前500字符）
            print(f"\n纯文本内容:\n{result['text'][:500]}...")
            print(f"\nHTML长度: {len(result['html'])} 字符")
        else:
            print("抓取失败")

        print()
        time.sleep(2)


if __name__ == "__main__":
    test_detail_scraper()