# 恢复摘要

**当前任务目标**  
tradeSystem（Vue + FastAPI + PostgreSQL + MiniQMT）已完成真实行情同步与 K 线展示；当前无进行中的开发任务，系统可正常使用。

**已完成的关键操作**
1. 后端：同步引擎、PG 仓储、API、文件/库双写日志（`backend/logs/sync.log`）
2. 修复 MiniQMT 批量下载回调、v4 数据格式解析、`get_local_data` 回退
3. 修复同步进度卡在 0%、假失败与写入 0 条等问题
4. 前端 K 线：蜡烛图 + 成交量 + KDJ 子图
5. 已确认：全量从 2024 同步会重下 2025，但 PG 用 UPSERT 不重复

**未完成 / 下一步**
- 按需：MACD/RSI、同步前健康检查、「仅补历史区间」模式
- 日常用**增量同步**；补 2024 历史可全量 `20240101`，接受耗时
- 未提交 git、未建 PR（用户未要求）

**重要路径**
- 项目：`e:\cursor_workspace\tradeSystem`
- 后端：`.env`、`services/sync_engine.py`、`db/schema.sql`、`db/repositories/kline.py`
- MiniQMT：`e:\cursor_workspace\minqmt\fetcher.py`
- 启动：`scripts/run_backend.cmd`、`scripts/run_frontend.cmd`、`scripts/init_db.cmd`
- 前端图表：`frontend/src/components/KlineChart.vue`

**约束与规则**
- 仅用户明确要求时 git commit / push / PR
- MiniQMT 须登录并保持运行
- 全量同步 `incrementally=False`，会重下重叠区间；增量只补新数据
- `kline_daily` 主键 `(symbol, trade_date)`，冲突则更新
