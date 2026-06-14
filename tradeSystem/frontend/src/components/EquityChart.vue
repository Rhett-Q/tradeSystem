<template>
  <div ref="containerRef" class="equity-chart"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ColorType, createChart, LineSeries } from 'lightweight-charts'

const props = defineProps({
  points: { type: Array, default: () => [] },
  height: { type: Number, default: 260 },
})

const containerRef = ref(null)
let chart = null
let lineSeries = null
let resizeObserver = null

function parseTime(dateStr) {
  return String(dateStr).slice(0, 10)
}

function initChart() {
  if (!containerRef.value || chart) return
  const width = containerRef.value.clientWidth || 640
  chart = createChart(containerRef.value, {
    width,
    height: props.height,
    layout: {
      background: { type: ColorType.Solid, color: 'transparent' },
      textColor: '#8b9cb3',
      fontSize: 11,
    },
    grid: {
      vertLines: { color: 'rgba(42, 53, 72, 0.5)' },
      horzLines: { color: 'rgba(42, 53, 72, 0.5)' },
    },
    rightPriceScale: { borderColor: '#2a3548' },
    timeScale: { borderColor: '#2a3548', fixLeftEdge: true, rightOffset: 4 },
  })
  lineSeries = chart.addSeries(LineSeries, {
    color: '#3b82f6',
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: true,
  })
  resizeObserver = new ResizeObserver(() => {
    if (chart && containerRef.value) {
      chart.applyOptions({ width: containerRef.value.clientWidth })
    }
  })
  resizeObserver.observe(containerRef.value)
}

function updateData(points) {
  if (!lineSeries || !points?.length) return
  const data = points.map((p) => ({ time: parseTime(p.date), value: p.value }))
  lineSeries.setData(data)
  chart.timeScale().fitContent()
}

function destroyChart() {
  resizeObserver?.disconnect()
  resizeObserver = null
  chart?.remove()
  chart = null
  lineSeries = null
}

onMounted(() => {
  initChart()
  updateData(props.points)
})

watch(
  () => props.points,
  (pts) => {
    if (!chart) initChart()
    updateData(pts)
  },
  { deep: true },
)

watch(
  () => props.height,
  (h) => chart?.applyOptions({ height: h }),
)

onBeforeUnmount(destroyChart)
</script>

<style scoped>
.equity-chart {
  width: 100%;
  min-height: 200px;
}
</style>
