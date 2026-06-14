<template>
  <div class="stack">
    <!-- 基础筛选 -->
    <div v-show="mode === 'basic'" class="grid-2 screener-layout">
      <div class="card">
        <h2>筛选条件</h2>
        <p class="hint">基于 PostgreSQL 日 K 与标的元数据。默认排除退市标的。</p>

        <label>市场
          <select v-model="form.market">
            <option value="">全部</option>
            <option value="SH">上海 SH</option>
            <option value="SZ">深圳 SZ</option>
            <option value="BJ">北京 BJ</option>
          </select>
        </label>

        <label>板块（申万一级）
          <select v-model="form.sector">
            <option value="">全部</option>
            <option v-for="s in sectors" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>

        <div class="row-2">
          <label>收盘价 ≥
            <input v-model.number="form.minClose" type="number" min="0" step="0.01" placeholder="不限" />
          </label>
          <label>收盘价 ≤
            <input v-model.number="form.maxClose" type="number" min="0" step="0.01" placeholder="不限" />
          </label>
        </div>

        <label>涨跌幅周期（交易日）
          <select v-model.number="form.changeDays">
            <option :value="1">1 日</option>
            <option :value="5">5 日</option>
            <option :value="10">10 日</option>
            <option :value="20">20 日</option>
            <option :value="60">60 日</option>
          </select>
        </label>

        <div class="row-2">
          <label>涨幅 ≥ %
            <input v-model.number="form.minChangePct" type="number" step="0.1" placeholder="不限" />
          </label>
          <label>涨幅 ≤ %
            <input v-model.number="form.maxChangePct" type="number" step="0.1" placeholder="不限" />
          </label>
        </div>

        <label>成交量 ≥
          <input v-model.number="form.minVolume" type="number" min="0" step="1000" placeholder="不限" />
        </label>

        <label>均线条件
          <select v-model="form.maRule">
            <option value="">不限</option>
            <option value="above5">收盘价 ≥ MA5</option>
            <option value="above20">收盘价 ≥ MA20</option>
            <option value="above60">收盘价 ≥ MA60</option>
            <option value="below20">收盘价 ≤ MA20</option>
          </select>
        </label>

        <div class="btn-row">
          <button class="btn primary" :disabled="loading" @click="runScreen(1)">
            {{ loading ? '筛选中…' : '开始选股' }}
          </button>
          <button class="btn ghost" @click="resetForm">重置</button>
        </div>
      </div>

      <div class="card">
        <div class="card-head">
          <h2>筛选结果</h2>
          <p v-if="result.total != null" class="muted result-meta">
            共 {{ result.total.toLocaleString() }} 只
            <span v-if="result.change_days">· {{ result.change_days }} 日涨跌幅</span>
            <span v-if="maLabel">· {{ maLabel }}</span>
          </p>
        </div>
        <div v-if="!hasRun && !loading" class="empty-state">
          <div class="icon">🔍</div>
          <p>设置条件后点击「开始选股」</p>
        </div>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>代码</th><th>名称</th><th>板块</th><th>收盘</th>
                <th>{{ result.change_days || form.changeDays }}日涨跌</th>
                <th>成交量</th><th>日期</th><th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in result.rows" :key="row.symbol">
                <td class="mono">{{ row.symbol }}</td>
                <td>{{ row.name }}</td>
                <td>{{ row.sector || '—' }}</td>
                <td>{{ row.close.toFixed(2) }}</td>
                <td :class="pctClass(row.change_pct)">{{ formatPct(row.change_pct) }}</td>
                <td>{{ formatVol(row.volume) }}</td>
                <td class="muted">{{ row.trade_date }}</td>
                <td><button class="btn sm ghost" @click="viewKline(row.symbol)">K 线</button></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="result.total > 0" class="pagination">
          <button class="btn sm" :disabled="result.page <= 1 || loading" @click="goBasicPage(result.page - 1)">上一页</button>
          <span class="muted">第 {{ result.page }} / {{ totalPages }} 页</span>
          <button class="btn sm" :disabled="result.page >= totalPages || loading" @click="goBasicPage(result.page + 1)">下一页</button>
        </div>
      </div>
    </div>

    <!-- Qlib 因子 -->
    <div v-show="mode === 'qlib'" class="grid-2 screener-layout">
      <div class="card">
        <h2>Qlib Alpha158 因子</h2>
        <p class="hint">
          使用 Microsoft Qlib Alpha158 因子表达式，基于 PG 日 K 计算。默认排除退市标的。
          <span v-if="factorMeta.qlib_installed" class="tag">pyqlib 已安装</span>
          <span v-else class="tag">内嵌因子定义</span>
        </p>

        <label>因子分类
          <select v-model="qlibForm.category" @change="onCategoryChange">
            <option value="">全部 ({{ factorMeta.total || 0 }})</option>
            <option v-for="c in factorMeta.categories" :key="c" :value="c">{{ categoryLabel(c) }}</option>
          </select>
        </label>

        <label>因子
          <select v-model="qlibForm.factor">
            <option v-for="f in filteredFactors" :key="f.name" :value="f.name">
              {{ f.name }}
            </option>
          </select>
        </label>

        <p v-if="selectedFactor" class="expr-hint mono">{{ selectedFactor.expression }}</p>

        <div v-if="selectedFactor?.description" class="factor-info">
          <p class="factor-desc">{{ selectedFactor.description }}</p>
          <p v-if="selectedFactor.usage" class="factor-usage">
            <span class="label">用法</span>{{ selectedFactor.usage }}
          </p>
          <p v-if="selectedFactor.value_hint" class="factor-hint muted">
            {{ selectedFactor.value_hint }}
          </p>
          <div v-if="selectedFactor.examples?.length" class="factor-examples">
            <span class="label">示例阈值</span>
            <button
              v-for="ex in selectedFactor.examples"
              :key="ex.factor + ex.min_value + ex.max_value"
              type="button"
              class="chip"
              @click="applyExample(ex)"
            >
              {{ ex.label }}
            </button>
          </div>
        </div>

        <p v-if="categoryHelpText" class="hint category-help">{{ categoryHelpText }}</p>

        <label>市场
          <select v-model="qlibForm.market">
            <option value="">全部</option>
            <option value="SH">上海 SH</option>
            <option value="SZ">深圳 SZ</option>
            <option value="BJ">北京 BJ</option>
          </select>
        </label>

        <label>板块
          <select v-model="qlibForm.sector">
            <option value="">全部</option>
            <option v-for="s in sectors" :key="'q-' + s" :value="s">{{ s }}</option>
          </select>
        </label>

        <div class="row-2">
          <label>因子值 ≥
            <input v-model.number="qlibForm.minValue" type="number" step="0.001" placeholder="不限" />
          </label>
          <label>因子值 ≤
            <input v-model.number="qlibForm.maxValue" type="number" step="0.001" placeholder="不限" />
          </label>
        </div>

        <p class="hint preset-hint">
          快捷示例：
          <button
            v-for="ex in usageExamples"
            :key="ex.factor + ex.label"
            type="button"
            class="link-chip"
            @click="applyGlobalExample(ex)"
          >
            {{ ex.label }}
          </button>
        </p>

        <div class="btn-row">
          <button class="btn primary" :disabled="qlibLoading" @click="runQlibScreen(1)">
            {{ qlibLoading ? '计算中…' : '因子选股' }}
          </button>
          <button class="btn ghost" @click="resetQlibForm">重置</button>
        </div>
      </div>

      <div class="card">
        <div class="card-head">
          <h2>因子筛选结果</h2>
          <p v-if="qlibResult.total != null" class="muted result-meta">
            共 {{ qlibResult.total.toLocaleString() }} 只
            <span v-if="qlibResult.factor">· {{ qlibResult.factor }}</span>
          </p>
        </div>

        <div v-if="!qlibHasRun && !qlibLoading" class="empty-state">
          <div class="icon">📐</div>
          <p>选择 Alpha158 因子并设置阈值</p>
        </div>

        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th>板块</th>
                <th>{{ qlibResult.factor || '因子' }}</th>
                <th>收盘</th>
                <th>日期</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in qlibResult.rows" :key="row.symbol">
                <td class="mono">{{ row.symbol }}</td>
                <td>{{ row.name }}</td>
                <td>{{ row.sector || '—' }}</td>
                <td class="mono">{{ formatFactor(row.factor_value) }}</td>
                <td>{{ row.close != null ? row.close.toFixed(2) : '—' }}</td>
                <td class="muted">{{ row.trade_date }}</td>
                <td>
                  <button class="btn sm ghost" @click="viewKline(row.symbol)">K 线</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="qlibResult.total > 0" class="pagination">
          <button class="btn sm" :disabled="qlibResult.page <= 1 || qlibLoading" @click="goQlibPage(qlibResult.page - 1)">
            上一页
          </button>
          <span class="muted">第 {{ qlibResult.page }} / {{ qlibTotalPages }} 页</span>
          <button class="btn sm" :disabled="qlibResult.page >= qlibTotalPages || qlibLoading" @click="goQlibPage(qlibResult.page + 1)">
            下一页
          </button>
        </div>
      </div>
    </div>

    <!-- 多因子选股 -->
    <div v-show="mode === 'multi'" class="grid-2 screener-layout">
      <div class="card">
        <h2>多因子组合</h2>
        <p class="hint">多个 Alpha158 因子取交集（AND），全部满足才命中。默认排除退市标的。</p>

        <div class="nl-parse card-inset">
          <p class="cond-add-title">一句话描述策略</p>
          <textarea
            v-model="multiNlText"
            rows="3"
            placeholder="例如：20日涨幅超过5%，站上5日均线，低波动盘整"
          />
          <div class="nl-parse-row">
            <label class="nl-parse-mode">解析方式
              <select v-model="multiNlPrefer">
                <option value="auto">自动（优先 LLM）</option>
                <option value="llm">仅 LLM</option>
                <option value="rules">仅规则引擎</option>
              </select>
            </label>
            <button
              type="button"
              class="btn sm primary"
              :disabled="multiNlLoading || !multiNlText.trim()"
              @click="parseMultiNl"
            >
              {{ multiNlLoading ? '解析中…' : '智能解析' }}
            </button>
          </div>
          <p v-if="multiNlResult.interpretation" class="nl-parse-result">
            {{ multiNlResult.interpretation }}
            <span v-if="multiNlResult.source" class="tag">{{ multiNlSourceLabel }}</span>
          </p>
          <p v-for="(w, i) in multiNlResult.warnings || []" :key="'w-' + i" class="hint nl-warn">{{ w }}</p>
          <div v-if="multiNlResult.log?.length" class="nl-log">
            <button type="button" class="btn sm ghost nl-log-toggle" @click="multiNlLogExpanded = !multiNlLogExpanded">
              {{ multiNlLogExpanded ? '收起' : '展开' }}解析日志
              <span v-if="multiNlResult.stats?.total_ms != null" class="muted">
                · {{ multiNlResult.stats.total_ms }}ms
              </span>
            </button>
            <div v-show="multiNlLogExpanded" class="nl-log-body">
              <div
                v-for="(entry, idx) in multiNlResult.log"
                :key="'nl-log-' + idx"
                class="log-line"
                :class="entry.level"
              >
                <span class="log-time">+{{ formatMs(entry.elapsed_ms) }}</span>
                <span v-if="entry.step_ms" class="log-step">Δ{{ formatMs(entry.step_ms) }}</span>
                <span class="log-msg">{{ entry.message }}</span>
              </div>
            </div>
          </div>
          <p class="hint">
            需在
            <router-link to="/settings">系统设置</router-link>
            配置 LLM（OpenAI 兼容接口）；未配置时使用内置规则引擎。
          </p>
        </div>

        <div v-if="multiForm.conditions.length" class="cond-list">
          <div
            v-for="(cond, idx) in multiForm.conditions"
            :key="cond.factor + '-' + idx"
            class="cond-row"
            :class="{ editing: multiEditingIdx === idx }"
          >
            <template v-if="multiEditingIdx === idx">
              <div class="cond-edit">
                <label class="cond-edit-field">因子
                  <select v-model="multiEditDraft.factor">
                    <option v-for="f in factorMeta.factors" :key="'edit-' + f.name" :value="f.name">
                      {{ f.name }}
                    </option>
                  </select>
                </label>
                <div class="row-2 cond-edit-thresholds">
                  <label>≥
                    <input v-model.number="multiEditDraft.min_value" type="number" step="0.001" placeholder="不限" />
                  </label>
                  <label>≤
                    <input v-model.number="multiEditDraft.max_value" type="number" step="0.001" placeholder="不限" />
                  </label>
                </div>
                <div class="cond-edit-actions">
                  <button type="button" class="btn sm primary" @click="saveEditMultiCondition">保存</button>
                  <button type="button" class="btn sm ghost" @click="cancelEditMultiCondition">取消</button>
                </div>
              </div>
            </template>
            <template v-else>
              <div class="cond-main">
                <strong class="mono">{{ cond.factor }}</strong>
                <span v-if="cond.min_value != null && cond.min_value !== ''" class="cond-threshold">≥ {{ cond.min_value }}</span>
                <span v-if="cond.max_value != null && cond.max_value !== ''" class="cond-threshold">≤ {{ cond.max_value }}</span>
                <span v-if="isEmptyThreshold(cond)" class="cond-threshold muted">未设阈值</span>
              </div>
              <div class="cond-row-actions">
                <button type="button" class="btn sm ghost" @click="startEditMultiCondition(idx)">编辑</button>
                <button type="button" class="btn sm ghost" @click="removeMultiCondition(idx)">删除</button>
              </div>
            </template>
          </div>
        </div>
        <p v-else class="hint">尚未添加因子条件</p>

        <div class="cond-add card-inset">
          <p class="cond-add-title">添加条件</p>
          <label>因子分类
            <select v-model="multiForm.category" @change="onMultiCategoryChange">
              <option value="">全部</option>
              <option v-for="c in factorMeta.categories" :key="'m-' + c" :value="c">{{ categoryLabel(c) }}</option>
            </select>
          </label>
          <label>因子
            <select v-model="multiForm.pickerFactor">
              <option v-for="f in multiFilteredFactors" :key="'mp-' + f.name" :value="f.name">{{ f.name }}</option>
            </select>
          </label>
          <div class="row-2">
            <label>≥
              <input v-model.number="multiForm.pickerMin" type="number" step="0.001" placeholder="不限" />
            </label>
            <label>≤
              <input v-model.number="multiForm.pickerMax" type="number" step="0.001" placeholder="不限" />
            </label>
          </div>
          <button type="button" class="btn sm" @click="addMultiCondition">加入条件</button>
        </div>

        <p class="hint preset-hint">
          快捷策略：
          <button
            v-for="preset in multiPresets"
            :key="preset.label"
            type="button"
            class="link-chip"
            @click="applyMultiPreset(preset)"
          >
            {{ preset.label }}
          </button>
        </p>

        <label>市场
          <select v-model="multiForm.market">
            <option value="">全部</option>
            <option value="SH">上海 SH</option>
            <option value="SZ">深圳 SZ</option>
            <option value="BJ">北京 BJ</option>
          </select>
        </label>

        <label>板块
          <select v-model="multiForm.sector">
            <option value="">全部</option>
            <option v-for="s in sectors" :key="'m-s-' + s" :value="s">{{ s }}</option>
          </select>
        </label>

        <div class="sort-block">
          <p class="cond-add-title">排序（先添加的优先级更高，支持多字段组合）</p>
          <div v-if="multiForm.sortRules.length" class="sort-list">
            <div v-for="(rule, idx) in multiForm.sortRules" :key="'sort-' + idx" class="sort-row">
              <select v-model="rule.factor">
                <option v-for="c in multiForm.conditions" :key="'sr-' + idx + c.factor" :value="c.factor">
                  {{ c.factor }}
                </option>
              </select>
              <select v-model="rule.order">
                <option value="desc">降序 ↓</option>
                <option value="asc">升序 ↑</option>
              </select>
              <button type="button" class="btn sm ghost" @click="removeSortRule(idx)">删除</button>
            </div>
          </div>
          <p v-else class="hint">未设置排序，默认按首个因子降序</p>
          <button
            type="button"
            class="btn sm"
            :disabled="!multiForm.conditions.length || multiForm.sortRules.length >= multiForm.conditions.length"
            @click="addSortRule"
          >
            添加排序字段
          </button>
        </div>

        <div class="btn-row">
          <button class="btn primary" :disabled="multiLoading || !multiForm.conditions.length" @click="runMultiScreen(1)">
            {{ multiLoading ? '计算中…' : '多因子选股' }}
          </button>
          <button class="btn ghost" @click="resetMultiForm">重置</button>
        </div>
      </div>

      <div class="card">
        <div class="card-head">
          <h2>多因子结果</h2>
          <p v-if="multiResult.total != null" class="muted result-meta">
            共 {{ multiResult.total.toLocaleString() }} 只
            <span v-if="multiResult.factors?.length">· {{ multiResult.factors.join(' ∩ ') }}</span>
            <span v-if="multiSortLabel">· 排序 {{ multiSortLabel }}</span>
          </p>
        </div>

        <div v-if="!multiHasRun && !multiLoading" class="empty-state">
          <div class="icon">🧩</div>
          <p>添加 2 个以上因子条件后运行</p>
        </div>

        <div v-else class="table-wrap table-sticky-action">
          <table class="multi-result-table">
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th>板块</th>
                <th v-for="f in multiResult.factors || []" :key="f">{{ f }}</th>
                <th>收盘</th>
                <th>日期</th>
                <th class="col-action">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in multiResult.rows" :key="row.symbol">
                <td class="mono">{{ row.symbol }}</td>
                <td>{{ row.name }}</td>
                <td>{{ row.sector || '—' }}</td>
                <td v-for="f in multiResult.factors || []" :key="row.symbol + f" class="mono">
                  {{ formatFactor(row.factor_values?.[f]) }}
                </td>
                <td>{{ row.close != null ? row.close.toFixed(2) : '—' }}</td>
                <td class="muted">{{ row.trade_date }}</td>
                <td class="col-action">
                  <button class="btn sm ghost" @click="viewKline(row.symbol)">K 线</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="multiResult.total > 0" class="pagination">
          <button class="btn sm" :disabled="multiResult.page <= 1 || multiLoading" @click="goMultiPage(multiResult.page - 1)">
            上一页
          </button>
          <span class="muted">第 {{ multiResult.page }} / {{ multiTotalPages }} 页</span>
          <button class="btn sm" :disabled="multiResult.page >= multiTotalPages || multiLoading" @click="goMultiPage(multiResult.page + 1)">
            下一页
          </button>
        </div>
      </div>
    </div>

    <!-- 历史记录 -->
    <div class="card history-card">
      <div class="card-head history-head">
        <h2>历史记录</h2>
        <div class="history-head-actions">
          <button type="button" class="btn sm ghost" @click="historyExpanded = !historyExpanded">
            {{ historyExpanded ? '收起' : '展开' }}
          </button>
          <button
            v-if="historyList.length"
            type="button"
            class="btn sm ghost"
            @click="clearHistory"
          >
            清空
          </button>
        </div>
      </div>
      <div v-show="historyExpanded">
        <p v-if="historyLoading" class="hint">加载中…</p>
        <p v-else-if="!historyList.length" class="hint">暂无历史，运行选股后会自动保存（最多 100 条）</p>
        <div v-else class="history-list">
          <div v-for="item in historyList" :key="item.id" class="history-item">
            <div class="history-main">
              <span class="mode-badge" :class="item.mode">{{ historyModeLabel(item.mode) }}</span>
              <strong class="history-title">{{ item.title }}</strong>
              <span class="muted history-meta">
                {{ formatHistoryTime(item.created_at) }}
                · {{ (item.result_summary?.total ?? 0).toLocaleString() }} 只
              </span>
            </div>
            <div class="history-actions">
              <button type="button" class="btn sm ghost" @click="applyHistory(item)">恢复条件</button>
              <button type="button" class="btn sm ghost" @click="replayHistory(item)">重新选股</button>
              <button type="button" class="btn sm ghost" @click="viewHistorySnapshot(item)">查看快照</button>
              <button type="button" class="btn sm ghost" @click="deleteHistoryItem(item.id)">删除</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 筛选日志 -->
    <div v-if="activeLog.length" class="card log-card">
      <div class="card-head log-head" @click="logExpanded = !logExpanded">
        <h2>筛选日志</h2>
        <p class="muted result-meta">
          {{ activeStats.total_ms != null ? `总耗时 ${activeStats.total_ms}ms` : '' }}
          <span v-if="activeStats.matched != null"> · 命中 {{ activeStats.matched.toLocaleString() }} 只</span>
          <span v-if="activeStats.query_ms != null"> · SQL {{ activeStats.query_ms }}ms</span>
          <span v-if="activeStats.panel_load_ms != null"> · 面板 {{ activeStats.panel_load_ms }}ms</span>
          <span v-if="activeStats.compute_ms != null"> · 计算 {{ activeStats.compute_ms }}ms</span>
        </p>
        <span class="log-toggle">{{ logExpanded ? '收起' : '展开' }}</span>
      </div>
      <div v-show="logExpanded" class="log-body">
        <div
          v-for="(entry, idx) in activeLog"
          :key="idx"
          class="log-line"
          :class="entry.level"
        >
          <span class="log-time">+{{ formatMs(entry.elapsed_ms) }}</span>
          <span v-if="entry.step_ms" class="log-step">Δ{{ formatMs(entry.step_ms) }}</span>
          <span class="log-msg">{{ entry.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import { showMockToast } from '@/mock'
import { isSymbolCode, normalizeSymbolInput } from '@/utils/symbol'

const route = useRoute()
const router = useRouter()

const SCREENER_MODE_PATH = {
  basic: '/screener/basic',
  qlib: '/screener/qlib',
  multi: '/screener/multi',
}

const mode = computed(() => route.meta?.screenerMode || 'basic')

function goScreenerMode(next) {
  const path = SCREENER_MODE_PATH[next]
  if (path && route.path !== path) router.push(path)
}
const sectors = ref([])
const loading = ref(false)
const hasRun = ref(false)
const qlibLoading = ref(false)
const qlibHasRun = ref(false)
const multiLoading = ref(false)
const multiHasRun = ref(false)
const logExpanded = ref(true)
const historyExpanded = ref(true)
const historyLoading = ref(false)
const historyList = ref([])

const form = reactive({
  market: '',
  sector: '',
  minClose: null,
  maxClose: null,
  changeDays: 5,
  minChangePct: null,
  maxChangePct: null,
  minVolume: null,
  maRule: '',
})

const qlibForm = reactive({
  category: '',
  factor: 'ROC20',
  market: '',
  sector: '',
  minValue: null,
  maxValue: null,
})

const multiForm = reactive({
  category: '',
  pickerFactor: 'ROC20',
  pickerMin: null,
  pickerMax: null,
  market: '',
  sector: '',
  sortRules: [
    { factor: 'ROC20', order: 'desc' },
  ],
  conditions: [
    { factor: 'ROC20', min_value: 0.95 },
    { factor: 'MA5', min_value: 1.0 },
  ],
})

const multiPresets = [
  {
    label: '强势突破',
    conditions: [
      { factor: 'ROC20', min_value: 0.95 },
      { factor: 'MA5', min_value: 1.0 },
    ],
  },
  {
    label: '趋势低波',
    conditions: [
      { factor: 'MA20', min_value: 1.0 },
      { factor: 'STD20', max_value: 0.02 },
    ],
  },
  {
    label: '量价齐升',
    conditions: [
      { factor: 'ROC10', min_value: 0.97 },
      { factor: 'CORR10', min_value: 0.3 },
    ],
  },
]

const factorMeta = ref({
  categories: [],
  factors: [],
  total: 0,
  qlib_installed: false,
  category_help: {},
  usage_examples: [],
})

const result = ref({ total: 0, page: 1, page_size: 50, change_days: 5, rows: [] })
const qlibResult = ref({ total: 0, page: 1, page_size: 50, factor: '', rows: [] })
const multiResult = ref({ total: 0, page: 1, page_size: 50, factors: [], rows: [] })
const multiEditingIdx = ref(-1)
const multiNlText = ref('')
const multiNlPrefer = ref('auto')
const multiNlLoading = ref(false)
const multiNlResult = ref({ interpretation: '', source: '', warnings: [], log: [], stats: {} })
const multiNlLogExpanded = ref(true)
const multiEditDraft = reactive({
  factor: '',
  min_value: null,
  max_value: null,
})

const totalPages = computed(() =>
  Math.max(1, Math.ceil((result.value.total || 0) / (result.value.page_size || 50))),
)
const qlibTotalPages = computed(() =>
  Math.max(1, Math.ceil((qlibResult.value.total || 0) / (qlibResult.value.page_size || 50))),
)
const multiTotalPages = computed(() =>
  Math.max(1, Math.ceil((multiResult.value.total || 0) / (multiResult.value.page_size || 50))),
)
const multiNlSourceLabel = computed(() => {
  const s = multiNlResult.value.source
  if (s === 'llm') return 'LLM'
  if (s === 'rules') return '规则'
  return s
})
const multiSortLabel = computed(() => {
  const rules = multiResult.value.sort || []
  if (!rules.length) return ''
  return rules
    .map((r) => `${r.factor}${r.order === 'asc' ? '↑' : '↓'}`)
    .join(' → ')
})

function syncSortRulesWithConditions() {
  const factors = new Set(multiForm.conditions.map((c) => c.factor))
  multiForm.sortRules = multiForm.sortRules.filter((r) => factors.has(r.factor))
  if (!multiForm.sortRules.length && multiForm.conditions.length) {
    multiForm.sortRules.push({ factor: multiForm.conditions[0].factor, order: 'desc' })
  }
}

function addSortRule() {
  const used = new Set(multiForm.sortRules.map((r) => r.factor))
  const next = multiForm.conditions.find((c) => !used.has(c.factor))
  if (!next) return
  multiForm.sortRules.push({ factor: next.factor, order: 'desc' })
}

function removeSortRule(idx) {
  multiForm.sortRules.splice(idx, 1)
}

const maLabel = computed(() => {
  const m = form.maRule
  if (m === 'above5') return '≥ MA5'
  if (m === 'above20') return '≥ MA20'
  if (m === 'above60') return '≥ MA60'
  if (m === 'below20') return '≤ MA20'
  return ''
})

const filteredFactors = computed(() => {
  const all = factorMeta.value.factors || []
  if (!qlibForm.category) return all
  return all.filter((f) => f.category === qlibForm.category)
})

const multiFilteredFactors = computed(() => {
  const all = factorMeta.value.factors || []
  if (!multiForm.category) return all
  return all.filter((f) => f.category === multiForm.category)
})

const selectedFactor = computed(() =>
  (factorMeta.value.factors || []).find((f) => f.name === qlibForm.factor),
)

const usageExamples = computed(() => factorMeta.value.usage_examples || [])

const categoryHelpText = computed(() => {
  const cat = qlibForm.category || selectedFactor.value?.category
  if (!cat) return ''
  const help = factorMeta.value.category_help || {}
  return help[cat] || ''
})

const activeLog = computed(() => {
  if (mode.value === 'basic') return result.value.log || []
  if (mode.value === 'multi') return multiResult.value.log || []
  return qlibResult.value.log || []
})

const activeStats = computed(() => {
  if (mode.value === 'basic') return result.value.stats || {}
  if (mode.value === 'multi') return multiResult.value.stats || {}
  return qlibResult.value.stats || {}
})

const CATEGORY_LABELS = {
  kbar: 'K 线形态',
  price: '价格',
  momentum: '动量',
  trend: '趋势',
  volatility: '波动',
  range: '区间',
  aroon: 'Aroon',
  volume: '量价',
  other: '其他',
}

function categoryLabel(c) {
  return CATEGORY_LABELS[c] || c
}

function buildParams(page) {
  const params = {
    page: String(page),
    page_size: '50',
    change_days: String(form.changeDays),
  }
  if (form.market) params.market = form.market
  if (form.sector) params.sector = form.sector
  if (form.minClose != null && form.minClose !== '') params.min_close = String(form.minClose)
  if (form.maxClose != null && form.maxClose !== '') params.max_close = String(form.maxClose)
  if (form.minChangePct != null && form.minChangePct !== '') params.min_change_pct = String(form.minChangePct)
  if (form.maxChangePct != null && form.maxChangePct !== '') params.max_change_pct = String(form.maxChangePct)
  if (form.minVolume != null && form.minVolume !== '') params.min_volume = String(form.minVolume)
  if (form.maRule === 'above5') params.above_ma = '5'
  else if (form.maRule === 'above20') params.above_ma = '20'
  else if (form.maRule === 'above60') params.above_ma = '60'
  else if (form.maRule === 'below20') params.below_ma = '20'
  return params
}

function buildQlibParams(page) {
  const params = {
    page: String(page),
    page_size: '50',
    factor: qlibForm.factor,
  }
  if (qlibForm.market) params.market = qlibForm.market
  if (qlibForm.sector) params.sector = qlibForm.sector
  if (qlibForm.minValue != null && qlibForm.minValue !== '') params.min_value = String(qlibForm.minValue)
  if (qlibForm.maxValue != null && qlibForm.maxValue !== '') params.max_value = String(qlibForm.maxValue)
  return params
}

async function runScreen(page = 1) {
  loading.value = true
  try {
    result.value = await api.screenerRun(buildParams(page))
    hasRun.value = true
    if (page === 1) loadHistory()
  } catch (e) {
    showMockToast(e.message)
  } finally {
    loading.value = false
  }
}

function goBasicPage(page) {
  const target = Math.max(1, Number(page) || 1)
  if (target === Number(result.value.page)) return
  runScreen(target)
}

async function runQlibScreen(page = 1) {
  if (!qlibForm.factor) {
    showMockToast('请选择因子')
    return
  }
  qlibLoading.value = true
  try {
    qlibResult.value = await api.screenerQlibRun(buildQlibParams(page))
    qlibHasRun.value = true
    if (qlibResult.value.message) showMockToast(qlibResult.value.message)
    if (page === 1) loadHistory()
  } catch (e) {
    showMockToast(e.message)
  } finally {
    qlibLoading.value = false
  }
}

function goQlibPage(page) {
  const target = Math.max(1, Number(page) || 1)
  if (target === Number(qlibResult.value.page)) return
  runQlibScreen(target)
}

function buildMultiBody(page) {
  const body = {
    page,
    page_size: 50,
    conditions: multiForm.conditions.map((c) => ({
      factor: c.factor,
      ...(c.min_value != null && c.min_value !== '' ? { min_value: c.min_value } : {}),
      ...(c.max_value != null && c.max_value !== '' ? { max_value: c.max_value } : {}),
    })),
  }
  if (multiForm.market) body.market = multiForm.market
  if (multiForm.sector) body.sector = multiForm.sector
  const sort = multiForm.sortRules
    .filter((r) => r.factor)
    .map((r) => ({ factor: r.factor, order: r.order || 'desc' }))
  if (sort.length) body.sort = sort
  return body
}

async function runMultiScreen(page = 1) {
  if (!multiForm.conditions.length) {
    showMockToast('请至少添加一个因子条件')
    return
  }
  multiLoading.value = true
  try {
    multiResult.value = await api.screenerMultiRun(buildMultiBody(page))
    multiHasRun.value = true
    if (multiResult.value.message) showMockToast(multiResult.value.message)
    if (page === 1) loadHistory()
  } catch (e) {
    showMockToast(e.message)
  } finally {
    multiLoading.value = false
  }
}

function goMultiPage(page) {
  const target = Math.max(1, Number(page) || 1)
  if (target === Number(multiResult.value.page)) return
  runMultiScreen(target)
}

function addMultiCondition() {
  if (!multiForm.pickerFactor) {
    showMockToast('请选择因子')
    return
  }
  if (
    (multiForm.pickerMin == null || multiForm.pickerMin === '')
    && (multiForm.pickerMax == null || multiForm.pickerMax === '')
  ) {
    showMockToast('请设置 ≥ 或 ≤ 阈值')
    return
  }
  if (multiForm.conditions.some((c) => c.factor === multiForm.pickerFactor)) {
    showMockToast('该因子已存在，可点击「编辑」修改阈值')
    return
  }
  multiForm.conditions.push({
    factor: multiForm.pickerFactor,
    min_value: multiForm.pickerMin != null && multiForm.pickerMin !== '' ? multiForm.pickerMin : null,
    max_value: multiForm.pickerMax != null && multiForm.pickerMax !== '' ? multiForm.pickerMax : null,
  })
  multiForm.pickerMin = null
  multiForm.pickerMax = null
}

function removeMultiCondition(idx) {
  if (multiEditingIdx.value === idx) multiEditingIdx.value = -1
  else if (multiEditingIdx.value > idx) multiEditingIdx.value -= 1
  multiForm.conditions.splice(idx, 1)
  syncSortRulesWithConditions()
}

function isEmptyThreshold(cond) {
  return (cond.min_value == null || cond.min_value === '')
    && (cond.max_value == null || cond.max_value === '')
}

function normalizeThreshold(v) {
  return v != null && v !== '' ? v : null
}

function startEditMultiCondition(idx) {
  const cond = multiForm.conditions[idx]
  multiEditingIdx.value = idx
  multiEditDraft.factor = cond.factor
  multiEditDraft.min_value = cond.min_value ?? null
  multiEditDraft.max_value = cond.max_value ?? null
}

function cancelEditMultiCondition() {
  multiEditingIdx.value = -1
}

function saveEditMultiCondition() {
  const idx = multiEditingIdx.value
  if (idx < 0) return

  if (!multiEditDraft.factor) {
    showMockToast('请选择因子')
    return
  }
  const minVal = normalizeThreshold(multiEditDraft.min_value)
  const maxVal = normalizeThreshold(multiEditDraft.max_value)
  if (minVal == null && maxVal == null) {
    showMockToast('请设置 ≥ 或 ≤ 阈值')
    return
  }
  const duplicate = multiForm.conditions.find(
    (c, i) => i !== idx && c.factor === multiEditDraft.factor,
  )
  if (duplicate) {
    showMockToast('该因子已在其他条件中使用')
    return
  }

  multiForm.conditions[idx] = {
    factor: multiEditDraft.factor,
    min_value: minVal,
    max_value: maxVal,
  }
  syncSortRulesWithConditions()
  multiEditingIdx.value = -1
}

function applyMultiPreset(preset) {
  multiEditingIdx.value = -1
  multiForm.conditions = preset.conditions.map((c) => ({ ...c }))
  multiForm.sortRules = preset.conditions.length
    ? [{ factor: preset.conditions[0].factor, order: 'desc' }]
    : []
  goScreenerMode('multi')
}

async function parseMultiNl() {
  const text = multiNlText.value.trim()
  if (!text) return
  multiNlLoading.value = true
  multiNlResult.value = { interpretation: '', source: '', warnings: [], log: [], stats: {} }
  try {
    const res = await api.screenerNlParse({ text, prefer: multiNlPrefer.value })
    multiNlResult.value = res
    if (res.conditions?.length) {
      if (multiForm.conditions.length && !window.confirm('将替换当前因子条件，是否继续？')) {
        return
      }
      multiForm.conditions = res.conditions.map((c) => ({
        factor: c.factor,
        min_value: c.min_value ?? null,
        max_value: c.max_value ?? null,
      }))
      if (res.market) multiForm.market = res.market
      if (res.sector) multiForm.sector = res.sector
      multiForm.sortRules = res.conditions.length
        ? [{ factor: res.conditions[0].factor, order: 'desc' }]
        : []
    }
  } catch (e) {
    showMockToast(e.message)
  } finally {
    multiNlLoading.value = false
  }
}

function resetMultiForm() {
  multiEditingIdx.value = -1
  multiForm.category = ''
  multiForm.pickerFactor = 'ROC20'
  multiForm.pickerMin = null
  multiForm.pickerMax = null
  multiForm.market = ''
  multiForm.sector = ''
  multiForm.sortRules = [{ factor: 'ROC20', order: 'desc' }]
  multiForm.conditions = [
    { factor: 'ROC20', min_value: 0.95 },
    { factor: 'MA5', min_value: 1.0 },
  ]
  multiHasRun.value = false
  multiResult.value = { total: 0, page: 1, page_size: 50, factors: [], rows: [] }
}

function onMultiCategoryChange() {
  const list = multiFilteredFactors.value
  if (list.length && !list.find((f) => f.name === multiForm.pickerFactor)) {
    multiForm.pickerFactor = list[0].name
  }
}

function resetForm() {
  Object.assign(form, {
    market: '', sector: '', minClose: null, maxClose: null,
    changeDays: 5, minChangePct: null, maxChangePct: null, minVolume: null, maRule: '',
  })
  hasRun.value = false
  result.value = { total: 0, page: 1, page_size: 50, change_days: 5, rows: [] }
}

function resetQlibForm() {
  qlibForm.category = ''
  qlibForm.factor = 'ROC20'
  qlibForm.market = ''
  qlibForm.sector = ''
  qlibForm.minValue = null
  qlibForm.maxValue = null
  qlibHasRun.value = false
  qlibResult.value = { total: 0, page: 1, page_size: 50, factor: '', rows: [] }
}

function applyExample(ex) {
  qlibForm.factor = ex.factor
  qlibForm.minValue = ex.min_value != null && ex.min_value !== '' ? Number(ex.min_value) : null
  qlibForm.maxValue = ex.max_value != null && ex.max_value !== '' ? Number(ex.max_value) : null
}

function applyGlobalExample(ex) {
  applyExample(ex)
  goScreenerMode('qlib')
}

function formatMs(v) {
  if (v == null || Number.isNaN(v)) return '—'
  if (v >= 1000) return (v / 1000).toFixed(2) + 's'
  return Math.round(v) + 'ms'
}

function onCategoryChange() {
  const list = filteredFactors.value
  if (list.length && !list.find((f) => f.name === qlibForm.factor)) {
    qlibForm.factor = list[0].name
  }
}

async function viewKline(symbol) {
  const code = normalizeSymbolInput(String(symbol || ''))
  if (!isSymbolCode(code)) {
    showMockToast('无效股票代码')
    return
  }
  await router.push({
    name: 'MarketData',
    query: { symbol: code, t: String(Date.now()) },
  })
}

function formatPct(v) {
  if (v == null || Number.isNaN(v)) return '—'
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'
}

function pctClass(v) {
  if (v == null) return ''
  return v >= 0 ? 'up' : 'down'
}

function formatVol(v) {
  if (v >= 1e8) return (v / 1e8).toFixed(2) + ' 亿'
  if (v >= 1e4) return (v / 1e4).toFixed(1) + ' 万'
  return String(v)
}

function formatFactor(v) {
  if (v == null || Number.isNaN(v)) return '—'
  if (Math.abs(v) >= 1000) return v.toExponential(3)
  return v.toFixed(4)
}

async function loadSectors() {
  try {
    sectors.value = await api.screenerSectors()
  } catch {
    sectors.value = []
  }
}

async function loadFactors() {
  try {
    factorMeta.value = await api.screenerFactors()
    if (!factorMeta.value.factors?.find((f) => f.name === qlibForm.factor)) {
      qlibForm.factor = factorMeta.value.factors?.[0]?.name || 'ROC20'
    }
    if (!factorMeta.value.factors?.find((f) => f.name === multiForm.pickerFactor)) {
      multiForm.pickerFactor = factorMeta.value.factors?.[0]?.name || 'ROC20'
    }
  } catch {
    factorMeta.value = { categories: [], factors: [], total: 0 }
  }
}

const HISTORY_MODE_LABELS = {
  basic: '基础',
  qlib: 'Alpha158',
  multi: '多因子',
}

function historyModeLabel(modeKey) {
  return HISTORY_MODE_LABELS[modeKey] || modeKey
}

function formatHistoryTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const data = await api.screenerHistory({ limit: '30' })
    historyList.value = data.rows || []
  } catch {
    historyList.value = []
  } finally {
    historyLoading.value = false
  }
}

function applyBasicQuery(q) {
  form.market = q.market || ''
  form.sector = q.sector || ''
  form.minClose = q.min_close ?? null
  form.maxClose = q.max_close ?? null
  form.changeDays = q.change_days ?? 5
  form.minChangePct = q.min_change_pct ?? null
  form.maxChangePct = q.max_change_pct ?? null
  form.minVolume = q.min_volume ?? null
  if (q.above_ma === 5) form.maRule = 'above5'
  else if (q.above_ma === 20) form.maRule = 'above20'
  else if (q.above_ma === 60) form.maRule = 'above60'
  else if (q.below_ma === 20) form.maRule = 'below20'
  else form.maRule = ''
}

function applyHistoryQuery(entry) {
  goScreenerMode(entry.mode || 'basic')
  multiEditingIdx.value = -1
  const q = entry.query || {}
  if (entry.mode === 'basic') {
    applyBasicQuery(q)
    return
  }
  if (entry.mode === 'qlib') {
    qlibForm.category = ''
    qlibForm.factor = q.factor || 'ROC20'
    qlibForm.market = q.market || ''
    qlibForm.sector = q.sector || ''
    qlibForm.minValue = q.min_value ?? null
    qlibForm.maxValue = q.max_value ?? null
    return
  }
  if (entry.mode === 'multi') {
    multiForm.category = ''
    multiForm.market = q.market || ''
    multiForm.sector = q.sector || ''
    if (Array.isArray(q.sort) && q.sort.length) {
      multiForm.sortRules = q.sort.map((r) => ({
        factor: r.factor,
        order: r.order === 'asc' ? 'asc' : 'desc',
      }))
    } else if (q.sort_by) {
      multiForm.sortRules = [{ factor: q.sort_by, order: 'desc' }]
    } else {
      multiForm.sortRules = []
    }
    multiForm.conditions = (q.conditions || []).map((c) => ({
      factor: c.factor,
      min_value: c.min_value ?? null,
      max_value: c.max_value ?? null,
    }))
    syncSortRulesWithConditions()
  }
}

function applyHistory(entry) {
  applyHistoryQuery(entry)
}

async function replayHistory(entry) {
  applyHistoryQuery(entry)
  if (entry.mode === 'basic') await runScreen(1)
  else if (entry.mode === 'qlib') await runQlibScreen(1)
  else await runMultiScreen(1)
}

function viewHistorySnapshot(entry) {
  applyHistoryQuery(entry)
  const summary = entry.result_summary || {}
  const q = entry.query || {}
  const snap = {
    total: summary.total ?? 0,
    page: 1,
    page_size: q.page_size || 50,
    rows: entry.result_rows || [],
  }
  if (entry.mode === 'basic') {
    result.value = {
      ...snap,
      change_days: summary.change_days ?? form.changeDays,
      above_ma: summary.above_ma,
      below_ma: summary.below_ma,
    }
    hasRun.value = true
  } else if (entry.mode === 'qlib') {
    qlibResult.value = { ...snap, factor: summary.factor || q.factor || '' }
    qlibHasRun.value = true
  } else {
    multiResult.value = { ...snap, factors: summary.factors || [] }
    multiHasRun.value = true
  }
}

async function deleteHistoryItem(id) {
  try {
    await api.screenerHistoryDelete(id)
    historyList.value = historyList.value.filter((h) => h.id !== id)
  } catch (e) {
    showMockToast(e.message)
  }
}

async function clearHistory() {
  if (!historyList.value.length) return
  if (!window.confirm('确定清空全部选股历史？')) return
  try {
    await api.screenerHistoryClear()
    historyList.value = []
  } catch (e) {
    showMockToast(e.message)
  }
}

onMounted(async () => {
  await Promise.all([loadSectors(), loadFactors(), loadHistory()])
})
</script>

<style scoped>
.screener-layout { align-items: start; }

.hint {
  margin: 0 0 1rem;
  color: var(--muted);
  font-size: 0.85rem;
}

.expr-hint {
  font-size: 0.75rem;
  color: var(--muted);
  word-break: break-all;
  margin: -0.25rem 0 0.75rem;
  padding: 0.5rem;
  background: var(--surface2);
  border-radius: 6px;
}

.preset-hint { margin-top: 0.5rem; font-size: 0.8rem; }

.row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.result-meta { margin: 0; font-size: 0.82rem; }

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--muted);
}

.empty-state .icon { font-size: 2rem; margin-bottom: 0.5rem; }

.pagination {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 1rem;
}

.up { color: var(--ok); }
.down { color: var(--err); }

@media (max-width: 960px) {
  .screener-layout { grid-template-columns: 1fr; }
}

.factor-info {
  margin: 0 0 1rem;
  padding: 0.75rem;
  background: var(--surface2);
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
}

.factor-desc { margin: 0 0 0.5rem; line-height: 1.5; }

.factor-usage, .factor-hint { margin: 0.35rem 0; line-height: 1.45; }

.factor-info .label {
  display: inline-block;
  min-width: 4rem;
  color: var(--muted);
  font-size: 0.78rem;
  margin-right: 0.35rem;
}

.factor-examples {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.5rem;
}

.chip, .link-chip {
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font-size: 0.78rem;
  cursor: pointer;
}

.link-chip {
  border: none;
  background: transparent;
  color: var(--accent);
  padding: 0;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.preset-hint { display: flex; flex-wrap: wrap; align-items: center; gap: 0.35rem; }

.history-card {
  padding-top: 0.75rem;
}

.history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.history-head h2 {
  margin: 0;
}

.history-head-actions {
  display: flex;
  gap: 0.35rem;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  background: var(--surface2);
  border-radius: var(--radius-sm);
  flex-wrap: wrap;
}

.history-main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
  min-width: 0;
  flex: 1;
}

.history-title {
  font-size: 0.88rem;
  font-weight: 500;
}

.history-meta {
  font-size: 0.78rem;
}

.mode-badge {
  font-size: 0.72rem;
  padding: 0.12rem 0.45rem;
  border-radius: 999px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--muted);
  flex-shrink: 0;
}

.mode-badge.qlib { color: var(--accent); border-color: rgba(59, 130, 246, 0.35); }
.mode-badge.multi { color: #8b5cf6; border-color: rgba(139, 92, 246, 0.35); }

.history-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  flex-shrink: 0;
}

.category-help { margin-top: -0.5rem; font-size: 0.8rem; }

.log-card { margin-top: 0.5rem; }

.log-head {
  cursor: pointer;
  user-select: none;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.5rem 1rem;
}

.log-toggle {
  margin-left: auto;
  font-size: 0.8rem;
  color: var(--muted);
}

.log-body {
  max-height: 280px;
  overflow: auto;
  margin-top: 0.75rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border);
  font-family: ui-monospace, monospace;
  font-size: 0.78rem;
}

.log-line {
  display: flex;
  gap: 0.5rem;
  padding: 0.2rem 0;
  line-height: 1.4;
}

.log-line.warn .log-msg { color: var(--warn, #d97706); }

.log-time { color: var(--muted); min-width: 4.5rem; }

.log-step { color: var(--accent); min-width: 3.5rem; }

.log-msg { flex: 1; word-break: break-word; }

.cond-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.cond-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.55rem 0.65rem;
  background: var(--surface2);
  border-radius: var(--radius-sm);
}

.cond-row.editing {
  align-items: stretch;
  padding: 0.65rem;
}

.cond-row-actions {
  display: flex;
  flex-shrink: 0;
  gap: 0.35rem;
}

.cond-edit {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.cond-edit-field {
  margin: 0;
}

.cond-edit-thresholds {
  margin: 0;
}

.cond-edit-actions {
  display: flex;
  gap: 0.4rem;
}

.cond-main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
}

.cond-threshold {
  font-size: 0.82rem;
  color: var(--accent);
}

.card-inset {
  padding: 0.75rem;
  margin-bottom: 1rem;
  background: var(--surface2);
  border-radius: var(--radius-sm);
}

.cond-add-title {
  margin: 0 0 0.65rem;
  font-size: 0.85rem;
  color: var(--muted);
}

/* 多因子结果：右侧 K 线列固定，其余列横向滚动 */
.table-sticky-action {
  max-width: 100%;
}

.table-sticky-action .multi-result-table {
  width: max-content;
  min-width: 100%;
}

.table-sticky-action .col-action {
  position: sticky;
  right: 0;
  z-index: 2;
  background: var(--surface);
  box-shadow: -6px 0 10px rgba(0, 0, 0, 0.12);
  text-align: center;
  min-width: 4.5rem;
}

.table-sticky-action thead .col-action {
  z-index: 4;
  background: var(--surface2);
}

.table-sticky-action tbody tr:hover .col-action {
  background: var(--surface2);
}

.nl-parse textarea {
  width: 100%;
  resize: vertical;
  min-height: 4.5rem;
  margin-bottom: 0.65rem;
}

.nl-parse-row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.nl-parse-mode {
  flex: 1;
  min-width: 10rem;
  margin: 0;
}

.nl-parse-result {
  margin: 0.5rem 0 0;
  font-size: 0.88rem;
  line-height: 1.5;
}

.nl-warn {
  color: var(--warn, #d97706);
  margin: 0.25rem 0 0;
}

.nl-log {
  margin-top: 0.65rem;
}

.nl-log-toggle {
  margin-bottom: 0.35rem;
}

.nl-log-body {
  max-height: 220px;
  overflow: auto;
  padding: 0.5rem 0.65rem;
  background: var(--surface2);
  border-radius: var(--radius-sm);
  font-family: ui-monospace, monospace;
  font-size: 0.76rem;
}

.sort-block {
  margin-bottom: 1rem;
}

.sort-list {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  margin-bottom: 0.55rem;
}

.sort-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
}

.sort-row select {
  min-width: 7rem;
}
</style>
