<template>
  <div class="stack">
    <div class="card toolbar-card">
      <div class="card-head">
        <h2>质量概览</h2>
        <div class="toolbar">
          <label class="stale-label">
            滞后阈值
            <select v-model.number="staleDays" @change="reload">
              <option :value="3">3 天</option>
              <option :value="5">5 天</option>
              <option :value="10">10 天</option>
              <option :value="20">20 天</option>
            </select>
          </label>
          <button class="btn sm ghost" :disabled="loading" @click="reload">
            {{ loading ? '刷新中…' : '刷新' }}
          </button>
        </div>
      </div>

      <div class="grid-4">
        <StatCard
          :value="summary.coverage_pct != null ? summary.coverage_pct + '%' : '—'"
          label="日 K 覆盖率"
          :hint="`${fmtNum(summary.symbols_with_daily)} / ${fmtNum(summary.listed_count)} 上市标的`"
          :value-color="coverageColor"
        />
        <StatCard
          :value="fmtNum(summary.latest_daily_date, 'date')"
          label="最新日 K 日期"
          :hint="`${fmtNum(summary.daily_rows)} 条日 K`"
        />
        <StatCard
          :value="fmtNum(summary.stale_symbols)"
          label="行情滞后标的"
          :hint="`较全局最新滞后 ≥ ${staleDays} 天`"
          :value-color="summary.stale_symbols > 0 ? 'var(--warn, #f59e0b)' : 'var(--ok)'"
        />
        <StatCard
          :value="fmtNum(totalIssues)"
          label="问题条目合计"
          :hint="`${breakdown.filter((b) => b.count > 0).length} 类问题有数据`"
          :value-color="totalIssues > 0 ? 'var(--err)' : 'var(--ok)'"
        />
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <h2>问题分类</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>类型</th>
                <th>严重度</th>
                <th>数量</th>
                <th>说明</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in breakdown"
                :key="item.type"
                :class="{ active: selectedType === item.type, muted: item.count === 0 }"
              >
                <td>{{ item.label }}</td>
                <td><span class="badge" :class="severityClass(item.severity)">{{ severityText(item.severity) }}</span></td>
                <td class="mono" :class="item.count > 0 ? 'count-warn' : ''">{{ item.count.toLocaleString() }}</td>
                <td class="desc muted">{{ item.description }}</td>
                <td>
                  <button
                    class="btn sm ghost"
                    :disabled="item.count === 0"
                    @click="selectIssue(item.type)"
                  >
                    查看
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h2>同步与元数据</h2>
        <div class="mini-stats">
          <div><span class="muted">近 7 天失败任务</span><strong :class="summary.failed_jobs_7d ? 'down' : ''">{{ fmtNum(summary.failed_jobs_7d) }}</strong></div>
          <div><span class="muted">近 7 天 error 日志</span><strong :class="summary.error_logs_7d ? 'down' : ''">{{ fmtNum(summary.error_logs_7d) }}</strong></div>
          <div><span class="muted">近 7 天 warn 日志</span><strong>{{ fmtNum(summary.warn_logs_7d) }}</strong></div>
          <div><span class="muted">无日 K（上市）</span><strong :class="summary.listed_no_kline ? 'down' : ''">{{ fmtNum(summary.listed_no_kline) }}</strong></div>
          <div><span class="muted">无效收盘价</span><strong :class="summary.invalid_close_rows ? 'down' : ''">{{ fmtNum(summary.invalid_close_rows) }}</strong></div>
          <div><span class="muted">OHLC 异常</span><strong :class="summary.ohlc_violation_rows ? 'down' : ''">{{ fmtNum(summary.ohlc_violation_rows) }}</strong></div>
          <div><span class="muted">零成交量 K 线</span><strong>{{ fmtNum(summary.zero_volume_rows) }}</strong></div>
          <div><span class="muted">孤儿 K 线标的</span><strong>{{ fmtNum(summary.orphan_symbols) }}</strong></div>
          <div><span class="muted">元数据缺失</span><strong>{{ fmtNum(summary.missing_metadata) }}</strong></div>
        </div>
      </div>
    </div>

    <div class="card cleanup-card">
      <div class="card-head">
        <h2>无效 K 线清理</h2>
        <p class="muted cleanup-desc">删除 close 为空/≤0/NaN 的占位行；可选同时清理 OHLC 逻辑异常</p>
      </div>
      <div class="cleanup-form">
        <label>
          标的（可选）
          <input v-model="cleanupSymbol" type="text" placeholder="留空=全库，如 001393.SZ" />
        </label>
        <label class="check-label">
          <input v-model="cleanupIncludeOhlc" type="checkbox" />
          含 OHLC 异常
        </label>
        <button class="btn sm ghost" :disabled="cleanupLoading" @click="previewCleanup">
          预览
        </button>
        <button
          class="btn sm danger"
          :disabled="cleanupLoading || !cleanupPreview"
          @click="runCleanup"
        >
          {{ cleanupLoading ? '处理中…' : '执行清理' }}
        </button>
      </div>
      <div v-if="cleanupPreview" class="cleanup-result">
        <span v-if="cleanupPreview.symbol" class="tag mono">{{ cleanupPreview.symbol }}</span>
        <span>日 K 将删 <strong>{{ cleanupPreview.preview.kline_daily.toLocaleString() }}</strong> 条</span>
        <span>分钟 K 将删 <strong>{{ cleanupPreview.preview.kline_intraday.toLocaleString() }}</strong> 条</span>
        <span class="muted">合计 {{ cleanupPreview.total.toLocaleString() }} 条</span>
      </div>
      <div v-if="cleanupResult && !cleanupResult.dry_run" class="cleanup-done">
        已删除：日 K {{ cleanupResult.deleted.kline_daily.toLocaleString() }} 条，
        分钟 K {{ cleanupResult.deleted.kline_intraday.toLocaleString() }} 条
      </div>
    </div>

    <div v-if="summary.intraday?.length" class="card">
      <h2>分钟线覆盖</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>周期</th>
              <th>行数</th>
              <th>标的数</th>
              <th>最新 Bar</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in summary.intraday" :key="row.period">
              <td class="mono">{{ row.period }}</td>
              <td>{{ Number(row.rows).toLocaleString() }}</td>
              <td>{{ Number(row.symbols).toLocaleString() }}</td>
              <td>{{ row.latest_bar ? fmtTime(row.latest_bar) : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <h2>问题明细 · {{ currentIssueLabel }}</h2>
        <div class="pager">
          <span class="muted">共 {{ issueTotal.toLocaleString() }} 条</span>
          <button class="btn sm ghost" :disabled="issuePage <= 1 || issueLoading" @click="prevPage">上一页</button>
          <span class="mono">第 {{ issuePage }} 页</span>
          <button class="btn sm ghost" :disabled="!hasNextPage || issueLoading" @click="nextPage">下一页</button>
        </div>
      </div>

      <div v-if="issueLoading" class="loading-hint muted">加载明细…</div>
      <div v-else-if="!issueRows.length" class="loading-hint muted">暂无此类问题记录</div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th v-for="col in issueColumns" :key="col">{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in issueRows" :key="idx">
              <td v-for="col in issueColumns" :key="col" :class="cellClass(col, row[col])">
                {{ formatCell(col, row[col]) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api/client'
import StatCard from '@/components/StatCard.vue'
import { showMockToast } from '@/mock'

const loading = ref(false)
const issueLoading = ref(false)
const staleDays = ref(5)
const summary = ref({})
const breakdown = ref([])
const selectedType = ref('stale')
const issueRows = ref([])
const issueTotal = ref(0)
const issuePage = ref(1)
const issuePageSize = 50

const cleanupSymbol = ref('')
const cleanupIncludeOhlc = ref(false)
const cleanupLoading = ref(false)
const cleanupPreview = ref(null)
const cleanupResult = ref(null)

const totalIssues = computed(() =>
  breakdown.value.reduce((s, b) => s + (b.count || 0), 0),
)

const coverageColor = computed(() => {
  const pct = summary.value.coverage_pct
  if (pct == null) return ''
  if (pct >= 95) return 'var(--ok)'
  if (pct >= 80) return 'var(--warn, #f59e0b)'
  return 'var(--err)'
})

const currentIssueLabel = computed(() =>
  breakdown.value.find((b) => b.type === selectedType.value)?.label || selectedType.value,
)

const hasNextPage = computed(() => issuePage.value * issuePageSize < issueTotal.value)

const issueColumns = computed(() => {
  if (!issueRows.value.length) return []
  return Object.keys(issueRows.value[0])
})

async function loadSummary() {
  loading.value = true
  try {
    const data = await api.dataQualitySummary({ stale_days: staleDays.value })
    summary.value = data.summary || {}
    breakdown.value = data.breakdown || []
    if (!breakdown.value.find((b) => b.type === selectedType.value && b.count > 0)) {
      const first = breakdown.value.find((b) => b.count > 0)
      if (first) selectedType.value = first.type
    }
  } catch (e) {
    showMockToast(e.message)
  } finally {
    loading.value = false
  }
}

async function loadIssues() {
  issueLoading.value = true
  try {
    const data = await api.dataQualityIssues({
      issue_type: selectedType.value,
      page: String(issuePage.value),
      page_size: String(issuePageSize),
      stale_days: String(staleDays.value),
    })
    issueRows.value = data.items || []
    issueTotal.value = data.total || 0
  } catch (e) {
    showMockToast(e.message)
  } finally {
    issueLoading.value = false
  }
}

async function reload() {
  issuePage.value = 1
  cleanupPreview.value = null
  cleanupResult.value = null
  await loadSummary()
  await loadIssues()
}

function cleanupParams() {
  const p = {}
  const sym = cleanupSymbol.value.trim()
  if (sym) p.symbol = sym
  if (cleanupIncludeOhlc.value) p.include_ohlc = 'true'
  return p
}

async function previewCleanup() {
  cleanupLoading.value = true
  cleanupResult.value = null
  try {
    cleanupPreview.value = await api.dataQualityCleanupPreview(cleanupParams())
  } catch (e) {
    showMockToast(e.message)
  } finally {
    cleanupLoading.value = false
  }
}

async function runCleanup() {
  if (!cleanupPreview.value?.total) {
    showMockToast('没有可清理的无效 K 线')
    return
  }
  if (!window.confirm(`确认删除 ${cleanupPreview.value.total.toLocaleString()} 条无效 K 线？此操作不可撤销。`)) {
    return
  }
  cleanupLoading.value = true
  try {
    const body = {
      dry_run: false,
      include_ohlc: cleanupIncludeOhlc.value,
    }
    const sym = cleanupSymbol.value.trim()
    if (sym) body.symbol = sym
    cleanupResult.value = await api.dataQualityCleanup(body)
    showMockToast('清理完成')
    cleanupPreview.value = null
    await reload()
  } catch (e) {
    showMockToast(e.message)
  } finally {
    cleanupLoading.value = false
  }
}

function selectIssue(type) {
  selectedType.value = type
  issuePage.value = 1
  loadIssues()
}

function prevPage() {
  if (issuePage.value <= 1) return
  issuePage.value -= 1
  loadIssues()
}

function nextPage() {
  if (!hasNextPage.value) return
  issuePage.value += 1
  loadIssues()
}

function fmtNum(v, mode) {
  if (v == null || v === '') return '—'
  if (mode === 'date') {
    return String(v).slice(0, 10)
  }
  return Number(v).toLocaleString()
}

function fmtTime(iso) {
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

function severityClass(s) {
  return { high: 'err', medium: 'warn', low: 'ok' }[s] || ''
}

function severityText(s) {
  return { high: '高', medium: '中', low: '低' }[s] || s
}

function formatCell(col, val) {
  if (val == null || val === '') return '—'
  if (col.includes('date') || col.endsWith('_at')) {
    return col.endsWith('_at') ? fmtTime(val) : String(val).slice(0, 10)
  }
  if (typeof val === 'number') {
    if (Number.isInteger(val)) return val.toLocaleString()
    return val.toFixed(4).replace(/\.?0+$/, '')
  }
  return String(val)
}

function cellClass(col, val) {
  if (col === 'symbol' || col === 'id' || col === 'job_id') return 'mono'
  if (col === 'days_stale' && val > 0) return 'down'
  return ''
}

onMounted(reload)
</script>

<style scoped>
.toolbar-card .card-head {
  margin-bottom: 0.75rem;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.stale-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.82rem;
  color: var(--muted);
  margin: 0;
}

.stale-label select {
  min-width: 88px;
}

.mini-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.85rem 1rem;
}

.mini-stats strong {
  display: block;
  font-size: 1.1rem;
  margin-top: 0.15rem;
}

@media (max-width: 768px) {
  .mini-stats { grid-template-columns: repeat(2, 1fr); }
}

tr.active {
  background: var(--accent-soft);
}

tr.muted td {
  opacity: 0.55;
}

.count-warn {
  color: var(--warn, #f59e0b);
  font-weight: 600;
}

.desc {
  font-size: 0.78rem;
  max-width: 280px;
}

.pager {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.82rem;
}

.loading-hint {
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.down { color: var(--err); }

.badge.warn {
  color: var(--warn, #f59e0b);
  border-color: rgba(245, 158, 11, 0.35);
}

.cleanup-desc {
  margin: 0;
  font-size: 0.82rem;
}

.cleanup-form {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 0.75rem;
}

.cleanup-form label {
  margin: 0;
  min-width: 180px;
}

.check-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  min-width: unset !important;
  font-size: 0.82rem;
  color: var(--muted);
  padding-bottom: 0.35rem;
}

.cleanup-result,
.cleanup-done {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem 1.25rem;
  margin-top: 0.85rem;
  padding-top: 0.85rem;
  border-top: 1px solid var(--border);
  font-size: 0.85rem;
}

.cleanup-done {
  color: var(--ok);
}
</style>
