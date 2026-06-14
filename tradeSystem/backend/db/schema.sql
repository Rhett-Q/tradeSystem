-- TradeSystem PostgreSQL Schema（设计稿，未接入应用）
-- 股票数据获取系统：MiniQMT → 同步任务 → PostgreSQL

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── 标的元数据 ──
CREATE TABLE IF NOT EXISTS symbols (
    id          BIGSERIAL PRIMARY KEY,
    symbol      VARCHAR(16) NOT NULL UNIQUE,   -- 600519.SH
    name        VARCHAR(64) NOT NULL,
    market      VARCHAR(8)  NOT NULL,          -- SH / SZ / BJ
    sector      VARCHAR(64),
    industry    VARCHAR(64),
    is_listed   BOOLEAN NOT NULL DEFAULT TRUE,
    list_date   DATE,
    delist_date DATE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE symbols ADD COLUMN IF NOT EXISTS name_pinyin VARCHAR(128);
ALTER TABLE symbols ADD COLUMN IF NOT EXISTS name_initials VARCHAR(32);

CREATE INDEX IF NOT EXISTS idx_symbols_market ON symbols (market);
CREATE INDEX IF NOT EXISTS idx_symbols_sector ON symbols (sector);
CREATE INDEX IF NOT EXISTS idx_symbols_name_pinyin ON symbols (name_pinyin);
CREATE INDEX IF NOT EXISTS idx_symbols_name_initials ON symbols (name_initials);

-- ── 日 K 线 ──
CREATE TABLE IF NOT EXISTS kline_daily (
    symbol      VARCHAR(16) NOT NULL,
    trade_date  DATE        NOT NULL,
    open        NUMERIC(12, 4) NOT NULL,
    high        NUMERIC(12, 4) NOT NULL,
    low         NUMERIC(12, 4) NOT NULL,
    close       NUMERIC(12, 4) NOT NULL,
    volume      BIGINT NOT NULL DEFAULT 0,
    amount      NUMERIC(18, 2) NOT NULL DEFAULT 0,
    PRIMARY KEY (symbol, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_kline_daily_date ON kline_daily (trade_date);

-- ── 分钟 K 线（按周期分表或统一 period 字段）──
CREATE TABLE IF NOT EXISTS kline_intraday (
    symbol      VARCHAR(16) NOT NULL,
    period      VARCHAR(8)  NOT NULL,          -- 1m / 5m / 15m / 30m / 1h
    bar_time    TIMESTAMPTZ NOT NULL,
    open        NUMERIC(12, 4) NOT NULL,
    high        NUMERIC(12, 4) NOT NULL,
    low         NUMERIC(12, 4) NOT NULL,
    close       NUMERIC(12, 4) NOT NULL,
    volume      BIGINT NOT NULL DEFAULT 0,
    amount      NUMERIC(18, 2) NOT NULL DEFAULT 0,
    PRIMARY KEY (symbol, period, bar_time)
);

CREATE INDEX IF NOT EXISTS idx_kline_intraday_time ON kline_intraday (bar_time);

-- ── 同步任务 ──
DO $$ BEGIN
    CREATE TYPE sync_job_type AS ENUM ('full', 'incremental');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE sync_job_status AS ENUM ('pending', 'running', 'completed', 'failed', 'cancelled');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS sync_jobs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_type        sync_job_type NOT NULL,
    period          VARCHAR(8) NOT NULL DEFAULT '1d',
    status          sync_job_status NOT NULL DEFAULT 'pending',
    progress        SMALLINT NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    symbols_total   INT NOT NULL DEFAULT 0,
    symbols_done    INT NOT NULL DEFAULT 0,
    start_date      VARCHAR(8),                -- YYYYMMDD，全量时使用
    batch_size      INT NOT NULL DEFAULT 200,
    message         TEXT,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sync_jobs_status ON sync_jobs (status, created_at DESC);

-- ── 同步日志 ──
CREATE TABLE IF NOT EXISTS sync_logs (
    id          BIGSERIAL PRIMARY KEY,
    job_id      UUID NOT NULL REFERENCES sync_jobs (id) ON DELETE CASCADE,
    level       VARCHAR(8) NOT NULL DEFAULT 'info',  -- info / warn / error
    symbol      VARCHAR(16),
    message     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sync_logs_job ON sync_logs (job_id, created_at);

-- ── 系统配置（键值存储）──
CREATE TABLE IF NOT EXISTS app_settings (
    key         VARCHAR(64) PRIMARY KEY,
    value       JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 选股历史 ──
CREATE TABLE IF NOT EXISTS screener_history (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    mode            VARCHAR(16) NOT NULL,
    title           VARCHAR(256) NOT NULL DEFAULT '',
    query           JSONB NOT NULL,
    result_summary  JSONB NOT NULL DEFAULT '{}',
    result_rows     JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_screener_history_created ON screener_history (created_at DESC);

-- ── 表与字段注释 ──
COMMENT ON TABLE symbols IS '全市场标的元数据，由 MiniQMT 板块成分同步';
COMMENT ON COLUMN symbols.id IS '自增主键';
COMMENT ON COLUMN symbols.symbol IS '证券代码，如 600519.SH';
COMMENT ON COLUMN symbols.name IS '证券简称';
COMMENT ON COLUMN symbols.market IS '交易所：SH / SZ / BJ';
COMMENT ON COLUMN symbols.sector IS '申万一级行业（板块）';
COMMENT ON COLUMN symbols.industry IS '细分行业（预留）';
COMMENT ON COLUMN symbols.is_listed IS '是否上市；刷新全市场时不在列表中的标的置为 FALSE';
COMMENT ON COLUMN symbols.list_date IS '上市日期（预留）';
COMMENT ON COLUMN symbols.delist_date IS '退市日期；为空表示未退市';
COMMENT ON COLUMN symbols.name_pinyin IS '名称拼音全拼，用于搜索';
COMMENT ON COLUMN symbols.name_initials IS '名称拼音首字母，用于搜索';
COMMENT ON COLUMN symbols.created_at IS '记录创建时间';
COMMENT ON COLUMN symbols.updated_at IS '记录最后更新时间';

COMMENT ON TABLE kline_daily IS '日 K 线，由 MiniQMT 下载后写入';
COMMENT ON COLUMN kline_daily.symbol IS '证券代码';
COMMENT ON COLUMN kline_daily.trade_date IS '交易日期';
COMMENT ON COLUMN kline_daily.open IS '开盘价';
COMMENT ON COLUMN kline_daily.high IS '最高价';
COMMENT ON COLUMN kline_daily.low IS '最低价';
COMMENT ON COLUMN kline_daily.close IS '收盘价';
COMMENT ON COLUMN kline_daily.volume IS '成交量（股）';
COMMENT ON COLUMN kline_daily.amount IS '成交额（元）';

COMMENT ON TABLE kline_intraday IS '分钟 K 线（多周期共用）';
COMMENT ON COLUMN kline_intraday.symbol IS '证券代码';
COMMENT ON COLUMN kline_intraday.period IS 'K 线周期：1m / 5m / 15m / 30m / 1h';
COMMENT ON COLUMN kline_intraday.bar_time IS 'K 线起始时间（含时区）';
COMMENT ON COLUMN kline_intraday.open IS '开盘价';
COMMENT ON COLUMN kline_intraday.high IS '最高价';
COMMENT ON COLUMN kline_intraday.low IS '最低价';
COMMENT ON COLUMN kline_intraday.close IS '收盘价';
COMMENT ON COLUMN kline_intraday.volume IS '成交量（股）';
COMMENT ON COLUMN kline_intraday.amount IS '成交额（元）';

COMMENT ON TYPE sync_job_type IS '同步任务类型：full=全量，incremental=增量';
COMMENT ON TYPE sync_job_status IS '同步任务状态：pending / running / completed / failed / cancelled';

COMMENT ON TABLE sync_jobs IS 'MiniQMT 数据同步任务队列与执行状态';
COMMENT ON COLUMN sync_jobs.id IS '任务 UUID';
COMMENT ON COLUMN sync_jobs.job_type IS '任务类型（全量 / 增量）';
COMMENT ON COLUMN sync_jobs.period IS 'K 线周期，如 1d / 5m';
COMMENT ON COLUMN sync_jobs.status IS '当前任务状态';
COMMENT ON COLUMN sync_jobs.progress IS '进度百分比 0–100';
COMMENT ON COLUMN sync_jobs.symbols_total IS '待同步标的总数';
COMMENT ON COLUMN sync_jobs.symbols_done IS '已完成同步的标的数';
COMMENT ON COLUMN sync_jobs.start_date IS '全量同步起始日期 YYYYMMDD';
COMMENT ON COLUMN sync_jobs.batch_size IS '每批下载的标的数量';
COMMENT ON COLUMN sync_jobs.message IS '任务摘要或错误信息';
COMMENT ON COLUMN sync_jobs.started_at IS '任务开始时间';
COMMENT ON COLUMN sync_jobs.finished_at IS '任务结束时间';
COMMENT ON COLUMN sync_jobs.created_at IS '任务创建时间';

COMMENT ON TABLE sync_logs IS '同步任务运行日志';
COMMENT ON COLUMN sync_logs.id IS '自增主键';
COMMENT ON COLUMN sync_logs.job_id IS '关联 sync_jobs.id';
COMMENT ON COLUMN sync_logs.level IS '日志级别：info / warn / error';
COMMENT ON COLUMN sync_logs.symbol IS '相关证券代码（可选）';
COMMENT ON COLUMN sync_logs.message IS '日志正文';
COMMENT ON COLUMN sync_logs.created_at IS '日志写入时间';

COMMENT ON TABLE app_settings IS '系统键值配置（JSON 存储）';
COMMENT ON COLUMN app_settings.key IS '配置键名';
COMMENT ON COLUMN app_settings.value IS '配置值（JSON）';
COMMENT ON COLUMN app_settings.updated_at IS '最后更新时间';

COMMENT ON TABLE screener_history IS '选股条件与结果快照历史';
COMMENT ON COLUMN screener_history.id IS '记录 UUID';
COMMENT ON COLUMN screener_history.mode IS '选股模式：basic / qlib / multi';
COMMENT ON COLUMN screener_history.title IS '条件摘要标题';
COMMENT ON COLUMN screener_history.query IS '完整筛选参数（JSON）';
COMMENT ON COLUMN screener_history.result_summary IS '结果摘要，如命中数量（JSON）';
COMMENT ON COLUMN screener_history.result_rows IS '第一页结果快照（JSON 数组，最多 50 条）';
COMMENT ON COLUMN screener_history.created_at IS '记录创建时间';
