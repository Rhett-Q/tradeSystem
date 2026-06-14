export function normalizeSymbolInput(raw) {
  const s = raw.trim().toUpperCase()
  if (/^\d{6}$/.test(s)) {
    if (s.startsWith('6') || s.startsWith('9')) return `${s}.SH`
    if (s.startsWith('0') || s.startsWith('3')) return `${s}.SZ`
    if (s.startsWith('4') || s.startsWith('8')) return `${s}.BJ`
  }
  if (/^\d{6}\.(SH|SZ|BJ)$/.test(s)) return s
  return s
}

export function isSymbolCode(input) {
  return /^\d{6}(\.(SH|SZ|BJ))?$/i.test(input.trim())
}
