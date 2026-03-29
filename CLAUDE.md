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
| `scheduler.py` | APScheduler-based daemon (8:00-23:00 hourly execution) |
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
# Start daemon (8:00-23:00 hourly)
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

### Runtime Config (config.json)

Contains sensitive/runtime settings:
- `ai.api_url`, `ai.api_key`, `ai.model`, `ai.timeout`, `ai.max_records_per_request`
- `feishu.webhook_url`
- `scraper.request_delay`, `scraper.max_records_per_type`
- `schedule.start_hour`, `schedule.end_hour`, `schedule.interval_hours`

### Static Config (config.py)

Contains platform-specific constants:
- `INDUSTRY_TYPES`: Industry type codes (房建及市政工程 = "002001")
- `INFO_TYPES`: Info type codes (招标计划, 招标公告, 中标候选人公示)
- `API_BASE_URL`, `API_ENDPOINT`: Platform API endpoints

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

- Bold syntax: `**text**`
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