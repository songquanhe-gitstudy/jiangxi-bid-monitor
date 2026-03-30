"""
AI数据提取模块 - 批量从详情文本中提取结构化信息
"""

import json
import os
import requests
import logging
from typing import Dict, Optional, List
from datetime import datetime

from config import get_ai_config, PROMPT_FILES

logger = logging.getLogger(__name__)


class AIExtractor:
    """AI数据提取器 - 支持批量提取"""

    def __init__(self, storage=None):
        self.storage = storage
        self._load_prompts()

    def _get_ai_config(self) -> dict:
        """动态获取AI配置"""
        return get_ai_config()

    @property
    def timeout(self) -> int:
        """动态获取超时配置"""
        return self._get_ai_config().get("timeout", 180)

    @property
    def max_records(self) -> int:
        """动态获取批量大小配置"""
        return self._get_ai_config().get("max_records_per_request", 10)

    def _load_prompts(self):
        """加载所有提示词模板"""
        self.prompts = {}

        for info_type, filepath in PROMPT_FILES.items():
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    self.prompts[info_type] = f.read()
                logger.info(f"加载提示词: {info_type}")
            else:
                logger.warning(f"提示词文件不存在: {filepath}")

    def get_prompt(self, info_type: str) -> Optional[str]:
        """获取指定类型的提示词"""
        return self.prompts.get(info_type)

    def extract_batch(self, records: List[Dict]) -> List[Dict]:
        """
        批量提取多条记录的结构化数据（一次API调用）

        Args:
            records: 记录列表，每条包含 {id, info_type, detail_json, link, publish_time, title}

        Returns:
            提取结果列表，每条包含 {id, info_type, data}
        """
        if not records:
            return []

        # 按类型分组
        by_type = {}
        for r in records:
            t = r.get('info_type')
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(r)

        results = []

        # 按类型批量提取
        for info_type, type_records in by_type.items():
            logger.info(f"批量提取 {info_type}: {len(type_records)} 条")

            # 构建批量文本（包含发布日期和链接）
            texts = []
            for i, r in enumerate(type_records, 1):
                try:
                    detail = json.loads(r.get('detail_json', '{}'))
                    text = detail.get('text', '').strip()
                    link = r.get('link', '')
                    publish_time = r.get('publish_time', '')
                    title = r.get('title', '')

                    if text:
                        # 在文本开头添加元信息
                        meta_info = f"项目标题: {title}"
                        if publish_time:
                            meta_info += f"\n发布日期: {publish_time[:10] if len(publish_time) >= 10 else publish_time}"
                        if link:
                            meta_info += f"\n原始链接: {link}"

                        texts.append(f"【项目{i}】\n{meta_info}\n\n{text}")
                except Exception as e:
                    logger.warning(f"构建文本失败: {e}")

            if not texts:
                continue

            # 合并文本，用分隔线分开
            combined_text = "\n\n===项目分隔线===\n\n".join(texts)

            # 调用AI提取
            extracted_list = self._call_ai_batch(combined_text, info_type)

            if extracted_list and isinstance(extracted_list, list):
                # 匹配结果
                for i, data in enumerate(extracted_list):
                    if i < len(type_records):
                        # 移除序号字段
                        clean_data = {k: v for k, v in data.items() if k != '序号'}

                        # 如果AI没有提取到发布日期和链接，使用原始数据
                        if not clean_data.get('发布日期') or clean_data.get('发布日期') == '无':
                            clean_data['发布日期'] = type_records[i].get('publish_time', '')[:10] if type_records[i].get('publish_time') else '无'
                        if not clean_data.get('原始链接') or clean_data.get('原始链接') == '无':
                            clean_data['原始链接'] = type_records[i].get('link', '无')

                        results.append({
                            'id': type_records[i].get('id'),
                            'info_type': info_type,
                            'data': clean_data
                        })
            else:
                logger.warning(f"批量提取失败: {info_type}")

        return results

    def _call_ai_batch(self, text: str, info_type: str) -> Optional[List]:
        """调用AI API批量提取"""

        prompt_template = self.get_prompt(info_type)
        if not prompt_template:
            logger.error(f"未找到提示词模板: {info_type}")
            return None

        prompt = prompt_template.replace("{text}", text)

        # 动态获取AI配置
        ai_config = self._get_ai_config()
        if not ai_config.get("api_url") or not ai_config.get("api_key"):
            logger.warning("AI API未配置")
            return None

        try:
            headers = {
                "Authorization": f"Bearer {ai_config['api_key']}",
                "Content-Type": "application/json",
            }
            data = {
                "model": ai_config.get("model", "qwen3.5-plus"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            }

            response = requests.post(
                ai_config["api_url"],
                headers=headers,
                json=data,
                timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return self._parse_json_array(content)
            else:
                logger.error(f"API错误: {response.status_code} - {response.text[:200]}")

        except requests.exceptions.Timeout:
            logger.error(f"AI API请求超时 ({self.timeout}秒)")
        except Exception as e:
            logger.error(f"AI API调用异常: {e}")

        return None

    def _parse_json_array(self, result: str) -> Optional[List]:
        """解析AI返回的JSON数组"""

        # 尝试直接解析
        try:
            data = json.loads(result)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

        # 尝试提取JSON数组
        import re
        json_match = re.search(r'\[[\s\S]*\]', result)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        logger.error(f"无法解析JSON数组: {result[:200]}...")
        return None

    def run_extraction(self, batch_size: int = 10) -> int:
        """
        执行提取任务

        Args:
            batch_size: 每批处理的记录数

        Returns:
            成功提取的记录数
        """
        if not self.storage:
            logger.error("未设置storage")
            return 0

        # 获取待提取记录
        records = self.storage.get_records_for_extraction(limit=batch_size)

        if not records:
            logger.info("没有待提取的记录")
            return 0

        logger.info(f"开始批量提取 {len(records)} 条记录")

        # 批量提取
        results = self.extract_batch(records)

        # 保存结果
        success_count = 0
        for r in results:
            if self.storage.update_extracted_data(r['id'], r['data']):
                success_count += 1

        logger.info(f"批量提取完成，成功 {success_count}/{len(records)} 条")
        return success_count


if __name__ == "__main__":
    # 测试配置加载
    ai_config = get_ai_config()
    print("AI配置:")
    print(f"  API URL: {ai_config.get('api_url', '未配置')}")
    print(f"  Model: {ai_config.get('model', '未配置')}")
    print(f"  Timeout: {ai_config.get('timeout', 60)}秒")
    print(f"  每批最大记录: {ai_config.get('max_records_per_request', 10)}条")