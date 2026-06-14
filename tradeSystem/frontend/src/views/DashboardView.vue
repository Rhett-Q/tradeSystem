<template>
  <div class="stack">
    <div class="grid-4">
      <StatCard :value="formatNum(health.universe_count)" label="标的数量" hint="全 A 股 universe" />
      <StatCard :value="formatNum(health.kline_rows)" label="K 线记录" hint="PostgreSQL 合计" value-color="var(--accent)" />
      <StatCard :value="runningJobs" label="运行中任务" :hint="lastSyncText" value-color="var(--warn)" />
      <StatCard :value="health.postgres_connected ? '在线' : '离线'" label="数据库" :hint="health.postgres_host" />
    </div>

    <div class="grid-2">
      <div class="card">
        <h2>数据管道</h2>
        <div class="pipeline">
          <div class="pipe-node">
            <span class="pipe-icon">📡</span>
            <strong>MiniQMT</strong>
            <span class="badge" :class="health.minqmt_connected ? 'ok' : 'err'">
              <span class="dot"></span>{{ health.minqmt_connected ? '已连接' : '未连接' }}
            </span>
            <p class="muted">xtquant · 行情下载</p>
          </div>
          <div class="pipe-arrow">→</div>
          <div class="pipe-node">
            <span class="pipe-icon">⚙</span>
            <strong>同步引擎</strong>
            <span class="badge info"><span class="dot"></span>Python</span>
            <p class="muted">全量 / 增量 · 批处理</p>
          </div>
          <div class="pipe-arrow">→</div>
          <div class="pipe-node">
            <span class="pipe-icon">🗄</span>
            <strong>PostgreSQL</strong>
            <span class="badge" :class="health.postgres_connected ? 'ok' : 'err'">
              <span class="dot"></span>{{ health.postgres_connected ? '已连接' : '未连接' }}
            </span>
            <p class="muted">K 线 · 元数据 · 任务</p>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-head">
          <h2>最近任务</h2>
          <RouterLink to="/tasks" class="btn sm ghost">查看全部</RouterLink>
        </div>
        <div v-for="job in recentJobs" :key="job.id" class="job-row">
          <div>
            <span class="mono">{{ job.id.slice(0, 8) }}…</span>
            <span class="tag">{{ job.type === 'full' ? '全量' : '增量' }}</span>
            <span class="tag">{{ job.period }}</span>
          </div>
          <span class="badge" :class="statusClass(job.status)">
            <span class="dot"></span>{{ statusText(job.status) }}
          </span>
        </div>
        <p v-if="!recentJobs.length" class="muted">暂无任务记录</p>
      </div>
    </div>

    <div class="card">
      <h2>快捷操作</h2>
      <div class="btn-row">
        <button class="btn primary" @click="goSync('full')">全量同步</button>
        <button class="btn" @click="goSync('incr')">增量同步</button>
        <RouterLink to="/market" class="btn ghost">查询 K 线</RouterLink>
        <RouterLink to="/settings" class="btn ghost">系统设置</RouterLink>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import StatCard from '@/components/StatCard.vue'
import { showMockToast } from '@/mock'

const router = useRouter()
const health = ref({ universe_count: 0, kline_rows: 0, postgres_connected: false, postgres_host: '', last_sync_at: null, minqmt_connected: false })
const jobs = ref([])

const recentJobs = computed(() => jobs.value.slice(0, 3))
const runningJobs = computed(() => jobs.value.filter((j) => j.status === 'running').length)
const lastSyncText = computed(() => {
  if (!health.value.last_sync_at) return '尚未同步'
  return `上次同步 ${new Date(health.value.last_sync_at).toLocaleString('zh-CN')}`
})

async function load() {
  try {
    health.value = await api.health()
    jobs.value = await api.listJobs()
  } catch (e) {
    showMockToast(e.message)
  }
}

function formatNum(n) {
  if (!n) return '0'
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (n >= 1e4) return (n / 1e4).toFixed(1) + '万'
  return String(n)
}

function statusClass(s) {
  return { completed: 'ok', running: 'info', failed: 'err', pending: 'warn', cancelled: 'warn' }[s] || ''
}

function statusText(s) {
  return { completed: '已完成', running: '运行中', failed: '失败', pending: '等待', cancelled: '已取消' }[s] || s
}

function goSync(mode) {
  router.push({ path: '/sync', query: { mode: mode === 'full' ? 'full' : 'incremental' } })
}

onMounted(load)
</script>

<style scoped>
.pipeline {
  display: flex;
  align-items: stretch;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 0.5rem;
}

.pipe-node {
  flex: 1;
  min-width: 140px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.pipe-icon { font-size: 1.4rem; }
.pipe-node strong { font-size: 0.9rem; }
.pipe-node .muted { font-size: 0.75rem; margin-top: 0.15rem; }

.pipe-arrow {
  display: flex;
  align-items: center;
  color: var(--muted);
  font-size: 1.25rem;
  padding: 0 0.25rem;
}

.job-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.55rem 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.85rem;
}

.job-row:last-child { border-bottom: none; }
.job-row .tag { margin-left: 0.35rem; }
</style>
