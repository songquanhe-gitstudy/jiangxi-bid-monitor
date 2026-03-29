#!/bin/bash

# 打包脚本 - 江西公共资源交易平台招标信息监控系统
# Usage: ./package.sh [version]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# 项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="jiangxi_bid_monitor"

# 版本号
VERSION="${1:-$(date +%Y%m%d)}"
PACKAGE_NAME="${PROJECT_NAME}-${VERSION}"
PACKAGE_DIR="${PROJECT_DIR}/dist/${PACKAGE_NAME}"
ARCHIVE_NAME="${PACKAGE_NAME}.tar.gz"

print_info "开始打包项目..."
print_info "版本: $VERSION"
print_info "包名: $ARCHIVE_NAME"
echo

# 创建打包目录
print_info "创建打包目录..."
rm -rf "${PROJECT_DIR}/dist"
mkdir -p "$PACKAGE_DIR"

# 复制主要文件
print_info "复制项目文件..."

# Python 核心模块
cp "${PROJECT_DIR}/config.py" "$PACKAGE_DIR/"
cp "${PROJECT_DIR}/scraper.py" "$PACKAGE_DIR/"
cp "${PROJECT_DIR}/detail_scraper.py" "$PACKAGE_DIR/"
cp "${PROJECT_DIR}/extractor.py" "$PACKAGE_DIR/"
cp "${PROJECT_DIR}/storage.py" "$PACKAGE_DIR/"
cp "${PROJECT_DIR}/feishu_sender.py" "$PACKAGE_DIR/"
cp "${PROJECT_DIR}/workflow.py" "$PACKAGE_DIR/"
cp "${PROJECT_DIR}/scheduler.py" "$PACKAGE_DIR/"
cp "${PROJECT_DIR}/query.py" "$PACKAGE_DIR/"
cp "${PROJECT_DIR}/main.py" "$PACKAGE_DIR/"
cp "${PROJECT_DIR}/notifier.py" "$PACKAGE_DIR/"
cp "${PROJECT_DIR}/web_dashboard.py" "$PACKAGE_DIR/"

# 启动脚本
cp "${PROJECT_DIR}/start.sh" "$PACKAGE_DIR/"
chmod +x "${PACKAGE_DIR}/start.sh"

# 依赖文件
cp "${PROJECT_DIR}/requirements.txt" "$PACKAGE_DIR/"

# 文档
cp "${PROJECT_DIR}/README.md" "$PACKAGE_DIR/"
cp "${PROJECT_DIR}/CLAUDE.md" "$PACKAGE_DIR/"

# 配置文件（使用示例配置）
if [ -f "${PROJECT_DIR}/config.json.example" ]; then
    cp "${PROJECT_DIR}/config.json.example" "${PACKAGE_DIR}/config.json"
else
    # 创建默认配置
    cat > "${PACKAGE_DIR}/config.json" << 'EOF'
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
fi

# 创建必要目录
mkdir -p "${PACKAGE_DIR}/data"
mkdir -p "${PACKAGE_DIR}/logs"
mkdir -p "${PACKAGE_DIR}/prompts"

# 复制 prompts 文件
if [ -d "${PROJECT_DIR}/prompts" ]; then
    cp -r "${PROJECT_DIR}/prompts/"* "${PACKAGE_DIR}/prompts/" 2>/dev/null || true
fi

# 复制 web 目录
if [ -d "${PROJECT_DIR}/web" ]; then
    cp -r "${PROJECT_DIR}/web" "${PACKAGE_DIR}/"
fi

# 创建安装说明
cat > "${PACKAGE_DIR}/INSTALL.md" << 'EOF'
# 安装部署说明

## 快速开始

### 1. 解压

```bash
tar -xzf jiangxi_bid_monitor-*.tar.gz
cd jiangxi_bid_monitor-*/
```

### 2. 配置

编辑 `config.json`，配置必要的参数：

- **AI API**: 配置 AI 服务用于数据提取
- **飞书通知**: 配置 webhook_url 用于消息推送

```json
{
  "ai": {
    "api_url": "https://api.openai.com/v1/chat/completions",
    "api_key": "your-api-key",
    "model": "gpt-3.5-turbo"
  },
  "feishu": {
    "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
  }
}
```

### 3. 启动

```bash
# 首次运行 - 初始化并启动
./start.sh setup

# 启动所有服务（后端 + 前端）
./start.sh start
```

## 目录结构

```
jiangxi_bid_monitor/
├── start.sh          # 启动脚本
├── config.json       # 配置文件（需自行配置）
├── requirements.txt  # Python依赖
├── data/             # 数据目录（数据库）
├── logs/             # 日志目录
├── prompts/          # AI提示词
├── web/              # Web监控大屏
└── *.py              # Python模块
```

## 常用命令

```bash
./start.sh setup      # 初始化环境
./start.sh start      # 启动所有服务
./start.sh daemon     # 仅启动后端
./start.sh dashboard  # 仅启动前端
./start.sh stop       # 停止服务
./start.sh status     # 查看状态
./start.sh logs       # 查看日志
```

## 访问

- Web监控大屏: http://localhost:8080
- 日志文件: logs/monitor.log

## 系统要求

- Python 3.8+
- Linux/macOS/Windows(WSL)
- 网络访问（用于API调用和飞书通知）
EOF

# 创建部署脚本
cat > "${PACKAGE_DIR}/deploy.sh" << 'EOF'
#!/bin/bash

# 部署脚本 - 在服务器上解压后运行
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=================================="
echo "  江西招标监控系统 - 部署"
echo "=================================="
echo

# 检查Python
echo "[INFO] 检查Python环境..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3未安装，请先安装Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "[OK] Python版本: $PYTHON_VERSION"

# 创建目录
echo "[INFO] 创建必要目录..."
mkdir -p "$PROJECT_DIR/data"
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/prompts"

# 安装依赖
echo "[INFO] 安装依赖..."
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    pip3 install -r "$PROJECT_DIR/requirements.txt" -q
    echo "[OK] 依赖安装完成"
else
    echo "[WARN] requirements.txt不存在"
fi

# 检查配置文件
echo "[INFO] 检查配置文件..."
if [ -f "$PROJECT_DIR/config.json" ]; then
    echo "[OK] 配置文件已存在"
    echo "[INFO] 请确保 config.json 中的 API 密钥和 webhook 已正确配置"
else
    echo "[WARN] config.json 不存在，将创建默认配置"
    cat > "$PROJECT_DIR/config.json" << 'CONFIGEOF'
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
CONFIGEOF
    echo "[WARN] 请编辑 config.json 配置API和webhook后再启动"
fi

echo
echo "=================================="
echo "[OK] 部署完成!"
echo "=================================="
echo
echo "下一步:"
echo "  1. 编辑 config.json 配置文件"
echo "  2. 运行 ./start.sh start 启动服务"
echo
echo "常用命令:"
echo "  ./start.sh setup    - 初始化"
echo "  ./start.sh start    - 启动所有服务"
echo "  ./start.sh status   - 查看状态"
echo
echo "访问地址: http://localhost:8080"
echo
EOF

chmod +x "${PACKAGE_DIR}/deploy.sh"

# 创建打包清单
cat > "${PACKAGE_DIR}/MANIFEST.txt" << EOF
江西公共资源交易平台招标信息监控系统
版本: $VERSION
打包时间: $(date '+%Y-%m-%d %H:%M:%S')

包含文件:
$(find "$PACKAGE_DIR" -type f | sed "s|$PACKAGE_DIR/||" | sort)

部署说明:
1. 解压: tar -xzf $ARCHIVE_NAME
2. 配置: 编辑 config.json
3. 启动: ./start.sh start

详细说明参见 INSTALL.md
EOF

# 创建压缩包
print_info "创建压缩包..."
cd "${PROJECT_DIR}/dist"

# 使用tar命令排除__pycache__和.pyc文件
tar -czf "$ARCHIVE_NAME" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    --exclude='*.db' \
    --exclude='*.log' \
    "$PACKAGE_NAME"

# 计算MD5
MD5=$(md5 -q "$ARCHIVE_NAME" 2>/dev/null || md5sum "$ARCHIVE_NAME" | awk '{print $1}')
SIZE=$(du -h "$ARCHIVE_NAME" | cut -f1)

echo
echo "=================================="
print_success "打包完成!"
echo "=================================="
echo
echo "包文件: ${PROJECT_DIR}/dist/${ARCHIVE_NAME}"
echo "大小: $SIZE"
echo "MD5: $MD5"
echo
echo "部署步骤:"
echo "  1. 上传到服务器"
echo "  2. 解压: tar -xzf $ARCHIVE_NAME"
echo "  3. 进入目录: cd $PACKAGE_NAME"
echo "  4. 运行部署: ./deploy.sh"
echo "  5. 配置: 编辑 config.json"
echo "  6. 启动: ./start.sh start"
echo
