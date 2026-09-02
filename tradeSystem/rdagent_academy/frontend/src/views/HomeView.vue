<template>
  <main>
    <section class="hero">
      <div class="hero-bg" aria-hidden="true"></div>
      <div class="shell hero-inner">
        <p class="eyebrow rise">Microsoft RD-Agent × TradeSystem</p>
        <h1 class="hero-brand rise rise-delay-1">RD-Agent Academy</h1>
        <p class="hero-lead rise rise-delay-2">
          独立学习站：用中文把因子演化链路讲清楚，并在本机一键做健康检查、备数据、开跑与读 Session。
        </p>
        <div class="hero-cta rise rise-delay-3">
          <RouterLink class="btn" to="/learn">开始学习</RouterLink>
          <RouterLink class="btn ghost" to="/lab">打开实验室</RouterLink>
        </div>
      </div>
    </section>

    <section class="shell section">
      <div class="pipeline">
        <div v-for="(step, i) in pipeline" :key="step.id" class="pipe-step rise" :style="{ animationDelay: `${0.05 * i}s` }">
          <span class="pipe-idx">{{ String(i + 1).padStart(2, '0') }}</span>
          <strong>{{ step.label }}</strong>
          <p class="muted">{{ step.desc }}</p>
        </div>
      </div>
    </section>

    <section class="shell section cards-row">
      <article class="panel">
        <h2>学什么</h2>
        <p class="muted">概念、双轨架构、四步 Loop、数据来源与 Session 读法——按轨道推进，每课可跳实验室。</p>
      </article>
      <article class="panel">
        <h2>做什么</h2>
        <p class="muted">包装现有 <span class="mono">scripts/rdagent_*.cmd</span>：检查环境、下载 cn_data、预生成 HDF5、fin_factor / 恢复、打开 Streamlit。</p>
      </article>
    </section>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '@/api'

const pipeline = ref([
  { id: 'idea', label: '提假设', desc: 'LLM 提出可检验因子假设' },
  { id: 'code', label: '写代码', desc: '生成可运行因子实现' },
  { id: 'run', label: '回测', desc: 'Qlib Docker 量化回测' },
  { id: 'feedback', label: '反馈', desc: '按指标决定采纳或迭代' },
])

onMounted(async () => {
  try {
    const cur = await api.curriculum()
    if (cur.pipeline?.length) pipeline.value = cur.pipeline
  } catch {
    /* offline fallback already set */
  }
})
</script>

<style scoped>
.hero {
  position: relative;
  min-height: min(88vh, 720px);
  display: grid;
  align-items: end;
  padding: 4rem 0 3rem;
  overflow: hidden;
}

.hero-bg {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, transparent 20%, rgba(10, 18, 16, 0.55) 70%, rgba(10, 18, 16, 0.92) 100%),
    repeating-linear-gradient(
      -18deg,
      transparent 0 18px,
      rgba(126, 200, 163, 0.035) 18px 19px
    ),
    radial-gradient(ellipse 80% 55% at 70% 30%, rgba(226, 180, 87, 0.2), transparent 60%);
  animation: drift 14s ease-in-out infinite alternate;
}

@keyframes drift {
  from {
    transform: scale(1) translateY(0);
  }
  to {
    transform: scale(1.04) translateY(-8px);
  }
}

.hero-inner {
  position: relative;
  max-width: 740px;
}

.eyebrow {
  margin: 0 0 0.75rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-size: 0.75rem;
  color: var(--accent-2);
}

.hero-brand {
  font-size: clamp(2.6rem, 7vw, 4.4rem);
  line-height: 1.05;
  margin-bottom: 1rem;
}

.hero-lead {
  font-size: 1.08rem;
  color: var(--muted);
  max-width: 38rem;
  margin: 0 0 1.5rem;
}

.hero-cta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.section {
  padding: 1.5rem 0 2.5rem;
}

.pipeline {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.75rem;
}

.pipe-step {
  border-top: 2px solid var(--accent);
  padding: 1rem 0.25rem 0.5rem;
}

.pipe-idx {
  display: block;
  font-family: var(--font-mono);
  color: var(--accent);
  font-size: 0.8rem;
  margin-bottom: 0.35rem;
}

.cards-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  padding-bottom: 3.5rem;
}

@media (max-width: 860px) {
  .pipeline,
  .cards-row {
    grid-template-columns: 1fr;
  }
}
</style>