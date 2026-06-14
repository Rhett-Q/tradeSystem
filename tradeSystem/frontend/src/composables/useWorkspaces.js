import { computed, ref } from 'vue'

const MAX_TABS = 10

const tabs = ref([])
const activeId = ref('')

export function useWorkspaces() {
  function upsertFromRoute(route) {
    if (!route.meta?.title) return

    const id = route.path
    const payload = {
      id,
      path: route.path,
      fullPath: route.fullPath,
      title: route.meta.title,
      icon: route.meta.icon || '•',
      name: route.name,
    }

    const existing = tabs.value.find((t) => t.id === id)
    if (existing) {
      Object.assign(existing, payload)
    } else {
      tabs.value.push(payload)
      while (tabs.value.length > MAX_TABS) {
        tabs.value.shift()
      }
    }
    activeId.value = id
  }

  function activate(tab, router) {
    activeId.value = tab.id
    if (router.currentRoute.value.fullPath !== tab.fullPath) {
      router.push(tab.fullPath)
    }
  }

  function closeTab(tab, router) {
    const idx = tabs.value.findIndex((t) => t.id === tab.id)
    if (idx === -1) return

    const closingActive = activeId.value === tab.id
    tabs.value.splice(idx, 1)

    if (!closingActive) return

    const next = tabs.value[idx] || tabs.value[idx - 1]
    if (next) {
      activate(next, router)
    } else {
      activeId.value = ''
      router.push('/dashboard')
    }
  }

  function closeOthers(tab, router) {
    if (!tab) return
    tabs.value = tabs.value.filter((t) => t.id === tab.id)
    activate(tab, router)
  }

  function closeAll(router) {
    tabs.value = []
    activeId.value = ''
    router.push('/dashboard')
  }

  const activeTab = computed(() => tabs.value.find((t) => t.id === activeId.value) || null)

  return {
    tabs,
    activeId,
    activeTab,
    upsertFromRoute,
    activate,
    closeTab,
    closeOthers,
    closeAll,
  }
}
