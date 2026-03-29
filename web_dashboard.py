#!/usr/bin/env python3
"""
Web Dashboard Launcher
启动前端仪表盘服务
"""

import os
import sys

def main():
    # 添加项目根目录到路径
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)

    # 切换到web目录
    web_dir = os.path.join(project_root, 'web')
    os.chdir(web_dir)

    # 导入并启动app
    sys.path.insert(0, web_dir)
    from app import app

    print("=" * 50)
    print("监控大屏启动中...")
    print("=" * 50)
    print(f"\n访问地址: http://localhost:5000")
    print(f"数据文件: {os.path.join(project_root, 'data', 'bid_info.db')}")
    print("\n按 Ctrl+C 停止服务\n")

    app.run(debug=True, host='0.0.0.0', port=8080)

if __name__ == '__main__':
    main()
