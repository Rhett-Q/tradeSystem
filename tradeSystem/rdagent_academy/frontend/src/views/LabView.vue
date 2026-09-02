<template>
  <main class="shell page">
    <header class="page-head rise">
      <h1>实验室</h1>
      <p class="muted">L2 操作台：直接调用本机 <span class="mono">tradeSystem/scripts</span> 脚本。同一时间只允许一个 fin_factor 类任务。</p>
    </header>

    <div class="tabs rise">
      <button
        v-for="t in tabs"
        :key="t.id"
        type="button"
        class="tab"
        :class="{ active: panel === t.id }"
        @click="go(t.id)"
      >
        {{ t.label }}
      </button>
    </div>

    <div class="grid">
      <section class="main-panel rise rise-delay-1">
        <!-- Health -->
        <div v-if="panel === 'health'" class="panel">
          <div class="row-between">
            <div>
              <h2>健康检查</h2>
              <p class="muted">实时探测本机 RD-Agent 依赖。</p>
            </div>
            <div class="row-actions">
              <span class="tag" :class="health?.ready_to_learn ? 'ok' : 'bad'">
                {{ health?.ready_to_learn ? '可学习' : '学习未就绪' }}
              </span>
              <span class="tag" :class="health?.ready_to_run ? 'ok' : 'warn'">
                {{ health?.ready_to_run ? '可开跑' : '开跑未就绪' }}
              </span>
              <button class="btn ghost" :disabled="busy" @click="refreshHealth">刷新</button>
              <button class="btn" :disabled="busy" @click="runJob('health_cli')">跑 health_check</button>
            </div>
          </div>
          <ul class="checks">
            <li v-for="c in health?.checks || []" :key="c.id">
              <span class="dot" :class="c.ok ? 'ok' : 'bad'"></span>
              <div>
                <strong>{{ c.title }}</strong>
                <p class="muted">{{ c.ok ? c.detail : c.hint }}</p>
                <p v-if="c.extra" class="mono muted">{{ formatExtra(c.extra) }}</p>
              </div>
            </li>
          </ul>
        </div>

        <!-- Data -->
        <div v-else-if="panel === 'data'" class="panel">
          <h2>数据准备</h2>
          <p class="muted">新手优先官方 cn_data；要对齐生产再导出 PG。</p>
          <div class="action-grid">
            <button class="btn" :disabled="busy" @click="runJob('download_qlib')">下载官方 cn_data</button>
            <button class="btn" :disabled="busy" @click="runJob('prepare_factor_data')">预生成因子 HDF5</button>
            <button class="btn ghost" :disabled="busy" @click="runJob('export_pg')">PG → Qlib 导出</button>
          </div>
          <div class="paths mono muted" v-if="health">
            <div>cn_data: {{ health.paths.cn_data }}</div>
            <div>pg_export: {{ health.paths.pg_export }}</div>
          </div>
        </div>

        <!-- Run -->
        <div v-else-if="panel === 'run'" class="panel">
          <h2>运行台</h2>
          <p class="muted">
            新开跑会创建新的 log 目录；恢复从最新 checkpoint 继续。请先确认「可开跑」。
          </p>
          <div class="action-grid">
            <button class="btn" :disabled="busy || !health?.ready_to_run" @click="runJob('fin_factor')">
              新开跑 fin_factor
            </button>
            <button class="btn ghost" :disabled="busy || !health?.ready_to_run" @click="runJob('resume_factor')">
              恢复 fin_factor
            </button>
          </div>
          <p v-if="!health?.ready_to_run" class="warn-text">先到「健康检查」把 Docker / 数据 / LLM Key 变绿。</p>
          <div v-if="latest" class="latest mono">
            <div>最新 session: {{ latest.latest_session?.log_path || '无' }}</div>
            <div v-if="latest.latest_session">
              进度: {{ latest.latest_session.latest_step_label }}
              · 完成 {{ latest.latest_session.loops_completed }}/{{ latest.latest_session.loops_started }} 轮
            </div>
          </div>
        </div>

        <!-- Sessions -->
        <div v-else class="panel">
          <div class="row-between">
            <div>
              <h2>Sessions</h2>
              <p class="muted">浏览历史实验，打开官方 Streamlit 看图。</p>
            </div>
            <button class="btn ghost" @click="refreshSessions">刷新</button>
          </div>
          <div v-if="!sessions.length" class="muted">还没有 log session。</div>
          <ul class="sessions">
            <li v-for="s in sessions" :key="s.id" :class="{ active: selected === s.id }" @click="selectSession(s.id)">
              <strong class="mono">{{ s.id }}</strong>
              <span class="tag" :class="s.has_session ? 'ok' : 'warn'">
                {{ s.has_session ? `${s.progress?.loops_completed || 0} 轮完成` : '无 checkpoint' }}
              </span>
            </li>
          </ul>
          <div v-if="detail" class="detail">
            <div class="row-actions">
              <button class="btn" @click="openUi(detail.log_path)">打开 Streamlit UI</button>
            </div>
            <p class="muted">
              接受假设 {{ detail.accepted }}/{{ detail.total }}
            </p>
            <div v-for="f in detail.feedbacks" :key="f.loop" class="fb">
              <div class="fb-head">
                <strong>Loop {{ f.loop }}</strong>
                <span class="tag" :class="f.decision === true ? 'ok' : 'warn'">
                  decision={{ String(f.decision) }}
                </span>
              </div>
              <pre class="obs">{{ f.observations || f.error }}</pre>
            </div>
          </div>
        </div>
      </section>

      <aside class="side-panel rise rise-delay-2">
        <div class="panel job-panel">
          <div class="row-between">
            <h3>任务日志</h3>
            <button
              v-if="activeJob && activeJob.status === 'running'"
              class="btn danger"
              @click="cancelActive"
            >
              终止
            </button>
          </div>
          <p v-if="!activeJob" class="muted">尚未启动任务。操作后日志会出现在这里。</p>
          <template v-else>
            <div class="job-meta">
              <strong>{{ activeJob.title }}</strong>
              <span class="tag" :class="statusClass(activeJob.status)">{{ activeJob.status }}</span>
            </div>
            <pre class="log">{{ logText }}</pre>
          </template>
          <p v-if="jobError" class="error">{{ jobError }}</p>
        </div>
      </aside>
    </div>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'

const props = defineProps({
  panel: { type: String, default: 'health' },
})

const router = useRouter()
const tabs = [
  { id: 'health', label: '健康检查' },
  { id: 'data', label: '数据' },
  { id: 'run', label: '运行台' },
  { id: 'sessions', label: 'Sessions' },
]

const panel = computed(() => {
  const p = props.panel || 'health'
  return tabs.some((t) => t.id === p) ? p : 'health'
})

const health = ref(null)
const sessions = ref([])
const latest = ref(null)
const selected = ref('')
const detail = ref(null)
const activeJob = ref(null)
const logText = ref('')
const jobError = ref('')
const busy = computed(() => activeJob.value?.status === 'running')

let pollTimer = null
let fromLine = 0

function go(id) {
  router.push(`/lab/${id}`)
}

function formatExtra(extra) {
  if (!extra || typeof extra !== 'object') return ''
  if (extra.days) return `${extra.days} days · ${extra.from} → ${extra.to}`
  if (extra.symbols_exported != null) {
    return `exported ${extra.symbols_exported} symbols · ${extra.date_from} → ${extra.date_to}`
  }
  return JSON.stringify(extra)
}

function statusClass(s) {
  if (s === 'succeeded') return 'ok'
  if (s === 'failed' || s === 'cancelled') return 'bad'
  return 'warn'
}

async function refreshHealth() {
  health.value = await api.health()
}

async function refreshSessions() {
  const data = await api.sessions()
  sessions.value = data.sessions || []
  latest.value = data.latest || null
}

async function selectSession(id) {
  selected.value = id
  detail.value = await api.session(id)
}

async function openUi(logPath) {
  jobError.value = ''
  try {
    const res = await api.openUi(logPath)
    jobError.value = res.message + ' → ' + res.url
  } catch (e) {
    jobError.value = e.message || String(e)
  }
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function pollJob() {
  if (!activeJob.value) return
  try {
    const data = await api.job(activeJob.value.id, fromLine)
    activeJob.value = data
    if (data.log_chunk) logText.value += data.log_chunk
    fromLine = data.next_line || fromLine
    if (data.status !== 'running') {
      stopPoll()
      await refreshHealth()
      await refreshSessions()
    }
  } catch (e) {
    jobError.value = e.message || String(e)
    stopPoll()
  }
}

async function runJob(kind) {
  jobError.value = ''
  try {
    const job = await api.startJob(kind)
    activeJob.value = job
    logText.value = job.log_tail || ''
    fromLine = job.log_lines || 0
    stopPoll()
    pollTimer = setInterval(pollJob, 1200)
    await pollJob()
  } catch (e) {
    jobError.value = e.message || String(e)
  }
}

async function cancelActive() {
  if (!activeJob.value) return
  try {
    await api.cancelJob(activeJob.value.id)
    await pollJob()
  } catch (e) {
    jobError.value = e.message || String(e)
  }
}

onMounted(async () => {
  try {
    await refreshHealth()
    await refreshSessions()
  } catch (e) {
    jobError.value = e.message || String(e)
  }
})

watch(
  () => props.panel,
  async (p) => {
    if (p === 'sessions' || p === 'run') await refreshSessions()
  },
)

onBeforeUnmount(stopPoll)
</script>

<style scoped>
.page {
  padding: 2rem 0 3.5rem;
}

.page-head {
  margin-bottom: 1rem;
  max-width: 46rem;
}

.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 1rem;
}

.tab {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--muted);
  border-radius: 999px;
  padding: 0.45rem 0.9rem;
  cursor: pointer;
}

.tab.active {
  background: var(--accent);
  color: var(--ink);
  border-color: transparent;
  font-weight: 600;
}

.grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.9fr);
  gap: 1rem;
  align-items: start;
}

.row-between {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
}

.checks {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.75rem;
}

.checks li {
  display: grid;
  grid-template-columns: 14px 1fr;
  gap: 0.75rem;
}

.dot {
  width: 10px;
  height: 10px;
  margin-top: 0.45rem;
  border-radius: 50%;
  background: var(--danger);
  animation: pulse-dot 2.2s ease infinite;
}

.dot.ok {
  background: var(--ok);
}

.action-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin: 1rem 0;
}

.paths {
  display: grid;
  gap: 0.35rem;
}

.warn-text {
  color: var(--warn);
}

.latest {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--line);
  display: grid;
  gap: 0.35rem;
}

.sessions {
  list-style: none;
  margin: 0.75rem 0;
  padding: 0;
  display: grid;
  gap: 0.4rem;
  max-height: 240px;
  overflow: auto;
}

.sessions li {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--line);
  border-radius: 10px;
  cursor: pointer;
}

.sessions li.active,
.sessions li:hover {
  border-color: rgba(226, 180, 87, 0.45);
}

.detail {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--line);
}

.fb {
  margin-top: 0.75rem;
}

.fb-head {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  margin-bottom: 0.35rem;
}

.obs {
  margin: 0;
  white-space: pre-wrap;
  background: rgba(0, 0, 0, 0.28);
  border-radius: 8px;
  padding: 0.65rem 0.75rem;
  font-family: var(--font-mono);
  font-size: 0.78rem;
  max-height: 160px;
  overflow: auto;
}

.job-meta {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  margin-bottom: 0.65rem;
}

.log {
  margin: 0;
  min-height: 280px;
  max-height: 520px;
  overflow: auto;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.75rem;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  white-space: pre-wrap;
}

.error {
  color: var(--danger);
  margin-top: 0.75rem;
}

@media (max-width: 960px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>