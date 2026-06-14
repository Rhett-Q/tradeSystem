<template>
  <div class="symbol-search" ref="rootRef">
    <label>{{ label }}
      <input
        ref="inputRef"
        v-model="inputValue"
        type="text"
        :placeholder="placeholder"
        autocomplete="off"
        @input="onInput"
        @focus="onFocus"
        @keydown="onKeydown"
        @blur="onBlur"
      />
    </label>
    <ul v-if="open && suggestions.length" class="suggestions">
      <li
        v-for="(item, index) in suggestions"
        :key="item.symbol"
        :class="{ active: index === highlightIndex }"
        @mousedown.prevent="pick(item)"
      >
        <span class="mono">{{ item.symbol }}</span>
        <span class="name">{{ item.name }}</span>
        <span v-if="item.sector" class="sector">{{ item.sector }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { api } from '@/api/client'
import { isSymbolCode, normalizeSymbolInput } from '@/utils/symbol'

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: '股票' },
  placeholder: { type: String, default: '代码 / 名称 / 拼音' },
})

const emit = defineEmits(['update:modelValue', 'pick', 'submit'])

const rootRef = ref(null)
const inputRef = ref(null)
const inputValue = ref(props.modelValue)
const suggestions = ref([])
const open = ref(false)
const highlightIndex = ref(0)
let debounceTimer = null

watch(
  () => props.modelValue,
  (value) => {
    if (value !== inputValue.value) inputValue.value = value
  },
)

function emitValue(value) {
  emit('update:modelValue', value)
}

async function fetchSuggestions(keyword) {
  const q = keyword.trim()
  if (!q || isSymbolCode(q)) {
    suggestions.value = []
    open.value = false
    return
  }
  try {
    suggestions.value = await api.searchSymbols({ q, limit: '10' })
    highlightIndex.value = 0
    open.value = suggestions.value.length > 0
  } catch {
    suggestions.value = []
    open.value = false
  }
}

function onInput() {
  emitValue(inputValue.value)
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => fetchSuggestions(inputValue.value), 200)
}

function onFocus() {
  if (suggestions.value.length) open.value = true
  else if (inputValue.value.trim() && !isSymbolCode(inputValue.value)) {
    fetchSuggestions(inputValue.value)
  }
}

function onBlur() {
  setTimeout(() => {
    open.value = false
  }, 150)
}

function pick(item) {
  inputValue.value = item.symbol
  emitValue(item.symbol)
  emit('pick', item)
  open.value = false
  suggestions.value = []
}

function onKeydown(event) {
  if (!open.value || !suggestions.value.length) return

  if (event.key === 'ArrowDown') {
    event.preventDefault()
    highlightIndex.value = (highlightIndex.value + 1) % suggestions.value.length
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    highlightIndex.value =
      (highlightIndex.value - 1 + suggestions.value.length) % suggestions.value.length
  } else if (event.key === 'Enter') {
    if (open.value && suggestions.value.length) {
      event.preventDefault()
      pick(suggestions.value[highlightIndex.value])
    } else {
      emit('submit')
    }
  } else if (event.key === 'Escape') {
    open.value = false
  }
}

async function resolveSymbol() {
  const raw = inputValue.value.trim()
  if (!raw) throw new Error('请输入股票代码或名称')

  if (isSymbolCode(raw)) return normalizeSymbolInput(raw)

  const matches = await api.searchSymbols({ q: raw, limit: '1' })
  if (!matches.length) throw new Error(`未找到标的: ${raw}`)
  const resolved = matches[0].symbol
  inputValue.value = resolved
  emitValue(resolved)
  return resolved
}

defineExpose({ resolveSymbol, focus: () => inputRef.value?.focus() })
</script>

<style scoped>
.symbol-search {
  position: relative;
}

.symbol-search label {
  display: block;
  margin-bottom: 0;
}

.suggestions {
  position: absolute;
  z-index: 20;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  margin: 0;
  padding: 0.25rem 0;
  list-style: none;
  background: var(--card, #1a1d24);
  border: 1px solid var(--border, #2a2f3a);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  max-height: 280px;
  overflow-y: auto;
}

.suggestions li {
  display: grid;
  grid-template-columns: 110px 1fr auto;
  gap: 0.5rem;
  align-items: center;
  padding: 0.45rem 0.75rem;
  cursor: pointer;
  font-size: 0.88rem;
}

.suggestions li:hover,
.suggestions li.active {
  background: rgba(99, 102, 241, 0.12);
}

.suggestions .mono {
  font-family: ui-monospace, monospace;
  color: var(--accent, #818cf8);
}

.suggestions .name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.suggestions .sector {
  color: var(--muted, #94a3b8);
  font-size: 0.78rem;
}
</style>
