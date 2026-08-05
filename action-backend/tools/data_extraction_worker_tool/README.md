# 数据抽取 Worker Tool

基于 `full_text_screening_worker_tool` 设计模式改造的数据抽取异步 Worker 服务。

---

## 📋 目录结构

```
backend/tools/data_extraction_worker_tool/
├── config/
│   └── worker_config.py          # Worker 配置（Redis、队列名称等）
├── worker_service/
│   ├── worker_service.py          # Worker 主服务（持续拉取任务）
│   ├── redis_queue_manager.py     # Redis 队列管理器
│   ├── resource_limiter.py        # 资源限流器
│   ├── data_extraction_session_task.py  # Session 任务处理器
│   └── data_extraction_extractor.py     # 数据抽取执行器
├── utils/
│   ├── async_log_writer.py        # 异步日志写入器
│   ├── checkpoint_json_manager.py # JSON 断点管理
│   └── data_extraction_checkpoint_manager.py  # 断点管理器
├── migrations/
│   └── create_tables.sql          # 数据库迁移脚本
├── __main__.py                    # 启动入口
├── start_worker.sh                # 启动脚本
└── README.md                      # 说明文档
```

---

## 🚀 快速开始

### 1. 数据库迁移

执行数据库迁移脚本创建所需表：

```bash
mysql -u your_user -p your_database < backend/tools/data_extraction_worker_tool/migrations/create_tables.sql
```

**创建的表**：
- `data_extraction_history`: 数据抽取历史记录表
- `data_extraction_file_status`: 数据抽取文件状态表

### 2. 配置环境变量

```bash
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0
export REDIS_PASSWORD=your_password  # 可选
```

### 3. 启动 Worker

**方式 1: 使用 backend 根目录启动脚本（推荐）**

Linux/Mac:
```bash
cd backend
chmod +x start_data_extraction_worker.sh
./start_data_extraction_worker.sh
```

Windows:
```bash
cd backend
start_data_extraction_worker.bat
```

或直接运行 Python 脚本:
```bash
cd backend
python start_data_extraction_worker.py
```

**方式 2: 使用模块方式启动**

```bash
cd backend
python -m tools.data_extraction_worker_tool
```

**方式 3: 使用 tool 目录内的启动脚本**

```bash
chmod +x backend/tools/data_extraction_worker_tool/start_worker.sh
./backend/tools/data_extraction_worker_tool/start_worker.sh
```

**方式 4: 使用 systemd（生产环境）**

创建 systemd 服务文件 `/etc/systemd/system/data-extraction-worker.service`：

```ini
[Unit]
Description=Data Extraction Worker Service
After=network.target redis.service mysql.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/SmartEBM/backend
Environment="PYTHONPATH=/path/to/SmartEBM/backend"
Environment="REDIS_HOST=localhost"
Environment="REDIS_PORT=6379"
Environment="REDIS_DB=0"
ExecStart=/usr/bin/python3 start_data_extraction_worker.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/data-extraction-worker.log
StandardError=append:/var/log/data-extraction-worker-error.log

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl start data-extraction-worker
sudo systemctl enable data-extraction-worker
sudo systemctl status data-extraction-worker
```

---

## 📡 API 使用

### 1. 启动数据抽取任务

**请求**：

```http
POST /api/data-extraction-worker/start
Content-Type: application/json

{
  "file_urls": [
    "https://your-cos-bucket.cos.ap-guangzhou.myqcloud.com/data_extraction/input/file1.pdf",
    "https://your-cos-bucket.cos.ap-guangzhou.myqcloud.com/data_extraction/input/file2.pdf"
  ],
  "extraction_mode": "table",
  "schema": {
    "Study_Info": {...},
    "Baseline_Characteristics": {...}
  },
  "llm_config": {
    "primary": {
      "api_key": "your_api_key",
      "base_url": "https://api.openai.com/v1",
      "model_name": "gpt-4",
      "temperature": 0.0
    }
  }
}
```

**响应**：

```json
{
  "code": 200,
  "msg": "Success",
  "data": {
    "session_id": "uuid-xxxxx",
    "status": "pending",
    "message": "数据抽取任务已提交，正在排队处理"
  }
}
```

### 2. 查询任务状态

**请求**：

```http
GET /api/data-extraction-worker/status/{session_id}
```

**响应**：

```json
{
  "session_id": "uuid-xxxxx",
  "status": "processing",
  "progress_current": 5,
  "progress_total": 10,
  "files_count": 10,
  "extraction_mode": "table",
  "output_excel_path": null,
  "error_message": null,
  "created_at": "2025-12-06T18:00:00",
  "updated_at": "2025-12-06T18:05:00",
  "completed_at": null
}
```

### 3. 获取任务日志

**请求**：

```http
GET /api/data-extraction-worker/log/{session_id}
```

**响应**：

```json
{
  "code": 200,
  "msg": "Success",
  "data": {
    "session_id": "uuid-xxxxx",
    "log_content": "2025-12-06 18:00:00 - INFO - 开始处理 Session...",
    "status": "processing"
  }
}
```

### 4. 获取任务结果

**请求**：

```http
GET /api/data-extraction-worker/result/{session_id}
```

**响应**：

```json
{
  "code": 200,
  "msg": "Success",
  "data": {
    "session_id": "uuid-xxxxx",
    "status": "completed",
    "message": "任务已完成",
    "output_excel_path": "https://your-cos-bucket.cos.ap-guangzhou.myqcloud.com/data_extraction/output/result.xlsx",
    "result_files": [
      {
        "filename": "extraction_results_20251206_180000.xlsx",
        "file_path": "https://...",
        "file_size": 102400,
        "description": "数据抽取结果文件"
      }
    ]
  }
}
```

---

## 🔄 工作流程

```
1. Web 后端接收请求
   ↓
2. 创建数据库记录 (data_extraction_history + data_extraction_file_status)
   ↓
3. 推送任务到 Redis 队列 (data_extraction)
   ↓
4. Worker 从 Redis 拉取任务
   ↓
5. Worker 创建 DataExtractionSessionTask
   ↓
6. SessionTask 执行：
   - 下载文件（并发）
   - 数据抽取（调用 DataExtractionExtractor）
   - 保存断点（JSON + DB）
   - 上传结果到 COS
   - 更新数据库状态
   ↓
7. 前端轮询获取状态和结果
```

---

## ⚙️ 配置说明

### Worker 配置

在 `config/worker_config.py` 中配置：

```python
class WorkerConfig:
    # Redis 配置
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

    # 队列名称
    QUEUE_NAME = 'data_extraction'

    # Worker 配置
    WORKER_NAME = 'data_extraction_worker'

    # 任务超时时间（秒）
    JOB_TIMEOUT = 7200  # 2 小时

    # 结果保留时间（秒）
    RESULT_TTL = 86400  # 24 小时
```

### 资源限流配置

在 `worker_service/worker_service.py` 中配置：

```python
worker = WorkerService(
    max_concurrent_sessions=5,      # 最大并发 Session 数
    max_concurrent_pdfs=20,         # 最大并发 PDF 解析数
    max_concurrent_llm_calls=50     # 最大并发 LLM 调用数
)
```

---

## 📊 数据库表设计

### data_extraction_history

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 主键 ID |
| session_id | VARCHAR(64) | 会话 ID（唯一） |
| user_id | INT | 用户 ID |
| input_files | JSON | 输入文件列表 |
| files_count | INT | 文件总数 |
| extraction_mode | VARCHAR(32) | 抽取模式（table/json） |
| extraction_schema | JSON | 抽取 schema |
| llm_config | JSON | LLM 配置 |
| status | VARCHAR(32) | 状态（pending/processing/completed/error） |
| progress_current | INT | 当前进度 |
| progress_total | INT | 总进度 |
| output_excel_path | VARCHAR(512) | 输出 Excel 路径 |
| result_files | JSON | 结果文件列表 |
| error_message | TEXT | 错误信息 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |
| completed_at | DATETIME | 完成时间 |

### data_extraction_file_status

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 主键 ID |
| session_id | VARCHAR(64) | 会话 ID |
| file_name | VARCHAR(512) | 文件名 |
| file_url | VARCHAR(1024) | 文件 URL |
| file_index | INT | 文件索引 |
| local_path | VARCHAR(1024) | 本地路径 |
| status | VARCHAR(32) | 状态（pending/processing/completed/error） |
| error_message | TEXT | 错误信息 |
| processing_duration | INT | 处理时长（秒） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |
| completed_at | DATETIME | 完成时间 |

**注意**：`extraction_result` 不再存储在数据库中，而是保存在临时文件夹的 JSON 文件中（`checkpoint/{session_id}/results/*.json`），减少数据库存储压力。

---

## 🛠️ 断点续传

系统支持完整的断点续传功能：

1. **双重存储**：
   - **JSON 文件**（临时文件夹）：`checkpoint/{session_id}/results/*.json` - 存储完整的抽取结果
   - **数据库**：`data_extraction_file_status` 表 - 仅记录文件状态、时间、错误信息（不存储抽取结果，减少数据库压力）

2. **自动检测**：
   - Worker 启动后自动检测是否有未完成的任务
   - 跳过已完成的文件（从数据库状态判断），继续处理待处理文件
   - 从 JSON 文件中加载已完成文件的抽取结果

3. **手动恢复**：
   - 任务失败后，重新推送相同的 session_id 到队列即可恢复

4. **存储策略**：
   - 抽取结果仅存储在临时文件夹的 JSON 文件中
   - 最终合并后的 Excel 文件上传到 COS
   - JSON 临时文件在任务完成后自动清理

---

## 📝 日志管理

日志文件位置：
```
backend/tools/data_extraction_worker_tool/logs/{session_id}/worker.log
```

日志级别：
- INFO: 一般信息（开始处理、进度更新等）
- ERROR: 错误信息（文件下载失败、抽取失败等）
- WARNING: 警告信息（断点恢复等）
- SUCCESS: 成功信息（文件处理完成、任务完成等）

---

## 🔍 监控与调试

### 查看 Worker 状态

```bash
# 查看 Worker 日志
tail -f data_extraction_worker.log

# 查看 Redis 队列长度
redis-cli LLEN data_extraction

# 查看 Worker 进程
ps aux | grep data_extraction_worker
```

### 清理队列

```bash
# 清空 Redis 队列
redis-cli DEL data_extraction
```

---

## ⚠️ 注意事项

1. **Redis 连接**：确保 Redis 服务正常运行
2. **数据库连接**：确保数据库连接池配置合理
3. **COS 配置**：确保 COS 配置正确（用于文件下载和上传）
4. **资源限制**：根据服务器性能调整并发数
5. **日志清理**：定期清理旧日志文件

---

## 🆚 与原工具的区别

| 特性 | 原工具 (data_extraction_tool) | Worker 工具 |
|------|-------------------------------|-------------|
| 运行方式 | 手动运行 CLI `python main.py` | Worker 服务持续运行 |
| 任务管理 | 无统一管理 | Redis 队列 + 数据库 |
| 并发控制 | `multiprocessing.Pool` | `ResourceLimiter` + `asyncio` |
| 断点续传 | 部分支持（基于 Excel） | 完整支持（JSON + DB） |
| 日志管理 | 控制台输出 | 异步日志文件，前端可拉取 |
| 进度监控 | CLI 进度条 | 数据库实时记录，前端轮询 |
| 结果存储 | 本地 Excel 文件 | 上传到 COS，数据库记录路径 |

---

## 📞 技术支持

如需帮助，请联系开发团队或查看相关文档。

**改造完成时间**: 2025-12-06
**改造参考**: `backend/tools/full_text_screening_worker_tool`
