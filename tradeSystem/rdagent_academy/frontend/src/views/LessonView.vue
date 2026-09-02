<template>
  <main class="shell page">
    <p v-if="loading" class="muted">加载中…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <template v-else-if="lesson">
      <div class="layout">
        <article class="panel prose rise">
          <div class="crumbs muted">
            <RouterLink to="/learn">课程</RouterLink>
            <span>/</span>
            <span>{{ lesson.track_title }}</span>
          </div>
          <div class="meta">
            <span class="tag">{{ lesson.level }}</span>
            <span class="muted">约 {{ lesson.minutes }} 分钟</span>
          </div>
          <div class="md" v-html="html"></div>
        </article>

        <aside class="side rise rise-delay-1">
          <div class="panel">
            <h3>本课行动</h3>
            <p class="muted" v-if="lesson.lab_action">
              学完概念后，去实验室对应面板动手。
            </p>
            <p class="muted" v-else>本课偏概念，可继续下一课或先逛流程地图。</p>
            <div class="actions">
              <RouterLink
                v-if="lesson.lab_action"
                class="btn"
                :to="`/lab/${lesson.lab_action}`"
              >
                去实验室 · {{ labLabel }}
              </RouterLink>
              <RouterLink class="btn ghost" to="/map">看流程地图</RouterLink>
              <RouterLink class="btn ghost" to="/learn">返回目录</RouterLink>
            </div>
          </div>
        </aside>
      </div>
    </template>
  </main>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { marked } from 'marked'
import { api } from '@/api'

const props = defineProps({ id: { type: String, required: true } })

const lesson = ref(null)
const loading = ref(true)
const error = ref('')

const html = computed(() => (lesson.value ? marked.parse(lesson.value.body_markdown || '') : ''))

const labLabel = computed(() => {
  const map = { health: '健康检查', data: '数据', run: '运行台', sessions: 'Sessions' }
  return map[lesson.value?.lab_action] || '实验室'
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    lesson.value = await api.lesson(props.id)
  } catch (e) {
    error.value = e.message || String(e)
    lesson.value = null
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.id, load)
</script>

<style scoped>
.page {
  padding: 2rem 0 3.5rem;
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 1rem;
  align-items: start;
}

.crumbs {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 0.75rem;
  font-size: 0.85rem;
}

.meta {
  display: flex;
  gap: 0.6rem;
  align-items: center;
  margin-bottom: 1rem;
}

.actions {
  display: grid;
  gap: 0.55rem;
  margin-top: 1rem;
}

.actions .btn {
  text-align: center;
}

.error {
  color: var(--danger);
}

:deep(.md h1) {
  font-size: 1.9rem;
  margin-top: 0;
}

:deep(.md h2) {
  font-size: 1.25rem;
  margin-top: 1.6rem;
}

:deep(.md pre) {
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.9rem 1rem;
  overflow: auto;
  font-family: var(--font-mono);
  font-size: 0.82rem;
}

:deep(.md code) {
  font-family: var(--font-mono);
  font-size: 0.86em;
}

:deep(.md table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
}

:deep(.md th),
:deep(.md td) {
  border: 1px solid var(--line);
  padding: 0.45rem 0.55rem;
  text-align: left;
}

@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>