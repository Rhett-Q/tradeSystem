const BASE = import.meta.env.VITE_API_BASE ?? ''
const DEFAULT_TIMEOUT_MS = 120_000

async function request(path, options = {}) {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...fetchOptions } = options
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...fetchOptions.headers },
      signal: controller.signal,
      ...fetchOptions,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || res.statusText || `HTTP ${res.status}`)
    }
    return res.json()
  } catch (e) {
    if (e.name === 'AbortError') {
      throw new Error('请求超时，后端可能繁忙或未启动（请先运行 run_backend.cmd）')
    }
    if (e instanceof TypeError) {
      throw new Error('无法连接后端，请确认后端已在 http://127.0.0.1:8000 启动')
    }
    throw e
  } finally {
    clearTimeout(timer)
  }
}

export const api = {
  health: () => request('/api/health'),
  listJobs: () => request('/api/sync/jobs'),
  startSync: (body) => request('/api/sync/start', { method: 'POST', body: JSON.stringify(body) }),
  cancelJob: (id) => request(`/api/sync/jobs/${id}/cancel`, { method: 'POST' }),
  jobLogs: (id, limit = 500) => request(`/api/sync/jobs/${id}/logs?limit=${limit}`),
  listSymbols: (params) => {
    const q = new URLSearchParams(params).toString()
    return request(`/api/symbols?${q}`)
  },
  searchSymbols: (params) => {
    const q = new URLSearchParams(params).toString()
    return request(`/api/symbols/search?${q}`)
  },
  refreshSymbols: () => request('/api/symbols/refresh', { method: 'POST' }),
  screenerSectors: () => request('/api/screener/sectors'),
  screenerFactors: (params = {}) => {
    const q = new URLSearchParams(params).toString()
    return request(`/api/screener/factors${q ? `?${q}` : ''}`)
  },
  screenerFactorDetail: (name) => request(`/api/screener/factors/${encodeURIComponent(name)}`),
  screenerRun: (params) => {
    const q = new URLSearchParams(params).toString()
    return request(`/api/screener/run?${q}`)
  },
  screenerQlibRun: (params) => {
    const q = new URLSearchParams(params).toString()
    return request(`/api/screener/qlib-run?${q}`)
  },
  screenerMultiRun: (body) =>
    request('/api/screener/multi-run', { method: 'POST', body: JSON.stringify(body) }),
  screenerNlParse: (body) =>
    request('/api/screener/nl-parse', { method: 'POST', body: JSON.stringify(body), timeoutMs: 180_000 }),
  screenerHistory: (params = {}) => {
    const q = new URLSearchParams(params).toString()
    return request(`/api/screener/history${q ? `?${q}` : ''}`)
  },
  screenerHistoryDetail: (id) => request(`/api/screener/history/${encodeURIComponent(id)}`),
  screenerHistoryDelete: (id) =>
    request(`/api/screener/history/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  screenerHistoryClear: () => request('/api/screener/history', { method: 'DELETE' }),
  kline: (params) => {
    const q = new URLSearchParams(params).toString()
    return request(`/api/market/kline?${q}`)
  },
  dbTables: () => request('/api/database/tables'),
  dbTableColumns: (table) => request(`/api/database/tables/${encodeURIComponent(table)}/columns`),
  dataQualitySummary: (params = {}) => {
    const q = new URLSearchParams(params).toString()
    return request(`/api/quality/summary${q ? `?${q}` : ''}`)
  },
  dataQualityIssues: (params = {}) => {
    const q = new URLSearchParams(params).toString()
    return request(`/api/quality/issues?${q}`)
  },
  dataQualityCleanupPreview: (params = {}) => {
    const q = new URLSearchParams(params).toString()
    return request(`/api/quality/cleanup/preview${q ? `?${q}` : ''}`)
  },
  dataQualityCleanup: (body) =>
    request('/api/quality/cleanup', { method: 'POST', body: JSON.stringify(body) }),
  backtestStrategies: () => request('/api/backtest/strategies'),
  backtestRun: (body) =>
    request('/api/backtest/run', { method: 'POST', body: JSON.stringify(body) }),
  backtestMultiRun: (body) =>
    request('/api/backtest/multi-run', { method: 'POST', body: JSON.stringify(body) }),
  strategyCatalog: (params = {}) => {
    const q = new URLSearchParams(params).toString()
    return request(`/api/strategy/catalog${q ? `?${q}` : ''}`)
  },
  strategyDetail: (id) => request(`/api/strategy/${encodeURIComponent(id)}`),
  getSettings: () => request('/api/database/settings'),
  saveSettings: (body) => request('/api/database/settings', { method: 'PUT', body: JSON.stringify(body) }),
  initDb: () => request('/api/database/init', { method: 'POST' }),
}
