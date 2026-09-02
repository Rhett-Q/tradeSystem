<template>
  <main class="shell page">
    <header class="page-head rise">
      <h1>课程轨道</h1>
      <p class="muted">按顺序学完基础 → 环境 → 第一次跑通。带「实验室」标记的课可直接跳到对应操作台。</p>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <section v-for="(track, ti) in tracks" :key="track.id" class="track rise" :style="{ animationDelay: `${0.06 * ti}s` }">
      <div class="track-head">
        <h2>{{ track.title }}</h2>
        <p class="muted">{{ track.summary }}</p>
      </div>
      <div class="lesson-list">
        <RouterLink
          v-for="lesson in track.lessons"
          :key="lesson.id"
          class="lesson-row"
          :to="`/learn/${lesson.id}`"
        >
          <div>
            <strong>{{ lesson.title }}</strong>
            <div class="meta">
              <span class="tag">{{ lesson.level }}</span>
              <span class="muted">约 {{ lesson.minutes }} 分钟</span>
            </div>
          </div>
          <span class="arrow">→</span>
        </RouterLink>
      </div>
    </section>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '@/api'

const tracks = ref([])
const error = ref('')

onMounted(async () => {
  try {
    const data = await api.curriculum()
    tracks.value = data.tracks || []
  } catch (e) {
    error.value = e.message || String(e)
  }
})
</script>

<style scoped>
.page {
  padding: 2rem 0 3.5rem;
}

.page-head {
  margin-bottom: 1.75rem;
  max-width: 40rem;
}

.track {
  margin-bottom: 1.75rem;
}

.track-head {
  margin-bottom: 0.75rem;
}

.lesson-list {
  display: grid;
  gap: 0.5rem;
}

.lesson-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.1rem;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: rgba(18, 36, 32, 0.55);
  color: var(--text);
  transition: border-color 0.2s ease, transform 0.2s ease;
}

.lesson-row:hover {
  border-color: rgba(226, 180, 87, 0.45);
  transform: translateX(4px);
  color: var(--text);
}

.meta {
  display: flex;
  gap: 0.55rem;
  align-items: center;
  margin-top: 0.35rem;
}

.arrow {
  color: var(--accent);
  font-size: 1.2rem;
}

.error {
  color: var(--danger);
}
</style>