<template>
  <div class="stack">
    <div class="card">
      <div class="card-head">
        <h2>{{ pageTitle }}</h2>
        <p v-if="result.symbol" class="muted chart-meta">
          <span v-if="result.name" class="symbol-name">{{ result.name }}</span>
          <span class="mono symbol-code">{{ result.symbol }}</span>
          <span v-if="result.sector" class="tag">{{ result.sector }}</span>
          <span class="tag">{{ result.rows.length }} 根</span>
          <span v-if="result.source" class="tag">来源: {{ result.source }}</span>
          <span v-if="priceChange" class="tag" :class="priceChange.up ? 'up-tag' : 'down-tag'">
            {{ priceChange.up ? '▲' : '▼' }} {{ priceChange.pct }}%
          </span>
        </p>
      </div>

      <div class="query-row">
        <SymbolSearchInput ref="symbolSearchRef" v-model="symbol" label="股票" @submit="query()" />
        <label>条数
          <input v-model.number="limit" type="number" min="10" max="500" />
        </label>
        <button class="btn primary query-btn" :disabled="loading" @click="query()">
          {{ loading ? '查询中…' : '查询' }}
        </button>
      </div>
      <p class="search-hint muted">支持代码、中文名称、拼音全拼或首字母（如 茅台、maotai、mt）</p>
    </div>

    <div class="card chart-card chart-card-wrap">
      <div class="period-bar period-bar-chart" role="tablist" aria-label="K 线周期">
        <button
          v-for="p in PERIODS"
          :key="'chart-' + p.value"
          type="button"
          role="tab"
          class="period-btn"
          :class="{ active: period === p.value }"
          :aria-selected="period === p.value"
          :disabled="loading"
          @click="switchPeriod(p.value)"
        >
          {{ p.label }}
        </button>
      </div>
      <div v-if="loading" class="chart-loading">K 线加载中…</div>
      <KlineChart
        v-if="result.rows.length > 0"
        :key="chartKey"
        :rows="result.rows"
        :period="period"
        :height="chartHeight"
      />
      <div v-else-if="!loading" class="chart-empty muted">
        {{ emptyChartHint }}
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <h2>摘要</h2>
        <div class="summary-grid">
          <div><span class="muted">最新收盘</span><strong :class="summary.up ? 'up' : 'down'">{{ summary.close }}</strong></div>
          <div><span class="muted">区间最高</span><strong>{{ summary.high }}</strong></div>
          <div><span class="muted">区间最低</span><strong>{{ summary.low }}</strong></div>
          <div><span class="muted">总成交量</span><strong>{{ summary.volume }}</strong></div>
          <div><span class="muted">总成交额</span><strong>{{ summary.amount }}</strong></div>
          <div><span class="muted">涨跌额</span><strong :class="summary.up ? 'up' : 'down'">{{ summary.change }}</strong></div>
        </div>
      </div>

      <div class="card">
        <h2>说明</h2>
        <ul class="hint-list">
          <li>滚轮缩放 · 拖拽平移 · 十字光标查看 OHLC / 均线 / KDJ</li>
          <li>主图 K 线 + 可选均线（MA5~250）· 副图1 成交量 · 副图2 KDJ</li>
          <li>点击日K / 周K / 分钟周期按钮即可切换，已选股票会自动重新加载</li>
          <li>周线由数据库日 K 重采样（需先同步日线 1d）</li>
        </ul>
      </div>
    </div>

    <div class="card">
      <h2>明细数据</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>日期</th>
              <th>开盘</th>
              <th>最高</th>
              <th>最低</th>
              <th>收盘</th>
              <th>成交量</th>
              <th>成交额</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in tableRows" :key="row.date">
              <td>{{ row.date }}</td>
              <td>{{ fmtPrice(row.open) }}</td>
              <td class="up">{{ fmtPrice(row.high) }}</td>
              <td class="down">{{ fmtPrice(row.low) }}</td>
              <td :class="row.close >= row.open ? 'up' : 'down'">{{ fmtPrice(row.close) }}</td>
              <td>{{ formatVol(row.volume) }}</td>
              <td>{{ formatAmt(row.amount) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'
import KlineChart from '@/components/KlineChart.vue'
import SymbolSearchInput from '@/components/SymbolSearchInput.vue'
import { showMockToast } from '@/mock'
import { isSymbolCode, normalizeSymbolInput } from '@/utils/symbol'

const route = useRoute()
const symbolSearchRef = ref(null)
const symbol = ref('600519.SH')
const period = ref('1d')
const limit = ref(120)
const loading = ref(false)
const result = ref({ symbol: '', name: '', sector: '', period: '1d', rows: [], source: '' })
let querySeq = 0

const PERIODS = [
  { value: '1d', label: '日K' },
  { value: '1w', label: '周K' },
  { value: '5m', label: '5分' },
  { value: '15m', label: '15分' },
  { value: '1h', label: '60分' },
]

const chartHeight = 480

const chartKey = computed(() => `${result.value.symbol}-${period.value}`)

const pageTitle = computed(() => {
  if (result.value.name) return result.value.name
  if (result.value.symbol) return result.value.symbol
  return 'K 线查询'
})

const emptyChartHint = computed(() => {
  if (!result.value.symbol) return '输入代码或从选股页跳转查看 K 线'
  const label = result.value.name
    ? `${result.value.name}（${result.value.symbol}）`
    : result.value.symbol
  return `${label} 暂无 K 线数据`
})

const tableRows = computed(() => [...result.value.rows].reverse())

function switchPeriod(next) {
  if (period.value === next || loading.value) return
  period.value = next
}

function resolveCurrentSymbol() {
  if (result.value.symbol) return result.value.symbol
  if (isSymbolCode(symbol.value)) return normalizeSymbolInput(symbol.value)
  return null
}

async function refreshOnPeriodChange() {
  const sym = resolveCurrentSymbol()
  if (sym) await query(sym)
}

const summary = computed(() => {
  const rows = result.value.rows
  if (!rows.length) {
    return { close: '-', high: '-', low: '-', volume: '-', amount: '-', change: '-', up: true }
  }
  const last = rows[rows.length - 1]
  const first = rows[0]
  const highs = rows.map((r) => r.high)
  const lows = rows.map((r) => r.low)
  const vol = rows.reduce((s, r) => s + r.volume, 0)
  const amt = rows.reduce((s, r) => s + r.amount, 0)
  const change = last.close - first.open
  return {
    close: last.close.toFixed(2),
    high: Math.max(...highs).toFixed(2),
    low: Math.min(...lows).toFixed(2),
    volume: formatVol(vol),
    amount: formatAmt(amt),
    change: (change >= 0 ? '+' : '') + change.toFixed(2),
    up: change >= 0,
  }
})

const priceChange = computed(() => {
  const rows = result.value.rows
  if (rows.length < 2) return null
  const last = rows[rows.length - 1]
  const prev = rows[rows.length - 2]
  const pct = ((last.close - prev.close) / prev.close) * 100
  return { up: pct >= 0, pct: Math.abs(pct).toFixed(2) }
})

async function query(explicitSymbol) {
  const seq = ++querySeq
  loading.value = true
  try {
    let resolved = null
    if (typeof explicitSymbol === 'string' && isSymbolCode(explicitSymbol)) {
      resolved = normalizeSymbolInput(explicitSymbol)
    }
    if (!resolved) {
      if (isSymbolCode(symbol.value)) {
        resolved = normalizeSymbolInput(symbol.value)
      } else if (symbolSearchRef.value) {
        resolved = await symbolSearchRef.value.resolveSymbol()
      } else {
        resolved = symbol.value
      }
    }
    const data = await api.kline({
      symbol: resolved,
      period: period.value,
      limit: String(limit.value),
    })
    if (seq !== querySeq) return
    result.value = data
    symbol.value = resolved
  } catch (e) {
    if (seq !== querySeq) return
    showMockToast(e.message)
  } finally {
    if (seq === querySeq) loading.value = false
  }
}

async function loadKlineForSymbol(code) {
  const normalized = normalizeSymbolInput(code)
  if (!isSymbolCode(normalized)) return

  symbol.value = normalized
  loading.value = true
  result.value = { symbol: normalized, name: '', sector: '', period: period.value, rows: [], source: '' }
  await query(normalized)
}

function symbolFromRoute() {
  const q = route.query.symbol
  if (!q) return null
  const raw = Array.isArray(q) ? q[0] : q
  if (!raw || !isSymbolCode(String(raw))) return null
  return normalizeSymbolInput(String(raw))
}

async function applyRouteSymbol() {
  const fromRoute = symbolFromRoute()
  if (!fromRoute) return
  await loadKlineForSymbol(fromRoute)
}

watch(
  () => (route.name === 'MarketData' ? route.fullPath : ''),
  () => {
    if (route.name !== 'MarketData') return
    applyRouteSymbol()
  },
  { immediate: true, flush: 'post' },
)

watch(period, () => {
  refreshOnPeriodChange()
})

function formatVol(v) {
  if (v >= 1e8) return (v / 1e8).toFixed(2) + ' 亿'
  if (v >= 1e4) return (v / 1e4).toFixed(1) + ' 万'
  return String(v)
}

function formatAmt(v) {
  if (v >= 1e8) return (v / 1e8).toFixed(2) + ' 亿'
  return (v / 1e4).toFixed(0) + ' 万'
}

function fmtPrice(v) {
  if (v == null || Number.isNaN(v)) return '—'
  return Number(v).toFixed(2)
}
</script>

<style scoped>
.query-row {
  display: grid;
  grid-template-columns: 1fr 100px auto;
  gap: 0.75rem;
  align-items: end;
}

.period-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.85rem;
  padding: 0.35rem;
  background: var(--surface2);
  border-radius: var(--radius-sm);
}

.period-bar-chart {
  margin: 0 0 0.65rem;
}

.period-btn {
  flex: 1;
  min-width: 3.2rem;
  padding: 0.45rem 0.65rem;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--muted);
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}

.period-btn:hover:not(:disabled) {
  color: var(--text);
  background: var(--surface);
}

.period-btn.active {
  color: var(--text);
  background: var(--accent-soft);
  border-color: rgba(59, 130, 246, 0.35);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.period-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.query-row label { margin-bottom: 0; }
.query-btn { margin-bottom: 0; height: 38px; }

.search-hint {
  margin: 0.5rem 0 0;
  font-size: 0.8rem;
}

@media (max-width: 768px) {
  .query-row { grid-template-columns: 1fr 1fr; }
}

.chart-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: center;
  margin: 0;
  font-size: 0.82rem;
}

.symbol-name {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text);
}

.symbol-code {
  font-size: 0.82rem;
}

.chart-card-wrap {
  position: relative;
  min-height: 360px;
}

.chart-card {
  padding: 0.75rem 1rem 1rem;
}

.chart-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.15);
  z-index: 2;
  color: var(--muted);
}

.chart-empty {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 1rem;
}

.up-tag { color: var(--ok); border-color: rgba(34, 197, 94, 0.35); }
.down-tag { color: var(--err); border-color: rgba(239, 68, 68, 0.35); }

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}

@media (max-width: 768px) {
  .summary-grid { grid-template-columns: repeat(2, 1fr); }
}

.summary-grid strong {
  display: block;
  font-size: 1.15rem;
  margin-top: 0.2rem;
}

.hint-list {
  margin: 0.25rem 0 0 1.1rem;
  color: var(--muted);
  font-size: 0.85rem;
  line-height: 1.8;
}

.up { color: var(--ok); }
.down { color: var(--err); }
</style>
