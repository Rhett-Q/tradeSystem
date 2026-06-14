<template>
  <div class="stack">
    <div class="card">
      <div class="card-head">
        <h2>同步任务</h2>
        <div class="btn-row" style="margin: 0">
          <select v-model="statusFilter">
            <option value="">全部状态</option>
            <option value="running">运行中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
          </select>
          <button class="btn sm ghost" @click="refresh">刷新</button>
        </div>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>任务 ID</th>
              <th>类型</th>
              <th>周期</th>
              <th>状态</th>
              <th>进度</th>
              <th>标的</th>
              <th>开始时间</th>
              <th>消息</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="job in filteredJobs"
              :key="job.id"
              :class="{ selected: selectedJob === job.id }"
              @click="viewLog(job.id)"
            >
              <td class="mono" :title="job.id">{{ job.id.slice(0, 8) }}…</td>
              <td><span class="tag">{{ job.type === 'full' ? '全量' : '增量' }}</span></td>
              <td>{{ job.period }}</td>
              <td><span class="badge" :class="statusClass(job.status)"><span class="dot"></span>{{ statusText(job.status) }}</span></td>
              <td style="min-width: 120px">
                <div class="progress-bar"><span :style="{ width: job.progress + '%' }"></span></div>
                <span class="muted">{{ job.progress }}%</span>
              </td>
              <td>{{ job.symbols_done }} / {{ job.symbols_total }}</td>
              <td>{{ fmtTime(job.started_at) }}</td>
              <td class="msg-cell" :title="job.message">{{ job.message }}</td>
              <td @click.stop>
                <button v-if="job.status === 'running'" class="btn sm danger" @click="cancel(job.id)">取消</button>
                <button v-else class="btn sm ghost" @click="viewLog(job.id)">日志</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <h2>任务日志 {{ selectedJob ? `· ${selectedJob.slice(0, 8)}…` : '' }}</h2>
        <label class="filter-errors">
          <input v-model="errorsOnly" type="checkbox" /> 仅看 error / warn
        </label>
      </div>
      <p class="hint">完整堆栈另见 <code class="mono">backend/logs/sync.log</code></p>
      <div class="log-box">
        <div
          v-for="(line, i) in displayLogs"
          :key="i"
          class="log-line"
          :class="line.level"
        >
          <span class="log-time">{{ line.time }}</span>
          <span class="log-level">[{{ line.level }}]</span>
          <span v-if="line.symbol" class="log-symbol">{{ line.symbol }}</span>
          <pre class="log-msg">{{ line.message }}</pre>
        </div>
        <p v-if="!displayLogs.length" class="muted">点击任务行查看日志；失败任务会自动加载</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { api } from '@/api/client'
import { showMockToast } from '@/mock'

const statusFilter = ref('')
const jobs = ref([])
const logLines = ref([])
const selectedJob = ref('')
const errorsOnly = ref(false)
let pollTimer = null

const filteredJobs = computed(() => {
  if (!statusFilter.value) return jobs.value
  return jobs.value.filter((j) => j.status === statusFilter.value)
})

const displayLogs = computed(() => {
  if (!errorsOnly.value) return logLines.value
  return logLines.value.filter((l) => l.level === 'error' || l.level === 'warn' || l.level === 'warning')
})

function statusClass(s) {
  return { completed: 'ok', running: 'info', failed: 'err', cancelled: 'warn' }[s] || ''
}

function statusText(s) {
  return { completed: '已完成', running: '运行中', failed: '失败', cancelled: '已取消', pending: '等待' }[s] || s
}

function fmtTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

async function refresh() {
  try {
    jobs.value = await api.listJobs()
    const running = jobs.value.find((j) => j.status === 'running')
    if (running && !selectedJob.value) {
      viewLog(running.id)
    }
  } catch (e) {
    showMockToast(e.message)
  }
}

async function cancel(id) {
  try {
    const res = await api.cancelJob(id)
    showMockToast(res.message)
    refresh()
  } catch (e) {
    showMockToast(e.message)
  }
}

async function viewLog(id) {
  selectedJob.value = id
  try {
    logLines.value = await api.jobLogs(id)
  } catch (e) {
    showMockToast(e.message)
  }
}

watch(statusFilter, async (val) => {
  if (val === 'failed') {
    const failed = jobs.value.find((j) => j.status === 'failed')
    if (failed) await viewLog(failed.id)
  }
})

onMounted(async () => {
  await refresh()
  const failed = jobs.value.find((j) => j.status === 'failed')
  if (failed) {
    statusFilter.value = 'failed'
    await viewLog(failed.id)
  }
  pollTimer = setInterval(refresh, 5000)
})

onUnmounted(() => clearInterval(pollTimer))
</script>

<style scoped>
.msg-cell { max-width: 220px; overflow: hidden; text-overflow: ellipsis; }

tr.selected td { background: rgba(59, 130, 246, 0.08); }
tbody tr { cursor: pointer; }

.filter-errors {
  flex-direction: row;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.82rem;
  color: var(--muted);
  margin: 0;
}
.filter-errors input { width: auto; }

.log-box {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.75rem;
  font-family: var(--mono);
  font-size: 0.78rem;
  max-height: 420px;
  overflow: auto;
}

.log-line {
  padding: 0.35rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  color: var(--muted);
}
.log-line.warn, .log-line.warning { color: var(--warn); }
.log-line.error { color: var(--err); }

.log-time { color: var(--muted); margin-right: 0.5rem; white-space: nowrap; }
.log-level { margin-right: 0.5rem; font-weight: 600; }
.log-symbol {
  display: inline-block;
  margin-right: 0.5rem;
  padding: 0 0.35rem;
  background: var(--surface3);
  border-radius: 3px;
  color: var(--text);
}

.log-msg {
  margin: 0.25rem 0 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: inherit;
  font-size: inherit;
  color: inherit;
}
</style>
