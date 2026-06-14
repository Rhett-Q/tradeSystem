<template>
  <div class="stack">
    <div class="card">
      <div class="card-head">
        <h2>标的列表</h2>
        <div class="toolbar">
          <input v-model="keyword" type="text" placeholder="搜索代码 / 名称…" class="search" />
          <select v-model="marketFilter" class="filter">
            <option value="">全部市场</option>
            <option value="SH">上海 SH</option>
            <option value="SZ">深圳 SZ</option>
          </select>
          <button class="btn sm" @click="loadPage(1)">搜索</button>
          <button class="btn sm primary" @click="refresh">刷新标的</button>
        </div>
      </div>

      <p class="muted">共 {{ data.total.toLocaleString() }} 只标的 · 第 {{ data.page }} 页</p>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>代码</th>
              <th>名称</th>
              <th>市场</th>
              <th>板块</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in data.rows" :key="row.symbol">
              <td class="mono">{{ row.symbol }}</td>
              <td>{{ row.name }}</td>
              <td><span class="tag">{{ row.market }}</span></td>
              <td>{{ row.sector || '—' }}</td>
              <td>
                <span class="badge ok" v-if="row.listed"><span class="dot"></span>上市</span>
                <span class="badge err" v-else><span class="dot"></span>退市</span>
              </td>
              <td>
                <button class="btn sm ghost" @click="viewKline(row.symbol)">K 线</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="pagination">
        <button class="btn sm" :disabled="data.page <= 1" @click="loadPage(data.page - 1)">上一页</button>
        <span class="muted">第 {{ data.page }} / {{ totalPages }} 页</span>
        <button class="btn sm" :disabled="data.page >= totalPages" @click="loadPage(data.page + 1)">下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import { showMockToast } from '@/mock'
import { isSymbolCode, normalizeSymbolInput } from '@/utils/symbol'

const router = useRouter()
const keyword = ref('')
const marketFilter = ref('')
const data = ref({ total: 0, page: 1, page_size: 10, rows: [] })

const totalPages = computed(() => Math.max(1, Math.ceil(data.value.total / data.value.page_size)))

async function loadPage(page) {
  try {
    data.value = await api.listSymbols({
      page: String(page),
      page_size: '10',
      keyword: keyword.value,
      market: marketFilter.value,
    })
  } catch (e) {
    showMockToast(e.message)
  }
}

async function refresh() {
  try {
    const res = await api.refreshSymbols()
    showMockToast(res.message)
    loadPage(1)
  } catch (e) {
    showMockToast(e.message)
  }
}

async function viewKline(symbol) {
  const code = normalizeSymbolInput(String(symbol || ''))
  if (!isSymbolCode(code)) {
    showMockToast('无效股票代码')
    return
  }
  await router.push({
    name: 'MarketData',
    query: { symbol: code, t: String(Date.now()) },
  })
}

onMounted(() => loadPage(1))
</script>

<style scoped>
.toolbar { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.search { width: 200px; }
.filter { width: 120px; }

.pagination {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 1rem;
}
</style>
