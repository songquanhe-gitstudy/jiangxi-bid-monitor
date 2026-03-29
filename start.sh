#!/bin/bash

# 江西公共资源交易平台招标信息监控系统启动脚本
# Usage: ./start.sh [command]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_CMD="${PYTHON_CMD:-python3}"

# 打印函数
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Python版本
check_python() {
    print_info "检查Python版本..."

    if ! command -v "$PYTHON_CMD" &> /dev/null; then
        print_error "未找到Python3，请先安装Python 3.8或更高版本"
        exit 1
    fi

    PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    REQUIRED_VERSION="3.8"

    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
        print_error "需要Python 3.8+, 当前版本: $PYTHON_VERSION"
        exit 1
    fi

    print_success "Python版本检查通过: $PYTHON_VERSION"
}

# 检查并安装依赖
install_deps() {
    print_info "检查依赖..."

    if [ ! -f "$PROJECT_DIR/requirements.txt" ]; then
        print_warning "requirements.txt 不存在，跳过依赖检查"
        return
    fi

    # 检查pip是否可用
    if ! $PYTHON_CMD -m pip --version &> /dev/null; then
        print_error "pip未安装，请先安装pip"
        exit 1
    fi

    # 安装依赖
    print_info "正在安装依赖..."
    if $PYTHON_CMD -m pip install -r "$PROJECT_DIR/requirements.txt" -q; then
        print_success "依赖安装完成"
    else
        print_error "依赖安装失败"
        exit 1
    fi
}

# 创建必要目录
setup_dirs() {
    print_info "创建必要目录..."

    for dir in data logs prompts; do
        if [ ! -d "$PROJECT_DIR/$dir" ]; then
            mkdir -p "$PROJECT_DIR/$dir"
            print_success "创建目录: $dir"
        fi
    done
}

# 检查配置文件
check_config() {
    if [ ! -f "$PROJECT_DIR/config.json" ]; then
        print_warning "config.json 不存在，将创建默认配置"

        cat > "$PROJECT_DIR/config.json" << 'EOF'
{
  "ai": {
    "api_url": "",
    "api_key": "",
    "model": "gpt-3.5-turbo",
    "timeout": 60,
    "max_records_per_request": 5
  },
  "feishu": {
    "webhook_url": "",
    "app_id": "",
    "app_secret": "",
    "receive_id": ""
  },
  "scraper": {
    "request_delay": 5,
    "max_records_per_type": 10
  },
  "schedule": {
    "start_hour": 8,
    "end_hour": 22,
    "interval_hours": 2
  }
}
EOF
        print_success "创建默认配置: config.json"
        print_warning "请编辑 config.json 配置AI API和飞书通知"
    fi
}

# 初始化设置
setup() {
    echo "=================================="
    echo "  江西招标监控系统 - 初始化"
    echo "=================================="
    echo

    check_python
    install_deps
    setup_dirs
    check_config

    echo
    echo "=================================="
    print_success "初始化完成!"
    echo "=================================="
    echo
    echo "可用命令:"
    echo -e "  ${YELLOW}./start.sh start${NC}      启动所有服务（后端 + 前端）"
    echo -e "  ${YELLOW}./start.sh daemon${NC}     仅启动定时监控守护进程"
    echo -e "  ${YELLOW}./start.sh once${NC}       单次执行完整流程"
    echo -e "  ${YELLOW}./start.sh dashboard${NC}  仅启动Web监控大屏"
    echo -e "  ${YELLOW}./start.sh stats${NC}      查看统计数据"
    echo -e "  ${YELLOW}./start.sh logs${NC}       查看日志"
    echo -e "  ${YELLOW}./start.sh stop${NC}       停止守护进程"
    echo -e "  ${YELLOW}./start.sh status${NC}     检查系统状态"
    echo
}

# 启动守护进程
run_daemon() {
    print_info "启动定时监控守护进程..."

    # 检查是否已在运行
    if pgrep -f "scheduler.py --daemon" > /dev/null; then
        print_warning "守护进程已在运行"
        exit 0
    fi

    cd "$PROJECT_DIR"
    nohup $PYTHON_CMD scheduler.py --daemon > logs/scheduler.out 2>&1 &

    sleep 1
    if pgrep -f "scheduler.py --daemon" > /dev/null; then
        print_success "守护进程已启动 (PID: $(pgrep -f "scheduler.py --daemon"))"
        print_info "日志文件: logs/scheduler.out"
    else
        print_error "启动失败"
        exit 1
    fi
}

# 停止守护进程
stop_daemon() {
    print_info "停止守护进程..."

    PID=$(pgrep -f "scheduler.py --daemon" || true)
    if [ -n "$PID" ]; then
        kill "$PID"
        print_success "守护进程已停止 (PID: $PID)"
    else
        print_warning "守护进程未运行"
    fi
}

# 单次执行
run_once() {
    print_info "执行单次完整流程..."
    cd "$PROJECT_DIR"
    $PYTHON_CMD workflow.py --full
}

# 启动Web大屏
run_dashboard() {
    print_info "启动Web监控大屏..."

    cd "$PROJECT_DIR"

    # 检查端口是否已被占用
    if command -v lsof &> /dev/null && lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_warning "端口8080已被占用"
        print_info "请访问: http://localhost:8080"
        return
    elif command -v netstat &> /dev/null && netstat -tuln 2>/dev/null | grep -q ":8080"; then
        print_warning "端口8080已被占用"
        print_info "请访问: http://localhost:8080"
        return
    fi

    # 启动Flask应用
    export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
    print_info "正在启动 Flask 服务..."
    print_info "访问地址: http://localhost:8080"
    echo

    # 前台运行（方便查看日志）
    $PYTHON_CMD web/app.py
}

# 启动所有服务（后端+前端）
start_all() {
    print_info "启动所有服务..."

    # 检查并初始化环境
    check_python
    setup_dirs
    check_config

    # 检查scheduler是否已在运行
    if pgrep -f "scheduler.py --daemon" > /dev/null; then
        print_success "调度器守护进程已在运行"
    else
        print_info "启动调度器守护进程..."
        cd "$PROJECT_DIR"
        nohup $PYTHON_CMD scheduler.py --daemon > logs/scheduler.out 2>&1 &
        sleep 1
        if pgrep -f "scheduler.py --daemon" > /dev/null; then
            PID=$(pgrep -f "scheduler.py --daemon")
            print_success "调度器守护进程已启动 (PID: $PID)"
        else
            print_error "调度器启动失败"
            exit 1
        fi
    fi

    # 检查dashboard是否已在运行
    if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_success "Web监控大屏已在运行"
        print_info "请访问: http://localhost:8080"
    else
        print_info "启动Web监控大屏..."
        echo
        export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
        print_info "访问地址: http://localhost:8080"
        echo "=================================="
        echo
        # 前台运行web服务
        $PYTHON_CMD web/app.py
    fi
}

# 查看统计
show_stats() {
    print_info "查看统计数据..."
    cd "$PROJECT_DIR"
    $PYTHON_CMD workflow.py --stats
}

# 查看日志
show_logs() {
    LOG_FILE="$PROJECT_DIR/logs/monitor.log"
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        print_warning "日志文件不存在: $LOG_FILE"
    fi
}

# 检查状态
show_status() {
    print_info "系统状态..."

    # 检查Python
    if command -v "$PYTHON_CMD" &> /dev/null; then
        PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
        print_success "Python: $PYTHON_VERSION"
    else
        print_error "Python未安装"
    fi

    # 检查依赖
    if $PYTHON_CMD -c "import requests" 2>/dev/null; then
        print_success "依赖: requests已安装"
    else
        print_warning "依赖: requests未安装"
    fi

    if $PYTHON_CMD -c "import flask" 2>/dev/null; then
        print_success "依赖: flask已安装"
    else
        print_warning "依赖: flask未安装"
    fi

    if $PYTHON_CMD -c "import apscheduler" 2>/dev/null; then
        print_success "依赖: apscheduler已安装"
    else
        print_warning "依赖: apscheduler未安装"
    fi

    # 检查目录
    if [ -d "$PROJECT_DIR/data" ]; then
        print_success "目录: data/ 已创建"
    else
        print_warning "目录: data/ 不存在"
    fi

    # 检查守护进程状态
    if pgrep -f "scheduler.py --daemon" > /dev/null; then
        PID=$(pgrep -f "scheduler.py --daemon")
        print_success "守护进程: 运行中 (PID: $PID)"
    else
        print_info "守护进程: 未运行"
    fi
}

# 帮助信息
show_help() {
    echo "江西公共资源交易平台招标信息监控系统"
    echo
    echo "用法: ./start.sh [命令]"
    echo
    echo "命令:"
    echo "  setup      初始化环境（安装依赖、创建目录）"
    echo "  start      启动所有服务（后端守护进程 + Web大屏）"
    echo "  daemon     仅启动定时监控守护进程"
    echo "  stop       停止守护进程"
    echo "  once       单次执行完整流程"
    echo "  dashboard  仅启动Web监控大屏"
    echo "  stats      查看统计数据"
    echo "  logs       查看实时监控日志"
    echo "  status     查看系统状态"
    echo "  help       显示此帮助信息"
    echo
    echo "示例:"
    echo "  ./start.sh setup      # 首次运行，初始化环境"
    echo "  ./start.sh start      # 启动所有服务（推荐）"
    echo "  ./start.sh daemon     # 仅启动监控后台"
    echo "  ./start.sh logs       # 查看日志"
    echo
}

# 主程序
main() {
    cd "$PROJECT_DIR"

    case "${1:-}" in
        setup)
            setup
            ;;
        start)
            start_all
            ;;
        daemon)
            run_daemon
            ;;
        stop)
            stop_daemon
            ;;
        once)
            run_once
            ;;
        dashboard)
            run_dashboard
            ;;
        stats)
            show_stats
            ;;
        logs)
            show_logs
            ;;
        status)
            show_status
            ;;
        help|--help|-h)
            show_help
            ;;
        "")
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            echo
            show_help
            exit 1
            ;;
    esac
}

main "$@"
