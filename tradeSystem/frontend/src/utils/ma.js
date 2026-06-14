export const MA_PERIODS = [5, 10, 20, 30, 60, 120, 250]

export const MA_COLORS = {
  5: '#fbbf24',
  10: '#a855f7',
  20: '#22c55e',
  30: '#3b82f6',
  60: '#ec4899',
  120: '#f97316',
  250: '#64748b',
}

/**
 * 简单移动平均线（收盘价）
 * @param {Array<{close:number}>} rows
 * @param {number} period
 * @param {(index: number) => string|number} getTime
 */
export function calcMALine(rows, period, getTime) {
  const line = []
  for (let i = period - 1; i < rows.length; i++) {
    let sum = 0
    for (let j = i - period + 1; j <= i; j++) {
      sum += rows[j].close
    }
    line.push({ time: getTime(i), value: +(sum / period).toFixed(2) })
  }
  return line
}
