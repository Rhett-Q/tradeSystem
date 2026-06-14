import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/dashboard' },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { title: '概览', icon: '📊' },
  },
  {
    path: '/sync',
    name: 'DataSync',
    component: () => import('@/views/DataSyncView.vue'),
    meta: { title: '数据同步', icon: '🔄' },
  },
  {
    path: '/symbols',
    name: 'Symbols',
    component: () => import('@/views/SymbolManageView.vue'),
    meta: { title: '标的管理', icon: '📋' },
  },
  {
    path: '/market',
    name: 'MarketData',
    component: () => import('@/views/MarketDataView.vue'),
    meta: { title: '行情查询', icon: '📈' },
  },
  {
    path: '/screener',
    redirect: '/screener/basic',
  },
  {
    path: '/screener/basic',
    name: 'ScreenerBasic',
    component: () => import('@/views/ScreenerView.vue'),
    meta: { title: '基础筛选', icon: '🔍', screenerMode: 'basic', navGroup: 'screener' },
  },
  {
    path: '/screener/qlib',
    name: 'ScreenerQlib',
    component: () => import('@/views/ScreenerView.vue'),
    meta: { title: 'Qlib Alpha158', icon: '🔍', screenerMode: 'qlib', navGroup: 'screener' },
  },
  {
    path: '/screener/multi',
    name: 'ScreenerMulti',
    component: () => import('@/views/ScreenerView.vue'),
    meta: { title: '多因子选股', icon: '🔍', screenerMode: 'multi', navGroup: 'screener' },
  },
  {
    path: '/tasks',
    name: 'Tasks',
    component: () => import('@/views/TaskMonitorView.vue'),
    meta: { title: '任务监控', icon: '⏱' },
  },
  {
    path: '/database',
    name: 'Database',
    component: () => import('@/views/DatabaseView.vue'),
    meta: { title: '数据库', icon: '🗄' },
  },
  {
    path: '/quality',
    name: 'DataQuality',
    component: () => import('@/views/DataQualityView.vue'),
    meta: { title: '数据质量', icon: '✓' },
  },
  {
    path: '/backtest',
    name: 'Backtest',
    component: () => import('@/views/BacktestView.vue'),
    meta: { title: '策略回测', icon: '📉' },
  },
  {
    path: '/strategy',
    name: 'Strategy',
    component: () => import('@/views/StrategyView.vue'),
    meta: { title: '策略库', icon: '🧠' },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { title: '系统设置', icon: '⚙' },
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})

export { routes }
