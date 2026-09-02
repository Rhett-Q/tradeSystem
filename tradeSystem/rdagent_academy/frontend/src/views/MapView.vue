<template>
  <main class="shell page">
    <header class="page-head rise">
      <h1>流程地图</h1>
      <p class="muted">把「学」和「做」放在同一张图上：先绿灯，再烧额度。</p>
    </header>

    <ol class="map rise rise-delay-1">
      <li v-for="(n, i) in nodes" :key="n.title">
        <span class="n">{{ i + 1 }}</span>
        <div>
          <strong>{{ n.title }}</strong>
          <p class="muted">{{ n.body }}</p>
          <RouterLink v-if="n.to" class="link" :to="n.to">{{ n.cta }} →</RouterLink>
        </div>
      </li>
    </ol>
  </main>
</template>

<script setup>
const nodes = [
  {
    title: '弄清双轨',
    body: '生产轨读 PG；研究轨用 Qlib + Docker。环境不要混。',
    to: '/learn/two-tracks',
    cta: '读概念课',
  },
  {
    title: '环境全部变绿',
    body: 'venv、.env、LLM Key、Docker、cn_data、symlink 权限。',
    to: '/lab/health',
    cta: '健康检查',
  },
  {
    title: '准备数据',
    body: '下载官方 cn_data，并预生成 daily_pv.h5（强烈建议）。',
    to: '/lab/data',
    cta: '数据面板',
  },
  {
    title: '限制轮数试跑',
    body: 'RDAGENT_MAX_LOOP=2，新开跑 fin_factor，观察日志。',
    to: '/lab/run',
    cta: '运行台',
  },
  {
    title: '读 Session / 反馈',
    body: '看 loops、decision，必要时开 Streamlit 看图。',
    to: '/lab/sessions',
    cta: 'Sessions',
  },
]
</script>

<style scoped>
.page {
  padding: 2rem 0 3.5rem;
}

.page-head {
  max-width: 36rem;
  margin-bottom: 1.5rem;
}

.map {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.85rem;
}

.map li {
  display: grid;
  grid-template-columns: 48px 1fr;
  gap: 0.9rem;
  padding: 1.1rem 1.15rem;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: rgba(18, 36, 32, 0.55);
  position: relative;
}

.map li:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 35px;
  top: calc(100% - 2px);
  width: 2px;
  height: 0.85rem;
  background: linear-gradient(var(--accent), transparent);
}

.n {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: rgba(226, 180, 87, 0.15);
  color: var(--accent);
  font-family: var(--font-mono);
  font-weight: 500;
}

.link {
  display: inline-block;
  margin-top: 0.35rem;
  color: var(--accent);
  font-weight: 600;
}
</style>