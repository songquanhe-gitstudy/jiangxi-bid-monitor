# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is a monitoring system for Jiangxi Public Resources Trading Platform (江西公共资源交易平台). It monitors "房建及市政工程" (building and municipal engineering) bid information, extracts structured data via AI, and sends notifications to Feishu.

### Processing Pipeline (4 Steps)

```
Step 1: Scrape List → Step 2: Fetch Details → Step 3: AI Extract → Step 4: Send Feishu
   (scraper.py)      (detail_scraper.py)      (extractor.py)      (feishu_sender.py)
```

Each step can run independently via `workflow.py --step N`, or as a full workflow.

### Key Components

| Module | Purpose |
|--------|---------|
| `workflow.py` | Orchestrates the 4-step pipeline, main entry point |
| `scheduler.py` | APScheduler-based daemon (8:00-22:00 every 2 hours execution) |
| `scraper.py` | Fetches list data from official API |
| `detail_scraper.py` | Scrapes detail page content |
| `extractor.py` | Batch AI extraction (uses OpenAI-compatible API) |
| `feishu_sender.py` | Sends formatted messages to Feishu webhook |
| `storage.py` | SQLite database + JSON ID cache for deduplication |
| `config.py` | Static constants (API URLs, info type codes) |
| `config.json` | Runtime configuration (API keys, timeouts, batch sizes) |

### Deduplication Strategy

1. **SQLite database** stores all records with `sent_to_feishu` flag
2. **JSON cache** (`data/records.json`) for fast ID lookup during scraping
3. Records only sent to Feishu once (`sent_to_feishu=0` → `sent_to_feishu=1`)

## Common Commands

### Quick Start (Using start.sh)

```bash
# First time setup (checks Python version, installs dependencies, creates directories)
./start.sh setup

# Start all services (backend daemon + web dashboard)
./start.sh start

# Start only the scheduler daemon
./start.sh daemon

# Start only the web dashboard
./start.sh dashboard

# Other commands
./start.sh once       # Run once (single execution)
./start.sh stats      # View statistics
./start.sh logs       # View logs
./start.sh stop       # Stop daemon
./start.sh status     # Check system status
```

### Development & Testing

```bash
# Check statistics
python workflow.py --stats

# Run single step
python workflow.py --step 1   # List scraping only
python workflow.py --step 2   # Detail fetching only
python workflow.py --step 3   # AI extraction only
python workflow.py --step 4   # Feishu sending only

# Run full workflow (skip list scrape for incremental)
python workflow.py --full --skip-scrape

# Run until all pending data processed
python workflow.py --continuous

# Test scheduler configuration
python scheduler.py --test

# Single execution
python scheduler.py --once
```

### Production

```bash
# Start daemon (8:00-22:00 every 2 hours)
python scheduler.py --daemon
```

### Query Tool

```bash
python query.py --stats              # Statistics
python query.py -t "招标公告"         # Filter by type
python query.py -k "关键词"           # Keyword search
python query.py -d "record_id"       # View detail
python query.py -x "record_id"       # View extracted data
```

## Configuration

All configuration is centralized in `config.json`:

```json
{
    "ai": {
        "api_url": "...",
        "api_key": "...",
        "model": "qwen3.5-plus",
        "timeout": 300,
        "max_records_per_request": 3
    },
    "feishu": {
        "webhook_url": "..."
    },
    "scraper": {
        "max_records_per_type": 20,
        "request_delay": 5,
        "request_timeout": 60
    },
    "schedule": {
        "start_hour": 8,
        "end_hour": 23,
        "interval_hours": 1,
        "startup_task": true
    },
    "database": {
        "path": "data/bid_info.db",
        "records_json_path": "data/records.json"
    }
}
```

`config.py` only contains platform-specific constants (API URLs, info type codes) and provides helper functions to load config.json.

## Critical Rules

### AI Extraction Prompts

Prompts are editable files in `prompts/`:
- `zhaobiao_jihua.txt` - 招标计划 (建设单位, 项目类型, 投资额, etc.)
- `zhaobiao_gonggao.txt` - 招标公告 (招标人, 工程地点, 资质要求, etc.)
- `zhongbiao_houxuanren.txt` - 中标候选人公示 (招标人, 最高限价, 中标候选人列表, etc.)

**Important Prompt Rules:**
- Missing fields must be filled with "无" (never fabricate data)
- Output must be valid JSON array format
- Each input project maps to one output record
- `发布日期` and `原始链接` must be included

### Feishu Message Format

- Use `interactive` card type with `lark_md` for rich formatting
- Bold syntax: `**text**` (or use Unicode bold for English)
- Each message max 10 projects
- Header shows type distribution and count
- Every project ends with `发布日期` and `原始链接`

### Data Integrity

- Never send duplicate data (check `sent_to_feishu` flag)
- Never send empty messages (prevent notification spam)
- Log scheduler start/end even when no new data

## Batch Processing

- AI extraction: `max_records_per_request` records per API call (reduces requests)
- Feishu sending: 10 records per message batch
- Request delay: `REQUEST_DELAY` seconds between API calls

## Web Dashboard

A Flask-based web dashboard is available for visualizing monitoring data.

### File Structure

```
web/
├── app.py              # Flask backend API
├── templates/
│   └── index.html      # Dashboard UI (glass-morphism design)
└── static/
    └── js/
        └── dashboard.js  # Frontend logic & charts
```

### Start Dashboard

```bash
# Method 1: Direct
python web/app.py

# Method 2: Using launcher
python web_dashboard.py
```

Access at `http://localhost:8080` (or port 5000 if available)

### API Endpoints

- `/api/stats` - Daily/weekly/monthly statistics
- `/api/by-type` - Distribution by info type
- `/api/daily-trend` - Last 7 days trend data
- `/api/recent-projects` - Recent 50 projects with status
- `/api/scheduler-logs` - Scheduler execution logs
- `/api/export` - Export data as CSV

### Dashboard Features

- **Statistics Cards**: Total, today, weekly, monthly counts
- **Charts**: Doughnut chart for type distribution, line chart for daily trend
- **Scheduler Logs**: Real-time execution status
- **Project List**: Filterable by type (招标计划/公告/中标公示), shows extraction/send status

## Deployment

### Package for Production

Use the provided `package.sh` script to create a deployable archive:

```bash
# Create package (default version: current date)
./package.sh

# Create package with specific version
./package.sh v1.0.0
```

This creates `dist/jiangxi_bid_monitor-<version>.tar.gz` containing:
- All Python modules
- Web dashboard files
- Start scripts (`start.sh`, `deploy.sh`)
- Configuration templates
- Documentation

Excluded from package:
- `__pycache__/`, `*.pyc` (Python cache)
- `data/*.db` (database files)
- `logs/*.log` (log files)
- `.git/` (version control)

### Server Deployment

```bash
# 1. Upload and extract
tar -xzf jiangxi_bid_monitor-v1.0.0.tar.gz
cd jiangxi_bid_monitor-v1.0.0/

# 2. Run deployment script
./deploy.sh

# 3. Configure
vim config.json  # Add API keys and webhook URL

# 4. Start all services
./start.sh start
```

Access the dashboard at `http://localhost:8080`

```bash
./start.sh setup      # Initialize (install deps, create directories, config)
./start.sh start      # Start all services (daemon + dashboard) - RECOMMENDED
./start.sh daemon     # Start scheduler daemon only
./start.sh dashboard  # Start web dashboard only
./start.sh once       # Run single workflow
./start.sh stats      # Show statistics
./start.sh logs       # View monitor logs
./start.sh stop       # Stop daemon
./start.sh status     # Check system status
```

The script automatically:
- Checks Python 3.8+ requirement
- Installs missing dependencies from requirements.txt
- Creates required directories (data/, logs/, prompts/)
- Generates default config.json if missing
- Manages daemon process (start/stop/status)
