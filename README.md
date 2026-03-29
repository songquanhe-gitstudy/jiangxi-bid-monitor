# 江西公共资源交易平台招标信息监控系统

自动监控江西省公共资源交易平台，抓取房建及市政工程的招标信息，通过AI提取结构化数据并发送到飞书。

## 功能特性

- 监控行业类型：房建及市政工程
- 监控信息类型：招标计划、招标公告、中标候选人公示
- 定时抓取：每天8点开始，每小时更新一次，直到晚上11点
- 详情抓取：抓取详情页面的完整文本内容
- AI提取：使用AI从详情文本中提取结构化数据
- 飞书通知：每10条提取数据批量发送到飞书
- 数据存储：SQLite本地数据库，支持历史查询
- 可编辑提示词：每种信息类型有独立的提取提示词模板

## 处理流程

```
步骤1: 抓取列表页 → 步骤2: 抓取详情页 → 步骤3: AI提取数据 → 步骤4: 发送飞书
```

## 快速开始

### 1. 安装依赖

```bash
cd jiangxi_bid_monitor
pip install -r requirements.txt
```

### 2. 配置飞书通知

编辑 `feishu_sender.py` 或 `config.py`，设置飞书通知方式：

**方式一：群机器人Webhook（推荐，最简单）**
```python
FEISHU_CONFIG = {
    "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx",
}
```

获取方式：在飞书群聊中 → 群设置 → 群机器人 → 添加机器人 → 复制Webhook地址

### 3. 配置AI API

编辑 `extractor.py`，设置AI API：

```python
AI_CONFIG = {
    "api_type": "openai",  # 或 claude, custom
    "api_url": "https://api.openai.com/v1/chat/completions",
    "api_key": "your-api-key",
    "model": "gpt-3.5-turbo",  # 或其他模型
}
```

或使用配置函数：
```python
from extractor import configure_ai
configure_ai('openai', 'https://api.xxx.com/v1/chat/completions', 'your-key', 'gpt-4')
```

### 4. 编辑提取提示词

提示词文件位于 `prompts/` 目录，可以自行修改：

- `prompts/zhaobiao_jihua.txt` - 招标计划提取模板
- `prompts/zhaobiao_gonggao.txt` - 招标公告提取模板
- `prompts/zhongbiao_houxuanren.txt` - 中标候选人公示提取模板

### 5. 测试系统

```bash
# 查看统计信息
python query.py --stats

# 查看待提取记录
python query.py --pending-extract

# 单次执行完整流程
python workflow.py --full

# 连续处理直到完成
python workflow.py --continuous

# 测试调度器配置
python scheduler.py --test
```

### 6. 启动监控

```bash
# 作为守护进程运行（推荐）
python scheduler.py --daemon

# 或单次运行
python scheduler.py --once
```

## 项目结构

```
jiangxi_bid_monitor/
├── config.py           # 配置文件
├── scraper.py          # 列表页抓取模块
├── detail_scraper.py   # 详情页抓取模块
├── extractor.py        # AI数据提取模块
├── feishu_sender.py    # 飞书消息发送模块
├── storage.py          # 数据存储模块
├── workflow.py         # 主流程整合模块
├── scheduler.py        # 定时调度模块
├── query.py            # 数据查询工具
├── prompts/            # AI提取提示词目录
│   ├── zhaobiao_jihua.txt
│   ├── zhaobiao_gonggao.txt
│   └── zhongbiao_houxuanren.txt
├── data/               # 数据存储目录
│   ├── bid_info.db     # SQLite数据库
│   └── records.json    # 已抓取记录ID缓存
└── logs/               # 日志目录
    └── monitor.log
```

## 数据库字段

| 字段 | 说明 |
|------|------|
| id | 记录唯一ID |
| title | 标题 |
| info_type | 信息类型 |
| detail_json | 详情页抓取数据（JSON） |
| extracted_data | AI提取的结构化数据（JSON） |
| extracted_time | 提取时间 |
| sent_to_feishu | 是否已发送飞书 |

## 查询命令

```bash
# 基本查询
python query.py                          # 查看最近20条记录
python query.py -t "招标公告"             # 按类型筛选
python query.py -k "关键词"               # 关键词搜索
python query.py -l 50                    # 显示50条

# 统计信息
python query.py --stats                  # 数据处理统计

# 详情查看
python query.py -d "记录ID"              # 查看详情内容
python query.py -x "记录ID"              # 查看提取数据

# 导出数据
python query.py -e data.json             # 导出为JSON
python query.py --export-detail full.json # 导出含详情数据
```

## 流程命令

```bash
# workflow.py 命令
python workflow.py --full               # 完整流程
python workflow.py --continuous         # 连续处理
python workflow.py --step 1             # 只执行列表抓取
python workflow.py --step 2             # 只执行详情抓取
python workflow.py --step 3             # 只执行AI提取
python workflow.py --step 4             # 只执行飞书发送
python workflow.py --stats              # 显示统计

# scheduler.py 命令
python scheduler.py --daemon            # 后台守护进程
python scheduler.py --once              # 单次执行
python scheduler.py --test              # 显示任务配置
```

## 提取数据格式

### 招标计划
```json
{
  "建设单位": "",
  "项目类型": "",
  "项目概况": "",
  "招标方式": "",
  "投资额": "",
  "资金来源": "",
  "预计招标时间": "",
  "拟交易场所": ""
}
```

### 招标公告
```json
{
  "招标人": "",
  "工程地点": "",
  "工程类别": "",
  "建筑面积": "",
  "项目总投资": "",
  "招标范围": "",
  "资质要求": "",
  "业绩要求": "",
  "项目经理要求": "",
  "招标文件获取": "",
  "招标方式": "",
  "特殊要求": "",
  "联系方式": ""
}
```

### 中标候选人公示
```json
{
  "招标人": "",
  "工程地点": "",
  "工程类别": "",
  "最高限价": "",
  "工期": "",
  "中标候选人": [
    {"名称": "", "报价": ""},
    {"名称": "", "报价": ""},
    {"名称": "", "报价": ""}
  ]
}
```