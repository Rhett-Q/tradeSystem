<template>
  <div class="stack">
    <div class="card">
      <h2>MiniQMT 连接</h2>
      <p class="hint">xtquant 随 QMT 客户端安装，Python 需与 QMT 位数一致。</p>
      <label>QMT 安装路径
        <input v-model="form.minqmt.path" type="text" />
      </label>
      <label>资金账号（可选）
        <input v-model="form.minqmt.account" type="text" placeholder="留空使用默认" />
      </label>
    </div>

    <div class="card">
      <h2>PostgreSQL</h2>
      <div class="grid-2">
        <label>主机
          <input v-model="form.postgres.host" type="text" />
        </label>
        <label>端口
          <input v-model.number="form.postgres.port" type="number" />
        </label>
        <label>数据库
          <input v-model="form.postgres.database" type="text" />
        </label>
        <label>用户名
          <input v-model="form.postgres.user" type="text" />
        </label>
      </div>
      <div class="btn-row">
        <button class="btn primary" @click="initSchema">初始化 Schema</button>
      </div>
    </div>

    <div class="card">
      <h2>LLM 智能解析</h2>
      <p class="hint">
        用于多因子选股「一句话转条件」。支持 OpenAI 及兼容接口（DeepSeek、通义、本地 Ollama 等）。
      </p>
      <label class="checkbox-row">
        <input v-model="form.llm.enabled" type="checkbox" />
        启用 LLM 解析（关闭时仅使用内置规则引擎）
      </label>
      <p class="hint preset-hint">
        快捷预设：
        <button
          v-for="p in llmPresets"
          :key="p.label"
          type="button"
          class="link-chip"
          @click="applyLlmPreset(p)"
        >
          {{ p.label }}
        </button>
      </p>
      <div class="grid-2">
        <label>API Base URL
          <input v-model="form.llm.base_url" type="text" placeholder="https://api.openai.com/v1" class="mono" />
        </label>
        <label>模型
          <input v-model="form.llm.model" type="text" placeholder="gpt-4o-mini" />
          <span class="field-hint">须与接口文档一致，如 deepseek-v4-flash</span>
        </label>
        <label>API Key
          <input
            v-model="form.llm.api_key"
            type="password"
            :placeholder="form.llm.api_key_configured ? '已配置，留空不修改' : 'sk-...'"
            autocomplete="off"
          />
        </label>
        <label>超时（秒）
          <input v-model.number="form.llm.timeout_sec" type="number" min="10" max="300" />
        </label>
      </div>
      <p v-if="form.llm.api_key_configured && !form.llm.api_key" class="hint">API Key 已保存，如需更换请直接输入新 Key。</p>
      <div class="btn-row">
        <button class="btn primary" @click="save">保存 LLM 配置</button>
      </div>
    </div>

    <div class="card">
      <h2>同步默认参数</h2>
      <div class="grid-2">
        <label>默认周期
          <select v-model="form.sync.default_period">
            <option value="1d">1d 日线</option>
            <option value="5m">5m</option>
          </select>
        </label>
        <label>批大小
          <input v-model.number="form.sync.batch_size" type="number" />
        </label>
        <label>全量起始日期
          <input v-model="form.sync.start_date" type="text" />
        </label>
        <label>定时 Cron
          <input v-model="form.sync.schedule_cron" type="text" class="mono" />
        </label>
      </div>
      <div class="btn-row">
        <button class="btn primary" @click="save">保存配置</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive } from 'vue'
import { api } from '@/api/client'
import { showMockToast } from '@/mock'

const form = reactive({
  minqmt: { path: '', account: '', auto_connect: true },
  postgres: { host: '127.0.0.1', port: 5432, database: 'trade_db', user: 'trade_user' },
  sync: { default_period: '1d', batch_size: 200, start_date: '20200101', schedule_cron: '0 18 * * 1-5' },
  llm: {
    enabled: false,
    base_url: 'https://api.openai.com/v1',
    api_key: '',
    api_key_configured: false,
    model: 'gpt-4o-mini',
    timeout_sec: 60,
  },
})

const llmPresets = [
  { label: 'OpenAI', base_url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  { label: 'DeepSeek 官方', base_url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  { label: 'DeepSeek V4 Flash', base_url: 'https://api.deepseek.com/v1', model: 'deepseek-v4-flash' },
  { label: 'DeepSeek V4 Pro', base_url: 'https://api.deepseek.com/v1', model: 'deepseek-v4-pro' },
]

function applyLlmPreset(preset) {
  form.llm.base_url = preset.base_url
  form.llm.model = preset.model
}

async function load() {
  try {
    const data = await api.getSettings()
    Object.assign(form.minqmt, data.minqmt)
    Object.assign(form.postgres, data.postgres)
    Object.assign(form.sync, data.sync)
    Object.assign(form.llm, data.llm || {})
    form.llm.api_key = ''
  } catch (e) {
    showMockToast(e.message)
  }
}

async function save() {
  try {
    const payload = {
      minqmt: { ...form.minqmt },
      postgres: { ...form.postgres },
      sync: { ...form.sync },
      llm: {
        enabled: form.llm.enabled,
        base_url: form.llm.base_url,
        model: form.llm.model,
        timeout_sec: form.llm.timeout_sec,
        api_key: form.llm.api_key || '',
      },
    }
    await api.saveSettings(payload)
    await load()
    showMockToast('配置已保存')
  } catch (e) {
    showMockToast(e.message)
  }
}

async function initSchema() {
  try {
    const res = await api.initDb()
    showMockToast(res.message)
  } catch (e) {
    showMockToast(e.message)
  }
}

onMounted(load)
</script>

<style scoped>
.checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
  cursor: pointer;
}

.checkbox-row input {
  width: auto;
}

.preset-hint {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.75rem;
}

.link-chip {
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--accent);
  font-size: 0.78rem;
  cursor: pointer;
}

.field-hint {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.75rem;
  color: var(--muted);
}
</style>
