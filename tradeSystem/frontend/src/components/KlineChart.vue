<template>
  <div class="kline-chart-wrap">
    <div class="ma-toolbar">
      <span class="ma-label">均线</span>
      <button
        v-for="p in MA_PERIODS"
        :key="p"
        type="button"
        class="ma-chip"
        :class="{ active: selectedMa.includes(p) }"
        :style="{ '--ma-color': MA_COLORS[p] }"
        @click="toggleMa(p)"
      >
        MA{{ p }}
      </button>
    </div>
    <div ref="containerRef" class="chart-container"></div>
    <div v-if="hoverInfo" class="ohlc-tooltip">
      <span>{{ hoverInfo.time }}</span>
      <span>开 <b>{{ hoverInfo.open }}</b></span>
      <span>高 <b class="up">{{ hoverInfo.high }}</b></span>
      <span>低 <b class="down">{{ hoverInfo.low }}</b></span>
      <span>收 <b :class="hoverInfo.up ? 'up' : 'down'">{{ hoverInfo.close }}</b></span>
      <span v-if="hoverInfo.volume">量 {{ hoverInfo.volume }}</span>
      <template v-for="p in selectedMa" :key="'ma-' + p">
        <span v-if="hoverInfo.ma[p]">
          MA{{ p }} <b :style="{ color: MA_COLORS[p] }">{{ hoverInfo.ma[p] }}</b>
        </span>
      </template>
      <template v-if="hoverInfo.k">
        <span class="sep">|</span>
        <span>K <b class="k-line">{{ hoverInfo.k }}</b></span>
        <span>D <b class="d-line">{{ hoverInfo.d }}</b></span>
        <span>J <b class="j-line">{{ hoverInfo.j }}</b></span>
      </template>
    </div>
    <div v-if="hasData" class="legend">
      <template v-if="markers.length">
        <span><i class="dot buy"></i>买入</span>
        <span><i class="dot sell"></i>卖出</span>
        <span class="sep">|</span>
      </template>
      <span><i class="dot k"></i>K</span>
      <span><i class="dot d"></i>D</span>
      <span><i class="dot j"></i>J</span>
      <span class="muted">N=9</span>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ColorType,
  CrosshairMode,
  createChart,
  createSeriesMarkers,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
} from 'lightweight-charts'
import { calcKDJ } from '@/utils/kdj'
import { MA_COLORS, MA_PERIODS, calcMALine } from '@/utils/ma'

/** A 股惯例：红涨绿跌 */
const CHART_UP = '#ef4444'
const CHART_DOWN = '#22c55e'
const CHART_UP_VOL = 'rgba(239, 68, 68, 0.55)'
const CHART_DOWN_VOL = 'rgba(34, 197, 94, 0.55)'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  period: { type: String, default: '1d' },
  height: { type: Number, default: 480 },
  markers: { type: Array, default: () => [] },
  initialMa: { type: Array, default: () => [5, 10, 20] },
})

const containerRef = ref(null)
const hoverInfo = ref(null)
const selectedMa = ref([...props.initialMa])

const hasData = computed(() => props.rows.length > 0)

let chart = null
let candleSeries = null
let volumeSeries = null
let kSeries = null
let dSeries = null
let jSeries = null
/** @type {Map<number, import('lightweight-charts').ISeriesApi<'Line'>>} */
const maSeriesMap = new Map()
let resizeObserver = null
let seriesMarkers = null

function parseTime(dateStr) {
  const s = String(dateStr)
  const isDaily = props.period === '1d' || props.period === '1w' || props.period === '1mon'
  if (isDaily || !s.includes(' ')) {
    return s.slice(0, 10)
  }
  return Math.floor(new Date(s.replace(' ', 'T')).getTime() / 1000)
}

function getTimeAt(rows, index) {
  return parseTime(rows[index].date)
}

function toChartData(rows) {
  const candles = []
  const volumes = []
  const kdj = calcKDJ(rows)
  const kLine = []
  const dLine = []
  const jLine = []

  for (let i = 0; i < rows.length; i++) {
    const r = rows[i]
    const time = parseTime(r.date)
    const up = r.close >= r.open
    candles.push({ time, open: r.open, high: r.high, low: r.low, close: r.close })
    volumes.push({
      time,
      value: r.volume,
      color: up ? CHART_UP_VOL : CHART_DOWN_VOL,
    })
    kLine.push({ time, value: kdj[i].k })
    dLine.push({ time, value: kdj[i].d })
    jLine.push({ time, value: kdj[i].j })
  }

  return { candles, volumes, kLine, dLine, jLine }
}

function formatVol(v) {
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(1) + '万'
  return String(v)
}

function initMaSeries() {
  for (const p of MA_PERIODS) {
    const enabled = selectedMa.value.includes(p)
    const series = chart.addSeries(
      LineSeries,
      {
        color: MA_COLORS[p],
        lineWidth: 1,
        title: '',
        priceLineVisible: false,
        lastValueVisible: false,
        visible: enabled,
      },
      0,
    )
    maSeriesMap.set(p, series)
  }
}

function updateMaSeries(rows) {
  for (const p of MA_PERIODS) {
    const series = maSeriesMap.get(p)
    if (!series) continue

    const enabled = selectedMa.value.includes(p)
    series.applyOptions({ visible: enabled, lastValueVisible: false, priceLineVisible: false })

    if (!enabled || rows.length < p) {
      series.setData([])
      continue
    }

    series.setData(calcMALine(rows, p, (i) => getTimeAt(rows, i)))
  }
}

function toggleMa(period) {
  const idx = selectedMa.value.indexOf(period)
  if (idx >= 0) {
    selectedMa.value = selectedMa.value.filter((p) => p !== period)
  } else {
    selectedMa.value = [...selectedMa.value, period].sort((a, b) => a - b)
  }
  if (props.rows.length) updateMaSeries(props.rows)
}

function initChart() {
  if (!containerRef.value || chart) return

  const width = containerRef.value.clientWidth || containerRef.value.offsetWidth || 640
  chart = createChart(containerRef.value, {
    width,
    height: props.height,
    layout: {
      background: { type: ColorType.Solid, color: 'transparent' },
      textColor: '#8b9cb3',
      fontSize: 11,
    },
    grid: {
      vertLines: { color: 'rgba(42, 53, 72, 0.6)' },
      horzLines: { color: 'rgba(42, 53, 72, 0.6)' },
    },
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: { color: 'rgba(59, 130, 246, 0.5)', width: 1, style: 2 },
      horzLine: { color: 'rgba(59, 130, 246, 0.5)', width: 1, style: 2 },
    },
    rightPriceScale: {
      borderColor: '#2a3548',
      alignLabels: true,
    },
    timeScale: {
      borderColor: '#2a3548',
      timeVisible: true,
      secondsVisible: false,
      fixLeftEdge: true,
      fixRightEdge: false,
      rightOffset: 8,
    },
    handleScroll: { mouseWheel: true, pressedMouseMove: true },
    handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
  })

  chart.addPane()
  chart.addPane()

  const panes = chart.panes()
  panes[0].setStretchFactor(3)
  panes[1].setStretchFactor(1)
  panes[2].setStretchFactor(1)

  candleSeries = chart.addSeries(
    CandlestickSeries,
    {
      upColor: CHART_UP,
      downColor: CHART_DOWN,
      borderUpColor: CHART_UP,
      borderDownColor: CHART_DOWN,
      wickUpColor: CHART_UP,
      wickDownColor: CHART_DOWN,
      priceLineVisible: false,
      lastValueVisible: true,
    },
    0,
  )

  panes[0].priceScale('right').applyOptions({
    scaleMargins: { top: 0.08, bottom: 0.08 },
  })

  initMaSeries()

  volumeSeries = chart.addSeries(
    HistogramSeries,
    {
      priceFormat: { type: 'volume' },
      priceLineVisible: false,
      lastValueVisible: false,
    },
    1,
  )

  panes[1].priceScale('right').applyOptions({
    scaleMargins: { top: 0.1, bottom: 0.05 },
  })

  kSeries = chart.addSeries(
    LineSeries,
    {
      color: '#f59e0b',
      lineWidth: 1.5,
      title: '',
      priceLineVisible: false,
      lastValueVisible: false,
    },
    2,
  )

  dSeries = chart.addSeries(
    LineSeries,
    {
      color: '#3b82f6',
      lineWidth: 1.5,
      title: '',
      priceLineVisible: false,
      lastValueVisible: false,
    },
    2,
  )

  jSeries = chart.addSeries(
    LineSeries,
    {
      color: '#ec4899',
      lineWidth: 1,
      title: '',
      priceLineVisible: false,
      lastValueVisible: false,
    },
    2,
  )

  panes[2].priceScale('right').applyOptions({
    scaleMargins: { top: 0.08, bottom: 0.05 },
  })

  chart.subscribeCrosshairMove((param) => {
    if (!param.time || !param.seriesData) {
      hoverInfo.value = null
      return
    }
    const candle = param.seriesData.get(candleSeries)
    const vol = param.seriesData.get(volumeSeries)
    const kv = param.seriesData.get(kSeries)
    const dv = param.seriesData.get(dSeries)
    const jv = param.seriesData.get(jSeries)
    if (!candle) {
      hoverInfo.value = null
      return
    }
    const t = param.time
    let timeLabel = typeof t === 'string' ? t : ''
    if (typeof t === 'number') {
      timeLabel = new Date(t * 1000).toLocaleString('zh-CN', { hour12: false })
    }

    const ma = {}
    for (const p of selectedMa.value) {
      const mv = param.seriesData.get(maSeriesMap.get(p))
      if (mv) ma[p] = mv.value.toFixed(2)
    }

    hoverInfo.value = {
      time: timeLabel,
      open: candle.open.toFixed(2),
      high: candle.high.toFixed(2),
      low: candle.low.toFixed(2),
      close: candle.close.toFixed(2),
      up: candle.close >= candle.open,
      volume: vol ? formatVol(vol.value) : '',
      ma,
      k: kv ? kv.value.toFixed(2) : '',
      d: dv ? dv.value.toFixed(2) : '',
      j: jv ? jv.value.toFixed(2) : '',
    }
  })

  resizeObserver = new ResizeObserver(() => {
    if (chart && containerRef.value) {
      chart.applyOptions({ width: containerRef.value.clientWidth })
    }
  })
  resizeObserver.observe(containerRef.value)
}

function updateData(rows) {
  if (!candleSeries || !rows.length) return
  const { candles, volumes, kLine, dLine, jLine } = toChartData(rows)
  candleSeries.setData(candles)
  volumeSeries.setData(volumes)
  kSeries.setData(kLine)
  dSeries.setData(dLine)
  jSeries.setData(jLine)
  updateMaSeries(rows)
  chart.timeScale().fitContent()
  chart.timeScale().applyOptions({ rightOffset: 8 })
  updateMarkers()
}

function buildChartMarkers(signals) {
  return signals.map((s) => {
    const isBuy = s.side === 'buy'
    return {
      time: parseTime(s.date),
      position: isBuy ? 'belowBar' : 'aboveBar',
      shape: isBuy ? 'arrowUp' : 'arrowDown',
      color: isBuy ? CHART_UP : CHART_DOWN,
      text: isBuy ? '买' : '卖',
    }
  })
}

function updateMarkers() {
  if (!candleSeries) return
  const list = buildChartMarkers(props.markers)
  if (!list.length) {
    seriesMarkers?.setMarkers([])
    return
  }
  if (!seriesMarkers) {
    seriesMarkers = createSeriesMarkers(candleSeries, list)
  } else {
    seriesMarkers.setMarkers(list)
  }
}

function destroyChart() {
  resizeObserver?.disconnect()
  resizeObserver = null
  seriesMarkers = null
  chart?.remove()
  chart = null
  candleSeries = null
  volumeSeries = null
  kSeries = null
  dSeries = null
  jSeries = null
  maSeriesMap.clear()
}

async function renderChart(rows) {
  if (!rows.length) {
    hoverInfo.value = null
    destroyChart()
    return
  }
  await nextTick()
  await new Promise((resolve) => requestAnimationFrame(resolve))
  if (!containerRef.value) return
  if (!chart) initChart()
  if (chart) updateData(rows)
}

onMounted(() => {
  renderChart(props.rows)
})

watch(
  () => props.rows,
  (rows) => {
    renderChart(rows)
  },
  { deep: true },
)

watch(
  () => props.height,
  (h) => chart?.applyOptions({ height: h }),
)

watch(
  () => props.markers,
  () => {
    if (chart && candleSeries) updateMarkers()
  },
  { deep: true },
)

watch(
  () => props.initialMa,
  (periods) => {
    selectedMa.value = [...periods]
    if (props.rows.length) updateMaSeries(props.rows)
  },
  { deep: true },
)

onBeforeUnmount(destroyChart)
</script>

<style scoped>
.kline-chart-wrap {
  position: relative;
  width: 100%;
}

.ma-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.5rem;
}

.ma-label {
  font-size: 0.78rem;
  color: var(--muted);
  margin-right: 0.15rem;
}

.ma-chip {
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--muted);
  font-size: 0.75rem;
  font-family: var(--mono);
  cursor: pointer;
  transition: all 0.15s ease;
}

.ma-chip:hover {
  border-color: var(--ma-color);
  color: var(--text);
}

.ma-chip.active {
  border-color: var(--ma-color);
  color: var(--ma-color);
  background: color-mix(in srgb, var(--ma-color) 12%, transparent);
}

.chart-container {
  width: 100%;
  min-height: 320px;
}

.chart-container.hidden {
  height: 0;
  min-height: 0;
  overflow: hidden;
}

.empty-chart {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 320px;
  color: var(--muted);
  font-size: 0.875rem;
}

.empty-icon {
  font-size: 2rem;
  margin-bottom: 0.5rem;
  opacity: 0.5;
}

.ohlc-tooltip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem 1rem;
  align-items: center;
  padding: 0.5rem 0;
  font-size: 0.78rem;
  color: var(--muted);
  font-family: var(--mono);
  border-bottom: 1px solid var(--border);
  margin-bottom: 0.35rem;
}

.ohlc-tooltip b {
  color: var(--text);
  font-weight: 600;
}

.ohlc-tooltip .sep { opacity: 0.35; }
.ohlc-tooltip .up { color: #ef4444; }
.ohlc-tooltip .down { color: #22c55e; }
.ohlc-tooltip .k-line { color: #f59e0b; }
.ohlc-tooltip .d-line { color: #3b82f6; }
.ohlc-tooltip .j-line { color: #ec4899; }

.legend {
  display: flex;
  gap: 1rem;
  align-items: center;
  font-size: 0.75rem;
  color: var(--muted);
  padding-top: 0.25rem;
}

.legend .dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 0.25rem;
  vertical-align: middle;
}

.legend .dot.k { background: #f59e0b; }
.legend .dot.d { background: #3b82f6; }
.legend .dot.j { background: #ec4899; }
.legend .dot.buy { background: #ef4444; }
.legend .dot.sell { background: #22c55e; }
.legend .sep { opacity: 0.35; margin: 0 0.15rem; }
</style>
