<template>
  <div class="stack">
    <div class="grid-2 screener-layout">
      <div class="card">
        <div class="card-head">
          <h2>策略库</h2>
          <button class="btn sm ghost" @click="loadCatalog">刷新</button>
        </div>
        <p class="hint">内置 Backtrader 策略，可一键跳转回测验证。</p>

        <label>分类
          <select v-model="categoryFilter" @change="loadCatalog">
            <option value="">全部（{{ catalog.total || 0 }}）</option>
            <option v-for="c in catalog.categories" :key="c.id" :value="c.id">
              {{ c.label }}（{{ c.count }}）
            </option>
          </select>
        </label>

        <div v-if="categoryHelp" class="category-help muted">{{ categoryHelp }}</div>

        <div class="strategy-list">
          <button
            v-for="s in catalog.strategies"
            :key="s.id"
            type="button"
            class="strategy-item"
            :class="{ active: selectedId === s.id }"
            @click="selectStrategy(s.id)"
          >
            <div class="strategy-item-head">
              <strong>{{ s.name }}</strong>
              <span class="tag">{{ categoryLabel(s.category) }}</span>
            </div>
            <p class="muted">{{ s.description }}</p>
            <div class="tag-row">
              <span v-for="t in s.tags" :key="s.id + t" class="tag ghost-tag">{{ t }}</span>
            </div>
          </button>
        </div>
      </div>

      <div class="card">
        <div v-if="!detail.id" class="empty-state">
          <div class="icon">🧠</div>
          <p>选择左侧策略查看详情</p>
        </div>

        <template v-else>
          <div class="card-head">
            <h2>{{ detail.name }}</h2>
            <span class="tag mono">{{ detail.id }}</span>
          </div>
          <p class="desc">{{ detail.description }}</p>

          <div v-if="detail.indicators?.length" class="info-block">
            <h3>使用指标</h3>
            <div class="tag-row">
              <span v-for="ind in detail.indicators" :key="ind" class="tag">{{ ind }}</span>
            </div>
          </div>

          <div class="info-block">
            <h3>交易逻辑</h3>
            <pre class="logic-box">{{ detail.logic }}</pre>
          </div>

          <div class="grid-2 info-block">
            <div>
              <h3>适用场景</h3>
              <p class="muted">{{ detail.suitable || '—' }}</p>
            </div>
            <div>
              <h3>风险提示</h3>
              <p class="muted risk">{{ detail.risk || '—' }}</p>
            </div>
          </div>

          <div class="info-block">
            <h3>参数</h3>
            <div class="param-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>参数</th>
                    <th>说明</th>
                    <th>默认</th>
                    <th>范围</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="p in detail.params" :key="p.key">
                    <td class="mono">{{ p.key }}</td>
                    <td>{{ p.label }}</td>
                    <td>{{ p.default }}</td>
                    <td class="muted">{{ p.min }} ~ {{ p.max }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="info-block">
            <h3>默认参数试算</h3>
            <div class="param-edit-grid">
              <label v-for="p in detail.params" :key="'edit-' + p.key">
                {{ p.label }}
                <input
                  v-model.number="trialParams[p.key]"
                  type="number"
                  :min="p.min"
                  :max="p.max"
                  :step="p.type === 'int' ? 1 : 0.001"
                />
              </label>
            </div>
          </div>

          <div class="btn-row">
            <button class="btn primary" @click="goBacktest">去回测</button>
            <button class="btn ghost" @click="resetTrialParams">恢复默认</button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import { showMockToast } from '@/mock'

const router = useRouter()
const categoryFilter = ref('')
const selectedId = ref('')
const catalog = ref({ total: 0, categories: [], strategies: [], category_help: {} })
const detail = ref({})

const trialParams = reactive({})

const categoryHelp = computed(() => {
  if (!categoryFilter.value) return ''
  return catalog.value.category_help?.[categoryFilter.value] || ''
})

const CATEGORY_LABELS = {
  trend: '趋势跟踪',
  momentum: '动量反转',
  composite: '组合策略',
}

function categoryLabel(c) {
  return CATEGORY_LABELS[c] || c
}

async function loadCatalog() {
  try {
    const params = categoryFilter.value ? { category: categoryFilter.value } : {}
    catalog.value = await api.strategyCatalog(params)
    if (!selectedId.value && catalog.value.strategies?.length) {
      await selectStrategy(catalog.value.strategies[0].id)
    } else if (selectedId.value && !catalog.value.strategies?.find((s) => s.id === selectedId.value)) {
      selectedId.value = catalog.value.strategies?.[0]?.id || ''
      if (selectedId.value) await selectStrategy(selectedId.value)
      else detail.value = {}
    }
  } catch (e) {
    showMockToast(e.message)
  }
}

async function selectStrategy(id) {
  selectedId.value = id
  try {
    detail.value = await api.strategyDetail(id)
    resetTrialParams()
  } catch (e) {
    showMockToast(e.message)
  }
}

function resetTrialParams() {
  Object.keys(trialParams).forEach((k) => delete trialParams[k])
  for (const p of detail.value.params || []) {
    trialParams[p.key] = p.default
  }
}

function goBacktest() {
  if (!detail.value.id) return
  if (detail.value.uses_conditions) {
    router.push({ name: 'Backtest', query: { mode: 'multi', strategy: detail.value.id } })
    return
  }
  const query = { strategy: detail.value.id }
  for (const p of detail.value.params || []) {
    query[p.key] = String(trialParams[p.key] ?? p.default)
  }
  router.push({ name: 'Backtest', query })
}

onMounted(loadCatalog)
</script>

<style scoped>
.category-help {
  font-size: 0.82rem;
  margin: 0 0 0.75rem;
  padding: 0.5rem 0.65rem;
  background: var(--surface2);
  border-radius: var(--radius-sm);
}

.strategy-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 520px;
  overflow: auto;
}

.strategy-item {
  text-align: left;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface2);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.strategy-item:hover {
  border-color: var(--accent);
}

.strategy-item.active {
  border-color: rgba(59, 130, 246, 0.45);
  background: var(--accent-soft);
}

.strategy-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.strategy-item p {
  margin: 0 0 0.35rem;
  font-size: 0.82rem;
  line-height: 1.45;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.ghost-tag {
  font-size: 0.72rem;
  opacity: 0.85;
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--muted);
}

.empty-state .icon {
  font-size: 2rem;
  margin-bottom: 0.5rem;
}

.desc {
  margin: 0 0 1rem;
  color: var(--muted);
  line-height: 1.55;
}

.info-block {
  margin-bottom: 1rem;
}

.info-block h3 {
  margin: 0 0 0.45rem;
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text);
}

.logic-box {
  margin: 0;
  padding: 0.75rem;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-family: var(--mono);
  font-size: 0.8rem;
  line-height: 1.65;
  white-space: pre-wrap;
  color: var(--muted);
}

.risk {
  color: var(--warn, #d97706);
}

.param-table-wrap {
  overflow: auto;
}

.param-edit-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

@media (max-width: 768px) {
  .param-edit-grid { grid-template-columns: 1fr; }
}
</style>
