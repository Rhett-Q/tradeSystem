<template>
  <span class="badge" :class="ok ? 'ok' : 'err'">
    <span class="dot"></span>
    {{ label }}
  </span>
</template>

<script setup>
defineProps({
  ok: { type: Boolean, default: false },
  label: { type: String, default: '' },
})
</script>
