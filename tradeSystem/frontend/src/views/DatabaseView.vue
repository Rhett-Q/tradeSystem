<template>
  <div class="stack">
    <div class="grid-3">
      <StatCard
        v-for="t in tableStats"
        :key="t.label"
        :value="t.value"
        :label="t.label"
        :hint="t.hint"
      />
    </div>

    <div class="card">
      <div class="card-head">
        <h2>数据表</h2>
        <button class="btn sm ghost" @click="load">刷新</button>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th></th>
              <th>表名</th>
              <th>行数</th>
              <th>大小 (MB)</th>
              <th>最后更新</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="t in tables" :key="t.name">
              <tr class="table-row" :class="{ expanded: expandedTable === t.name }">
                <td>
                  <button type="button" class="btn sm ghost expand-btn" @click="toggleTable(t.name)">
                    {{ expandedTable === t.name ? '▾' : '▸' }}
                  </button>
                </td>
                <td class="mono">{{ t.name }}</td>
                <td>{{ t.rows.toLocaleString() }}</td>
                <td>{{ t.size_mb.toFixed(1) }}</td>
                <td>{{ t.last_updated ? fmtTime(t.last_updated) : '—' }}</td>
                <td class="muted">{{ t.description || '—' }}</td>
              </tr>
              <tr v-if="expandedTable === t.name" class="columns-row">
                <td colspan="6">
                  <div v-if="columnsLoading" class="muted columns-hint">加载字段…</div>
                  <div v-else-if="!columns.length" class="muted columns-hint">无字段信息</div>
                  <table v-else class="columns-table">
                    <thead>
                      <tr>
                        <th>字段</th>
                        <th>类型</th>
                        <th>可空</th>
                        <th>说明</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="col in columns" :key="col.name">
                        <td class="mono">{{ col.name }}</td>
                        <td class="mono muted">{{ col.type }}</td>
                        <td>{{ col.nullable ? '是' : '否' }}</td>
                        <td>{{ col.description || '—' }}</td>
                      </tr>
                    </tbody>
                  </table>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h2>ER 关系（设计）</h2>
      <pre class="er-diagram">symbols (1) ──&lt; (N) kline_daily
symbols (1) ──&lt; (N) kline_intraday
sync_jobs (1) ──&lt; (N) sync_logs</pre>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api/client'
import StatCard from '@/components/StatCard.vue'
import { showMockToast } from '@/mock'

const tables = ref([])
const expandedTable = ref('')
const columns = ref([])
const columnsLoading = ref(false)

const tableStats = computed(() => {
  const totalRows = tables.value.reduce((s, t) => s + t.rows, 0)
  const totalMb = tables.value.reduce((s, t) => s + t.size_mb, 0)
  return [
    { label: '数据表', value: tables.value.length, hint: 'PostgreSQL public' },
    { label: '总行数', value: totalRows >= 1e6 ? (totalRows / 1e6).toFixed(1) + 'M' : totalRows.toLocaleString(), hint: '含 K 线' },
    { label: '存储占用', value: totalMb.toFixed(0) + ' MB', hint: '估算值' },
  ]
})

async function load() {
  try {
    tables.value = await api.dbTables()
    if (expandedTable.value && !tables.value.find((t) => t.name === expandedTable.value)) {
      expandedTable.value = ''
      columns.value = []
    }
  } catch (e) {
    showMockToast(e.message)
  }
}

async function toggleTable(name) {
  if (expandedTable.value === name) {
    expandedTable.value = ''
    columns.value = []
    return
  }
  expandedTable.value = name
  columnsLoading.value = true
  try {
    columns.value = await api.dbTableColumns(name)
  } catch (e) {
    columns.value = []
    showMockToast(e.message)
  } finally {
    columnsLoading.value = false
  }
}

function fmtTime(iso) {
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

onMounted(load)
</script>

<style scoped>
.er-diagram {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 1rem;
  font-family: var(--mono);
  font-size: 0.82rem;
  color: var(--muted);
  line-height: 1.7;
}

.expand-btn {
  min-width: 1.75rem;
  padding: 0.15rem 0.35rem;
}

.columns-row td {
  padding: 0.5rem 0.75rem 0.85rem;
  background: var(--surface2);
}

.columns-hint {
  font-size: 0.82rem;
  padding: 0.35rem 0;
}

.columns-table {
  width: 100%;
  font-size: 0.82rem;
}

.columns-table th,
.columns-table td {
  padding: 0.35rem 0.5rem;
}
</style>
