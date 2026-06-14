# TradeSystem · 股票数据获取系统

基于 **Python + Vue 3 + PostgreSQL + MiniQMT** 的股票数据获取系统。

## 架构

```
Vue 3 UI ──REST──► FastAPI ──xtquant──► MiniQMT
                      │
                      └──SQL──► PostgreSQL
```

数据流：MiniQMT 下载 K 线 → Python 批处理 → PostgreSQL UPSERT

## 快速启动

### 1. 配置 PostgreSQL

复制 `backend/.env.example` 为 `backend/.env`，填写数据库连接：

```env
PG_HOST=127.0.0.1
PG_PORT=5432
PG_DATABASE=trade_db
PG_USER=trade_user
PG_PASSWORD=trade_password
```

创建数据库后初始化 Schema：

```cmd
tradeSystem\scripts\init_db.cmd
```

或在系统设置页点击「初始化 Schema」，或调用 `POST /api/database/init`。

### 2. 启动后端

```cmd
tradeSystem\scripts\run_backend.cmd
```

- API: http://127.0.0.1:8000/docs
- 需 MiniQMT 客户端已登录（同步功能）

### 3. 启动前端

```cmd
tradeSystem\scripts\run_frontend.cmd
```

http://127.0.0.1:5173（dev 模式代理 `/api` 到 8000）

## 后端 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 连接状态与统计 |
| POST | `/api/sync/start` | 启动全量/增量同步 |
| GET | `/api/sync/jobs` | 任务列表 |
| GET | `/api/sync/jobs/{id}/logs` | 任务日志 |
| POST | `/api/sync/jobs/{id}/cancel` | 取消任务 |
| GET | `/api/symbols` | 标的分页查询 |
| POST | `/api/symbols/refresh` | 从 MiniQMT 刷新标的 |
| GET | `/api/market/kline` | K 线查询（PG 优先，fallback MiniQMT） |
| GET | `/api/database/tables` | 表统计 |
| GET/PUT | `/api/database/settings` | 系统配置 |
| POST | `/api/database/init` | 初始化 Schema |

## 目录结构

```
tradeSystem/
├── backend/
│   ├── main.py                 # FastAPI 入口
│   ├── config/settings.py      # 环境配置
│   ├── db/
│   │   ├── schema.sql          # PostgreSQL DDL
│   │   ├── connection.py       # 连接池
│   │   └── repositories/       # 数据访问层
│   └── services/
│       ├── sync_engine.py      # MiniQMT → PG 同步引擎
│       ├── market_service.py   # K 线查询
│       └── health_service.py
├── frontend/                   # Vue 3 UI
└── scripts/
```

## 同步说明

- **全量同步**：从 `start_date` 下载全市场 K 线，写入 `kline_daily` / `kline_intraday`
- **增量同步**：`incrementally=True`，补最新数据
- 同步在后台线程执行，进度写入 `sync_jobs` / `sync_logs`
- 复用工作区 `minqmt/` 模块（`MarketDataSync`、`MinQmtDataFetcher`）

## 依赖

- Python 3.9+（与 MiniQMT xtquant 版本匹配）
- PostgreSQL 14+
- MiniQMT 客户端 + xtquant
- Node.js 18+（前端）
