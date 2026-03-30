"""
飞书消息发送模块 - 将提取的数据发送到飞书
"""

import json
import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime

from config import get_feishu_config, get_dashboard_config

logger = logging.getLogger(__name__)


class FeishuSender:
    """飞书消息发送器"""

    def __init__(self, storage=None):
        self.storage = storage

    def _get_feishu_config(self) -> dict:
        """动态获取飞书配置"""
        return get_feishu_config()

    def _get_access_token(self) -> Optional[str]:
        """获取飞书access_token（使用API方式时需要）"""

        feishu_config = self._get_feishu_config()
        if not feishu_config["app_id"] or not feishu_config["app_secret"]:
            return None

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        data = {
            "app_id": feishu_config["app_id"],
            "app_secret": feishu_config["app_secret"],
        }

        try:
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    return result.get("tenant_access_token")
        except Exception as e:
            logger.error(f"获取飞书token失败: {e}")

        return None

    def format_records_to_card(self, records: List[Dict]) -> Dict:
        """
        将记录格式化为飞书卡片消息
        使用 interactive 消息类型支持加粗和大字体
        """
        elements = []

        # 获取网站地址
        dashboard_config = get_dashboard_config()
        dashboard_url = dashboard_config.get("url", "")

        # 头部标题
        elements.append({
            "tag": "div",
            "text": {
                "tag": "plain_text",
                "content": f"招标信息提取汇总 ({datetime.now().strftime('%Y-%m-%d %H:%M')})",
                "text_size": "heading",
                "text_align": "left",
                "text_color": "default"
            }
        })

        # 统计信息
        type_count = {}
        for r in records:
            t = r.get('info_type', '未知')
            type_count[t] = type_count.get(t, 0) + 1

        # 类型对应的 emoji 和颜色
        type_emoji = {
            "招标计划": "🟢",
            "招标公告": "🔵",
            "中标候选人公示": "🔴"
        }

        stats_parts = []
        for t, c in type_count.items():
            emoji = type_emoji.get(t, "⚪")
            stats_parts.append(f"{emoji}{t}: {c}条")

        stats_text = " | ".join(stats_parts)
        elements.append({
            "tag": "div",
            "text": {
                "tag": "plain_text",
                "content": f"本次共 {len(records)} 条项目 | {stats_text}",
                "text_size": "normal",
                "text_align": "left"
            }
        })

        # 添加网站链接（如果配置）
        if dashboard_url:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**网站**: [{dashboard_url}]({dashboard_url})",
                    "text_size": "normal",
                    "text_align": "left"
                }
            })

        elements.append({"tag": "hr"})  # 分隔线

        # 每个项目的详情
        for i, record in enumerate(records, 1):
            info_type = record.get('info_type', '')
            title = record.get('title', '')
            link = record.get('link', '')
            publish_time = record.get('publish_time', '')

            # 解析提取数据
            try:
                extracted = json.loads(record.get('extracted_data', '{}'))
            except:
                extracted = {}

            # 获取原始链接
            orig_link = extracted.get('原始链接', '') or link

            # 根据类型设置标题颜色和 emoji
            type_style = {
                "招标计划": {"color": "green", "emoji": "🟢"},
                "招标公告": {"color": "blue", "emoji": "🔵"},
                "中标候选人公示": {"color": "red", "emoji": "🔴"}
            }.get(info_type, {"color": "blue", "emoji": "⚪"})

            # 项目标题（emoji + 加粗 + 颜色 + 大字体）
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"{type_style['emoji']} <font color='{type_style['color']}'>**{i}. 【{info_type}】{title}**</font>",
                    "text_size": "large",
                    "text_align": "left"
                }
            })

            # 根据类型显示字段（大字体）
            fields = self._get_fields_for_type(info_type, extracted)
            for label, value in fields:
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**{label}**: {value}",
                        "text_size": "large",
                        "text_align": "left"
                    }
                })

            # 发布日期（大字体，精确到秒）
            pub_date = extracted.get('发布日期', '') or publish_time if publish_time else '无'
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**发布日期**: {pub_date if pub_date else '无'}",
                    "text_size": "large",
                    "text_align": "left"
                }
            })

            # 原始链接（可点击 + 大字体）
            if orig_link:
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**原始链接**: [{orig_link}]({orig_link})",
                        "text_size": "large",
                        "text_align": "left"
                    }
                })

            elements.append({"tag": "hr"})  # 分隔线

        # 构建卡片数据
        card_data = {
            "elements": elements,
            "header": {
                "title": {
                    "content": "招标信息监控",
                    "tag": "plain_text"
                },
                "template": "blue"
            }
        }

        return card_data

    def _get_fields_for_type(self, info_type: str, data: Dict) -> List[tuple]:
        """根据类型获取字段列表"""
        fields = []

        if info_type == "招标计划":
            field_list = [
                ("建设单位", "建设单位"),
                ("项目类型", "项目类型"),
                ("项目概况", "项目概况"),
                ("招标方式", "招标方式"),
                ("投资额", "投资额"),
                ("资金来源", "资金来源"),
                ("预计招标时间", "预计招标时间"),
                ("拟交易场所", "拟交易场所"),
            ]
        elif info_type == "招标公告":
            field_list = [
                ("招标人", "招标人"),
                ("工程地点", "工程地点"),
                ("工程类别", "工程类别"),
                ("建筑面积", "建筑面积"),
                ("项目总投资", "项目总投资"),
                ("招标范围", "招标范围"),
                ("资质要求", "资质要求"),
                ("招标方式", "招标方式"),
            ]
        elif info_type == "中标候选人公示":
            field_list = [
                ("招标人", "招标人"),
                ("工程地点", "工程地点"),
                ("工程类别", "工程类别"),
                ("最高限价", "最高限价"),
                ("工期", "工期"),
            ]
        else:
            field_list = []

        for label, key in field_list:
            value = data.get(key, "")
            if value and value not in ["未提供", "无", ""]:
                # 精简长字段
                if key in ["项目概况", "招标范围", "资质要求"] and len(value) > 50:
                    value = value[:50] + "..."
                fields.append((label, value))

        # 中标候选人特殊处理
        if info_type == "中标候选人公示":
            candidates = data.get("中标候选人", [])
            if candidates:
                for idx, candidate in enumerate(candidates, 1):
                    name = candidate.get("名称", "无")
                    price = candidate.get("报价", "无")
                    if name and name not in ["未提供", "无"]:
                        fields.append((f"第{idx}名", f"{name} | 报价: {price}"))

        return fields

    def send_via_webhook(self, content: str) -> bool:
        """通过webhook发送消息"""

        webhook_url = self._get_feishu_config().get("webhook_url")
        if not webhook_url:
            logger.warning("飞书webhook_url未配置")
            return False

        # 使用 interactive（卡片）消息类型支持富文本
        data = {
            "msg_type": "interactive",
            "card": content if isinstance(content, dict) else {
                "elements": [{
                    "tag": "div",
                    "text": {
                        "tag": "plain_text",
                        "content": content,
                        "text_size": "normal",
                        "text_align": "left"
                    }
                }]
            }
        }

        try:
            response = requests.post(webhook_url, json=data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("StatusCode") == 0 or result.get("code") == 0:
                    logger.info("飞书webhook消息发送成功")
                    return True
                else:
                    logger.error(f"飞书发送失败: {result}")
        except Exception as e:
            logger.error(f"飞书webhook发送异常: {e}")

        return False

    def _to_bold_text(self, text: str) -> str:
        """将普通文本转换为数学粗体 Unicode 字符（仅支持英文和数字）"""
        bold_chars = {
            'A': '𝐀', 'B': '𝐁', 'C': '𝐂', 'D': '𝐃', 'E': '𝐄', 'F': '𝐅', 'G': '𝐆', 'H': '𝐇',
            'I': '𝐈', 'J': '𝐉', 'K': '𝐊', 'L': '𝐋', 'M': '𝐌', 'N': '𝐍', 'O': '𝐎', 'P': '𝐏',
            'Q': '𝐐', 'R': '𝐑', 'S': '𝐒', 'T': '𝐓', 'U': '𝐔', 'V': '𝐕', 'W': '𝐖', 'X': '𝐗',
            'Y': '𝐘', 'Z': '𝐙',
            'a': '𝐚', 'b': '𝐛', 'c': '𝐜', 'd': '𝐝', 'e': '𝐞', 'f': '𝐟', 'g': '𝐠', 'h': '𝐡',
            'i': '𝐢', 'j': '𝐣', 'k': '𝐤', 'l': '𝐥', 'm': '𝐦', 'n': '𝐧', 'o': '𝐨', 'p': '𝐩',
            'q': '𝐪', 'r': '𝐫', 's': '𝐬', 't': '𝐭', 'u': '𝐮', 'v': '𝐯', 'w': '𝐰', 'x': '𝐱',
            'y': '𝐲', 'z': '𝐳',
            '0': '𝟎', '1': '𝟏', '2': '𝟐', '3': '𝟑', '4': '𝟒', '5': '𝟓', '6': '𝟔', '7': '𝟕',
            '8': '𝟖', '9': '𝟗',
        }
        result = []
        for char in text:
            result.append(bold_chars.get(char, char))
        return ''.join(result)

    def send_card_via_webhook(self, card_data: Dict) -> bool:
        """通过webhook发送卡片消息(interactive类型)"""

        webhook_url = self._get_feishu_config().get("webhook_url")
        if not webhook_url:
            logger.warning("飞书webhook_url未配置")
            return False

        # 使用 interactive（卡片）消息类型支持富文本
        data = {
            "msg_type": "interactive",
            "card": card_data
        }

        try:
            response = requests.post(webhook_url, json=data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("StatusCode") == 0 or result.get("code") == 0:
                    logger.info("飞书卡片消息发送成功")
                    return True
                else:
                    logger.error(f"飞书发送失败: {result}")
        except Exception as e:
            logger.error(f"飞书webhook发送异常: {e}")

        return False

    def _parse_markdown_to_bold(self, content: str) -> str:
        """将 Markdown **文本** 转换为粗体 Unicode 字符"""
        import re
        # 匹配 **文本** 格式
        pattern = r'\*\*(.*?)\*\*'

        def replace_bold(match):
            text = match.group(1)
            # 如果文本已经包含【】，直接返回原样（已经是强调格式）
            if text.startswith('【') and text.endswith('】'):
                return text
            # 如果包含中文，使用【】强调
            has_chinese = any('\u4e00' <= c <= '\u9fff' for c in text)
            if has_chinese:
                return f"【{text}】"
            else:
                # 纯英文数字，使用数学粗体
                return self._to_bold_text(text)

        return re.sub(pattern, replace_bold, content)

    def send_via_api(self, content: str, receive_type: str = "chat_id") -> bool:
        """通过飞书API发送消息"""

        token = self._get_access_token()
        if not token:
            logger.warning("无法获取飞书access_token")
            return False

        receive_id = self._get_feishu_config().get("receive_id")
        if not receive_id:
            logger.warning("飞书receive_id未配置")
            return False

        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        params = {
            "receive_id_type": receive_type,  # open_id, user_id, chat_id, email
        }
        data = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": content}),
        }

        try:
            response = requests.post(url, headers=headers, params=params, json=data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    logger.info("飞书API消息发送成功")
                    return True
                else:
                    logger.error(f"飞书API发送失败: {result}")
        except Exception as e:
            logger.error(f"飞书API发送异常: {e}")

        return False

    def send_message(self, content: str) -> bool:
        """发送消息（自动选择webhook或API）"""

        # 优先使用webhook
        if self._get_feishu_config().get("webhook_url"):
            return self.send_via_webhook(content)

        # 其次使用API
        if self._get_feishu_config().get("app_id") and self._get_feishu_config().get("receive_id"):
            return self.send_via_api(content)

        logger.warning("飞书未配置，请设置webhook_url或app_id+receive_id")
        return False

    def format_records_message(self, records: List[Dict]) -> str:
        """
        格式化记录列表为飞书消息

        每条消息最多10个项目，开头说明类型和数量
        飞书加粗语法: **文本**
        """

        lines = []
        lines.append("**【招标信息提取汇总】**")
        lines.append(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"本次共 {len(records)} 条项目")
        lines.append("=" * 40)

        # 按类型分组统计
        type_count = {}
        for r in records:
            t = r.get('info_type', '未知')
            type_count[t] = type_count.get(t, 0) + 1

        lines.append("类型分布:")
        for t, c in type_count.items():
            lines.append(f"  {t}: {c}条")
        lines.append("")

        for i, record in enumerate(records, 1):
            info_type = record.get('info_type', '')
            title = record.get('title', '')
            link = record.get('link', '')
            publish_time = record.get('publish_time', '')

            # 解析提取数据
            try:
                extracted = json.loads(record.get('extracted_data', '{}'))
            except:
                extracted = {}

            # 项目类型标题（加粗）
            lines.append(f"**【{i}.{info_type}】{title}**")

            # 根据类型显示提取字段
            if info_type == "招标计划":
                self._format_zhaobiao_jihua(lines, extracted)
            elif info_type == "招标公告":
                self._format_zhaobiao_gonggao(lines, extracted)
            elif info_type == "中标候选人公示":
                self._format_zhongbiao(lines, extracted)
            else:
                # 通用格式
                for key, value in extracted.items():
                    if value and value not in ["未提供", "无"]:
                        lines.append(f"  **{key}**: {value}")

            # 发布日期和原始链接（精确到秒）
            pub_date = extracted.get('发布日期', '') or publish_time if publish_time else '无'
            orig_link = extracted.get('原始链接', '') or link

            lines.append(f"  **发布日期**: {pub_date if pub_date else '无'}")
            lines.append(f"  **原始链接**: {orig_link if orig_link else '无'}")
            lines.append("")

        return "\n".join(lines)

    def _format_zhaobiao_jihua(self, lines: List[str], data: Dict):
        """格式化招标计划 - 属性名加粗"""

        fields = [
            ("建设单位", "建设单位"),
            ("项目类型", "项目类型"),
            ("项目概况", "项目概况"),
            ("招标方式", "招标方式"),
            ("投资额", "投资额"),
            ("资金来源", "资金来源"),
            ("预计招标时间", "预计招标时间"),
            ("拟交易场所", "拟交易场所"),
        ]

        for label, key in fields:
            value = data.get(key, "")
            if value and value not in ["未提供", "无", ""]:
                # 项目概况精简
                if key == "项目概况" and len(value) > 50:
                    value = value[:50] + "..."
                lines.append(f"  **{label}**: {value}")

    def _format_zhaobiao_gonggao(self, lines: List[str], data: Dict):
        """格式化招标公告 - 属性名加粗"""

        fields = [
            ("招标人", "招标人"),
            ("工程地点", "工程地点"),
            ("工程类别", "工程类别"),
            ("建筑面积", "建筑面积"),
            ("项目总投资", "项目总投资"),
            ("招标范围", "招标范围"),
            ("资质要求", "资质要求"),
            ("业绩要求", "业绩要求"),
            ("项目经理要求", "项目经理要求"),
            ("招标文件获取", "招标文件获取"),
            ("招标方式", "招标方式"),
            ("特殊要求", "特殊要求"),
            ("联系方式", "联系方式"),
        ]

        for label, key in fields:
            value = data.get(key, "")
            if value and value not in ["未提供", "无", ""]:
                # 长字段精简
                if key in ["招标范围", "资质要求", "业绩要求", "特殊要求"] and len(value) > 30:
                    value = value[:30] + "..."
                lines.append(f"  **{label}**: {value}")

    def _format_zhongbiao(self, lines: List[str], data: Dict):
        """格式化中标候选人公示 - 属性名加粗"""

        fields = [
            ("招标人", "招标人"),
            ("工程地点", "工程地点"),
            ("工程类别", "工程类别"),
            ("最高限价", "最高限价"),
            ("工期", "工期"),
        ]

        for label, key in fields:
            value = data.get(key, "")
            if value and value not in ["未提供", "无", ""]:
                lines.append(f"  **{label}**: {value}")

        # 中标候选人
        candidates = data.get("中标候选人", [])
        if candidates:
            lines.append("  **中标候选人**:")
            for idx, candidate in enumerate(candidates, 1):
                name = candidate.get("名称", "无")
                price = candidate.get("报价", "无")
                if name and name not in ["未提供", "无"]:
                    lines.append(f"    第{idx}名: {name} | 报价: {price}")

    def send_batch(self, batch_size: int = 10) -> int:
        """
        发送一批记录到飞书（使用卡片格式支持加粗和大字体）

        Args:
            batch_size: 每批发送数量

        Returns:
            发送的记录数
        """

        # 获取待发送记录
        records = self.storage.get_records_for_feishu(batch_size)

        if not records:
            logger.info("没有待发送飞书的记录")
            return 0

        # 格式化为卡片消息
        card_content = self.format_records_to_card(records)

        # 发送卡片消息
        if self.send_card_via_webhook(card_content):
            # 标记已发送
            record_ids = [r['id'] for r in records]
            self.storage.mark_as_sent_to_feishu(record_ids)
            logger.info(f"成功发送 {len(records)} 条记录到飞书")
            return len(records)

        return 0


def configure_feishu(webhook_url: str = "", app_id: str = "",
                     app_secret: str = "", receive_id: str = ""):
    """配置飞书 - 更新config.json文件"""

    import json
    config = get_feishu_config()
    if webhook_url:
        config["webhook_url"] = webhook_url
    if app_id:
        config["app_id"] = app_id
    if app_secret:
        config["app_secret"] = app_secret
    if receive_id:
        config["receive_id"] = receive_id

    logger.info("飞书配置完成（已更新config.json）")


def test_feishu():
    """测试飞书发送"""

    print("请先配置飞书，使用 configure_feishu() 函数")
    print("示例:")
    print("  # 使用webhook方式（推荐）")
    print("  configure_feishu(webhook_url='https://open.feishu.cn/open-apis/bot/v2/hook/xxx')")
    print("")
    print("  # 使用API方式")
    print("  configure_feishu(app_id='cli_xxx', app_secret='xxx', receive_id='oc_xxx')")


if __name__ == "__main__":
    test_feishu()