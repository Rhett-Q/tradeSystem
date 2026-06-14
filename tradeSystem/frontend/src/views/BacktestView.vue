<template>
  <div class="stack">
    <div class="tab-row">
      <button class="tab" :class="{ active: mode === 'classic' }" @click="mode = 'classic'">技术指标</button>
      <button class="tab" :class="{ active: mode === 'multi' }" @click="mode = 'multi'">多因子</button>
    </div>

    <div class="grid-2 screener-layout">
      <div class="card">
        <h2>{{ mode === 'multi' ? '多因子回测' : '回测参数' }}</h2>
        <p v-if="mode === 'classic'" class="hint">基于 PostgreSQL 日 K 数据，使用 Backtrader 引擎回测。</p>
        <p v-else class="hint">多个 Alpha158 因子取交集（AND），全部满足时买入/持有，任一不满足则卖出。</p>

        <SymbolSearchInput ref="symbolSearchRef" v-model="form.symbol" label="股票" />

        <template v-if="mode === 'classic'">
          <label>策略
            <select v-model="form.strategy" @change="onStrategyChange">
              <option v-for="s in classicStrategies" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>
          <p v-if="currentStrategy?.description" class="hint">{{ currentStrategy.description }}</p>

          <div v-if="currentStrategy?.params?.length" class="param-grid">
            <label v-for="p in currentStrategy.params" :key="p.key">
              {{ p.label }}
              <input
                v-model.number="form.params[p.key]"
                type="number"
                :min="p.min"
                :max="p.max"
                :step="p.type === 'int' ? 1 : 0.001"
              />
            </label>
          </div>
        </template>

        <template v-else>
          <div v-if="multiForm.conditions.length" class="cond-list">
            <div
              v-for="(cond, idx) in multiForm.conditions"
              :key="cond.factor + '-' + idx"
              class="cond-row"
              :class="{ editing: multiEditingIdx === idx }"
            >
              <template v-if="multiEditingIdx === idx">
                <div class="cond-edit">
                  <label class="cond-edit-field">因子
                    <select v-model="multiEditDraft.factor">
                      <option v-for="f in factorMeta.factors" :key="'edit-' + f.name" :value="f.name">
                        {{ f.name }}
                      </option>
                    </select>
                  </label>
                  <div class="row-2 cond-edit-thresholds">
                    <label>≥
                      <input v-model.number="multiEditDraft.min_value" type="number" step="0.001" placeholder="不限" />
                    </label>
                    <label>≤
                      <input v-model.number="multiEditDraft.max_value" type="number" step="0.001" placeholder="不限" />
                    </label>
                  </div>
                  <div class="cond-edit-actions">
                    <button type="button" class="btn sm primary" @click="saveEditMultiCondition">保存</button>
                    <button type="button" class="btn sm ghost" @click="cancelEditMultiCondition">取消</button>
                  </div>
                </div>
              </template>
              <template v-else>
                <div class="cond-main">
                  <strong class="mono">{{ cond.factor }}</strong>
                  <span v-if="cond.min_value != null && cond.min_value !== ''" class="cond-threshold">≥ {{ cond.min_value }}</span>
                  <span v-if="cond.max_value != null && cond.max_value !== ''" class="cond-threshold">≤ {{ cond.max_value }}</span>
                  <span v-if="isEmptyThreshold(cond)" class="cond-threshold muted">未设阈值</span>
                </div>
                <div class="cond-row-actions">
                  <button type="button" class="btn sm ghost" @click="startEditMultiCondition(idx)">编辑</button>
                  <button type="button" class="btn sm ghost" @click="removeMultiCondition(idx)">删除</button>
                </div>
              </template>
            </div>
          </div>
          <p v-else class="hint">尚未添加因子条件</p>

          <div class="cond-add card-inset">
            <p class="cond-add-title">添加条件</p>
            <label>因子分类
              <select v-model="multiForm.category" @change="onMultiCategoryChange">
                <option value="">全部</option>
                <option v-for="c in factorMeta.categories" :key="'m-' + c" :value="c">{{ categoryLabel(c) }}</option>
              </select>
            </label>
            <label>因子
              <select v-model="multiForm.pickerFactor">
                <option v-for="f in multiFilteredFactors" :key="'mp-' + f.name" :value="f.name">{{ f.name }}</option>
              </select>
            </label>
            <div class="row-2">
              <label>≥
                <input v-model.number="multiForm.pickerMin" type="number" step="0.001" placeholder="不限" />
              </label>
              <label>≤
                <input v-model.number="multiForm.pickerMax" type="number" step="0.001" placeholder="不限" />
              </label>
            </div>
            <button type="button" class="btn sm" @click="addMultiCondition">加入条件</button>
          </div>

          <p class="hint preset-hint">
            快捷策略：
            <button
              v-for="preset in multiPresets"
              :key="preset.label"
              type="button"
              class="link-chip"
              @click="applyMultiPreset(preset)"
            >
              {{ preset.label }}
            </button>
          </p>
        </template>

        <div class="row-2">
          <label>开始日期
            <input v-model="form.startDate" type="date" />
          </label>
          <label>结束日期
            <input v-model="form.endDate" type="date" />
          </label>
        </div>

        <label>初始资金
          <input v-model.number="form.initialCash" type="number" min="1000" step="1000" />
        </label>
        <div class="row-2">
          <label>佣金比例
            <input v-model.number="form.commission" type="number" min="0" max="0.05" step="0.0001" />
          </label>
          <label>买入仓位 %
            <input v-model.number="form.stakePct" type="number" min="1" max="100" step="1" />
          </label>
        </div>

        <div class="btn-row">
          <button
            class="btn primary"
            :disabled="loading || (mode === 'multi' && !multiForm.conditions.length)"
            @click="runBacktest"
          >
            {{ loading ? '回测中…' : '运行回测' }}
          </button>
          <button class="btn ghost" @click="resetForm">重置</button>
        </div>
      </div>

      <div class="card">
        <div class="card-head">
          <h2>{{ resultTitle }}</h2>
          <p v-if="result.bars" class="muted result-meta">
            {{ result.start_date }} ~ {{ result.end_date }} · {{ result.bars }} 根日 K
            <span v-if="result.factors?.length"> · {{ result.factors.join(' ∩ ') }}</span>
            <span v-if="result.signal_coverage_pct != null"> · 信号覆盖 {{ result.signal_coverage_pct }}%</span>
          </p>
        </div>

        <div v-if="!hasRun && !loading" class="empty-state">
          <div class="icon">📉</div>
          <p>设置参数后运行回测</p>
        </div>

        <template v-else-if="hasRun">
          <div class="grid-3 metrics-grid">
            <StatCard
              :value="fmtPct(result.metrics?.total_return_pct)"
              label="总收益率"
              :value-color="returnColor(result.metrics?.total_return_pct)"
            />
            <StatCard
              :value="fmtPct(result.metrics?.max_drawdown_pct)"
              label="最大回撤"
              value-color="var(--err)"
            />
            <StatCard
              :value="result.metrics?.sharpe != null ? result.metrics.sharpe : '—'"
              label="Sharpe"
            />
            <StatCard
              :value="`${result.metrics?.win_rate_pct ?? '—'}%`"
              label="胜率"
              :hint="`${result.metrics?.total_trades ?? 0} 笔交易`"
            />
            <StatCard
              :value="fmtMoney(result.metrics?.final_value)"
              label="期末资产"
            />
            <StatCard
              :value="fmtMoney(result.initial_cash)"
              label="初始资金"
            />
            <StatCard
              v-if="result.signal_coverage_pct != null"
              :value="`${result.signal_coverage_pct}%`"
              label="信号覆盖率"
              hint="全部因子满足的交易日占比"
            />
          </div>

          <div v-if="result.equity_curve?.length" class="equity-wrap">
            <h3>净值曲线</h3>
            <EquityChart :points="result.equity_curve" :height="260" />
          </div>
        </template>
      </div>
    </div>

    <div v-if="hasRun && result.rows?.length" class="card kline-card">
      <div class="card-head">
        <h2>K 线与买卖点</h2>
        <p v-if="result.signals?.length" class="muted result-meta">
          {{ result.signals.length }} 个信号 · 红色▲买入 · 绿色▼卖出
        </p>
      </div>
      <KlineChart
        :key="`${result.symbol}-${result.start_date}-${result.end_date}`"
        :rows="result.rows"
        :markers="result.signals || []"
        :initial-ma="backtestMaPeriods"
        period="1d"
        :height="520"
      />
    </div>

    <div v-if="hasRun && result.trades?.length" class="card">
      <h2>交易明细</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>开仓</th>
              <th>平仓</th>
              <th>数量</th>
              <th>价格</th>
              <th>盈亏</th>
              <th>收益率</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(t, i) in result.trades" :key="i">
              <td>{{ t.open_date }}</td>
              <td>{{ t.close_date }}</td>
              <td>{{ t.size }}</td>
              <td>{{ t.price }}</td>
              <td :class="t.pnl >= 0 ? 'up' : 'down'">{{ fmtSigned(t.pnl) }}</td>
              <td :class="t.return_pct >= 0 ? 'up' : 'down'">{{ fmtSignedPct(t.return_pct) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="result.log?.length" class="card">
      <div class="card-head">
        <h2>运行日志</h2>
        <span v-if="result.stats?.total_ms" class="muted">{{ result.stats.total_ms }} ms</span>
      </div>
      <div class="log-box">
        <div v-for="(line, i) in result.log" :key="i" class="log-line" :class="line.level">
          <span class="log-time">{{ Math.round(line.elapsed_ms) }}ms</span>
          <span class="log-msg">{{ line.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'
import EquityChart from '@/components/EquityChart.vue'
import KlineChart from '@/components/KlineChart.vue'
import StatCard from '@/components/StatCard.vue'
import SymbolSearchInput from '@/components/SymbolSearchInput.vue'
import { showMockToast } from '@/mock'
import { isSymbolCode, normalizeSymbolInput } from '@/utils/symbol'

const route = useRoute()
const mode = ref('classic')
const symbolSearchRef = ref(null)
const loading = ref(false)
const hasRun = ref(false)
const strategies = ref([])

const form = reactive({
  symbol: '600519.SH',
  strategy: 'ma_crossover',
  params: { fast: 5, slow: 20 },
  startDate: '',
  endDate: '',
  initialCash: 100000,
  commission: 0.001,
  stakePct: 95,
})

const multiForm = reactive({
  category: '',
  pickerFactor: 'ROC20',
  pickerMin: null,
  pickerMax: null,
  conditions: [
    { factor: 'ROC20', min_value: 0.95 },
    { factor: 'MA5', min_value: 1.0 },
  ],
})

const multiPresets = [
  {
    label: '强势突破',
    conditions: [
      { factor: 'ROC20', min_value: 0.95 },
      { factor: 'MA5', min_value: 1.0 },
    ],
  },
  {
    label: '趋势低波',
    conditions: [
      { factor: 'MA20', min_value: 1.0 },
      { factor: 'STD20', max_value: 0.02 },
    ],
  },
  {
    label: '量价齐升',
    conditions: [
      { factor: 'ROC10', min_value: 0.97 },
      { factor: 'CORR10', min_value: 0.3 },
    ],
  },
]

const factorMeta = ref({
  categories: [],
  factors: [],
  total: 0,
})

const multiEditingIdx = ref(-1)
const multiEditDraft = reactive({
  factor: '',
  min_value: null,
  max_value: null,
})

const result = ref({})

const CATEGORY_LABELS = {
  kbar: 'K 线形态',
  price: '价格',
  momentum: '动量',
  trend: '趋势',
  volatility: '波动',
  range: '区间',
  aroon: 'Aroon',
  volume: '量价',
  other: '其他',
}

const classicStrategies = computed(() =>
  strategies.value.filter((s) => s.id !== 'multi_factor'),
)

const currentStrategy = computed(() =>
  strategies.value.find((s) => s.id === form.strategy),
)

const multiFilteredFactors = computed(() => {
  const all = factorMeta.value.factors || []
  if (!multiForm.category) return all
  return all.filter((f) => f.category === multiForm.category)
})

const resultTitle = computed(() => {
  if (!hasRun.value) return '回测结果'
  const name = result.value.name
  const sym = result.value.symbol
  if (name) return `${name}（${sym}）`
  return sym || '回测结果'
})

const backtestMaPeriods = computed(() => {
  const p = result.value.params
  if (!p) return [5, 10, 20]
  if (result.value.strategy === 'ma_crossover' && p.fast && p.slow) {
    return [Number(p.fast), Number(p.slow)]
  }
  if (result.value.strategy === 'macd_crossover' && p.fast && p.slow) {
    return [Number(p.fast), Number(p.slow)]
  }
  return [5, 10, 20]
})

function categoryLabel(c) {
  return CATEGORY_LABELS[c] || c
}

function applyStrategyDefaults(strategy) {
  if (!strategy?.params) return
  const next = { ...form.params }
  for (const p of strategy.params) {
    if (next[p.key] == null) next[p.key] = p.default
  }
  form.params = next
}

function onStrategyChange() {
  applyStrategyDefaults(currentStrategy.value)
}

function applyRouteStrategy() {
  const q = route.query
  if (q.mode === 'multi' || q.strategy === 'multi_factor') {
    mode.value = 'multi'
  }
  if (q.strategy && q.strategy !== 'multi_factor') {
    mode.value = 'classic'
    form.strategy = String(q.strategy)
    applyStrategyDefaults(currentStrategy.value)
    for (const p of currentStrategy.value?.params || []) {
      if (q[p.key] != null && q[p.key] !== '') {
        form.params[p.key] = p.type === 'int' ? parseInt(q[p.key], 10) : parseFloat(q[p.key])
      }
    }
  }
  if (q.symbol && isSymbolCode(String(q.symbol))) {
    form.symbol = normalizeSymbolInput(String(q.symbol))
  }
}

async function loadStrategies() {
  try {
    strategies.value = await api.backtestStrategies()
    if (classicStrategies.value.length && !classicStrategies.value.find((s) => s.id === form.strategy)) {
      form.strategy = classicStrategies.value[0].id
    }
    applyStrategyDefaults(currentStrategy.value)
    applyRouteStrategy()
  } catch (e) {
    showMockToast(e.message)
  }
}

async function loadFactorMeta() {
  try {
    factorMeta.value = await api.screenerFactors()
    if (!factorMeta.value.factors?.find((f) => f.name === multiForm.pickerFactor)) {
      multiForm.pickerFactor = factorMeta.value.factors?.[0]?.name || 'ROC20'
    }
  } catch (e) {
    showMockToast(e.message)
  }
}

async function resolveSymbol() {
  if (isSymbolCode(form.symbol)) return normalizeSymbolInput(form.symbol)
  if (symbolSearchRef.value) return symbolSearchRef.value.resolveSymbol()
  return form.symbol
}

function buildClassicBody() {
  return {
    symbol: form.symbol,
    strategy: form.strategy,
    params: { ...form.params },
    initial_cash: form.initialCash,
    commission: form.commission,
    stake_pct: form.stakePct,
    ...(form.startDate ? { start_date: form.startDate } : {}),
    ...(form.endDate ? { end_date: form.endDate } : {}),
  }
}

function buildMultiBody() {
  return {
    symbol: form.symbol,
    conditions: multiForm.conditions.map((c) => ({
      factor: c.factor,
      ...(c.min_value != null && c.min_value !== '' ? { min_value: c.min_value } : {}),
      ...(c.max_value != null && c.max_value !== '' ? { max_value: c.max_value } : {}),
    })),
    initial_cash: form.initialCash,
    commission: form.commission,
    stake_pct: form.stakePct,
    ...(form.startDate ? { start_date: form.startDate } : {}),
    ...(form.endDate ? { end_date: form.endDate } : {}),
  }
}

async function runBacktest() {
  loading.value = true
  try {
    form.symbol = await resolveSymbol()
    if (mode.value === 'multi') {
      if (!multiForm.conditions.length) {
        showMockToast('请至少添加一个因子条件')
        return
      }
      result.value = await api.backtestMultiRun(buildMultiBody())
    } else {
      const body = buildClassicBody()
      body.symbol = form.symbol
      result.value = await api.backtestRun(body)
    }
    hasRun.value = true
  } catch (e) {
    showMockToast(e.message)
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.symbol = '600519.SH'
  form.strategy = 'ma_crossover'
  form.params = { fast: 5, slow: 20 }
  form.startDate = ''
  form.endDate = ''
  form.initialCash = 100000
  form.commission = 0.001
  form.stakePct = 95
  multiEditingIdx.value = -1
  multiForm.category = ''
  multiForm.pickerFactor = 'ROC20'
  multiForm.pickerMin = null
  multiForm.pickerMax = null
  multiForm.conditions = [
    { factor: 'ROC20', min_value: 0.95 },
    { factor: 'MA5', min_value: 1.0 },
  ]
  hasRun.value = false
  result.value = {}
  applyStrategyDefaults(currentStrategy.value)
}

function onMultiCategoryChange() {
  const list = multiFilteredFactors.value
  if (list.length && !list.find((f) => f.name === multiForm.pickerFactor)) {
    multiForm.pickerFactor = list[0].name
  }
}

function addMultiCondition() {
  if (!multiForm.pickerFactor) {
    showMockToast('请选择因子')
    return
  }
  if (
    (multiForm.pickerMin == null || multiForm.pickerMin === '')
    && (multiForm.pickerMax == null || multiForm.pickerMax === '')
  ) {
    showMockToast('请至少设置 min 或 max 阈值')
    return
  }
  if (multiForm.conditions.some((c) => c.factor === multiForm.pickerFactor)) {
    showMockToast('该因子已在条件列表中')
    return
  }
  multiForm.conditions.push({
    factor: multiForm.pickerFactor,
    min_value: multiForm.pickerMin != null && multiForm.pickerMin !== '' ? multiForm.pickerMin : null,
    max_value: multiForm.pickerMax != null && multiForm.pickerMax !== '' ? multiForm.pickerMax : null,
  })
  multiForm.pickerMin = null
  multiForm.pickerMax = null
}

function removeMultiCondition(idx) {
  if (multiEditingIdx.value === idx) multiEditingIdx.value = -1
  else if (multiEditingIdx.value > idx) multiEditingIdx.value -= 1
  multiForm.conditions.splice(idx, 1)
}

function isEmptyThreshold(cond) {
  return (cond.min_value == null || cond.min_value === '')
    && (cond.max_value == null || cond.max_value === '')
}

function normalizeThreshold(v) {
  return v != null && v !== '' ? v : null
}

function startEditMultiCondition(idx) {
  const cond = multiForm.conditions[idx]
  multiEditingIdx.value = idx
  multiEditDraft.factor = cond.factor
  multiEditDraft.min_value = cond.min_value ?? null
  multiEditDraft.max_value = cond.max_value ?? null
}

function cancelEditMultiCondition() {
  multiEditingIdx.value = -1
}

function saveEditMultiCondition() {
  const idx = multiEditingIdx.value
  if (idx < 0) return
  if (!multiEditDraft.factor) {
    showMockToast('请选择因子')
    return
  }
  const minVal = normalizeThreshold(multiEditDraft.min_value)
  const maxVal = normalizeThreshold(multiEditDraft.max_value)
  if (minVal == null && maxVal == null) {
    showMockToast('请至少设置 min 或 max 阈值')
    return
  }
  const duplicate = multiForm.conditions.find(
    (c, i) => i !== idx && c.factor === multiEditDraft.factor,
  )
  if (duplicate) {
    showMockToast('该因子已在条件列表中')
    return
  }
  multiForm.conditions[idx] = {
    factor: multiEditDraft.factor,
    min_value: minVal,
    max_value: maxVal,
  }
  multiEditingIdx.value = -1
}

function applyMultiPreset(preset) {
  multiEditingIdx.value = -1
  multiForm.conditions = preset.conditions.map((c) => ({ ...c }))
  mode.value = 'multi'
}

function fmtPct(v) {
  if (v == null || Number.isNaN(v)) return '—'
  return (v >= 0 ? '+' : '') + Number(v).toFixed(2) + '%'
}

function fmtSigned(v) {
  if (v == null) return '—'
  return (v >= 0 ? '+' : '') + Number(v).toFixed(2)
}

function fmtSignedPct(v) {
  if (v == null) return '—'
  return (v >= 0 ? '+' : '') + Number(v).toFixed(2) + '%'
}

function fmtMoney(v) {
  if (v == null) return '—'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

function returnColor(v) {
  if (v == null) return ''
  return v >= 0 ? 'var(--ok)' : 'var(--err)'
}

onMounted(() => {
  loadStrategies()
  loadFactorMeta()
})

watch(
  () => route.query.strategy,
  () => {
    if (route.name === 'Backtest' && route.query.strategy) {
      applyRouteStrategy()
    }
  },
)

watch(
  () => route.query.mode,
  () => {
    if (route.name === 'Backtest' && route.query.mode === 'multi') {
      mode.value = 'multi'
    }
  },
)
</script>

<style scoped>
.tab-row {
  display: flex;
  gap: 0.35rem;
  margin-bottom: 0.25rem;
}

.tab {
  padding: 0.45rem 1rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--muted);
  cursor: pointer;
  font-size: 0.875rem;
}

.tab.active {
  background: var(--accent-soft);
  color: var(--text);
  border-color: rgba(59, 130, 246, 0.35);
}

.screener-layout { align-items: start; }

.hint {
  margin: 0 0 1rem;
  color: var(--muted);
  font-size: 0.85rem;
}

.preset-hint {
  margin-top: 0.5rem;
  font-size: 0.8rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
}

.link-chip {
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--accent);
  font-size: 0.78rem;
  cursor: pointer;
}

.cond-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.cond-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.55rem 0.65rem;
  background: var(--surface2);
  border-radius: var(--radius-sm);
}

.cond-row.editing {
  align-items: stretch;
  padding: 0.65rem;
}

.cond-row-actions {
  display: flex;
  flex-shrink: 0;
  gap: 0.35rem;
}

.cond-edit {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.cond-edit-field { margin: 0; }
.cond-edit-thresholds { margin: 0; }

.cond-edit-actions {
  display: flex;
  gap: 0.4rem;
}

.cond-main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
}

.cond-threshold {
  font-size: 0.82rem;
  color: var(--accent);
}

.card-inset {
  padding: 0.75rem;
  margin-bottom: 1rem;
  background: var(--surface2);
  border-radius: var(--radius-sm);
}

.cond-add-title {
  margin: 0 0 0.65rem;
  font-size: 0.85rem;
  color: var(--muted);
}

.kline-card {
  padding: 0.75rem 1rem 1rem;
}

.kline-card .card-head {
  margin-bottom: 0.5rem;
}

.param-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.metrics-grid {
  margin-bottom: 1rem;
}

.equity-wrap h3 {
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
  color: var(--muted);
  font-weight: 500;
}

.empty-state {
  text-align: center;
  padding: 2.5rem 1rem;
  color: var(--muted);
}

.empty-state .icon {
  font-size: 2rem;
  margin-bottom: 0.5rem;
  opacity: 0.6;
}

.result-meta {
  margin: 0;
  font-size: 0.82rem;
}

.log-box {
  max-height: 200px;
  overflow: auto;
  font-family: var(--mono);
  font-size: 0.78rem;
}

.log-line {
  display: flex;
  gap: 0.75rem;
  padding: 0.25rem 0;
  border-bottom: 1px solid var(--border);
}

.log-time { color: var(--muted); min-width: 4rem; }
.log-msg { flex: 1; }

.up { color: var(--ok); }
.down { color: var(--err); }
</style>
