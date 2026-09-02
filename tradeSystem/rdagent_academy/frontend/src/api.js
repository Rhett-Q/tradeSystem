const BASE = ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const text = await res.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { raw: text }
  }
  if (!res.ok) {
    const msg = data?.detail || data?.message || res.statusText
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return data
}

export const api = {
  meta: () => request('/api/meta'),
  health: () => request('/api/health'),
  curriculum: () => request('/api/curriculum'),
  lesson: (id) => request(`/api/lessons/${id}`),
  jobs: () => request('/api/jobs'),
  catalog: () => request('/api/jobs/catalog'),
  startJob: (kind, meta = {}) =>
    request('/api/jobs', { method: 'POST', body: JSON.stringify({ kind, meta }) }),
  job: (id, fromLine = 0) => request(`/api/jobs/${id}?from_line=${fromLine}`),
  cancelJob: (id) => request(`/api/jobs/${id}/cancel`, { method: 'POST' }),
  sessions: () => request('/api/sessions'),
  session: (id) => request(`/api/sessions/${id}`),
  openUi: (log_path = null) =>
    request('/api/ui/streamlit', { method: 'POST', body: JSON.stringify({ log_path }) }),
}