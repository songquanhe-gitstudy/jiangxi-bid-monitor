"""
数据存储模块
使用SQLite存储数据，使用JSON文件快速检查已抓取记录
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Set, Optional
import logging

from config import get_database_config

logger = logging.getLogger(__name__)


class BidStorage:
    """招标信息存储管理"""

    def __init__(self):
        # 动态获取数据库配置
        db_config = get_database_config()
        self.database_path = db_config.get("path", "data/bid_info.db")
        self.records_json_path = db_config.get("records_json_path", "data/records.json")

        # 确保数据目录存在
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.records_json_path), exist_ok=True)

        # 初始化数据库
        self._init_database()
        # 加载已抓取记录ID集合（用于快速去重）
        self._load_existing_ids()

    def _init_database(self):
        """初始化SQLite数据库"""

        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bid_records (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                link TEXT,
                publish_time TEXT,
                info_type TEXT,
                region TEXT,
                region_code TEXT,
                bid_type TEXT,
                content TEXT,
                detail_json TEXT,
                detail_fetch_time TEXT,
                extracted_data TEXT,
                extracted_time TEXT,
                sent_to_feishu INTEGER DEFAULT 0,
                fetch_time TEXT,
                notified INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_info_type ON bid_records(info_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_publish_time ON bid_records(publish_time)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_region ON bid_records(region)
        """)

        # 数据库迁移 - 添加新字段（如果不存在）
        self._migrate_database(cursor)

        conn.commit()
        conn.close()
        logger.info("数据库初始化完成")

    def _migrate_database(self, cursor):
        """数据库迁移 - 添加缺失的列"""

        # 获取现有列
        cursor.execute("PRAGMA table_info(bid_records)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # 需要添加的列
        new_columns = [
            ("extracted_data", "TEXT"),
            ("extracted_time", "TEXT"),
            ("sent_to_feishu", "INTEGER DEFAULT 0"),
        ]

        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                cursor.execute(f"ALTER TABLE bid_records ADD COLUMN {col_name} {col_type}")
                logger.info(f"添加新列: {col_name}")

    def _load_existing_ids(self) -> Set[str]:
        """加载已抓取的记录ID"""

        self.existing_ids: Set[str] = set()

        if os.path.exists(self.records_json_path):
            try:
                with open(self.records_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.existing_ids = set(data.get("ids", []))
                logger.info(f"加载了 {len(self.existing_ids)} 个已存在的记录ID")
            except Exception as e:
                logger.warning(f"加载记录ID文件失败: {e}")

        return self.existing_ids

    def _save_existing_ids(self):
        """保存已抓取的记录ID"""

        try:
            with open(self.records_json_path, "w", encoding="utf-8") as f:
                json.dump({
                    "ids": list(self.existing_ids),
                    "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存记录ID文件失败: {e}")

    def is_new_record(self, record_id: str) -> bool:
        """检查是否为新记录"""

        return record_id not in self.existing_ids

    def save_records(self, records: List[Dict]) -> int:
        """保存记录到数据库"""

        if not records:
            return 0

        new_count = 0
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        for record in records:
            record_id = record.get("id")

            if not record_id or record_id in self.existing_ids:
                continue

            try:
                cursor.execute("""
                    INSERT INTO bid_records (
                        id, title, link, publish_time, info_type,
                        region, region_code, bid_type, content, fetch_time
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record_id,
                    record.get("title", ""),
                    record.get("link", ""),
                    record.get("publish_time", ""),
                    record.get("info_type", ""),
                    record.get("region", ""),
                    record.get("region_code", ""),
                    record.get("bid_type", ""),
                    record.get("content", ""),
                    record.get("fetch_time", ""),
                ))

                self.existing_ids.add(record_id)
                new_count += 1

            except sqlite3.IntegrityError:
                logger.warning(f"记录已存在: {record_id}")
            except Exception as e:
                logger.error(f"保存记录失败: {e}")

        conn.commit()
        conn.close()

        # 更新ID缓存文件
        self._save_existing_ids()

        logger.info(f"保存了 {new_count} 条新记录")
        return new_count

    def get_unnotified_records(self) -> List[Dict]:
        """获取未通知的记录"""

        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, title, link, publish_time, info_type, region, bid_type
            FROM bid_records
            WHERE notified = 0
            ORDER BY publish_time DESC
        """)

        records = []
        for row in cursor.fetchall():
            records.append({
                "id": row[0],
                "title": row[1],
                "link": row[2],
                "publish_time": row[3],
                "info_type": row[4],
                "region": row[5],
                "bid_type": row[6],
            })

        conn.close()
        return records

    def mark_as_notified(self, record_ids: List[str]):
        """标记记录为已通知"""

        if not record_ids:
            return

        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        for record_id in record_ids:
            cursor.execute("UPDATE bid_records SET notified = 1 WHERE id = ?", (record_id,))

        conn.commit()
        conn.close()
        logger.info(f"标记了 {len(record_ids)} 条记录为已通知")

    def get_records_by_type(
        self,
        info_type: Optional[str] = None,
        region: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """查询记录"""

        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM bid_records WHERE 1=1"
        params = []

        if info_type:
            query += " AND info_type = ?"
            params.append(info_type)

        if region:
            query += " AND region LIKE ?"
            params.append(f"%{region}%")

        if start_date:
            query += " AND publish_time >= ?"
            params.append(start_date)

        if end_date:
            query += " AND publish_time <= ?"
            params.append(end_date)

        query += f" ORDER BY publish_time DESC LIMIT {limit}"

        cursor.execute(query, params)

        records = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return records

    def get_statistics(self) -> Dict:
        """获取统计信息"""

        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        # 总记录数
        cursor.execute("SELECT COUNT(*) FROM bid_records")
        total = cursor.fetchone()[0]

        # 各类型记录数
        cursor.execute("""
            SELECT info_type, COUNT(*) as count
            FROM bid_records
            GROUP BY info_type
        """)
        by_type = {row[0]: row[1] for row in cursor.fetchall()}

        # 各地区记录数
        cursor.execute("""
            SELECT region, COUNT(*) as count
            FROM bid_records
            GROUP BY region
            ORDER BY count DESC
            LIMIT 10
        """)
        by_region = {row[0]: row[1] for row in cursor.fetchall()}

        # 今日新增
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("SELECT COUNT(*) FROM bid_records WHERE publish_time LIKE ?", (f"{today}%",))
        today_new = cursor.fetchone()[0]

        conn.close()

        return {
            "total": total,
            "by_type": by_type,
            "by_region": by_region,
            "today_new": today_new,
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def update_detail(self, record_id: str, detail_json: str) -> bool:
        """更新记录的详情数据"""

        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE bid_records
            SET detail_json = ?, detail_fetch_time = ?
            WHERE id = ?
        """, (
            detail_json,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            record_id
        ))

        conn.commit()
        conn.close()
        logger.info(f"更新详情: {record_id}")
        return True

    def get_records_without_detail(self, limit: int = 100) -> List[Dict]:
        """获取没有详情的记录"""

        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, title, link, info_type, publish_time
            FROM bid_records
            WHERE detail_json IS NULL OR detail_json = ''
            LIMIT ?
        """, (limit,))

        records = []
        for row in cursor.fetchall():
            records.append({
                "id": row[0],
                "title": row[1],
                "link": row[2],
                "info_type": row[3],
                "publish_time": row[4],
            })

        conn.close()
        return records

    def get_records_for_extraction(self, limit: int = 100) -> List[Dict]:
        """获取需要AI提取的记录（有详情但未提取）"""

        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, title, link, info_type, publish_time, detail_json
            FROM bid_records
            WHERE detail_json IS NOT NULL AND detail_json != ''
            AND (extracted_data IS NULL OR extracted_data = '')
            LIMIT ?
        """, (limit,))

        records = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return records

    def update_extracted_data(self, record_id: str, extracted_data: Dict) -> bool:
        """更新记录的AI提取数据"""

        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE bid_records
                SET extracted_data = ?, extracted_time = ?
                WHERE id = ?
            """, (
                json.dumps(extracted_data, ensure_ascii=False),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                record_id
            ))

            conn.commit()
            conn.close()
            logger.info(f"更新提取数据: {record_id}")
            return True
        except Exception as e:
            logger.error(f"更新提取数据失败: {e}")
            return False

    def get_records_for_feishu(self, batch_size: int = 10) -> List[Dict]:
        """获取待发送飞书的记录（已提取未发送）"""

        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, title, info_type, publish_time, extracted_data
            FROM bid_records
            WHERE extracted_data IS NOT NULL AND extracted_data != ''
            AND sent_to_feishu = 0
            ORDER BY publish_time DESC
            LIMIT ?
        """, (batch_size,))

        records = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return records

    def mark_as_sent_to_feishu(self, record_ids: List[str]):
        """标记记录为已发送飞书"""

        if not record_ids:
            return

        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        for record_id in record_ids:
            cursor.execute("UPDATE bid_records SET sent_to_feishu = 1 WHERE id = ?", (record_id,))

        conn.commit()
        conn.close()
        logger.info(f"标记 {len(record_ids)} 条记录已发送飞书")

    def get_extraction_stats(self) -> Dict:
        """获取AI提取统计"""

        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        # 有详情的记录数
        cursor.execute("SELECT COUNT(*) FROM bid_records WHERE detail_json IS NOT NULL AND detail_json != ''")
        with_detail = cursor.fetchone()[0]

        # 已提取的记录数
        cursor.execute("SELECT COUNT(*) FROM bid_records WHERE extracted_data IS NOT NULL AND extracted_data != ''")
        extracted = cursor.fetchone()[0]

        # 已发送飞书的记录数
        cursor.execute("SELECT COUNT(*) FROM bid_records WHERE sent_to_feishu = 1")
        sent = cursor.fetchone()[0]

        conn.close()

        return {
            "with_detail": with_detail,
            "extracted": extracted,
            "pending_extraction": with_detail - extracted,
            "sent_to_feishu": sent,
            "pending_send": extracted - sent,
        }

    def get_detail_stats(self) -> Dict:
        """获取详情抓取统计"""

        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        # 总记录数
        cursor.execute("SELECT COUNT(*) FROM bid_records")
        total = cursor.fetchone()[0]

        # 已有详情的记录数
        cursor.execute("SELECT COUNT(*) FROM bid_records WHERE detail_json IS NOT NULL AND detail_json != ''")
        with_detail = cursor.fetchone()[0]

        # 按类型统计
        cursor.execute("""
            SELECT info_type,
                   COUNT(*) as total,
                   SUM(CASE WHEN detail_json IS NOT NULL AND detail_json != '' THEN 1 ELSE 0 END) as with_detail
            FROM bid_records
            GROUP BY info_type
        """)
        by_type = {}
        for row in cursor.fetchall():
            by_type[row[0]] = {"total": row[1], "with_detail": row[2]}

        conn.close()

        return {
            "total": total,
            "with_detail": with_detail,
            "without_detail": total - with_detail,
            "by_type": by_type,
        }


def test_storage():
    """测试存储功能"""

    storage = BidStorage()

    # 测试数据
    test_records = [
        {
            "id": "test-001",
            "title": "[测试区]测试项目招标公告",
            "link": "https://example.com/test1",
            "publish_time": "2024-01-01 10:00:00",
            "info_type": "招标公告",
            "region": "测试区",
            "bid_type": "不见面项目",
            "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    ]

    # 保存测试数据
    count = storage.save_records(test_records)
    print(f"保存了 {count} 条记录")

    # 获取统计
    stats = storage.get_statistics()
    print(f"\n统计信息: {json.dumps(stats, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    test_storage()