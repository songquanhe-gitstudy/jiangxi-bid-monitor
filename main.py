"""
江西公共资源交易平台招标信息监控系统
主入口文件

功能:
1. 定时抓取房建及市政工程的招标计划、招标公告、中标候选人公示信息
2. 抓取详情页面内容
3. AI提取结构化数据
4. 每10条批量发送飞书

使用方式:
- 直接运行: python main.py (启动定时监控)
- 单次流程: python main.py --once
- 连续处理: python main.py --continuous
- 查看统计: python main.py --stats
"""

import argparse
import logging
import os
import sys

# 配置日志
def setup_logging():
    """配置日志系统"""

    # 确保日志目录存在
    log_dir = os.path.dirname("logs/monitor.log")
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("logs/monitor.log", encoding="utf-8"),
        ]
    )


def run_once():
    """单次完整流程"""

    from workflow import WorkflowRunner

    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("执行单次完整流程")
    logger.info("=" * 60)

    runner = WorkflowRunner()
    runner.run_full_workflow()


def run_continuous():
    """连续处理直到完成"""

    from workflow import WorkflowRunner

    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("开始连续处理流程")
    logger.info("=" * 60)

    runner = WorkflowRunner()
    runner.run_continuous()


def run_stats():
    """显示统计信息"""

    from storage import BidStorage

    storage = BidStorage()
    stats = storage.get_statistics()
    extraction_stats = storage.get_extraction_stats()
    detail_stats = storage.get_detail_stats()

    print("\n" + "=" * 80)
    print("江西招标信息监控系统 - 统计信息")
    print("=" * 80)

    print(f"\n📊 总记录数: {stats['total']}")
    print(f"📅 今日新增: {stats['today_new']}")
    print(f"🕐 最后更新: {stats['last_update']}")

    print("\n📋 处理进度:")
    print(f"   详情已抓: {detail_stats['with_detail']}/{stats['total']}")
    print(f"   AI已提取: {extraction_stats['extracted']}/{detail_stats['with_detail']}")
    print(f"   已发飞书: {extraction_stats['sent_to_feishu']}/{extraction_stats['extracted']}")

    print("\n📋 各类型记录数:")
    for info_type, count in stats.get("by_type", {}).items():
        type_detail = detail_stats['by_type'].get(info_type, {})
        extracted = type_detail.get('with_detail', 0)
        print(f"   • {info_type}: {count} 条 (详情: {extracted})")

    print("\n📍各地区记录数 (前10):")
    for region, count in stats.get("by_region", {}).items():
        print(f"   • {region}: {count}")

    print("\n" + "=" * 80)


def run_monitor():
    """启动定时监控"""

    from scheduler import BidMonitorScheduler

    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("启动江西招标信息监控系统")
    logger.info("=" * 60)
    logger.info(f"监控行业: 房建及市政工程")
    logger.info(f"监控类型: 招标计划、招标公告、中标候选人公示")
    logger.info(f"运行时间: 每天 8:00 - 23:00")
    logger.info(f"流程步骤: 抓取列表 → 抓取详情 → AI提取 → 发送飞书")

    monitor = BidMonitorScheduler()

    import signal
    def handle_exit(signum, frame):
        logger.info("收到退出信号，正在停止...")
        monitor.stop()
        exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    try:
        monitor.start()

        # 保持运行
        import time
        while monitor.is_running:
            time.sleep(60)

    except KeyboardInterrupt:
        logger.info("收到停止信号，正在退出...")
        monitor.stop()
        logger.info("系统已停止")


def test_feishu():
    """测试飞书通知"""

    from feishu_sender import FeishuSender, FEISHU_CONFIG
    from datetime import datetime

    sender = FeishuSender()

    if not (FEISHU_CONFIG.get("webhook_url") or
            (FEISHU_CONFIG.get("app_id") and FEISHU_CONFIG.get("receive_id"))):
        print("\n⚠️ 飞书通知未配置!")
        print("\n请编辑 feishu_sender.py，设置以下配置项之一:")
        print("1. FEISHU_CONFIG['webhook_url'] = 'your_webhook_url'")
        print("   → 用于群机器人，获取方式: 群设置 → 群机器人 → 添加机器人")
        print("")
        print("2. FEISHU_CONFIG['app_id'] = 'your_app_id'")
        print("   FEISHU_CONFIG['app_secret'] = 'your_app_secret'")
        print("   FEISHU_CONFIG['receive_id'] = 'chat_id/open_id/user_id'")
        print("   → 用于飞书应用")
        return False

    # 发送测试消息
    print("\n正在发送测试消息...")
    test_content = f"【测试消息】\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n飞书通知配置成功！"

    result = sender.send_message(test_content)

    if result:
        print("✅ 测试消息已发送，请检查飞书是否收到")
    else:
        print("❌ 发送失败，请检查配置")

    return result


def test_ai():
    """测试AI配置"""

    from extractor import AIExtractor, AI_CONFIG

    if not AI_CONFIG.get("api_url") or not AI_CONFIG.get("api_key"):
        print("\n⚠️ AI API未配置!")
        print("\n请编辑 extractor.py，设置以下配置:")
        print("AI_CONFIG = {")
        print("    'api_type': 'openai',  # 或 claude, custom")
        print("    'api_url': 'https://api.xxx.com/v1/chat/completions',")
        print("    'api_key': 'your-api-key',")
        print("    'model': 'gpt-3.5-turbo',")
        print("}")
        return False

    print("\n✅ AI配置已设置:")
    print(f"   API类型: {AI_CONFIG.get('api_type')}")
    print(f"   API地址: {AI_CONFIG.get('api_url')}")
    print(f"   模型: {AI_CONFIG.get('model')}")

    return True


def main():
    """主入口"""

    setup_logging()

    parser = argparse.ArgumentParser(
        description="江西公共资源交易平台招标信息监控系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py              # 启动定时监控（8:00-23:00每小时执行）
  python main.py --once       # 单次执行完整流程
  python main.py --continuous # 连续处理直到完成
  python main.py --stats      # 显示统计信息
  python main.py --test-feishu # 测试飞书通知配置
  python main.py --test-ai    # 测试AI配置
        """
    )

    parser.add_argument("--once", action="store_true", help="执行单次完整流程")
    parser.add_argument("--continuous", action="store_true", help="连续处理直到完成")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")
    parser.add_argument("--test-feishu", action="store_true", help="测试飞书通知")
    parser.add_argument("--test-ai", action="store_true", help="测试AI配置")

    args = parser.parse_args()

    if args.once:
        run_once()
    elif args.continuous:
        run_continuous()
    elif args.stats:
        run_stats()
    elif args.test_feishu:
        test_feishu()
    elif args.test_ai:
        test_ai()
    else:
        run_monitor()


if __name__ == "__main__":
    main()