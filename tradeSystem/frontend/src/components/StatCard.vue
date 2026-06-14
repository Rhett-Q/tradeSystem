<template>
  <div class="stat-card">
    <div class="stat-value" :style="valueColor ? { color: valueColor } : {}">{{ value }}</div>
    <div class="stat-label">{{ label }}</div>
    <p v-if="hint" class="hint">{{ hint }}</p>
  </div>
</template>

<script setup>
defineProps({
  value: { type: [String, Number], required: true },
  label: { type: String, required: true },
  hint: { type: String, default: '' },
  valueColor: { type: String, default: '' },
})
</script>

<style scoped>
.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem 1.1rem;
}
.hint { margin-top: 0.35rem; margin-bottom: 0; font-size: 0.75rem; }
</style>
