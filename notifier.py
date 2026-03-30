"""
飞书通知模块
支持Webhook和API两种方式发送消息
"""

import requests
import json
from datetime import datetime
from typing import List, Dict, Optional
import logging

from config import get_feishu_config

logger = logging.getLogger(__name__)


class FeishuNotifier:
    """飞书消息通知器"""

    def __init__(self):
        feishu_config = get_feishu_config()
        self.webhook_url = feishu_config.get("webhook_url")
        self.app_id = feishu_config.get("app_id")
        self.app_secret = feishu_config.get("app_secret")
        self.receive_id = feishu_config.get("receive_id")

        # 检查配置
        self.use_webhook = bool(self.webhook_url)
        self.use_api = bool(self.app_id and self.app_secret and self.receive_id)

        if not self.use_webhook and not self.use_api:
            logger.warning("飞书通知未配置，请设置webhook_url或app_id/app_secret/receive_id")

    def _send_webhook(self, content: str) -> bool:
        """通过Webhook发送消息（用于群机器人）"""

        if not self.webhook_url:
            logger.warning("Webhook URL未配置")
            return False

        try:
            response = requests.post(
                self.webhook_url,
                json={
                    "msg_type": "text",
                    "content": {"text": content}
                },
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("StatusCode") == 0 or result.get("code") == 0:
                    logger.info("Webhook消息发送成功")
                    return True
                else:
                    logger.error(f"Webhook返回错误: {result}")
            else:
                logger.error(f"Webhook请求失败: {response.status_code}")

        except Exception as e:
            logger.error(f"Webhook发送异常: {e}")

        return False

    def _get_tenant_access_token(self) -> Optional[str]:
        """获取飞书tenant_access_token"""

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"

        try:
            response = requests.post(
                url,
                json={
                    "app_id": self.app_id,
                    "app_secret": self.app_secret
                },
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    return result.get("tenant_access_token")

            logger.error(f"获取token失败: {response.json()}")

        except Exception as e:
            logger.error(f"获取token异常: {e}")

        return None

    def _send_api_message(self, content: str, msg_type: str = "text") -> bool:
        """通过API发送消息"""

        token = self._get_tenant_access_token()
        if not token:
            return False

        url = "https://open.feishu.cn/open-apis/im/v1/messages"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        params = {
            "receive_id_type": "chat_id"  # 或 open_id/user_id
        }

        body = {
            "receive_id": self.receive_id,
            "msg_type": msg_type,
            "content": json.dumps({"text": content}) if msg_type == "text" else content
        }

        try:
            response = requests.post(url, headers=headers, params=params, json=body, timeout=10)

            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    logger.info("API消息发送成功")
                    return True
                else:
                    logger.error(f"API返回错误: {result}")
            else:
                logger.error(f"API请求失败: {response.status_code}")

        except Exception as e:
            logger.error(f"API发送异常: {e}")

        return False

    def send_text(self, content: str) -> bool:
        """发送文本消息"""

        if self.use_webhook:
            return self._send_webhook(content)
        elif self.use_api:
            return self._send_api_message(content)
        else:
            logger.warning("飞书通知未配置，跳过发送")
            return False

    def send_card(self, title: str, records: List[Dict]) -> bool:
        """发送卡片消息（更美观的通知格式）"""

        if self.use_webhook:
            # Webhook方式发送交互式卡片
            card_content = self._build_card_content(title, records)
            return self._send_webhook_card(card_content)
        elif self.use_api:
            # API方式发送卡片
            card_content = self._build_card_content(title, records)
            return self._send_api_message(json.dumps(card_content), "interactive")
        else:
            logger.warning("飞书通知未配置")
            return False

    def _build_card_content(self, title: str, records: List[Dict]) -> Dict:
        """构建飞书卡片内容"""

        # 构建卡片元素
        elements = []

        # 标题
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**{title}**"
            }
        })

        # 分隔线
        elements.append({"tag": "hr"})

        # 每条记录
        for i, record in enumerate(records[:10]):  # 最多显示10条
            info_type = record.get("info_type", "")
            region = record.get("region", "")
            title_text = record.get("title", "")
            publish_time = record.get("publish_time", "")
            link = record.get("link", "")

            # 构建单条记录内容
            content = f"**{i+1}. [{info_type}] [{region}]**\n{title_text}\n📅 {publish_time}"

            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": content
                },
                "extra": {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看详情"},
                            "type": "primary",
                            "url": link
                        }
                    ]
                }
            })

            if i < len(records[:10]) - 1:
                elements.append({"tag": "hr"})

        # 底部提示
        total = len(records)
        if total > 10:
            elements.append({
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": f"共 {total} 条记录，仅显示前10条"
                    }
                ]
            })

        # 时间戳
        elements.append({
            "tag": "note",
            "elements": [
                {
                    "tag": "plain_text",
                    "content": f"抓取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            ]
        })

        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "江西招标信息监控"
                },
                "template": "blue"
            },
            "elements": elements
        }

        return card

    def _send_webhook_card(self, card_content: Dict) -> bool:
        """通过Webhook发送卡片"""

        if not self.webhook_url:
            return False

        try:
            response = requests.post(
                self.webhook_url,
                json={
                    "msg_type": "interactive",
                    "card": card_content
                },
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("StatusCode") == 0 or result.get("code") == 0:
                    logger.info("Webhook卡片发送成功")
                    return True

            logger.error(f"Webhook卡片发送失败: {response.text}")

        except Exception as e:
            logger.error(f"Webhook卡片发送异常: {e}")

        return False

    def notify_new_records(self, records: List[Dict]) -> bool:
        """通知新记录"""

        if not records:
            logger.info("无新记录需要通知")
            return True

        # 按信息类型分组
        by_type: Dict[str, List[Dict]] = {}
        for record in records:
            info_type = record.get("info_type", "未知")
            if info_type not in by_type:
                by_type[info_type] = []
            by_type[info_type].append(record)

        # 发送汇总消息
        summary_lines = [
            "🔔 江西招标信息更新通知",
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"共发现 {len(records)} 条新信息:",
        ]

        for info_type, type_records in by_type.items():
            summary_lines.append(f"  • {info_type}: {len(type_records)} 条")

        summary_lines.append("")
        summary_lines.append("详细信息请查看系统或点击链接")

        # 先发送汇总文本
        self.send_text("\n".join(summary_lines))

        # 再发送详细卡片（每种类型一张卡片）
        for info_type, type_records in by_type.items():
            title = f"📋 {info_type} - {len(type_records)} 条"
            self.send_card(title, type_records)

        return True


def test_notifier():
    """测试通知功能"""

    notifier = FeishuNotifier()

    # 测试数据
    test_records = [
        {
            "id": "test-001",
            "title": "[南昌市]某市政道路改造工程招标公告",
            "link": "https://ggzy.jiangxi.gov.cn/test.html",
            "publish_time": "2024-01-01 10:00:00",
            "info_type": "招标公告",
            "region": "南昌市",
        },
        {
            "id": "test-002",
            "title": "[赣州市]某污水处理厂中标候选人公示",
            "link": "https://ggzy.jiangxi.gov.cn/test2.html",
            "publish_time": "2024-01-01 11:00:00",
            "info_type": "中标候选人公示",
            "region": "赣州市",
        }
    ]

    # 发送测试通知
    if notifier.use_webhook or notifier.use_api:
        notifier.notify_new_records(test_records)
    else:
        print("飞书通知未配置")
        print("请设置以下配置项之一:")
        print("1. FEISHU_CONFIG['webhook_url'] - 群机器人Webhook地址")
        print("2. FEISHU_CONFIG['app_id'] + app_secret + receive_id - 飞书应用配置")


if __name__ == "__main__":
    test_notifier()