<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">对比分析</h1>
        <div class="page-sub">六条基线 + PPO · 服务率 / 短缺 / 成本</div>
      </div>
      <div class="row">
        <span class="tag" :class="source === 'experiments' ? 'tag-blue' : 'tag-amber'">
          {{ source === 'experiments' ? '评估结果' : '实时计算' }}
        </span>
        <button class="btn" :disabled="loading" @click="load">刷新</button>
        <button class="btn btn-primary" @click="exportCsv">导出 CSV</button>
      </div>
    </div>

    <div v-if="loading" class="empty">正在加载对比数据…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <template v-else>
      <div class="stat-grid">
        <div class="stat-card"><span>参与对比策略</span><b>{{ rows.length }}</b><small>六条基线与 PPO</small></div>
        <div class="stat-card"><span>最高服务率</span><b>{{ pct(bestService) }}</b><small>当前策略集合</small></div>
        <div class="stat-card"><span>最低单位成本</span><b>{{ num(bestCost, 3) }}</b><small>元 / 单</small></div>
        <div class="stat-card"><span>PPO 总短缺</span><b>{{ num(ppoRow.total_shortage, 1) }}</b><small>较不调度下降 {{ ppoDrop }}%</small></div>
      </div>

      <Panel title="策略指标">
        <table class="table">
          <thead>
            <tr>
              <th>策略</th>
              <th>服务率</th>
              <th>总短缺</th>
              <th>单位成本</th>
              <th>搬运趟次</th>
              <th>借车短缺</th>
              <th>还车短缺</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.policy" :class="{ 'ppo-row': r.policy === 'ppo' }">
              <td>
                <div class="policy-cell">
                  <span>{{ policyLabel(r.policy) }}</span>
                  <b v-if="r.policy === 'ppo'" class="tag">当前配置</b>
                </div>
              </td>
              <td class="mono">{{ pct(r.service_rate) }}</td>
              <td class="mono">{{ num(r.total_shortage, 1) }}</td>
              <td class="mono">{{ num(r.unit_service_cost, 3) }}</td>
              <td class="mono">{{ num(r.truck_trips, 0) }}</td>
              <td class="mono">{{ num(r.bike_shortage, 1) }}</td>
              <td class="mono">{{ num(r.return_shortage, 1) }}</td>
            </tr>
          </tbody>
        </table>
      </Panel>

      <div class="grid grid-2 mt-16">
        <Panel title="服务率 · 局部视图 90%–100%">
          <EChart :option="serviceOption" height="300px" />
        </Panel>
        <Panel title="单位服务成本">
          <EChart :option="costOption" height="300px" />
        </Panel>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api/client'
import Panel from '../components/Panel.vue'
import EChart from '../components/EChart.vue'

const rows = ref([])
const source = ref('experiments')
const loading = ref(true)
const error = ref('')

function policyLabel(p) {
  return {
    ppo: 'PPO 策略', noop: '不调度', random: '随机',
    pure_truck: '纯搬运', pure_coupon: '纯激励',
    greedy: '约束贪心', sa: '模拟退火'
  }[p] || p
}

function pct(v) { return v == null ? '—' : `${(Number(v) * 100).toFixed(2)}%` }
function num(v, d = 1) { return v == null ? '—' : Number(v).toFixed(d) }

const labels = computed(() => rows.value.map((r) => policyLabel(r.policy)))
const bestService = computed(() => Math.max(0, ...rows.value.map((r) => Number(r.service_rate || 0))))
const bestCost = computed(() => {
  const values = rows.value.map((r) => Number(r.unit_service_cost || 0)).filter((v) => v > 0)
  return values.length ? Math.min(...values) : 0
})
const ppoRow = computed(() => rows.value.find((r) => r.policy === 'ppo') || {})
const ppoDrop = computed(() => {
  const base = rows.value.find((r) => r.policy === 'noop')
  if (!base || !base.total_shortage || ppoRow.value.total_shortage == null) return '—'
  return ((1 - Number(ppoRow.value.total_shortage) / Number(base.total_shortage)) * 100).toFixed(1)
})

const baseAxis = {
  axisLine: { lineStyle: { color: '#1E3A5F' } },
  axisTick: { show: false },
  axisLabel: { color: '#8BA3C7', fontSize: 14, rotate: 18 }
}

const serviceOption = computed(() => ({
  backgroundColor: 'transparent',
  grid: { left: 52, right: 16, top: 20, bottom: 56 },
  xAxis: { type: 'category', data: labels.value, ...baseAxis },
  yAxis: {
    type: 'value', min: 0.9, max: 1,
    splitLine: { lineStyle: { color: '#17324b' } },
    axisLabel: { color: '#8BA3C7', fontSize: 14, formatter: (v) => `${(v * 100).toFixed(0)}%` }
  },
  tooltip: { trigger: 'axis', backgroundColor: '#0D1B2A', borderColor: '#1E3A5F', textStyle: { color: '#E6F1FF', fontSize: 14 }, valueFormatter: (v) => `${(Number(v) * 100).toFixed(2)}%` },
  series: [{
    type: 'bar', barWidth: 26,
    data: rows.value.map((r) => ({
      value: Number((r.service_rate || 0).toFixed(4)),
      itemStyle: { color: r.policy === 'ppo' ? '#22d3ee' : '#2F81F7', borderRadius: [4, 4, 0, 0] }
    })),
    label: { show: true, position: 'top', color: '#9fb8d0', fontSize: 14, formatter: (p) => `${(Number(p.value) * 100).toFixed(1)}%` }
  }]
}))

const costOption = computed(() => ({
  backgroundColor: 'transparent',
  grid: { left: 56, right: 16, top: 20, bottom: 56 },
  xAxis: { type: 'category', data: labels.value, ...baseAxis },
  yAxis: {
    type: 'value',
    splitLine: { lineStyle: { color: '#17324b' } },
    axisLabel: { color: '#8BA3C7', fontSize: 14 }
  },
  tooltip: { trigger: 'axis', backgroundColor: '#0D1B2A', borderColor: '#1E3A5F', textStyle: { color: '#E6F1FF', fontSize: 14 }, valueFormatter: (v) => `¥ ${Number(v).toFixed(3)}` },
  series: [{
    type: 'bar', barWidth: 26,
    data: rows.value.map((r) => ({
      value: Number((r.unit_service_cost || 0).toFixed(4)),
      itemStyle: { color: r.policy === 'ppo' ? '#22d3ee' : '#2F81F7', borderRadius: [4, 4, 0, 0] }
    })),
    label: { show: true, position: 'top', color: '#9fb8d0', fontSize: 14, formatter: (p) => Number(p.value).toFixed(3) }
  }]
}))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/compare')
    rows.value = data.rows || []
    source.value = data.source || 'live'
  } catch (e) {
    error.value = (e.response && e.response.data && e.response.data.detail) || '加载失败'
  } finally {
    loading.value = false
  }
}

function exportCsv() {
  const header = ['策略', '服务率', '总短缺', '单位成本', '搬运趟次', '借车短缺', '还车短缺']
  const lines = [header.join(',')]
  rows.value.forEach((r) => {
    lines.push([
      policyLabel(r.policy), r.service_rate, r.total_shortage, r.unit_service_cost,
      r.truck_trips, r.bike_shortage, r.return_shortage
    ].join(','))
  })
  const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'compare.csv'
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(load)
</script>

<style scoped>
.policy-cell { display: flex; align-items: center; gap: 9px; }
.policy-cell .tag { height: 22px; font-size: 14px; }
.ppo-row { background: rgba(22, 81, 101, .22); }
.ppo-row:hover { background: rgba(24, 96, 117, .3); }
</style>
