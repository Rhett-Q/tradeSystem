<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">
        <span class="logo">T</span>
        <div>
          <strong>TradeSystem</strong>
          <small>股票数据获取</small>
        </div>
      </div>

      <nav class="nav">
        <template v-for="item in navStructure" :key="item.path || item.id">
          <RouterLink
            v-if="item.type === 'link'"
            :to="item.path"
            class="nav-item"
            active-class="active"
          >
            <span class="icon">{{ item.icon }}</span>
            <span>{{ item.title }}</span>
          </RouterLink>

          <div v-else-if="item.type === 'group'" class="nav-group">
            <button
              type="button"
              class="nav-item nav-group-toggle"
              :class="{ expanded: expandedGroups[item.id], 'group-active': isGroupActive(item) }"
              @click="toggleGroup(item.id)"
            >
              <span class="icon">{{ item.icon }}</span>
              <span class="nav-group-label">{{ item.title }}</span>
              <span class="chevron">{{ expandedGroups[item.id] ? '▾' : '▸' }}</span>
            </button>
            <div v-show="expandedGroups[item.id]" class="nav-children">
              <RouterLink
                v-for="child in item.children"
                :key="child.path"
                :to="child.path"
                class="nav-item nav-child"
                active-class="active"
              >
                <span>{{ child.title }}</span>
              </RouterLink>
            </div>
          </div>
        </template>
      </nav>

      <div class="sidebar-footer">
        <div class="conn-row">
          <StatusBadge :ok="health.minqmt_connected" label="MiniQMT" />
          <StatusBadge :ok="health.postgres_connected" label="PostgreSQL" />
        </div>
        <p class="muted">MiniQMT + PostgreSQL</p>
      </div>
    </aside>

    <div class="main-area">
      <header class="topbar">
        <div>
          <h1>{{ currentTitle }}</h1>
          <p class="muted">{{ currentSubtitle }}</p>
        </div>
        <div class="topbar-actions">
          <StatusBadge :ok="health.minqmt_connected" :label="health.minqmt_account || 'MiniQMT'" />
          <button class="btn sm ghost" @click="refreshMock">刷新状态</button>
        </div>
      </header>

      <div v-if="tabs.length" class="workspace-tabs" role="tablist">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          role="tab"
          class="workspace-tab"
          :class="{ active: tab.id === activeId }"
          :aria-selected="tab.id === activeId"
          @click="activate(tab, router)"
          @contextmenu.prevent="onTabContextMenu($event, tab)"
        >
          <span class="tab-icon">{{ tab.icon }}</span>
          <span class="tab-title">{{ tab.title }}</span>
          <span
            v-if="tabs.length > 1"
            class="tab-close"
            title="关闭"
            @click.stop="closeTab(tab, router)"
          >×</span>
        </button>
        <button
          v-if="tabs.length > 1"
          type="button"
          class="workspace-tab-action"
          title="关闭其他标签"
          @click="activeTab && closeOthers(activeTab, router)"
        >
          关闭其他
        </button>
      </div>

      <main class="content">
        <router-view v-slot="{ Component, route: viewRoute }">
          <keep-alive :max="10">
            <component :is="Component" :key="viewRoute.path" />
          </keep-alive>
        </router-view>
      </main>
    </div>

    <Transition name="fade">
      <div v-if="toast" class="toast">{{ toast }}</div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { routes } from '@/router'
import { api } from '@/api/client'
import { showMockToast } from '@/mock'
import { useWorkspaces } from '@/composables/useWorkspaces'
import StatusBadge from '@/components/StatusBadge.vue'

const route = useRoute()
const router = useRouter()
const { tabs, activeId, activeTab, upsertFromRoute, activate, closeTab, closeOthers } = useWorkspaces()
const health = ref({
  minqmt_connected: false,
  minqmt_account: '检测中…',
  postgres_connected: false,
})
const toast = ref('')
const expandedGroups = ref({ screener: true })

const SCREENER_NAV_GROUP = {
  type: 'group',
  id: 'screener',
  title: '选股',
  icon: '🔍',
  children: [
    { path: '/screener/basic', title: '基础筛选' },
    { path: '/screener/qlib', title: 'Qlib Alpha158' },
    { path: '/screener/multi', title: '多因子选股' },
  ],
}

const NAV_ORDER = [
  '/dashboard',
  '/sync',
  '/symbols',
  '/market',
  'screener',
  '/tasks',
  '/database',
  '/quality',
  '/backtest',
  '/strategy',
  '/settings',
]

const navStructure = NAV_ORDER.map((key) => {
  if (key === 'screener') return SCREENER_NAV_GROUP
  const r = routes.find((item) => item.path === key)
  if (!r?.meta?.title) return null
  return {
    type: 'link',
    path: r.path,
    title: r.meta.title,
    icon: r.meta.icon,
  }
}).filter(Boolean)

function isGroupActive(group) {
  return group.children?.some((child) => route.path === child.path || route.path.startsWith(`${child.path}/`))
}

function toggleGroup(id) {
  expandedGroups.value[id] = !expandedGroups.value[id]
}

async function loadHealth() {
  try {
    health.value = await api.health()
  } catch (e) {
    health.value.minqmt_account = e.message
  }
}

function refreshMock() {
  loadHealth()
  showMockToast('状态已刷新')
}

const subtitles = {
  '/dashboard': 'MiniQMT 数据管道与 PostgreSQL 存储概览',
  '/sync': '配置并触发全量 / 增量 K 线同步',
  '/symbols': '全市场标的列表与筛选',
  '/market': '按代码查询历史 K 线',
  '/screener/basic': '基于 PostgreSQL 日 K 与标的元数据筛选',
  '/screener/qlib': 'Qlib Alpha158 单因子选股',
  '/screener/multi': '多个 Alpha158 因子取交集（AND）',
  '/tasks': '同步任务队列与执行日志',
  '/database': 'PostgreSQL 表结构与存储统计',
  '/quality': 'K 线完整性、异常值与同步问题统计',
  '/backtest': 'Backtrader 策略回测与净值分析',
  '/strategy': '内置交易策略说明与参数配置',
  '/settings': 'MiniQMT 与数据库连接配置',
}

const currentTitle = computed(() => route.meta?.title || 'TradeSystem')
const currentSubtitle = computed(() => subtitles[route.path] || '')

function onTabContextMenu(event, tab) {
  if (tabs.value.length <= 1) return
  closeOthers(tab, router)
}

watch(
  () => route.fullPath,
  () => {
    upsertFromRoute(route)
    if (route.path.startsWith('/screener')) {
      expandedGroups.value.screener = true
    }
  },
  { immediate: true },
)

function onToast(e) {
  toast.value = e.detail
  setTimeout(() => { toast.value = '' }, 2800)
}

onMounted(() => {
  loadHealth()
  window.addEventListener('tradesystem-toast', onToast)
})
onUnmounted(() => window.removeEventListener('tradesystem-toast', onToast))
</script>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  width: var(--sidebar-w);
  background: var(--bg-elevated);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 1rem 0.75rem;
  position: sticky;
  top: 0;
  height: 100vh;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.25rem 0.5rem 1.25rem;
}

.logo {
  width: 36px;
  height: 36px;
  border-radius: 9px;
  background: linear-gradient(135deg, var(--accent), var(--purple));
  display: grid;
  place-items: center;
  font-weight: 700;
}

.brand strong { display: block; font-size: 0.95rem; }
.brand small { color: var(--muted); font-size: 0.72rem; }

.nav { flex: 1; display: flex; flex-direction: column; gap: 0.2rem; }

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.55rem 0.75rem;
  border-radius: var(--radius-sm);
  color: var(--muted);
  text-decoration: none;
  font-size: 0.875rem;
  transition: background 0.15s, color 0.15s;
}

.nav-item:hover { background: var(--surface2); color: var(--text); text-decoration: none; }
.nav-item.active {
  background: var(--accent-soft);
  color: var(--text);
  border: 1px solid rgba(59, 130, 246, 0.25);
}

.nav-group { display: flex; flex-direction: column; gap: 0.15rem; }

.nav-group-toggle {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  width: 100%;
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  font: inherit;
  text-align: left;
}

.nav-group-toggle.group-active:not(.expanded) {
  color: var(--text);
}

.nav-group-label { flex: 1; }

.chevron {
  font-size: 0.65rem;
  opacity: 0.55;
  margin-left: auto;
}

.nav-children {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  padding-left: 0.35rem;
  margin-left: 0.85rem;
  border-left: 1px solid var(--border);
}

.nav-child {
  padding: 0.45rem 0.65rem;
  font-size: 0.82rem;
}

.nav-child .icon { display: none; }

.icon { font-size: 1rem; width: 1.25rem; text-align: center; }

.sidebar-footer {
  padding: 0.75rem 0.5rem 0;
  border-top: 1px solid var(--border);
  margin-top: 0.5rem;
}

.conn-row { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 0.5rem; }
.sidebar-footer .muted { font-size: 0.72rem; }

.main-area { flex: 1; min-width: 0; display: flex; flex-direction: column; }

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.1rem 1.5rem;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}

.topbar h1 { font-size: 1.2rem; font-weight: 600; }
.topbar .muted { font-size: 0.82rem; margin-top: 0.15rem; }

.topbar-actions { display: flex; align-items: center; gap: 0.6rem; }

.workspace-tabs {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.45rem 1rem 0;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
  scrollbar-width: thin;
}

.workspace-tab {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  max-width: 11rem;
  padding: 0.4rem 0.55rem;
  border: 1px solid transparent;
  border-bottom: none;
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  background: transparent;
  color: var(--muted);
  font-size: 0.8rem;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}

.workspace-tab:hover {
  background: var(--surface2);
  color: var(--text);
}

.workspace-tab.active {
  background: var(--bg-elevated);
  color: var(--text);
  border-color: var(--border);
  margin-bottom: -1px;
  padding-bottom: calc(0.4rem + 1px);
}

.tab-icon {
  font-size: 0.85rem;
  line-height: 1;
}

.tab-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tab-close {
  display: grid;
  place-items: center;
  width: 1.1rem;
  height: 1.1rem;
  margin-left: 0.1rem;
  border-radius: 4px;
  font-size: 1rem;
  line-height: 1;
  opacity: 0.55;
}

.tab-close:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.08);
}

.workspace-tab-action {
  margin-left: auto;
  padding: 0.3rem 0.55rem;
  border: none;
  background: transparent;
  color: var(--muted);
  font-size: 0.75rem;
  cursor: pointer;
  flex-shrink: 0;
}

.workspace-tab-action:hover {
  color: var(--text);
}

.content { flex: 1; padding: 1.25rem 1.5rem 2rem; overflow: auto; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

@media (max-width: 900px) {
  .layout { flex-direction: column; }
  .sidebar {
    width: 100%;
    height: auto;
    position: relative;
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
  }
  .nav { flex-direction: row; flex-wrap: wrap; flex: unset; }
  .sidebar-footer { display: none; }
}
</style>
