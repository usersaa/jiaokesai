<template>
  <div
    class="command-root"
    :class="{ 'is-pure': pure, 'is-record': record }"
    @mousemove="wakeCursor"
  >
    <MapPanel
      ref="mapRef"
      class="command-map"
      :stations="stations"
      :step-data="stepData"
      :truck-path="truckPath"
      :selected="selected"
      :view-mode="viewMode"
      :satellite="satellite"
      :edit-mode="editMode"
      :center="mapCenter"
      :boundary="campusBoundary"
      :boundary-ids="BOUNDARY_STATION_IDS"
      :show-legend="!pure && !activePanel"
      :intro-mode="intro"
      @select="selectStation"
      @map-click="onMapClick"
      @ready="onMapReady"
    />

    <div v-if="intro && !loading" class="intro-layer" :class="`stage-${introStage}`">
      <div class="intro-frame">
        <span class="corner top-left"></span><span class="corner top-right"></span>
        <span class="corner bottom-left"></span><span class="corner bottom-right"></span>
        <div class="intro-heading">
          <div class="intro-kicker">LANZHOU JIAOTONG UNIVERSITY</div>
          <h2>共享单车调度中心</h2>
          <div class="intro-rule"><span></span><b></b><span></span></div>
          <p>校园共享电单车 · 一日调度演示</p>
        </div>
        <div class="intro-stats">
          <div><b>{{ introBikes }}</b><span>运营车辆</span></div>
          <div><b>{{ serviceStations.length }}</b><span>停车点位</span></div>
          <div><b>7</b><span>需求脉冲</span></div>
          <div><b>{{ steps.length }}</b><span>决策步骤</span></div>
        </div>
        <div class="intro-status"><i></i><span>{{ introStatus }}</span></div>
        <button v-if="!record" class="intro-skip" @click="finishIntro">跳过开场</button>
      </div>
    </div>

    <header v-if="!intro" class="command-header hud">
      <div class="header-side header-left">
        <img src="/logo.png" alt="兰州交通大学" class="header-logo" />
        <span class="system-state"><i></i>校园调度在线</span>
      </div>
      <div class="title-block">
        <h1>共享单车调度中心</h1>
        <div class="title-rule"><span></span><b></b><span></span></div>
      </div>
      <div class="header-side header-right">
        <span class="header-clock mono">{{ now }}</span>
        <button v-if="!record" class="icon-btn" @click="toggleFullscreen" title="全屏">全屏</button>
      </div>
    </header>

    <div v-if="!pure && !record && !intro" class="left-tools hud">
      <button class="tool-btn" :class="{ active: menuOpen }" @click="menuOpen = !menuOpen">
        <span class="tool-icon menu-icon"></span>功能
      </button>
      <button class="tool-btn" :class="{ active: activePanel === 'metrics' }" @click="togglePanel('metrics')">
        <span class="tool-icon metric-icon"></span>指标
      </button>
      <button class="tool-btn" :class="{ active: activePanel === 'curves' }" @click="togglePanel('curves')">
        <span class="tool-icon curve-icon"></span>分析
      </button>
      <button class="tool-btn" :class="{ active: activePanel === 'events' }" @click="togglePanel('events')">
        <span class="tool-icon event-icon"></span>动态
      </button>
      <button v-if="canEdit" class="tool-btn" :class="{ active: editMode }" @click="toggleEdit">
        <span class="tool-icon pin-icon"></span>标定
      </button>
    </div>

    <div v-if="!pure && !intro" class="right-tools hud">
      <div class="view-switch">
        <button :class="{ active: viewMode === '2D' }" @click="setView('2D')">2D</button>
        <button :class="{ active: viewMode === '3D' }" @click="setView('3D')">3D</button>
      </div>
      <button class="map-btn" :class="{ active: satellite }" @click="toggleSatellite">卫星</button>
      <button class="map-btn" @click="mapRef && mapRef.resetView()">复位</button>
      <button class="map-btn" @click="mapRef && mapRef.fitView()">全部点位</button>
      <button v-if="!record" class="map-btn" @click="pure = true">纯净</button>
    </div>

    <transition name="slide-left">
      <nav v-if="menuOpen && !pure" class="function-menu hud-panel">
        <div class="menu-head">
          <div><b>调度中心</b><span>{{ auth.displayName }} · {{ roleLabel }}</span></div>
          <button class="close-btn" @click="menuOpen = false">关闭</button>
        </div>
        <button v-for="item in visibleNav" :key="item.path" @click="go(item.path)">
          <span>{{ item.label }}</span><i>进入</i>
        </button>
        <button v-if="!screen" @click="go('/screen')"><span>独立大屏</span><i>展示</i></button>
        <button v-else @click="go('/app/dashboard')"><span>返回工作台</span><i>返回</i></button>
        <button @click="replayIntro"><span>重播开场</span><i>演示</i></button>
        <button class="logout-item" @click="logout"><span>退出登录</span><i>退出</i></button>
      </nav>
    </transition>

    <transition name="slide-left">
      <section v-if="activePanel && !pure" class="data-panel hud-panel">
        <div class="panel-head">
          <div>
            <span class="eyebrow">CAMPUS DISPATCH</span>
            <h2>{{ panelTitle }}</h2>
          </div>
          <button class="close-btn" @click="activePanel = ''">关闭</button>
        </div>

        <template v-if="activePanel === 'metrics'">
          <div class="metric-grid">
            <div class="metric-item"><span>服务率</span><b class="green">{{ pct(liveMetrics.service_rate) }}</b></div>
            <div class="metric-item"><span>累计短缺</span><b class="red">{{ num(liveMetrics.total_shortage, 1) }}</b></div>
            <div class="metric-item"><span>搬运趟次</span><b>{{ num(liveMetrics.truck_trips, 0) }}</b></div>
            <div class="metric-item"><span>服务骑行</span><b class="cyan">{{ num(liveMetrics.served_rides, 0) }}</b></div>
          </div>
          <div class="action-card">
            <span>当前调度动作</span>
            <strong>{{ currentAction }}</strong>
            <small>{{ currentTime }} · 第 {{ currentStep }} 决策步</small>
          </div>
          <div class="section-title">点位压力排行</div>
          <button v-for="r in ranking" :key="r.id" class="rank-row" @click="focusStation(r.id)">
            <span class="rank-id mono">{{ r.id }}</span>
            <span class="rank-name">{{ r.name }}</span>
            <span class="status-text" :class="r.statusClass">{{ r.status }}</span>
            <b class="mono">{{ Math.round(r.n) }}/{{ r.cap }}</b>
          </button>
        </template>

        <template v-else-if="activePanel === 'curves'">
          <div class="analysis-tabs">
            <button :class="{ active: analysisTab === 'supply' }" @click="analysisTab = 'supply'">供需缺口</button>
            <button :class="{ active: analysisTab === 'service' }" @click="analysisTab = 'service'">服务水平</button>
            <button :class="{ active: analysisTab === 'cost' }" @click="analysisTab = 'cost'">成本构成</button>
          </div>
          <div class="chart-title"><span>{{ analysisTitle }}</span><b>{{ currentTime }}</b></div>
          <EChart :option="analysisOption" height="270px" />
          <div class="analysis-facts">
            <div><span>累计服务</span><b>{{ num(liveMetrics.served_rides, 0) }} 人次</b></div>
            <div><span>搬运时间</span><b>{{ num(liveMetrics.truck_time, 0) }} 分钟</b></div>
            <div><span>当前步骤</span><b>{{ currentStep }} / {{ maxStep }}</b></div>
          </div>
          <p class="panel-note">图表只统计截至当前时刻的累计数据，随回放时间同步更新。</p>
        </template>

        <template v-else-if="activePanel === 'events'">
          <div class="live-action">
            <span class="live-ring"></span>
            <div><small>当前执行</small><strong>{{ currentAction }}</strong></div>
          </div>
          <div class="event-line">
            <button v-for="(e, i) in events" :key="`${e.step}-${i}`" class="event-row" @click="jumpEvent(e)">
              <span class="event-node"></span>
              <span class="event-time mono">{{ e.time }}</span>
              <span>{{ e.label }}</span>
            </button>
            <div v-if="!events.length" class="no-events">当前时段等待调度</div>
          </div>
        </template>
      </section>
    </transition>

    <transition name="fade">
      <div v-if="selectedStation && !activePanel && !pure" class="station-card hud-panel">
        <button class="card-close" @click="selected = ''">×</button>
        <span class="eyebrow">停车点实时状态</span>
        <h3>{{ selectedStation.id }} · {{ selectedStation.name }}</h3>
        <div class="station-stats">
          <div><span>当前车辆</span><b>{{ Math.round(selectedInventory) }}</b></div>
          <div><span>停车容量</span><b>{{ selectedStation.capacity }}</b></div>
          <div><span>空间占用</span><b>{{ occupancy }}</b></div>
        </div>
        <div class="occupancy-track"><i :style="{ width: occupancy }"></i></div>
        <div v-if="canEdit" class="station-actions">
          <button @click="openEdit(selectedStation)">编辑</button>
          <button @click="enableMove">移动位置</button>
          <button class="danger" @click="removeStation(selectedStation)">删除</button>
        </div>
      </div>
    </transition>

    <div v-if="editMode && !pure" class="edit-banner hud">
      <span class="edit-cross">＋</span>
      {{ movingId ? '点击地图确定新位置' : '点击校园地图放置停车点' }}
      <button @click="cancelEdit">退出标定</button>
    </div>

    <section v-if="showTimeline && !pure && !intro" class="timeline-dock hud-panel">
      <div class="dock-head">
        <div class="demand-title"><span class="live-ring"></span><b>一日调度回放</b><small>06:30 — 23:30 · 每步 10 分钟</small></div>
        <div class="dock-action"><span>{{ currentAction }}</span><b class="mono">{{ currentTime }}</b></div>
        <button class="close-btn" @click="showTimeline = false">收起</button>
      </div>
      <EChart :option="demandOption" height="82px" />
      <Timeline
        :model-value="currentStep"
        :max="maxStep"
        :time="currentTime"
        :end-time="endTime"
        :playing="playing"
        :speed="speed"
        @update:model-value="onSeek"
        @toggle="togglePlay"
        @step="stepBy"
        @speed="changeSpeed"
      />
    </section>

    <button v-if="!showTimeline && !pure && !intro" class="timeline-open hud" @click="showTimeline = true">展开回放</button>
    <button v-if="pure && !record" class="restore-btn hud" @click="pure = false">显示界面</button>

    <div v-if="loading" class="command-loading">
      <img src="/logo.png" alt="兰州交通大学" />
      <strong>共享单车调度中心</strong>
      <span>正在装载校园调度状态</span>
      <i><b></b></i>
    </div>
    <div v-else-if="loadError" class="command-loading">
      <strong>调度数据暂时无法加载</strong>
      <span>{{ loadError }}</span>
      <button class="retry-btn" @click="load">重新加载</button>
    </div>

    <div v-if="stationModal" class="station-modal-mask" @click.self="stationModal = false">
      <div class="station-modal hud-panel">
        <div class="panel-head">
          <div><span class="eyebrow">停车点标定</span><h2>{{ editingId ? '编辑停车点' : '新增停车点' }}</h2></div>
          <button class="close-btn" @click="stationModal = false">关闭</button>
        </div>
        <div class="station-form">
          <label>点位编号<input v-model.trim="form.id" :disabled="!!editingId" /></label>
          <label>点位名称<input v-model.trim="form.name" placeholder="请输入停车点名称" /></label>
          <label>功能类别<select v-model="form.func"><option v-for="f in funcOptions" :key="f.value" :value="f.value">{{ f.label }}</option></select></label>
          <div class="form-two">
            <label>停车容量<input v-model.number="form.capacity" type="number" min="1" /></label>
            <label>初始车辆<input v-model.number="form.init_bikes" type="number" min="0" /></label>
          </div>
          <div class="form-two">
            <label>经度<input v-model.number="form.lng" type="number" step="0.000001" /></label>
            <label>纬度<input v-model.number="form.lat" type="number" step="0.000001" /></label>
          </div>
        </div>
        <p v-if="formError" class="form-error">{{ formError }}</p>
        <div class="modal-actions">
          <button @click="stationModal = false">取消</button>
          <button class="primary" :disabled="saving" @click="saveStation">{{ saving ? '正在保存' : '保存点位' }}</button>
        </div>
      </div>
    </div>

    <div v-if="toast" class="command-toast" :class="{ error: toastError }">{{ toast }}</div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'
import { useAuthStore } from '../stores/auth'
import {
  BOUNDARY_STATION_IDS,
  CAMPUS_BOUNDARY,
  CAMPUS_CENTER,
  CAMPUS_ZOOM,
  CENTER_STATION_ID
} from '../config/map'
import MapPanel from './MapPanel.vue'
import EChart from './EChart.vue'
import Timeline from './Timeline.vue'

const props = defineProps({
  screen: { type: Boolean, default: false },
  record: { type: Boolean, default: false }
})

const router = useRouter()
const auth = useAuthStore()
const mapRef = ref(null)
const loading = ref(true)
const loadError = ref('')
const stations = ref([])
const steps = ref([])
const summary = ref({})
const demand = ref({ times: [], values: [] })
const currentStep = ref(0)
const playing = ref(false)
const speed = ref(1)
const selected = ref('')
const activePanel = ref('')
const analysisTab = ref('supply')
const menuOpen = ref(false)
const pure = ref(false)
const showTimeline = ref(true)
const viewMode = ref('2D')
const satellite = ref(false)
const editMode = ref(false)
const movingId = ref('')
const stationModal = ref(false)
const editingId = ref('')
const saving = ref(false)
const formError = ref('')
const toast = ref('')
const toastError = ref(false)
const now = ref('')
const intro = ref(false)
const introStage = ref(0)
const introTimers = []
let mapReady = false
let timer = null
let clockTimer = null
let cursorTimer = null
let toastTimer = null

const canEdit = computed(() => auth.role !== 'viewer')
const roleLabel = computed(() => ({ admin: '管理员', operator: '调度员', viewer: '观察者' }[auth.role] || '观察者'))
const nav = [
  { path: '/app/dashboard', label: '地图工作台' },
  { path: '/app/simulation', label: '实时推演' },
  { path: '/app/compare', label: '对比分析' },
  { path: '/app/stations', label: '点位管理' },
  { path: '/app/scenarios', label: '方案管理' },
  { path: '/app/night', label: '夜间调度' },
  { path: '/app/users', label: '用户管理', roles: ['admin'] },
  { path: '/app/settings', label: '系统设置', roles: ['admin'] },
  { path: '/app/logs', label: '日志审计', roles: ['admin'] }
]
const visibleNav = computed(() => nav.filter((n) => !n.roles || n.roles.includes(auth.role)))
const funcOptions = [
  { value: 'dorm', label: '宿舍区' }, { value: 'teach', label: '教学区' },
  { value: 'canteen', label: '食堂' }, { value: 'library', label: '图书馆' },
  { value: 'gate', label: '校门' }, { value: 'sport', label: '运动场' },
  { value: 'other', label: '其他' }
]
const form = reactive({ id: '', name: '', lng: 103.723371, lat: 36.105326, capacity: 30, func: 'other', attraction: 0.5, init_bikes: 0, target_bikes: 0 })

const stepData = computed(() => steps.value[currentStep.value] || null)
const maxStep = computed(() => Math.max(steps.value.length - 1, 0))
const currentTime = computed(() => (stepData.value && stepData.value.time) || '06:30')
const endTime = computed(() => steps.value.length ? steps.value[steps.value.length - 1].time : '23:30')
const currentAction = computed(() => (stepData.value && stepData.value.action && stepData.value.action.label) || '等待调度')
const liveMetrics = computed(() => (stepData.value && stepData.value.metrics) || summary.value || {})
const serviceStations = computed(() => stations.value
  .map((station, index) => ({ ...station, _index: index }))
  .filter((station) => !BOUNDARY_STATION_IDS.includes(station.id)))
const introBikes = computed(() => serviceStations.value.reduce((sum, s) => sum + Number(s.init_bikes || 0), 0))
const mapCenter = computed(() => {
  const centerStation = stations.value.find((s) => s.id === CENTER_STATION_ID)
  return centerStation ? [centerStation.lng, centerStation.lat] : CAMPUS_CENTER
})
const campusBoundary = computed(() => {
  const byId = new Map(stations.value.map((s) => [s.id, s]))
  const points = BOUNDARY_STATION_IDS
    .map((id) => byId.get(id))
    .filter(Boolean)
    .map((s) => [Number(s.lng), Number(s.lat)])
  if (points.length < 3) return CAMPUS_BOUNDARY
  return [...points, points[0]]
})
const panelTitle = computed(() => ({ metrics: '实时运行指标', curves: '调度分析', events: '调度事件动态' }[activePanel.value] || ''))
const analysisTitle = computed(() => ({ supply: '借车与还车缺口', service: '服务率变化', cost: '累计成本构成' }[analysisTab.value] || '调度分析'))
const introStatus = computed(() => [
  '正在建立校园调度视图',
  '识别重点楼宇与通行道路',
  '接入停车点与车辆状态',
  '同步一日需求脉冲'
][introStage.value] || '调度视图准备就绪')
const truckPath = computed(() => {
  const path = []
  for (let i = 0; i <= currentStep.value; i += 1) {
    const t = steps.value[i] && steps.value[i].truck
    if (t && (path.length === 0 || path[path.length - 1] !== t.station)) path.push(t.station)
  }
  return path
})
const ranking = computed(() => {
  const inv = (stepData.value && stepData.value.inventory) || stations.value.map((s) => s.init_bikes)
  return serviceStations.value.map((s) => {
    const n = inv[s._index] != null ? inv[s._index] : s.init_bikes
    const ratio = s.capacity ? n / s.capacity : 0
    const status = ratio < 0.2 ? '偏低' : ratio > 0.8 ? '偏高' : '正常'
    return { id: s.id, name: s.name, n, cap: s.capacity, ratio, status, statusClass: ratio < 0.2 ? 'low' : ratio > 0.8 ? 'high' : 'normal' }
  }).sort((a, b) => Math.abs(b.ratio - 0.5) - Math.abs(a.ratio - 0.5)).slice(0, 6)
})
const events = computed(() => {
  const list = []
  for (let i = currentStep.value; i >= 0 && list.length < 10; i -= 1) {
    const s = steps.value[i]
    if (s && s.action && s.action.mode !== 0 && s.action.label) list.push({ step: i, time: s.time, label: s.action.label, station: s.action.station })
  }
  return list
})
const selectedStation = computed(() => stations.value.find((s) => s.id === selected.value) || null)
const selectedIndex = computed(() => stations.value.findIndex((s) => s.id === selected.value))
const selectedInventory = computed(() => {
  if (!selectedStation.value) return 0
  const inv = stepData.value && stepData.value.inventory
  return inv && inv[selectedIndex.value] != null ? inv[selectedIndex.value] : selectedStation.value.init_bikes
})
const occupancy = computed(() => selectedStation.value && selectedStation.value.capacity ? `${Math.min(100, selectedInventory.value / selectedStation.value.capacity * 100).toFixed(0)}%` : '0%')

const axisStyle = { color: '#8ba3c7', fontSize: 14 }
const demandOption = computed(() => ({
  backgroundColor: 'transparent',
  animationDuration: 240,
  grid: { left: 8, right: 8, top: 4, bottom: 4 },
  xAxis: { type: 'category', data: demand.value.times, boundaryGap: false, show: false },
  yAxis: { type: 'value', show: false },
  tooltip: { trigger: 'axis', backgroundColor: '#0d1b2a', borderColor: '#2a4a73', textStyle: { color: '#e6f1ff', fontSize: 14 } },
  series: [{
    name: '需求强度', type: 'line', data: demand.value.values, smooth: 0.35, showSymbol: false,
    lineStyle: { color: '#35dff2', width: 2, shadowColor: 'rgba(34,211,238,.4)', shadowBlur: 8 },
    itemStyle: { color: '#35dff2' }, areaStyle: { color: 'rgba(34,211,238,.09)' },
    markLine: { silent: true, symbol: 'none', label: { show: false }, lineStyle: { color: '#f5c15d', width: 1, type: 'dashed' }, data: [{ xAxis: currentStep.value }] }
  }]
}))
const analysisOption = computed(() => {
  const list = steps.value.slice(0, currentStep.value + 1)
  const times = list.map((s) => s.time)
  const base = {
    backgroundColor: 'transparent',
    animation: false,
    grid: { left: 54, right: 26, top: 38, bottom: 34 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0d1b2a',
      borderColor: '#2a4a73',
      textStyle: { color: '#e6f1ff', fontSize: 14 }
    },
    xAxis: {
      type: 'category', data: times, boundaryGap: analysisTab.value === 'cost',
      axisLabel: { ...axisStyle, interval: Math.max(0, Math.floor(times.length / 6) - 1) },
      axisLine: { lineStyle: { color: '#24466b' } }, axisTick: { show: false }
    },
    yAxis: {
      type: 'value', axisLabel: axisStyle,
      splitLine: { lineStyle: { color: 'rgba(39,74,110,.35)' } }
    }
  }
  if (analysisTab.value === 'service') {
    const values = list.map((s) => Number((s.metrics && s.metrics.service_rate) ?? 1))
    const min = values.length ? Math.min(...values) : 0.99
    return {
      ...base,
      grid: { ...base.grid, top: 24 },
      yAxis: {
        type: 'value',
        min: Math.max(0.9, Math.floor((min - 0.0015) * 1000) / 1000),
        max: 1,
        axisLabel: { ...axisStyle, formatter: (v) => `${(v * 100).toFixed(1)}%` },
        splitLine: { lineStyle: { color: 'rgba(39,74,110,.35)' } }
      },
      series: [{
        name: '服务率', type: 'line', data: values, showSymbol: false, smooth: 0.25,
        lineStyle: { color: '#35dff2', width: 3 }, areaStyle: { color: 'rgba(34,211,238,.07)' },
        markLine: { silent: true, symbol: 'none', label: { formatter: '100%', color: '#89a7c4', fontSize: 14 }, lineStyle: { color: 'rgba(137,167,196,.35)', type: 'dashed' }, data: [{ yAxis: 1 }] }
      }]
    }
  }
  if (analysisTab.value === 'cost') {
    const m = liveMetrics.value || {}
    const coupon = Number(m.coupon_cost || m.coupon_cost_yuan || 0)
    const total = Number(m.total_cost_yuan || 0)
    const truck = Math.max(total - coupon, 0)
    return {
      ...base,
      tooltip: { ...base.tooltip, valueFormatter: (v) => `¥ ${Number(v).toFixed(2)}` },
      xAxis: { ...base.xAxis, data: ['搬运成本', '激励成本'] },
      yAxis: { ...base.yAxis, name: '元', nameTextStyle: axisStyle },
      series: [{
        type: 'bar', barWidth: 44, data: [
          { value: truck, itemStyle: { color: '#2f81f7', borderRadius: [4, 4, 0, 0] } },
          { value: coupon, itemStyle: { color: '#22d3ee', borderRadius: [4, 4, 0, 0] } }
        ],
        label: { show: true, position: 'top', color: '#d6e8f8', fontSize: 14, formatter: (p) => `¥${Number(p.value).toFixed(2)}` }
      }]
    }
  }
  return {
    ...base,
    legend: { top: 0, right: 0, textStyle: axisStyle, itemWidth: 16, itemHeight: 8 },
    series: [
      { name: '借车短缺', type: 'line', data: list.map((s) => Number((s.metrics && s.metrics.bike_shortage) || 0)), showSymbol: false, smooth: true, lineStyle: { color: '#ef7777', width: 2 }, areaStyle: { color: 'rgba(239,119,119,.06)' } },
      { name: '还车短缺', type: 'line', data: list.map((s) => Number((s.metrics && s.metrics.return_shortage) || 0)), showSymbol: false, smooth: true, lineStyle: { color: '#f5b74f', width: 2 } }
    ]
  }
})

function pct(v) { return v == null ? '—' : `${(Number(v) * 100).toFixed(2)}%` }
function num(v, d = 1) { return v == null ? '—' : Number(v).toFixed(d) }
function tick() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  now.value = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
function notify(message, isError = false) {
  toast.value = message
  toastError.value = isError
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 2600)
}
function onMapReady() {
  mapReady = true
  if (intro.value && mapRef.value) mapRef.value.setCamera(mapCenter.value, 14.8, 0)
}

function clearIntroTimers() {
  while (introTimers.length) clearTimeout(introTimers.pop())
}

function beginIntro() {
  clearIntroTimers()
  pause()
  intro.value = true
  introStage.value = 0
  currentStep.value = 0
  nextTick(() => {
    if (mapRef.value) mapRef.value.setCamera(mapCenter.value, 14.8, 0)
    introTimers.push(setTimeout(() => {
      if (mapRef.value) mapRef.value.setCamera(mapCenter.value, CAMPUS_ZOOM, 1600)
    }, 520))
  })
  introTimers.push(setTimeout(() => { introStage.value = 1 }, 850))
  introTimers.push(setTimeout(() => { introStage.value = 2 }, 1950))
  introTimers.push(setTimeout(() => { introStage.value = 3 }, 3150))
  introTimers.push(setTimeout(() => { finishIntro() }, 5900))
}

function finishIntro() {
  clearIntroTimers()
  intro.value = false
  introStage.value = 0
  try { sessionStorage.setItem('campus-intro-seen', '1') } catch (e) { /* 本地存储不可用时忽略 */ }
  if (mapRef.value) mapRef.value.resetView()
  if (steps.value.length) startTimer()
}

function replayIntro() {
  menuOpen.value = false
  beginIntro()
}

function pause() {
  playing.value = false
  if (timer) clearInterval(timer)
  timer = null
}
function startTimer() {
  pause()
  playing.value = true
  timer = setInterval(() => {
    if (currentStep.value >= maxStep.value) {
      if (props.screen) currentStep.value = 0
      else { pause(); return }
    } else currentStep.value += 1
  }, 1100 / Math.max(speed.value, 0.1))
}
function togglePlay() { if (playing.value) pause(); else { if (currentStep.value >= maxStep.value) currentStep.value = 0; startTimer() } }
function stepBy(n) { pause(); currentStep.value = Math.min(Math.max(currentStep.value + n, 0), maxStep.value) }
function onSeek(v) { pause(); currentStep.value = Number(v) }
function changeSpeed(v) { speed.value = v; if (playing.value) startTimer() }
function togglePanel(name) { activePanel.value = activePanel.value === name ? '' : name; menuOpen.value = false; selected.value = '' }
function selectStation(id) { selected.value = id; activePanel.value = '' }
function focusStation(id) { selected.value = id; activePanel.value = ''; if (mapRef.value) mapRef.value.focusStation(id) }
function jumpEvent(e) { onSeek(e.step); const s = stations.value[e.station]; if (s) focusStation(s.id) }
function setView(mode) { if (mode === '3D') satellite.value = false; viewMode.value = mode }
function toggleSatellite() { if (viewMode.value === '3D') viewMode.value = '2D'; satellite.value = !satellite.value }
function go(path) { menuOpen.value = false; pause(); router.push(path) }
function logout() { pause(); auth.logout(); router.push('/login') }
async function toggleFullscreen() {
  try { if (!document.fullscreenElement) await document.documentElement.requestFullscreen(); else await document.exitFullscreen() } catch (e) { notify('当前浏览器未允许全屏', true) }
}
function wakeCursor() {
  if (!props.record) return
  document.body.style.cursor = 'default'
  if (cursorTimer) clearTimeout(cursorTimer)
  cursorTimer = setTimeout(() => { document.body.style.cursor = 'none' }, 3000)
}
function onKey(e) {
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement && document.activeElement.tagName)) return
  if (e.key === 'Escape') { if (stationModal.value) stationModal.value = false; else if (editMode.value) cancelEdit(); else if (activePanel.value) activePanel.value = ''; else if (menuOpen.value) menuOpen.value = false; else pure.value = false }
  if (props.record) return
  if (e.key.toLowerCase() === 'h') pure.value = !pure.value
  if (e.key.toLowerCase() === 'f') toggleFullscreen()
  if (e.key.toLowerCase() === 'e' && canEdit.value) toggleEdit()
  if (e.code === 'Space') { e.preventDefault(); togglePlay() }
  if (e.key === 'ArrowLeft') stepBy(-1)
  if (e.key === 'ArrowRight') stepBy(1)
}

function nextId() {
  let max = 0
  stations.value.forEach((s) => { const m = /^P(\d+)$/.exec(s.id || ''); if (m) max = Math.max(max, Number(m[1])) })
  return `P${String(max + 1).padStart(2, '0')}`
}
function toggleEdit() { editMode.value = !editMode.value; movingId.value = ''; activePanel.value = ''; selected.value = ''; menuOpen.value = false }
function cancelEdit() { editMode.value = false; movingId.value = '' }
function onMapClick(pos) {
  if (movingId.value) {
    const s = stations.value.find((item) => item.id === movingId.value)
    if (s) openEdit(s, pos)
    movingId.value = ''
    return
  }
  editingId.value = ''
  Object.assign(form, { id: nextId(), name: '', lng: pos.lng, lat: pos.lat, capacity: 30, func: 'other', attraction: 0.5, init_bikes: 0, target_bikes: 0 })
  formError.value = ''
  stationModal.value = true
}
function openEdit(s, pos = null) {
  editingId.value = s.id
  Object.assign(form, { id: s.id, name: s.name, lng: pos ? pos.lng : s.lng, lat: pos ? pos.lat : s.lat, capacity: s.capacity, func: s.func, attraction: s.attraction, init_bikes: s.init_bikes, target_bikes: s.target_bikes })
  formError.value = ''
  stationModal.value = true
}
function enableMove() { if (!selectedStation.value) return; movingId.value = selectedStation.value.id; editMode.value = true; selected.value = '' }
async function saveStation() {
  if (!form.id || !form.name) { formError.value = '请填写点位编号和名称'; return }
  if (!form.capacity || form.capacity < 1) { formError.value = '停车容量必须大于 0'; return }
  if (form.init_bikes < 0 || form.init_bikes > form.capacity) { formError.value = '初始车辆数应在 0 与停车容量之间'; return }
  saving.value = true
  formError.value = ''
  try {
    if (editingId.value) await api.put(`/stations/${editingId.value}`, { ...form })
    else await api.post('/stations', { ...form })
    stationModal.value = false
    cancelEdit()
    notify('停车点已保存')
    await load(false)
  } catch (e) {
    formError.value = (e.response && e.response.data && e.response.data.detail) || '保存失败，请检查点位信息'
  } finally { saving.value = false }
}
async function removeStation(s) {
  if (!confirm(`确定删除 ${s.id} · ${s.name}？新推演将不再使用该点位。`)) return
  try { await api.delete(`/stations/${s.id}`); selected.value = ''; notify('停车点已删除'); await load(false) } catch (e) { notify('删除失败，请稍后重试', true) }
}

async function load(autoplay = true) {
  loading.value = true
  loadError.value = ''
  pause()
  try {
    const [sim, dem] = await Promise.all([api.post('/simulations', { policy: 'ppo', seed: 101 }), api.get('/demand-profile')])
    stations.value = sim.data.stations
    steps.value = sim.data.steps
    summary.value = sim.data.summary
    demand.value = dem.data
    currentStep.value = 0
    selected.value = ''
    let seen = false
    try { seen = sessionStorage.getItem('campus-intro-seen') === '1' } catch (e) { seen = false }
    if (props.screen || !seen) {
      beginIntro()
    } else {
      if (mapRef.value) mapRef.value.setCamera(mapCenter.value, CAMPUS_ZOOM, 500)
      if (autoplay) startTimer()
    }
  } catch (e) {
    loadError.value = (e.response && e.response.data && e.response.data.detail) || '请检查服务连接后重试'
  } finally { loading.value = false }
}

onMounted(() => {
  tick()
  load(true)
  clockTimer = setInterval(tick, 1000)
  window.addEventListener('keydown', onKey)
  wakeCursor()
})
onBeforeUnmount(() => {
  pause()
  clearIntroTimers()
  if (clockTimer) clearInterval(clockTimer)
  if (cursorTimer) clearTimeout(cursorTimer)
  if (toastTimer) clearTimeout(toastTimer)
  document.body.style.cursor = 'default'
  window.removeEventListener('keydown', onKey)
})
</script>

<style scoped>
.command-root { position: relative; width: 100%; height: 100%; min-height: 600px; overflow: hidden; background: #07111f; color: #e6f1ff; }
.command-map { position: absolute; inset: 0; }
.hud { z-index: 100; }
.hud-panel {
  z-index: 110;
  background: rgba(7, 20, 35, .96);
  border: 1px solid rgba(71, 131, 180, .46);
  border-radius: 10px;
  box-shadow: 0 14px 40px rgba(0,0,0,.28), inset 0 1px 0 rgba(158,220,255,.04);
}
.command-header {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 82px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  background: rgba(5, 15, 28, .93);
  border-bottom: 1px solid rgba(65, 128, 177, .45);
  pointer-events: none;
}
.command-header::after { content: ''; position: absolute; left: 30%; right: 30%; bottom: -1px; height: 2px; background: #22d3ee; opacity: .55; }
.header-side { width: 330px; display: flex; align-items: center; gap: 14px; pointer-events: auto; }
.header-right { justify-content: flex-end; }
.header-logo { width: 46px; height: 46px; object-fit: contain; padding: 3px; border-radius: 50%; background: #fff; }
.system-state { display: inline-flex; align-items: center; gap: 8px; color: #9eb7d3; font-size: 15px; }
.system-state i { width: 7px; height: 7px; border-radius: 50%; background: #36d399; box-shadow: 0 0 10px rgba(54,211,153,.6); }
.title-block { text-align: center; }
.title-block h1 { margin: 0; font-size: 32px; font-weight: 600; letter-spacing: 5px; color: #edf8ff; text-shadow: 0 0 20px rgba(34,211,238,.18); }
.title-rule { display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 7px; }
.title-rule span { width: 68px; height: 1px; background: #2b749b; }
.title-rule b { width: 7px; height: 7px; border: 1px solid #52e8fa; transform: rotate(45deg); }
.header-clock { color: #a9c4df; font-size: 15px; }
.icon-btn, .map-btn, .close-btn {
  border: 1px solid rgba(75, 130, 176, .5);
  background: rgba(12, 31, 51, .9);
  color: #c6daed;
  cursor: pointer;
  transition: border-color .16s, background .16s, color .16s;
}
.icon-btn:hover, .map-btn:hover, .close-btn:hover { border-color: #22d3ee; color: #fff; background: #14324c; }
.icon-btn { height: 36px; padding: 0 13px; border-radius: 6px; font-size: 14px; }
.left-tools { position: absolute; top: 104px; left: 22px; display: grid; gap: 8px; }
.tool-btn {
  width: 66px;
  height: 62px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid rgba(66, 121, 165, .42);
  border-radius: 8px;
  background: rgba(7, 22, 38, .92);
  color: #b6cce2;
  font-size: 14px;
  cursor: pointer;
  transition: all .16s;
}
.tool-btn:hover, .tool-btn.active { color: #8ff4ff; border-color: #22d3ee; background: rgba(12, 48, 67, .96); }
.tool-icon { position: relative; display: block; width: 22px; height: 18px; }
.menu-icon { border-top: 2px solid currentColor; border-bottom: 2px solid currentColor; }
.menu-icon::after { content: ''; position: absolute; left: 0; right: 0; top: 6px; border-top: 2px solid currentColor; }
.metric-icon { border-left: 2px solid currentColor; border-bottom: 2px solid currentColor; }
.metric-icon::after { content: ''; position: absolute; left: 5px; bottom: 3px; width: 3px; height: 7px; background: currentColor; box-shadow: 6px -4px 0 currentColor, 12px -9px 0 currentColor; }
.curve-icon::after { content: ''; position: absolute; inset: 3px 0; border-top: 2px solid currentColor; transform: skewY(-24deg); box-shadow: 0 6px 0 -1px currentColor; }
.event-icon { border: 2px solid currentColor; border-radius: 50%; }
.event-icon::after { content: ''; position: absolute; left: 9px; top: 3px; height: 7px; border-left: 2px solid currentColor; transform: rotate(-30deg); transform-origin: bottom; }
.pin-icon { width: 17px; height: 17px; border: 2px solid currentColor; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); }
.right-tools { position: absolute; top: 104px; right: 22px; display: flex; gap: 8px; }
.view-switch { display: flex; border: 1px solid rgba(75,130,176,.5); border-radius: 7px; overflow: hidden; }
.view-switch button { width: 50px; border: 0; background: rgba(7,22,38,.92); color: #a9c2da; cursor: pointer; font-size: 14px; }
.view-switch button.active { color: #8ff4ff; background: #123c50; }
.map-btn { height: 40px; padding: 0 15px; border-radius: 7px; font-size: 14px; }
.map-btn.active { color: #8ff4ff; border-color: #22d3ee; }
.function-menu { position: absolute; top: 104px; left: 102px; width: 310px; padding: 18px; }
.menu-head, .panel-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding-bottom: 16px; margin-bottom: 14px; border-bottom: 1px solid rgba(65,112,153,.35); }
.menu-head b { display: block; font-size: 20px; font-weight: 500; }
.menu-head span { display: block; color: #8ba3c7; font-size: 14px; margin-top: 4px; }
.function-menu > button { width: 100%; height: 44px; display: flex; align-items: center; justify-content: space-between; padding: 0 12px; border: 0; border-bottom: 1px solid rgba(52,91,128,.25); background: transparent; color: #d5e6f7; cursor: pointer; font-size: 16px; }
.function-menu > button:hover { background: #122f47; color: #8ff4ff; }
.function-menu > button i { color: #6686a6; font-size: 14px; font-style: normal; }
.function-menu > button.logout-item { color: #f4a6a6; margin-top: 8px; }
.close-btn { height: 32px; padding: 0 10px; border-radius: 5px; font-size: 14px; }
.data-panel { position: absolute; top: 104px; left: 102px; width: 390px; max-height: calc(100% - 320px); padding: 20px; overflow-y: auto; }
.eyebrow { display: block; color: #4fd9e9; font: 14px/1.4 Consolas, monospace; letter-spacing: 1px; }
.panel-head h2 { margin: 4px 0 0; font-size: 22px; font-weight: 500; }
.metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.metric-item { padding: 14px; border: 1px solid rgba(57,104,144,.4); border-radius: 7px; background: rgba(16,40,61,.72); }
.metric-item span { display: block; color: #8ba3c7; font-size: 14px; }
.metric-item b { display: block; margin-top: 4px; font: 500 26px/1.3 Consolas, monospace; }
.green { color: #56dda0; }.red { color: #ff8585; }.cyan { color: #62e8f5; }
.action-card { margin: 14px 0; padding: 15px; border-left: 3px solid #22d3ee; background: rgba(20,54,75,.65); }
.action-card span, .action-card small { display: block; color: #8ba3c7; font-size: 14px; }
.action-card strong { display: block; margin: 5px 0; font-size: 21px; font-weight: 500; }
.section-title { margin: 18px 0 8px; color: #a9c2da; font-size: 16px; }
.rank-row { width: 100%; display: grid; grid-template-columns: 42px 1fr 42px 60px; align-items: center; gap: 7px; padding: 11px 4px; border: 0; border-bottom: 1px solid rgba(58,99,135,.25); background: transparent; color: #d8e8f7; cursor: pointer; text-align: left; font-size: 14px; }
.rank-row:hover { background: rgba(32,74,101,.5); }
.rank-id { color: #61e4f2; }.rank-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.rank-row b { text-align: right; font-weight: 500; }
.status-text.low { color: #ff8585; }.status-text.high { color: #f7c66b; }.status-text.normal { color: #79b6ff; }
.analysis-tabs { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; padding: 4px; border: 1px solid rgba(63,111,150,.35); border-radius: 7px; background: rgba(8,24,40,.72); }
.analysis-tabs button { height: 34px; border: 0; border-radius: 5px; background: transparent; color: #8ba3c7; font-size: 14px; cursor: pointer; }
.analysis-tabs button:hover { color: #d9ecfb; }
.analysis-tabs button.active { background: #173c55; color: #8ff4ff; }
.analysis-facts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 12px; }
.analysis-facts div { padding: 10px; border: 1px solid rgba(57,104,144,.35); border-radius: 6px; background: rgba(12,34,52,.6); }
.analysis-facts span { display: block; color: #7895b2; font-size: 14px; }
.analysis-facts b { display: block; margin-top: 3px; color: #dceeff; font: 500 16px/1.4 Consolas, monospace; }
.chart-title { display: flex; justify-content: space-between; color: #cfe2f4; font-size: 16px; margin: 16px 0 4px; }.chart-title b { color: #6de7f3; font: 500 15px Consolas, monospace; }
.panel-note { color: #8ba3c7; font-size: 14px; line-height: 1.7; }
.live-action { display: flex; align-items: center; gap: 14px; padding: 16px; background: rgba(18,55,74,.7); border: 1px solid rgba(34,211,238,.25); border-radius: 7px; }
.live-ring { display: inline-block; width: 9px; height: 9px; flex: 0 0 9px; border-radius: 50%; background: #35dff2; box-shadow: 0 0 0 5px rgba(53,223,242,.12); }
.live-action small { display: block; color: #8ba3c7; font-size: 14px; }.live-action strong { display: block; margin-top: 4px; font-size: 20px; font-weight: 500; }
.event-line { margin-top: 16px; }
.event-row { position: relative; width: 100%; display: grid; grid-template-columns: 14px 54px 1fr; gap: 8px; padding: 10px 0; border: 0; background: transparent; color: #c9dbec; text-align: left; cursor: pointer; font-size: 14px; }
.event-row:hover { color: #8ff4ff; }.event-node { width: 7px; height: 7px; margin-top: 7px; border: 1px solid #35dff2; transform: rotate(45deg); }.event-time { color: #6f91b2; }
.no-events { padding: 30px 0; text-align: center; color: #8ba3c7; }
.station-card { position: absolute; right: 24px; bottom: 230px; width: 340px; padding: 20px; }
.card-close { position: absolute; top: 10px; right: 12px; border: 0; background: transparent; color: #8ba3c7; font-size: 25px; cursor: pointer; }
.station-card h3 { margin: 6px 0 16px; font-size: 20px; font-weight: 500; }
.station-stats { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; }
.station-stats span { display: block; color: #8ba3c7; font-size: 14px; }.station-stats b { display: block; margin-top: 5px; color: #e6f1ff; font: 500 23px Consolas, monospace; }
.occupancy-track { height: 5px; margin: 16px 0; background: #17344f; overflow: hidden; }.occupancy-track i { display: block; height: 100%; max-width: 100%; background: #22d3ee; transition: width .25s; }
.station-actions { display: flex; gap: 8px; }.station-actions button { flex: 1; height: 36px; border: 1px solid #315a7d; border-radius: 5px; background: #102a41; color: #cfe1f2; cursor: pointer; }.station-actions button.danger { color: #ff9b9b; border-color: #80454b; }
.edit-banner { position: absolute; top: 102px; left: 50%; transform: translateX(-50%); display: flex; align-items: center; gap: 12px; padding: 10px 16px; border: 1px solid #22d3ee; border-radius: 7px; background: rgba(7,35,48,.96); color: #c9f9ff; font-size: 16px; }
.edit-cross { color: #54e8f6; font-size: 23px; }.edit-banner button { border: 0; background: transparent; color: #8ba3c7; cursor: pointer; }
.timeline-dock { position: absolute; left: 110px; right: 24px; bottom: 20px; height: 190px; padding: 10px 18px 12px; }
.dock-head { height: 34px; display: flex; align-items: center; justify-content: space-between; gap: 20px; }
.demand-title { display: flex; align-items: center; gap: 10px; }.demand-title b { font-size: 16px; font-weight: 500; }.demand-title small { color: #7795b3; font-size: 14px; }
.dock-action { display: flex; align-items: center; gap: 18px; margin-left: auto; color: #bcd1e5; font-size: 14px; }.dock-action b { color: #62e8f5; font-size: 20px; font-weight: 500; }
.timeline-open, .restore-btn { position: absolute; right: 24px; bottom: 22px; height: 42px; padding: 0 18px; border: 1px solid #2b7894; border-radius: 7px; background: rgba(7,28,43,.94); color: #a9edf4; cursor: pointer; }
.restore-btn { bottom: 28px; }
.intro-layer {
  position: absolute;
  inset: 0;
  z-index: 900;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(3, 9, 16, .86);
  transition: background 1.1s ease-out;
  overflow: hidden;
}
.intro-layer::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 1px;
  background: rgba(78, 226, 243, .5);
  box-shadow: 0 0 18px rgba(78, 226, 243, .45);
  animation: intro-scan 3.2s linear infinite;
}
.intro-layer.stage-1 { background: rgba(3, 9, 16, .52); }
.intro-layer.stage-2, .intro-layer.stage-3 { background: rgba(3, 9, 16, .16); }
.intro-frame { position: relative; width: 100%; height: 100%; }
.corner { position: absolute; width: 42px; height: 42px; border-color: rgba(81, 206, 224, .55); border-style: solid; }
.corner.top-left { top: 28px; left: 30px; border-width: 1px 0 0 1px; }
.corner.top-right { top: 28px; right: 30px; border-width: 1px 1px 0 0; }
.corner.bottom-left { bottom: 28px; left: 30px; border-width: 0 0 1px 1px; }
.corner.bottom-right { bottom: 28px; right: 30px; border-width: 0 1px 1px 0; }
.intro-heading {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  padding: 28px 46px 24px;
  border: 1px solid rgba(45, 126, 154, .55);
  border-radius: 8px;
  background: rgba(4, 18, 30, .88);
  text-align: center;
  box-shadow: 0 18px 50px rgba(0,0,0,.25);
  transition: transform .9s cubic-bezier(.2,.7,.3,1), opacity .7s;
}
.intro-layer.stage-1 .intro-heading { transform: translate(-50%, -210px) scale(.82); }
.intro-layer.stage-2 .intro-heading, .intro-layer.stage-3 .intro-heading { transform: translate(-50%, -280px) scale(.7); opacity: .45; }
.intro-kicker { color: #5ad7e8; font: 14px/1.4 Consolas, monospace; letter-spacing: 4px; }
.intro-heading h2 { margin: 16px 0 0; color: #f1fbff; font-size: 54px; line-height: 1.25; font-weight: 600; letter-spacing: 10px; text-shadow: 0 0 26px rgba(34, 211, 238, .22); }
.intro-rule { display: flex; align-items: center; justify-content: center; gap: 10px; margin: 20px 0 15px; }
.intro-rule span { width: 120px; height: 1px; background: #2b7e95; }
.intro-rule b { width: 8px; height: 8px; border: 1px solid #61edf9; transform: rotate(45deg); }
.intro-heading p { color: #9db9d0; font-size: 17px; letter-spacing: 3px; }
.intro-stats { position: absolute; left: 50%; bottom: 125px; transform: translateX(-50%); display: flex; border: 1px solid rgba(68, 137, 165, .45); background: rgba(5, 20, 33, .9); opacity: 0; transition: opacity .7s ease-out; }
.intro-layer.stage-2 .intro-stats, .intro-layer.stage-3 .intro-stats { opacity: 1; }
.intro-stats div { width: 150px; padding: 14px 18px; border-right: 1px solid rgba(68, 137, 165, .35); text-align: center; }
.intro-stats div:last-child { border-right: 0; }
.intro-stats b { display: block; color: #72eaf5; font: 500 31px/1.2 Consolas, monospace; }
.intro-stats span { display: block; margin-top: 3px; color: #91acc4; font-size: 14px; letter-spacing: 1px; }
.intro-status { position: absolute; left: 54px; bottom: 50px; display: flex; align-items: center; gap: 10px; color: #9ab7cc; font-size: 15px; }
.intro-status i { width: 7px; height: 7px; border-radius: 50%; background: #3be0b0; box-shadow: 0 0 10px rgba(59,224,176,.7); }
.intro-skip { position: absolute; right: 54px; bottom: 44px; height: 36px; padding: 0 15px; border: 1px solid rgba(78, 154, 181, .55); border-radius: 5px; background: rgba(6, 24, 38, .8); color: #a9c8dc; font-size: 14px; cursor: pointer; }
.intro-skip:hover { border-color: #5fe7f5; color: #e9fdff; }
.command-loading { position: absolute; inset: 0; z-index: 1000; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; background: #07111f; color: #8ba3c7; }
.command-loading img { width: 70px; height: 70px; border-radius: 50%; background: #fff; padding: 5px; }.command-loading strong { color: #e6f1ff; font-size: 30px; letter-spacing: 3px; font-weight: 500; }.command-loading > i { width: 220px; height: 2px; margin-top: 10px; background: #183752; overflow: hidden; }.command-loading > i b { display: block; width: 70px; height: 2px; background: #22d3ee; animation: command-load 1.4s ease-in-out infinite; }
.retry-btn { height: 42px; padding: 0 20px; border: 1px solid #2f81f7; border-radius: 6px; background: #122f4b; color: #e6f1ff; cursor: pointer; }
.station-modal-mask { position: absolute; inset: 0; z-index: 600; display: flex; align-items: center; justify-content: center; background: rgba(2,8,16,.68); }
.station-modal { width: 520px; padding: 22px; }.station-form { display: grid; gap: 13px; }.station-form label { display: grid; gap: 6px; color: #9cb4cc; font-size: 14px; }.station-form input, .station-form select { width: 100%; height: 42px; padding: 0 12px; border: 1px solid #2a4a73; border-radius: 6px; background: #0a1b2d; color: #e6f1ff; font-size: 16px; }.station-form input:disabled { opacity: .55; }.form-two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }.form-error { margin-top: 12px; color: #ff9b9b; font-size: 14px; }.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }.modal-actions button { height: 40px; padding: 0 18px; border: 1px solid #2a4a73; border-radius: 6px; background: #102a41; color: #d8e8f7; cursor: pointer; }.modal-actions button.primary { background: #167c9a; border-color: #22a9c4; color: #fff; }
.command-toast { position: absolute; z-index: 800; left: 50%; bottom: 232px; transform: translateX(-50%); padding: 12px 20px; border: 1px solid #28b996; border-radius: 7px; background: #0c2c32; color: #a8f0d3; box-shadow: 0 10px 30px rgba(0,0,0,.3); }.command-toast.error { border-color: #d65d65; color: #ffb4b4; background: #351a24; }
.slide-left-enter-active, .slide-left-leave-active { transition: opacity .18s, transform .18s; }.slide-left-enter-from, .slide-left-leave-to { opacity: 0; transform: translateX(-10px); }.fade-enter-active, .fade-leave-active { transition: opacity .18s; }.fade-enter-from, .fade-leave-to { opacity: 0; }
.is-pure .command-header { background: rgba(5,15,28,.82); }
@keyframes command-load { from { transform: translateX(-70px); } to { transform: translateX(220px); } }
@keyframes intro-scan { 0% { transform: translateY(0); opacity: 0; } 12% { opacity: 1; } 88% { opacity: 1; } 100% { transform: translateY(100vh); opacity: 0; } }
@media (max-width: 1200px) { .header-side { width: 250px; }.header-clock { display: none; }.title-block h1 { font-size: 28px; }.timeline-dock { left: 100px; }.data-panel { width: 350px; } }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>
