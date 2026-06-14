<template>
  <div class="stack">
    <div class="grid-2">
      <div class="card">
        <h2>同步配置</h2>
        <p class="hint">通过 MiniQMT xtquant 下载历史 K 线，写入 PostgreSQL。</p>

        <label>同步模式
          <select v-model="form.mode">
            <option value="full">全量同步</option>
            <option value="incremental">增量同步</option>
          </select>
        </label>

        <label>K 线周期
          <select v-model="form.period">
            <option value="1d">日线 1d</option>
            <option value="5m">5 分钟 5m</option>
            <option value="15m">15 分钟 15m</option>
            <option value="30m">30 分钟 30m</option>
            <option value="1h">60 分钟 1h</option>
          </select>
        </label>
        <p class="hint">周线/月线在 K 线页由日 K 自动重采样，无需单独同步。</p>

        <label v-if="form.mode === 'full'">起始日期 (YYYYMMDD)
          <input v-model="form.startDate" type="text" placeholder="20200101" />
        </label>

        <label>批大小
          <input v-model.number="form.batchSize" type="number" min="50" max="500" />
        </label>

        <div class="btn-row">
          <button class="btn primary" :disabled="starting" @click="startSync">
            {{ starting ? '提交中…' : '开始同步' }}
          </button>
          <button class="btn ghost" @click="resetForm">重置</button>
        </div>
      </div>

      <div class="card">
        <h2>当前任务</h2>
        <div v-if="currentJob" class="current-job">
          <div class="card-head">
            <span class="mono">{{ currentJob.id.slice(0, 8) }}…</span>
            <span class="badge info"><span class="dot"></span>运行中</span>
          </div>
          <p>{{ currentJob.message }}</p>
          <div class="progress-bar"><span :style="{ width: currentJob.progress + '%' }"></span></div>
          <p class="muted">
            {{ currentJob.symbols_done }} / {{ currentJob.symbols_total }} 标的 · {{ currentJob.progress }}%
          </p>
        </div>
        <div v-else class="empty-state">
          <div class="icon">⏸</div>
          <p>暂无运行中的同步任务</p>
        </div>
      </div>
    </div>

    <div class="card">
      <h2>同步说明</h2>
      <ul class="doc-list">
        <li><strong>全量同步</strong>：从起始日期下载全部标的 K 线，适合首次部署。</li>
        <li><strong>增量同步</strong>：仅补全最新交易日数据，适合日常维护。</li>
        <li>数据流：MiniQMT download → Python 批处理 → PostgreSQL UPSERT。</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'
import { showMockToast } from '@/mock'

const route = useRoute()
const starting = ref(false)
const jobs = ref([])
let pollTimer = null

const form = reactive({
  mode: 'incremental',
  period: '1d',
  startDate: '20200101',
  batchSize: 200,
})

const currentJob = computed(() => jobs.value.find((j) => j.status === 'running'))

async function loadJobs() {
  try {
    jobs.value = await api.listJobs()
  } catch (_) { /* ignore */ }
}

async function startSync() {
  starting.value = true
  try {
    const res = await api.startSync({
      mode: form.mode,
      period: form.period,
      start_date: form.startDate,
      batch_size: form.batchSize,
    })
    showMockToast(res.message)
    await loadJobs()
  } catch (e) {
    showMockToast(e.message)
  } finally {
    starting.value = false
  }
}

function resetForm() {
  form.mode = 'incremental'
  form.period = '1d'
  form.startDate = '20200101'
  form.batchSize = 200
}

onMounted(() => {
  if (route.query.mode === 'full') form.mode = 'full'
  loadJobs()
  pollTimer = setInterval(loadJobs, 5000)
})

onUnmounted(() => clearInterval(pollTimer))
</script>

<style scoped>
.current-job { margin-top: 0.25rem; }

.doc-list {
  margin: 0.5rem 0 0 1.1rem;
  color: var(--muted);
  font-size: 0.875rem;
}

.doc-list li { margin-bottom: 0.45rem; }
</style>
