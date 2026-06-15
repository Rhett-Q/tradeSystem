<template>
  <div class="stack">
    <div class="tab-row">
      <button class="tab" :class="{ active: tab === 'ic' }" @click="tab = 'ic'">因子 IC</button>
      <button class="tab" :class="{ active: tab === 'train' }" @click="tab = 'train'">模型训练</button>
      <button class="tab" :class="{ active: tab === 'predict' }" @click="tab = 'predict'">模型预测</button>
    </div>

    <div class="grid-2 screener-layout">
      <div class="card">
        <h2>{{ tabTitle }}</h2>
        <p class="hint">{{ tabHint }}</p>

        <label>因子库
          <select v-model="form.library" @change="onLibraryChange">
            <option v-for="lib in libraries" :key="lib.id" :value="lib.id">
              {{ lib.label }} ({{ lib.factor_count }})
            </option>
          </select>
        </label>

        <template v-if="tab === 'ic'">
          <label>因子
            <select v-model="form.factor">
              <option v-for="f in factors" :key="f.name" :value="f.name">{{ f.name }}</option>
            </select>
          </label>
          <div class="row-2">
            <label>开始日期<input v-model="form.startDate" type="date" /></label>
            <label>结束日期<input v-model="form.endDate" type="date" /></label>
          </div>
          <label>前瞻收益（交易日）<input v-model.number="form.forwardDays" type="number" min="1" max="20" /></label>
        </template>

        <template v-else-if="tab === 'train'">
          <div class="row-2">
            <label>开始日期<input v-model="form.startDate" type="date" /></label>
            <label>结束日期<input v-model="form.endDate" type="date" /></label>
          </div>
          <label>标签天数<input v-model.number="form.labelDays" type="number" min="1" max="20" /></label>
          <label>最大标的数<input v-model.number="form.maxSymbols" type="number" min="100" max="3000" step="100" /></label>
          <p class="hint">留空因子列表则使用该库全部因子（Alpha360 训练较慢）。</p>
        </template>

        <template v-else>
          <label>已训练模型
            <select v-model="form.modelId">
              <option value="">请选择</option>
              <option v-for="m in models" :key="m.id" :value="m.id">
                {{ m.id }} · {{ m.library_id }} · {{ m.samples }} 样本
              </option>
            </select>
          </label>
          <label>Top N<input v-model.number="form.topN" type="number" min="10" max="200" /></label>
        </template>

        <label>市场
          <select v-model="form.market">
            <option value="">全部</option>
            <option value="SH">上海 SH</option>
            <option value="SZ">深圳 SZ</option>
            <option value="BJ">北京 BJ</option>
          </select>
        </label>

        <label>板块
          <select v-model="form.sector">
            <option value="">全部</option>
            <option v-for="s in sectors" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>

        <div class="btn-row">
          <button class="btn primary" :disabled="loading" @click="runAction">
            {{ loading ? '计算中…' : actionLabel }}
          </button>
          <button v-if="tab === 'predict'" class="btn ghost" @click="loadModels">刷新模型</button>
        </div>
      </div>

      <div class="card">
        <h2>结果</h2>

        <div v-if="tab === 'ic' && icResult.ic_mean != null" class="metrics">
          <div class="metric"><span class="label">IC 均值</span><strong>{{ icResult.ic_mean }}</strong></div>
          <div class="metric"><span class="label">IC 标准差</span><strong>{{ icResult.ic_std }}</strong></div>
          <div class="metric"><span class="label">IC_IR</span><strong>{{ icResult.ic_ir ?? '—' }}</strong></div>
          <div class="metric"><span class="label">IC&gt;0 占比</span><strong>{{ formatPct(icResult.ic_positive_ratio) }}</strong></div>
          <div class="metric"><span class="label">多空 spread</span><strong>{{ icResult.long_short_spread ?? '—' }}</strong></div>
        </div>

        <div v-if="tab === 'ic' && icResult.quintile_returns?.length" class="quintile-chart">
          <p class="hint">分组平均前瞻收益（Q1 低因子值 → Q5 高因子值）</p>
          <div v-for="q in icResult.quintile_returns" :key="q.group" class="bar-row">
            <span class="bar-label">{{ q.label }}</span>
            <div class="bar-track">
              <div
                class="bar-fill"
                :style="{ width: barWidth(q.mean_return), background: barColor(q.mean_return) }"
              />
            </div>
            <span class="bar-val mono">{{ formatReturn(q.mean_return) }}</span>
          </div>
        </div>

        <div v-if="tab === 'train' && trainResult.id" class="metrics">
          <div class="metric"><span class="label">模型 ID</span><strong class="mono">{{ trainResult.id }}</strong></div>
          <div class="metric"><span class="label">后端</span><strong>{{ trainResult.backend }}</strong></div>
          <div class="metric"><span class="label">验证 IC</span><strong>{{ trainResult.valid_ic ?? '—' }}</strong></div>
          <div class="metric"><span class="label">验证 MSE</span><strong>{{ trainResult.valid_mse }}</strong></div>
          <div class="metric"><span class="label">样本</span><strong>{{ trainResult.samples?.toLocaleString() }}</strong></div>
          <div class="metric"><span class="label">标的</span><strong>{{ trainResult.symbols }}</strong></div>
        </div>

        <div v-if="tab === 'train' && trainError" class="train-error">
          <p class="error-msg">{{ trainError }}</p>
        </div>

        <div v-if="tab === 'train' && trainLog.length" class="train-log">
          <button type="button" class="btn sm ghost train-log-toggle" @click="trainLogExpanded = !trainLogExpanded">
            {{ trainLogExpanded ? '收起' : '展开' }}训练日志
            <span v-if="trainStats.total_ms != null" class="muted">· {{ trainStats.total_ms }}ms</span>
          </button>
          <div v-show="trainLogExpanded" class="train-log-body">
            <div
              v-for="(entry, idx) in trainLog"
              :key="'train-log-' + idx"
              class="log-line"
              :class="entry.level"
            >
              <span class="log-time muted">{{ entry.elapsed_ms }}ms</span>
              <span class="log-msg">{{ entry.message }}</span>
            </div>
          </div>
        </div>

        <div v-if="tab === 'predict' && predictResult.rows?.length" class="table-wrap">
          <p class="hint">共 {{ predictResult.total }} 只 · 展示 Top {{ predictResult.top_n }}</p>
          <table>
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th>预测分</th>
                <th>收盘</th>
                <th>日期</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in predictResult.rows" :key="row.symbol">
                <td class="mono">{{ row.symbol }}</td>
                <td>{{ row.name }}</td>
                <td class="mono">{{ row.score?.toFixed(6) }}</td>
                <td>{{ row.close?.toFixed(2) ?? '—' }}</td>
                <td class="muted">{{ row.trade_date }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="!loading && !hasResult && tab === 'train' && !trainLog.length" class="empty-state">
          <div class="icon">📊</div>
          <p>配置参数后点击「开始训练」</p>
        </div>

        <div v-if="!loading && !hasResult && tab !== 'train'" class="empty-state">
          <div class="icon">📊</div>
          <p>配置参数后点击运行</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '@/api/client'

const tab = ref('ic')
const loading = ref(false)
const sectors = ref([])
const libraries = ref([
  { id: 'alpha158', label: 'Alpha158', factor_count: 158 },
  { id: 'alpha360', label: 'Alpha360', factor_count: 360 },
])
const factors = ref([])
const models = ref([])
const icResult = ref({})
const trainResult = ref({})
const predictResult = ref({})
const trainLog = ref([])
const trainStats = ref({})
const trainError = ref('')
const trainLogExpanded = ref(true)

const today = new Date()
const defaultEnd = today.toISOString().slice(0, 10)
const defaultStart = new Date(today.getTime() - 180 * 86400000).toISOString().slice(0, 10)

const form = reactive({
  library: 'alpha158',
  factor: 'ROC20',
  startDate: defaultStart,
  endDate: defaultEnd,
  forwardDays: 5,
  labelDays: 5,
  maxSymbols: 800,
  market: '',
  sector: '',
  modelId: '',
  topN: 50,
})

const tabTitle = computed(() => ({
  ic: '因子 IC / 分组分析',
  train: 'LightGBM 训练',
  predict: '模型预测选股',
}[tab.value]))

const tabHint = computed(() => ({
  ic: '基于 PG 面板数据计算截面 Spearman IC 与五分组收益，不依赖 qlib.init()。',
  train: '使用 Alpha158/360 特征训练回归模型，预测 N 日前瞻收益。未安装 LightGBM 时回退 sklearn。',
  predict: '加载已保存模型，对全市场最新截面打分并排序。',
}[tab.value]))

const actionLabel = computed(() => ({
  ic: '计算 IC',
  train: '开始训练',
  predict: '运行预测',
}[tab.value]))

const hasResult = computed(() => {
  if (tab.value === 'ic') return icResult.value.ic_mean != null
  if (tab.value === 'train') return !!trainResult.value.id
  return (predictResult.value.rows?.length || 0) > 0
})

function applyTrainLog(payload) {
  trainLog.value = payload?.log || []
  trainStats.value = payload?.stats || {}
}

function formatPct(v) {
  if (v == null) return '—'
  return `${(v * 100).toFixed(1)}%`
}

function formatReturn(v) {
  if (v == null) return '—'
  return `${(v * 100).toFixed(3)}%`
}

function barWidth(v) {
  if (v == null) return '0%'
  const pct = Math.min(100, Math.abs(v) * 2000)
  return `${Math.max(4, pct)}%`
}

function barColor(v) {
  if (v == null) return 'var(--muted)'
  return v >= 0 ? 'var(--success, #22c55e)' : 'var(--danger, #ef4444)'
}

async function loadLibraries() {
  try {
    const data = await api.qlibLibraries()
    if (data.libraries?.length) libraries.value = data.libraries
  } catch { /* noop */ }
}

async function loadFactors() {
  try {
    const data = await api.qlibFactors({ library: form.library })
    factors.value = data.factors || []
    const fallback = form.library === 'alpha360' ? 'CLOSE5' : 'ROC20'
    if (!factors.value.find((f) => f.name === form.factor)) {
      form.factor = factors.value[0]?.name || fallback
    }
  } catch {
    factors.value = []
  }
}

async function loadSectors() {
  try {
    sectors.value = await api.screenerSectors()
  } catch {
    sectors.value = []
  }
}

async function loadModels() {
  try {
    const data = await api.qlibModels()
    models.value = data.models || []
    if (!form.modelId && models.value.length) form.modelId = models.value[0].id
  } catch {
    models.value = []
  }
}

async function onLibraryChange() {
  await loadFactors()
}

async function runAction() {
  loading.value = true
  trainError.value = ''
  if (tab.value === 'train') {
    trainResult.value = {}
    trainLog.value = []
    trainStats.value = {}
  }
  try {
    if (tab.value === 'ic') {
      icResult.value = await api.qlibFactorIc({
        factor: form.factor,
        library: form.library,
        start_date: form.startDate,
        end_date: form.endDate,
        forward_days: String(form.forwardDays),
        market: form.market,
        sector: form.sector,
      })
    } else if (tab.value === 'train') {
      const result = await api.qlibTrain({
        library: form.library,
        factors: [],
        start_date: form.startDate,
        end_date: form.endDate,
        label_days: form.labelDays,
        market: form.market,
        sector: form.sector,
        max_symbols: form.maxSymbols,
      })
      trainResult.value = result
      applyTrainLog(result)
      await loadModels()
      if (trainResult.value.id) form.modelId = trainResult.value.id
    } else {
      if (!form.modelId) throw new Error('请选择模型')
      predictResult.value = await api.qlibPredict({
        model_id: form.modelId,
        market: form.market,
        sector: form.sector,
        top_n: form.topN,
      })
    }
  } catch (e) {
    if (tab.value === 'train' && e.detail) {
      trainError.value = e.detail.message || e.message
      applyTrainLog(e.detail)
      trainLogExpanded.value = true
    } else {
      trainError.value = e.message
      window.alert(e.message)
    }
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadLibraries(), loadFactors(), loadSectors(), loadModels()])
})
</script>

<style scoped>
.stack { display: flex; flex-direction: column; gap: 1rem; }

.tab-row {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.tab {
  padding: 0.45rem 1rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface2);
  cursor: pointer;
}

.tab.active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

.screener-layout { align-items: start; }

.hint {
  margin: 0 0 1rem;
  color: var(--muted);
  font-size: 0.85rem;
}

.row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.btn-row {
  display: flex;
  gap: 0.5rem;
  margin-top: 1rem;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.metric {
  padding: 0.75rem;
  background: var(--surface2);
  border-radius: 8px;
}

.metric .label {
  display: block;
  font-size: 0.75rem;
  color: var(--muted);
  margin-bottom: 0.25rem;
}

.quintile-chart { margin-top: 1rem; }

.bar-row {
  display: grid;
  grid-template-columns: 2rem 1fr 4.5rem;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}

.bar-track {
  height: 10px;
  background: var(--surface2);
  border-radius: 4px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 4px;
}

.bar-val { font-size: 0.8rem; text-align: right; }

.empty-state {
  text-align: center;
  padding: 2rem;
  color: var(--muted);
}

.empty-state .icon { font-size: 2rem; margin-bottom: 0.5rem; }

.train-error {
  margin: 0.75rem 0;
  padding: 0.75rem;
  background: rgba(239, 68, 68, 0.08);
  border-radius: 8px;
  border: 1px solid rgba(239, 68, 68, 0.25);
}

.error-msg {
  margin: 0;
  color: var(--danger, #ef4444);
  font-size: 0.9rem;
}

.train-log { margin-top: 1rem; }

.train-log-toggle { margin-bottom: 0.5rem; }

.train-log-body {
  max-height: 320px;
  overflow-y: auto;
  padding: 0.5rem;
  background: var(--surface2);
  border-radius: 8px;
  font-size: 0.8rem;
}

.log-line {
  display: flex;
  gap: 0.5rem;
  padding: 0.2rem 0;
  line-height: 1.4;
}

.log-line.warn .log-msg { color: var(--warn, #d97706); }
.log-line.error .log-msg { color: var(--danger, #ef4444); }

.log-time { flex-shrink: 0; width: 4.5rem; text-align: right; font-size: 0.75rem; }
</style>
