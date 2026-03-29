"""
主流程模块 - 整合抓取、详情、提取、发送流程
"""

import logging
import argparse
from datetime import datetime

from scraper import JiangxiBidScraper
from detail_scraper import DetailScraper
from extractor import AIExtractor
from feishu_sender import FeishuSender
from storage import BidStorage
from config import (
    MONITOR_INFO_TYPES,
    REQUEST_DELAY,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/workflow.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)


class WorkflowRunner:
    """流程执行器"""

    def __init__(self):
        self.storage = BidStorage()
        self.scraper = JiangxiBidScraper()
        self.detail_scraper = DetailScraper()
        self.extractor = AIExtractor(self.storage)
        self.feishu_sender = FeishuSender(self.storage)

    def step1_scrape_list(self) -> int:
        """步骤1: 抓取列表页"""

        logger.info("=" * 50)
        logger.info("【步骤1】抓取招标信息列表 - 开始")
        logger.info("=" * 50)

        total_new = 0
        for info_type in MONITOR_INFO_TYPES:
            logger.info(f"抓取类型: {info_type}")
            result = self.scraper.fetch_by_info_type(info_type, page_num=0, page_size=10)
            records = result.get("records", [])
            if records:
                new_count = self.storage.save_records(records)
                total_new += new_count

        logger.info("-" * 50)
        logger.info(f"【步骤1】抓取招标信息列表 - 完成，新增 {total_new} 条记录")
        logger.info("=" * 50)
        return total_new

    def step2_fetch_details(self) -> int:
        """步骤2: 抓取详情页"""

        logger.info("=" * 50)
        logger.info("【步骤2】抓取详情页 - 开始")
        logger.info("=" * 50)

        # 获取需要抓取详情的记录
        records = self.storage.get_records_without_detail(limit=50)

        if not records:
            logger.info("没有需要抓取详情的记录")
            logger.info("-" * 50)
            logger.info("【步骤2】抓取详情页 - 完成，无待处理记录")
            logger.info("=" * 50)
            return 0

        logger.info(f"需要抓取详情: {len(records)} 条")

        # 批量抓取详情
        details = self.detail_scraper.fetch_batch(records, delay=REQUEST_DELAY)

        # 保存详情
        import json
        for detail in details:
            record_id = detail.get('record_id')
            detail_json = detail.copy()
            del detail_json['record_id']  # 移除record_id字段
            self.storage.update_detail(record_id, json.dumps(detail_json, ensure_ascii=False))

        logger.info("-" * 50)
        logger.info(f"【步骤2】抓取详情页 - 完成，成功 {len(details)} 条")
        logger.info("=" * 50)
        return len(details)

    def step3_extract_data(self, batch_size: int = 10) -> int:
        """步骤3: AI提取数据"""

        logger.info("=" * 50)
        logger.info("【步骤3】AI提取结构化数据 - 开始")
        logger.info("=" * 50)

        success_count = self.extractor.run_extraction(batch_size)
        logger.info("-" * 50)
        logger.info(f"【步骤3】AI提取结构化数据 - 完成，成功 {success_count} 条")
        logger.info("=" * 50)
        return success_count

    def step4_send_to_feishu(self, batch_size: int = 10) -> int:
        """步骤4: 发送到飞书"""

        logger.info("=" * 50)
        logger.info("【步骤4】发送提取数据到飞书 - 开始")
        logger.info("=" * 50)

        sent_count = self.feishu_sender.send_batch(batch_size)
        logger.info("-" * 50)
        logger.info(f"【步骤4】发送提取数据到飞书 - 完成，发送 {sent_count} 条")
        logger.info("=" * 50)
        return sent_count

    def run_full_workflow(self, skip_scrape: bool = False):
        """运行完整流程"""

        logger.info("\n" + "=" * 60)
        logger.info(f"调度任务开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        # 步骤1: 抓取列表
        if not skip_scrape:
            self.step1_scrape_list()

        # 步骤2: 抓取详情
        self.step2_fetch_details()

        # 步骤3: AI提取
        self.step3_extract_data(batch_size=10)

        # 步骤4: 发送飞书（每10条一批）
        self.step4_send_to_feishu(batch_size=10)

        # 显示统计
        self.show_stats()

        logger.info("=" * 60)
        logger.info(f"调度任务结束 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

    def run_continuous(self):
        """连续运行 - 直到所有数据处理完成"""

        logger.info("开始连续处理流程...")

        while True:
            # 检查是否有待处理数据
            stats = self.storage.get_extraction_stats()

            pending_detail = stats.get('without_detail', 0)
            pending_extraction = stats.get('pending_extraction', 0)
            pending_send = stats.get('pending_send', 0)

            if pending_detail == 0 and pending_extraction == 0 and pending_send == 0:
                logger.info("所有数据处理完成，退出")
                break

            logger.info(f"待处理: 详情={pending_detail}, 提取={pending_extraction}, 发送={pending_send}")

            # 依次处理
            if pending_detail > 0:
                self.step2_fetch_details()

            if pending_extraction > 0:
                self.step3_extract_data()

            if pending_send > 0:
                self.step4_send_to_feishu()

    def show_stats(self):
        """显示统计信息"""

        stats = self.storage.get_statistics()
        extraction_stats = self.storage.get_extraction_stats()
        detail_stats = self.storage.get_detail_stats()

        logger.info("\n【数据统计】")
        logger.info(f"  总记录数: {stats['total']}")
        logger.info(f"  今日新增: {stats['today_new']}")
        logger.info(f"  详情已抓: {detail_stats['with_detail']}")
        logger.info(f"  AI已提取: {extraction_stats['extracted']}")
        logger.info(f"  已发飞书: {extraction_stats['sent_to_feishu']}")

        logger.info("\n【按类型统计】")
        for t, cnt in stats['by_type'].items():
            logger.info(f"  {t}: {cnt} 条")


def main():
    """主函数"""

    parser = argparse.ArgumentParser(description="招标信息监控流程")
    parser.add_argument("--step", type=int, help="只执行指定步骤(1-4)")
    parser.add_argument("--full", action="store_true", help="运行完整流程")
    parser.add_argument("--continuous", action="store_true", help="连续运行直到处理完成")
    parser.add_argument("--stats", action="store_true", help="只显示统计信息")
    parser.add_argument("--skip-scrape", action="store_true", help="跳过列表抓取")
    parser.add_argument("--batch", type=int, default=10, help="批量处理数量")

    args = parser.parse_args()

    runner = WorkflowRunner()

    if args.stats:
        runner.show_stats()
    elif args.full:
        runner.run_full_workflow(skip_scrape=args.skip_scrape)
    elif args.continuous:
        runner.run_continuous()
    elif args.step:
        if args.step == 1:
            runner.step1_scrape_list()
        elif args.step == 2:
            runner.step2_fetch_details()
        elif args.step == 3:
            runner.step3_extract_data(args.batch)
        elif args.step == 4:
            runner.step4_send_to_feishu(args.batch)
        runner.show_stats()
    else:
        # 默认运行完整流程
        runner.run_full_workflow()


if __name__ == "__main__":
    main()