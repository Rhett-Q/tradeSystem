/**
 * KDJ 指标计算（默认 N=9，K/D 初值 50）
 * @param {Array<{high:number, low:number, close:number}>} rows
 * @param {number} n
 */
export function calcKDJ(rows, n = 9) {
  let k = 50
  let d = 50
  const out = []

  for (let i = 0; i < rows.length; i++) {
    const start = Math.max(0, i - n + 1)
    const slice = rows.slice(start, i + 1)
    const highest = Math.max(...slice.map((r) => r.high))
    const lowest = Math.min(...slice.map((r) => r.low))
    const close = rows[i].close

    let rsv = 50
    if (highest !== lowest) {
      rsv = ((close - lowest) / (highest - lowest)) * 100
    }

    k = (2 / 3) * k + (1 / 3) * rsv
    d = (2 / 3) * d + (1 / 3) * k
    const j = 3 * k - 2 * d

    out.push({
      k: +k.toFixed(2),
      d: +d.toFixed(2),
      j: +j.toFixed(2),
    })
  }

  return out
}
