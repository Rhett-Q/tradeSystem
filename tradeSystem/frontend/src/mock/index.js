/** 前端 Mock 数据 — UI 原型，按钮操作仅弹出提示 */

const NOW = new Date('2026-06-10T15:00:00')

export const health = {
  minqmt_connected: true,
  minqmt_account: '模拟账户',
  postgres_connected: true,
  postgres_host: '127.0.0.1:5432/trade_db',
  last_sync_at: new Date(NOW - 2 * 3600 * 1000).toISOString(),
  universe_count: 5124,
  kline_rows: 18420000,
}

export const syncJobs = [
  {
    id: 'job-001',
    type: 'incremental',
    period: '1d',
    status: 'completed',
    progress: 100,
    symbols_total: 5124,
    symbols_done: 5124,
    started_at: new Date(NOW - 2.3 * 3600 * 1000).toISOString(),
    finished_at: new Date(NOW - 1.87 * 3600 * 1000).toISOString(),
    message: '增量同步完成',
  },
  {
    id: 'job-002',
    type: 'full',
    period: '1d',
    status: 'running',
    progress: 67,
    symbols_total: 5124,
    symbols_done: 3433,
    started_at: new Date(NOW - 25 * 60 * 1000).toISOString(),
    finished_at: null,
    message: '正在下载 K 线…',
  },
  {
    id: 'job-003',
    type: 'incremental',
    period: '5m',
    status: 'failed',
    progress: 12,
    symbols_total: 800,
    symbols_done: 96,
    started_at: new Date(NOW - 86400000).toISOString(),
    finished_at: new Date(NOW - 82800000).toISOString(),
    message: 'MiniQMT 连接超时',
  },
]

const symbolBase = [
  { symbol: '600519.SH', name: '贵州茅台', market: 'SH', sector: '白酒', listed: true },
  { symbol: '000858.SZ', name: '五粮液', market: 'SZ', sector: '白酒', listed: true },
  { symbol: '601318.SH', name: '中国平安', market: 'SH', sector: '保险', listed: true },
  { symbol: '300750.SZ', name: '宁德时代', market: 'SZ', sector: '新能源', listed: true },
  { symbol: '600036.SH', name: '招商银行', market: 'SH', sector: '银行', listed: true },
  { symbol: '000001.SZ', name: '平安银行', market: 'SZ', sector: '银行', listed: true },
  { symbol: '601012.SH', name: '隆基绿能', market: 'SH', sector: '新能源', listed: true },
  { symbol: '002594.SZ', name: '比亚迪', market: 'SZ', sector: '汽车', listed: true },
]

export function getSymbols(page = 1, pageSize = 10) {
  const rows = Array.from({ length: pageSize }, (_, i) => {
    const base = symbolBase[i % symbolBase.length]
    const offset = (page - 1) * pageSize + i
    return { ...base, symbol: base.symbol.replace(/\d+/, (m) => String(+m + offset).padStart(6, '0')) }
  })
  return { total: 5124, page, page_size: pageSize, rows }
}

export function getKline(symbol = '600519.SH') {
  const rows = []
  let price = 1680
  for (let i = 0; i < 30; i++) {
    const d = new Date(NOW)
    d.setDate(d.getDate() - (29 - i))
    const o = price
    const c = price + ((i % 5) - 2) * 3.5
    rows.push({
      date: d.toISOString().slice(0, 10),
      open: +o.toFixed(2),
      high: +(Math.max(o, c) + 5).toFixed(2),
      low: +(Math.min(o, c) - 4).toFixed(2),
      close: +c.toFixed(2),
      volume: 1200000 + i * 10000,
      amount: 2.1e9 + i * 1e7,
    })
    price = c
  }
  return { symbol, period: '1d', rows }
}

export const dbTables = [
  { name: 'symbols', rows: 5124, size_mb: 1.2, last_updated: NOW.toISOString() },
  { name: 'kline_daily', rows: 12800000, size_mb: 890.5, last_updated: NOW.toISOString() },
  { name: 'kline_intraday', rows: 5620000, size_mb: 1240, last_updated: new Date(NOW - 86400000).toISOString() },
  { name: 'sync_jobs', rows: 128, size_mb: 0.3, last_updated: NOW.toISOString() },
  { name: 'sync_logs', rows: 4520, size_mb: 2.1, last_updated: NOW.toISOString() },
]

export const settings = {
  minqmt: { path: 'D:\\gjqmt', account: '', auto_connect: true },
  postgres: { host: '127.0.0.1', port: 5432, database: 'trade_db', user: 'trade_user' },
  sync: { default_period: '1d', batch_size: 200, start_date: '20200101', schedule_cron: '0 18 * * 1-5' },
}

export function showMockToast(message) {
  window.dispatchEvent(new CustomEvent('tradesystem-toast', { detail: message }))
}
