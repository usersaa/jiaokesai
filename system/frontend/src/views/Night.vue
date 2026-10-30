<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">夜间调度</h1>
        <div class="page-sub">23:30–06:30 静态再平衡 · 次日早高峰目标库存</div>
      </div>
      <button class="btn btn-primary" :disabled="loading" @click="run">运行夜间调度</button>
    </div>

    <div v-if="loading" class="empty">正在求解夜间调度…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!result" class="empty">点击「运行夜间调度」生成夜间再平衡方案</div>
    <template v-else>
      <div class="grid grid-4">
        <KpiCard label="求解状态" :value="result.feasible ? '可行' : '不可行'" :color="result.feasible ? 'var(--success)' : 'var(--danger)'" />
        <KpiCard label="行驶时间" :value="num(result.travel_min, 1)" hint="分钟" />
        <KpiCard label="调动车辆" :value="moved" hint="辆" />
        <KpiCard label="目标偏差" :value="num(result.objective, 0)" hint="目标函数值" />
      </div>

      <div class="grid grid-2 mt-16">
        <Panel title="调度路径">
          <div class="route mono">{{ routeText }}</div>
          <div class="route-sub">车场出发，按序访问，返回车场</div>
        </Panel>
        <Panel title="调度前后库存">
          <EChart :option="chartOption" height="260px" />
        </Panel>
      </div>

      <Panel title="各点位调动量" class="mt-16">
        <table class="table">
          <thead>
            <tr><th>点位</th><th>名称</th><th>调出/调入</th><th>调度前</th><th>调度后</th><th>目标</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.id">
              <td class="mono">{{ r.id }}</td>
              <td>{{ r.name }}</td>
              <td :class="r.y > 0 ? 'in' : r.y < 0 ? 'out' : ''">
                {{ r.y > 0 ? `+${r.y}` : r.y }}
              </td>
              <td class="mono">{{ r.before }}</td>
              <td class="mono">{{ r.after }}</td>
              <td class="mono">{{ Number(r.target).toFixed(1) }}</td>
            </tr>
          </tbody>
        </table>
      </Panel>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/client'
import Panel from '../components/Panel.vue'
import KpiCard from '../components/KpiCard.vue'
import EChart from '../components/EChart.vue'

const route = useRoute()

const loading = ref(false)
const error = ref('')
const result = ref(null)

function num(v, d = 1) { return v == null ? '—' : Number(v).toFixed(d) }

const moved = computed(() => {
  if (!result.value || !result.value.y) return '—'
  return result.value.y.reduce((a, b) => a + Math.abs(b), 0) / 2
})

const routeText = computed(() => {
  if (!result.value || !result.value.route || !result.value.station_ids) return '—'
  return result.value.route.map((i) => result.value.station_ids[i] || i).join(' → ')
})

const rows = computed(() => {
  if (!result.value || !result.value.station_ids) return []
  return result.value.station_ids.map((id, i) => ({
    id,
    name: result.value.station_names[i],
    y: result.value.y[i],
    before: result.value.inventory_before[i],
    after: result.value.u[i],
    target: result.value.target[i]
  }))
})

const chartOption = computed(() => {
  const ids = rows.value.map((r) => r.id)
  return {
    backgroundColor: 'transparent',
    legend: { data: ['调度前', '调度后'], textStyle: { color: '#8BA3C7', fontSize: 14 }, top: 0 },
    grid: { left: 48, right: 16, top: 40, bottom: 36 },
    xAxis: {
      type: 'category', data: ids,
      axisLine: { lineStyle: { color: '#1E3A5F' } }, axisTick: { show: false },
      axisLabel: { color: '#8BA3C7', fontSize: 14, rotate: 30 }
    },
    yAxis: {
      type: 'value', splitLine: { lineStyle: { color: '#12233A' } },
      axisLabel: { color: '#8BA3C7', fontSize: 14 }
    },
    tooltip: { trigger: 'axis', backgroundColor: '#0D1B2A', borderColor: '#1E3A5F', textStyle: { color: '#E6F1FF', fontSize: 14 } },
    series: [
      { name: '调度前', type: 'bar', data: rows.value.map((r) => r.before), itemStyle: { color: '#5B7191', borderRadius: [4, 4, 0, 0] } },
      { name: '调度后', type: 'bar', data: rows.value.map((r) => r.after), itemStyle: { color: '#22D3EE', borderRadius: [4, 4, 0, 0] } }
    ]
  }
})

async function run() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.post('/night/solve', {})
    result.value = data
  } catch (e) {
    error.value = (e.response && e.response.data && e.response.data.detail) || '求解失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (route.query.run === '1') run()
})
</script>

<style scoped>
.route { font-size: 20px; line-height: 1.8; color: var(--accent-2); word-break: break-all; }
.route-sub { font-size: 14px; color: var(--text-2); margin-top: 10px; }
.in { color: var(--success); }
.out { color: var(--warning); }
</style>
