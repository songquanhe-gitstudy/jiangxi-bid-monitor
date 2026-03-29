"""
数据查询和导出工具
"""

import sqlite3
import json
import csv
from datetime import datetime
from typing import Optional

DB_PATH = "data/bid_info.db"


def query_records(
    info_type: Optional[str] = None,
    region: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 20,
    output_format: str = "table"
):
    """查询记录"""

    conn = sqlite3.connect(DB_PATH)
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

    if keyword:
        query += " AND (title LIKE ? OR content LIKE ?)"
        params.append(f"%{keyword}%")
        params.append(f"%{keyword}%")

    query += f" ORDER BY publish_time DESC LIMIT {limit}"

    cursor.execute(query, params)
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if output_format == "json":
        print(json.dumps(records, ensure_ascii=False, indent=2))
    elif output_format == "csv":
        if records:
            writer = csv.DictWriter(
                __import__('sys').stdout,
                fieldnames=['id', 'title', 'info_type', 'region', 'publish_time', 'link']
            )
            writer.writeheader()
            for r in records:
                writer.writerow({
                    'id': r['id'],
                    'title': r['title'],
                    'info_type': r['info_type'],
                    'region': r['region'],
                    'publish_time': r['publish_time'],
                    'link': r['link']
                })
    else:
        # 表格格式
        print("\n" + "=" * 100)
        print(f"查询结果: 共 {len(records)} 条记录")
        print("=" * 100)

        for i, r in enumerate(records, 1):
            print(f"\n【{i}】{r['title']}")
            print(f"    类型: {r['info_type']} | 地区: {r['region']} | 时间: {r['publish_time']}")
            print(f"    链接: {r['link']}")

        print("\n" + "=" * 100)

    return records


def list_info_types():
    """列出所有信息类型"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT info_type, COUNT(*) as cnt FROM bid_records GROUP BY info_type")
    types = cursor.fetchall()
    conn.close()

    print("\n可用的信息类型:")
    for t in types:
        print(f"  • {t[0]} ({t[1]} 条)")


def export_to_file(filename: str, format: str = "json"):
    """导出数据到文件"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bid_records ORDER BY publish_time DESC")
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if format == "json":
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    elif format == "csv":
        with open(filename, 'w', encoding='utf-8', newline='') as f:
            if records:
                writer = csv.DictWriter(f, fieldnames=['id', 'title', 'info_type', 'region', 'publish_time', 'link', 'bid_type'])
                writer.writeheader()
                for r in records:
                    writer.writerow({k: r.get(k, '') for k in writer.fieldnames})

    print(f"已导出 {len(records)} 条记录到 {filename}")


def show_detail(record_id: str):
    """查看单条记录的详情"""

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM bid_records WHERE id = ?", (record_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        print(f"未找到记录: {record_id}")
        return

    record = dict(row)

    print("\n" + "=" * 80)
    print("招标信息详情")
    print("=" * 80)

    print(f"\n【基本信息】")
    print(f"  标题: {record['title']}")
    print(f"  类型: {record['info_type']}")
    print(f"  地区: {record['region']}")
    print(f"  发布时间: {record['publish_time']}")
    print(f"  链接: {record['link']}")

    if record.get('detail_json'):
        detail = json.loads(record['detail_json'])
        print(f"\n【详情内容】")
        print(f"  抓取时间: {detail.get('fetch_time', 'N/A')}")

        # 显示纯文本内容
        text = detail.get('text', '')
        if text:
            print(f"\n【页面文本】")
            # 只显示前1000字符
            display_text = text[:1000] + "..." if len(text) > 1000 else text
            print(display_text)
    else:
        print(f"\n【详情】暂未抓取")

    print("\n" + "=" * 80)


def export_with_details(filename: str):
    """导出包含详情的数据"""

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bid_records ORDER BY publish_time DESC")
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()

    # 解析detail_json字符串为对象
    for r in records:
        if r.get('detail_json'):
            try:
                r['detail_json'] = json.loads(r['detail_json'])
            except:
                pass  # 保持原样

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"已导出 {len(records)} 条记录（含详情）到 {filename}")


def show_detail_stats():
    """显示详情抓取统计"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM bid_records")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM bid_records WHERE detail_json IS NOT NULL AND detail_json != ''")
    with_detail = cursor.fetchone()[0]

    # AI提取统计
    cursor.execute("SELECT COUNT(*) FROM bid_records WHERE extracted_data IS NOT NULL AND extracted_data != ''")
    extracted = cursor.fetchone()[0]

    # 飞书发送统计
    cursor.execute("SELECT COUNT(*) FROM bid_records WHERE sent_to_feishu = 1")
    sent = cursor.fetchone()[0]

    cursor.execute("""
        SELECT info_type,
               COUNT(*) as total,
               SUM(CASE WHEN detail_json IS NOT NULL AND detail_json != '' THEN 1 ELSE 0 END) as with_detail,
               SUM(CASE WHEN extracted_data IS NOT NULL AND extracted_data != '' THEN 1 ELSE 0 END) as extracted,
               SUM(CASE WHEN sent_to_feishu = 1 THEN 1 ELSE 0 END) as sent
        FROM bid_records
        GROUP BY info_type
    """)

    print("\n" + "=" * 80)
    print("数据处理统计")
    print("=" * 80)

    print(f"\n总记录数: {total}")
    print(f"已抓详情: {with_detail}")
    print(f"AI已提取: {extracted}")
    print(f"已发飞书: {sent}")

    print(f"\n待处理:")
    print(f"  待抓详情: {total - with_detail}")
    print(f"  待提取: {with_detail - extracted}")
    print(f"  待发送: {extracted - sent}")

    print(f"\n按类型统计:")
    for row in cursor.fetchall():
        print(f"  • {row[0]}:")
        print(f"      总数={row[1]}, 详情={row[2]}, 提取={row[3]}, 发送={row[4]}")

    conn.close()


def show_extracted_data(record_id: str):
    """查看提取的结构化数据"""

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM bid_records WHERE id = ?", (record_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        print(f"未找到记录: {record_id}")
        return

    record = dict(row)

    print("\n" + "=" * 80)
    print("提取数据详情")
    print("=" * 80)

    print(f"\n【基本信息】")
    print(f"  ID: {record['id']}")
    print(f"  标题: {record['title']}")
    print(f"  类型: {record['info_type']}")
    print(f"  发布时间: {record['publish_time']}")

    if record.get('extracted_data'):
        try:
            data = json.loads(record['extracted_data'])
            print(f"\n【提取数据】")
            print(json.dumps(data, ensure_ascii=False, indent=2))
            print(f"\n提取时间: {record.get('extracted_time', 'N/A')}")
        except Exception as e:
            print(f"解析失败: {e}")
    else:
        print(f"\n【提取数据】暂未提取")

    print(f"\n【飞书状态】")
    print(f"  已发送: {'是' if record.get('sent_to_feishu') else '否'}")

    print("\n" + "=" * 80)


def list_pending_extraction(limit: int = 20):
    """列出待提取的记录"""

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, info_type, publish_time
        FROM bid_records
        WHERE detail_json IS NOT NULL AND detail_json != ''
        AND (extracted_data IS NULL OR extracted_data = '')
        ORDER BY publish_time DESC
        LIMIT ?
    """, (limit,))

    records = [dict(row) for row in cursor.fetchall()]
    conn.close()

    print("\n" + "=" * 80)
    print(f"待提取记录: 共 {len(records)} 条")
    print("=" * 80)

    for i, r in enumerate(records, 1):
        print(f"\n【{i}】{r['title']}")
        print(f"    类型: {r['info_type']} | 时间: {r['publish_time']}")
        print(f"    ID: {r['id']}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="招标信息查询工具")
    parser.add_argument("--type", "-t", help="按信息类型筛选")
    parser.add_argument("--region", "-r", help="按地区筛选")
    parser.add_argument("--keyword", "-k", help="关键词搜索")
    parser.add_argument("--limit", "-l", type=int, default=20, help="显示数量限制")
    parser.add_argument("--format", "-f", choices=["table", "json", "csv"], default="table", help="输出格式")
    parser.add_argument("--types", action="store_true", help="列出所有信息类型")
    parser.add_argument("--export", "-e", help="导出到文件 (例如: data.json 或 data.csv)")
    parser.add_argument("--detail", "-d", help="查看指定ID的详情")
    parser.add_argument("--export-detail", help="导出包含详情的数据到JSON文件")
    parser.add_argument("--stats", action="store_true", help="显示数据处理统计")
    parser.add_argument("--extracted", "-x", help="查看指定ID的提取数据")
    parser.add_argument("--pending-extract", action="store_true", help="列出待提取的记录")

    args = parser.parse_args()

    if args.types:
        list_info_types()
    elif args.detail:
        show_detail(args.detail)
    elif args.extracted:
        show_extracted_data(args.extracted)
    elif args.stats:
        show_detail_stats()
    elif args.pending_extract:
        list_pending_extraction(args.limit)
    elif args.export_detail:
        export_with_details(args.export_detail)
    elif args.export:
        fmt = "csv" if args.export.endswith('.csv') else "json"
        export_to_file(args.export, fmt)
    else:
        query_records(
            info_type=args.type,
            region=args.region,
            keyword=args.keyword,
            limit=args.limit,
            output_format=args.format
        )