"""
定时调度模块
使用APScheduler实现定时抓取、详情、提取、发送完整流程
"""

import logging
from datetime import datetime
from typing import Optional
import time
import signal

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logging.warning("APScheduler未安装，定时功能不可用")

from config import get_schedule_config
from workflow import WorkflowRunner

logger = logging.getLogger(__name__)


class BidMonitorScheduler:
    """招标信息监控调度器"""

    def __init__(self):
        self.runner = WorkflowRunner()

        if APSCHEDULER_AVAILABLE:
            self.scheduler = BackgroundScheduler()
        else:
            self.scheduler = None

        self.is_running = False

    def run_full_workflow(self, skip_scrape: bool = False):
        """执行完整流程"""

        logger.info(f"开始执行监控流程 - {'跳过列表抓取' if skip_scrape else '完整流程'}")

        try:
            self.runner.run_full_workflow(skip_scrape=skip_scrape)
        except Exception as e:
            logger.error(f"流程执行失败: {e}", exc_info=True)

        logger.info("监控流程完成")

    def setup_schedule(self):
        """设置定时任务"""

        if not APSCHEDULER_AVAILABLE:
            logger.error("APScheduler未安装，无法设置定时任务")
            return False

        start_hour = get_schedule_config()["start_hour"]
        end_hour = get_schedule_config()["end_hour"]
        interval_hours = get_schedule_config().get("interval_hours", 1)

        # 每天start_hour点执行首次完整流程
        trigger_full = CronTrigger(hour=start_hour, minute=0)
        self.scheduler.add_job(
            self.run_full_workflow,
            trigger=trigger_full,
            kwargs={"skip_scrape": False},
            id="full_workflow_job",
            name="每日首次流程",
        )
        logger.info(f"已设置首次流程任务: 每天 {start_hour}:00")

        # 后续定时任务：每次都执行完整流程（包括列表抓取）
        # 去重由storage模块保证，不会重复保存已存在的记录
        next_hour = start_hour + interval_hours
        while next_hour <= end_hour:
            trigger_incremental = CronTrigger(hour=next_hour, minute=5)
            self.scheduler.add_job(
                self.run_full_workflow,
                trigger=trigger_incremental,
                kwargs={"skip_scrape": False},  # 改为不跳过，每次都抓取列表
                id=f"workflow_{next_hour}",
                name=f"定时流程-{next_hour}点",
            )
            logger.info(f"已设置定时流程任务: 每天 {next_hour}:05")
            next_hour += interval_hours

        logger.info(f"调度配置: 每天 {start_hour}:00 开始, 每 {interval_hours} 小时执行一次, 直到 {end_hour}:00")

        return True

    def start(self, run_startup_task: bool = None):
        """启动调度器

        Args:
            run_startup_task: 是否在启动时执行一次完整流程任务
                              None 时从配置文件读取
        """

        if not APSCHEDULER_AVAILABLE:
            logger.error("APScheduler未安装，使用简单轮询模式")
            self._start_simple_mode(run_startup_task=run_startup_task)
            return

        if self.setup_schedule():
            self.scheduler.start()
            self.is_running = True
            logger.info("调度器已启动")

            # 从配置读取是否执行启动任务
            if run_startup_task is None:
                run_startup_task = get_schedule_config().get("startup_task", True)

            # 服务重启时执行一次完整流程任务（包含列表抓取）
            if run_startup_task:
                logger.info("执行启动时完整流程任务...")
                self.run_full_workflow(skip_scrape=False)
        else:
            logger.error("调度器启动失败")

    def stop(self):
        """停止调度器"""

        if self.scheduler and self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("调度器已停止")

    def _start_simple_mode(self, run_startup_task: bool = None):
        """简单轮询模式（当APScheduler不可用时）

        Args:
            run_startup_task: 是否在启动时执行一次完整流程任务
                              None 时从配置文件读取
        """

        logger.warning("使用简单轮询模式运行")

        # 从配置读取是否执行启动任务
        if run_startup_task is None:
            run_startup_task = get_schedule_config().get("startup_task", True)

        # 服务启动时执行一次完整流程任务（包含列表抓取）
        if run_startup_task:
            logger.info("执行启动时完整流程任务...")
            self.run_full_workflow(skip_scrape=False)

        while True:
            now = datetime.now()
            current_hour = now.hour

            # 检查是否在工作时间范围内
            if current_hour < get_schedule_config()["start_hour"]:
                # 早于8点，等待
                wait_seconds = (get_schedule_config()["start_hour"] - current_hour) * 3600 - now.minute * 60
                logger.info(f"等待到早上{get_schedule_config()['start_hour']}点，还需等待{wait_seconds}秒")
                time.sleep(wait_seconds)
                continue

            if current_hour > get_schedule_config()["end_hour"]:
                # 晚于23点，等待到次日早上
                wait_seconds = (24 - current_hour + get_schedule_config()["start_hour"]) * 3600
                logger.info(f"今日任务结束，等待到次日早上{get_schedule_config()['start_hour']}点")
                time.sleep(wait_seconds)
                continue

            # 执行流程（每次都执行完整流程，去重由storage模块保证）
            self.run_full_workflow(skip_scrape=False)

            # 等待下一次
            time.sleep(get_schedule_config()["interval_hours"] * 3600)


def run_scheduler(run_startup_task: bool = True):
    """运行调度器

    Args:
        run_startup_task: 是否在启动时执行一次增量流程任务
    """

    monitor = BidMonitorScheduler()

    def handle_exit(signum, frame):
        logger.info("收到退出信号，停止调度器...")
        monitor.stop()
        exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    try:
        monitor.start(run_startup_task=run_startup_task)

        # 保持运行
        while monitor.is_running:
            time.sleep(60)

    except KeyboardInterrupt:
        logger.info("收到停止信号")
        monitor.stop()


if __name__ == "__main__":
    import argparse

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    parser = argparse.ArgumentParser(description="招标监控调度器")
    parser.add_argument("--daemon", action="store_true", help="作为守护进程运行")
    parser.add_argument("--once", action="store_true", help="单次运行完整流程")
    parser.add_argument("--test", action="store_true", help="测试模式，显示任务配置")

    args = parser.parse_args()

    scheduler = BidMonitorScheduler()

    if args.test:
        scheduler.setup_schedule()
        if scheduler.scheduler:
            jobs = scheduler.scheduler.get_jobs()
            logger.info("\n任务配置:")
            for job in jobs:
                next_run = job.next_run_time
                if next_run:
                    logger.info(f"  {job.name}: {next_run.strftime('%Y-%m-%d %H:%M')}")
    elif args.once:
        scheduler.run_full_workflow(skip_scrape=False)
    elif args.daemon:
        run_scheduler(run_startup_task=None)  # 从配置读取是否执行启动任务
    else:
        parser.print_help()
        interval = get_schedule_config().get("interval_hours", 1)
        startup_task = get_schedule_config().get("startup_task", True)
        print(f"\n使用说明:")
        print(f"  --daemon   作为后台守护进程运行（{get_schedule_config()['start_hour']:02d}:00-{get_schedule_config()['end_hour']:02d}:00 每{interval}小时执行）")
        print("  --once     单次执行完整监控流程")
        print("  --test     测试模式，显示任务配置")
        print(f"\n提示: 守护进程启动时会{'执行' if startup_task else '不执行'}一次完整流程任务（可在config.json中配置startup_task）")