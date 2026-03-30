"""
Web Dashboard API
Flask后端服务，为前端提供统计数据API
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, jsonify, send_from_directory, render_template

# 先设置正确的数据库路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_PATH = os.path.join(PROJECT_ROOT, 'data', 'bid_info.db')

# 添加父目录到路径
sys.path.insert(0, PROJECT_ROOT)

from config import get_schedule_config
from storage import BidStorage

app = Flask(__name__,
            static_folder='static',
            template_folder='templates')

# 初始化存储
storage = BidStorage()


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/stats')
def get_stats():
    """获取总体统计"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 总记录数
    cursor.execute("SELECT COUNT(*) FROM bid_records")
    total = cursor.fetchone()[0]

    # 今日新增
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(*) FROM bid_records WHERE publish_time LIKE ?", (f'{today}%',))
    today_new = cursor.fetchone()[0]

    # 本周新增（周一到周日）
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(*) FROM bid_records WHERE publish_time >= ?", (f'{week_start} 00:00:00',))
    week_new = cursor.fetchone()[0]

    # 本月新增
    month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(*) FROM bid_records WHERE publish_time >= ?", (f'{month_start} 00:00:00',))
    month_new = cursor.fetchone()[0]

    conn.close()

    return jsonify({
        'total': total,
        'today_new': today_new,
        'week_new': week_new,
        'month_new': month_new,
        'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })


@app.route('/api/by-type')
def get_by_type():
    """按类型统计"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT info_type, COUNT(*) as count
        FROM bid_records
        GROUP BY info_type
    """)

    result = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()

    return jsonify(result)


@app.route('/api/daily-trend')
def get_daily_trend():
    """获取近7天趋势"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    labels = []
    values = []

    for i in range(6, -1, -1):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        labels.append(datetime.strptime(date, '%Y-%m-%d').strftime('%m/%d'))

        cursor.execute("""
            SELECT COUNT(*) FROM bid_records
            WHERE publish_time LIKE ?
        """, (f'{date}%',))

        values.append(cursor.fetchone()[0])

    conn.close()

    return jsonify({
        'labels': labels,
        'values': values
    })


@app.route('/api/recent-projects')
def get_recent_projects():
    """获取最近项目"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, info_type, region, publish_time, sent_to_feishu, link,
               CASE WHEN extracted_data IS NOT NULL AND extracted_data != '' THEN 1 ELSE 0 END as has_extracted
        FROM bid_records
        ORDER BY publish_time DESC
        LIMIT 50
    """)

    records = []
    for row in cursor.fetchall():
        records.append({
            'id': row['id'],
            'title': row['title'],
            'info_type': row['info_type'],
            'region': row['region'],
            'publish_time': row['publish_time'],
            'sent_to_feishu': bool(row['sent_to_feishu']),
            'extracted_data': bool(row['has_extracted']),
            'original_url': row['link']
        })

    conn.close()
    return jsonify(records)


@app.route('/api/scheduler-logs')
def get_scheduler_logs():
    """获取调度日志"""
    log_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'monitor.log')

    logs = []

    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 解析最近20条日志
            for line in lines[-20:]:
                line = line.strip()
                if not line:
                    continue

                # 尝试解析日志格式
                # 格式: 2026-03-29 15:41:11,360 - storage - INFO - 消息
                if ' - ' in line:
                    parts = line.split(' - ', 3)
                    if len(parts) >= 4:
                        timestamp = parts[0]
                        module = parts[1]
                        level = parts[2]
                        message = parts[3]

                        # 判断状态
                        status = 'success'
                        if 'ERROR' in level or '失败' in message or '错误' in message:
                            status = 'error'
                        elif '开始' in message or '正在' in message:
                            status = 'running'

                        logs.append({
                            'timestamp': timestamp,
                            'module': module,
                            'level': level,
                            'message': message,
                            'status': status
                        })
        except Exception as e:
            logs.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'error',
                'message': f'读取日志失败: {str(e)}'
            })

    # 如果没有日志，返回模拟数据
    if not logs:
        logs = [
            {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'step': '调度任务',
                'status': 'running',
                'message': '系统初始化完成',
                'details': '等待调度任务执行'
            }
        ]

    return jsonify(logs[-10:])  # 返回最近10条


@app.route('/api/project/<project_id>')
def get_project_detail(project_id):
    """获取项目详情"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM bid_records WHERE id = ?
    """, (project_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'Project not found'}), 404

    project = dict(row)

    # 解析JSON字段
    if project.get('detail_json'):
        try:
            project['detail'] = json.loads(project['detail_json'])
        except:
            project['detail'] = None

    if project.get('extracted_data'):
        try:
            project['extracted'] = json.loads(project['extracted_data'])
        except:
            project['extracted'] = None

    return jsonify(project)


@app.route('/api/export')
def export_data():
    """导出数据为CSV"""
    import csv
    from io import StringIO
    from flask import Response

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, info_type, region, publish_time, sent_to_feishu,
               fetch_time, extracted_time
        FROM bid_records
        ORDER BY publish_time DESC
    """)

    output = StringIO()
    writer = csv.writer(output)

    # 写入表头
    writer.writerow(['ID', '标题', '信息类型', '地区', '发布时间', '已发送飞书', '抓取时间', '提取时间'])

    # 写入数据
    for row in cursor.fetchall():
        writer.writerow([
            row['id'],
            row['title'],
            row['info_type'],
            row['region'],
            row['publish_time'],
            '是' if row['sent_to_feishu'] else '否',
            row['fetch_time'],
            row['extracted_time']
        ])

    conn.close()

    output.seek(0)
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=bid_export_{datetime.now().strftime("%Y%m%d")}.csv'}
    )


@app.route('/api/scheduler-status')
def get_scheduler_status():
    """获取调度器状态"""
    schedule_config = get_schedule_config()
    return jsonify({
        'schedule_config': schedule_config,
        'is_running': True,  # 这里可以添加实际的调度器状态检查
        'next_run': '每小时执行',
        'working_hours': f"{schedule_config['start_hour']:02d}:00 - {schedule_config['end_hour']:02d}:00"
    })


@app.route('/api/refresh')
def refresh_data():
    """手动触发数据刷新（调用workflow）"""
    import subprocess
    try:
        # 在后台运行workflow
        subprocess.Popen([sys.executable, os.path.join('..', 'workflow.py'), '--full', '--skip-scrape'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE)
        return jsonify({'status': 'started', 'message': '数据刷新任务已启动'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
