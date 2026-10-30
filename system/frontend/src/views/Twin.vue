<template>
  <div ref="root" class="twin-root" :class="[{ 'is-record': record }, `theme-${theme}`]" @mousemove="wakeCursor">
    <div class="twin-canvas">
      <TwinScene ref="sceneRef" :stations="serviceStations" :no-parking="noParkingZones" :step-data="activeStepData"
        :truck-path="mode === 'live' ? [] : truckPath" :bikes="mode === 'live' ? live.bikes : []"
        :arcs="mode === 'live' ? arcFeed : []" :display-mode="mode" :session-key="`${mode}-${live.gen}`"
        :heat-points="heatPoints" :heat-mode="heatMode" @follow-change="onFollowChange" @route-status="routeStatus = $event" :theme="theme" :show-labels="showLabels" :selected="selected" @select="selected = $event" />

      <header class="twin-header">
        <div class="header-meta"><span class="connection-dot" :class="{ online: live.connected }"></span><span>{{ mode === 'live' ? (live.connected ? '运行状态同步' : '正在连接') : metricBasis }}</span></div>
        <div class="banner-center"><i class="banner-wing"></i><h1>西北某高校共享单车调度中心</h1><i class="banner-wing right"></i></div>
        <div class="header-clock"><span>{{ dateText }}</span><b class="mono">{{ timeText }}</b></div>
      </header>

      <aside class="side-panel left-panel" aria-label="运行概览">
        <section class="panel-block fleet-block">
          <div class="block-head"><h2>车辆构成</h2><span class="head-dots">···</span></div>
          <div class="fleet-body">
            <div class="fleet-donut"><EChart :option="fleetOption" height="100%" /><div class="donut-center"><b>{{ displayFleet }}</b><span>{{ mode === 'live' ? '总车辆' : '可用车辆' }}</span></div></div>
            <div class="fleet-legend">
              <div><i class="dot cyan"></i><span>可用车辆</span><b>{{ mode === 'live' ? liveValue('in_station') : currentFleet }}</b></div>
              <div><i class="dot blue"></i><span>在途车辆</span><b>{{ mode === 'live' ? liveValue('riding') : '—' }}</b></div>
              <div><i class="dot amber"></i><span>违停车辆</span><b>{{ mode === 'live' ? liveValue('misplaced') : '—' }}</b></div>
            </div>
          </div>
          <div class="panel-foot"><span>{{ serviceStations.length }} 个停车点</span><span>{{ mode === 'live' ? live.time : currentTime }}</span></div>
        </section>

        <section class="panel-block pressure-block">
          <div class="block-head"><h2>分点供需</h2><div class="mini-legend"><i class="dot cyan"></i>可用<i class="dot amber"></i>需求</div></div>
          <div class="demand-totals"><span>预计需求 <b>{{ demandLoaded ? demandTotal : '—' }}</b></span><span>预计缺口 <b class="gold">{{ demandLoaded ? gapTotal : '—' }}</b></span><small>辆 / {{ heatWindow }}</small></div>
          <div v-if="topGap" class="gap-banner"><span>{{ topGap.id }} 当前缺口</span><b>{{ topGap.gap }}</b><em>辆</em></div>
          <div v-if="pointDemandRank.length" class="pressure-list">
            <button v-for="s in pointDemandRank" :key="s.id" class="pressure-row demand-row" :class="{ selected: selected === s.id }" @click="focusStation(s.id)">
              <b>{{ s.id }}</b><div class="dual-track"><i :style="{ width: `${s.n / barScale * 100}%` }"></i><em :style="{ width: `${(s.d || 0) / barScale * 100}%` }"></em></div><span class="dual-num">可用<b>{{ Math.round(s.n) }}</b>·需求<b>{{ Math.round(s.d || 0) }}</b></span>
            </button>
          </div>
          <div class="panel-foot"><span>{{ demandError || '缺口优先 TOP5 · 点击定位' }}</span><span>{{ heatWindow }}</span></div>
        </section>

        <section class="panel-block demand-block">
          <div class="block-head"><h2>校园需求脉冲</h2><span class="head-dots">···</span></div>
          <div class="chart-box"><EChart :option="demandOption" height="100%" /></div>
          <div class="panel-foot"><span>模型需求 · 辆 / 10 分钟</span><span>06:30 — 23:30</span></div>
        </section>
      </aside>

      <aside class="side-panel right-panel" aria-label="调度工作台">
        <section class="panel-block action-block">
          <div class="block-head"><h2>当前调度</h2><button v-if="canEdit && !record" class="head-action" @click="openDispatch">{{ mode === 'live' ? '调拨 ›' : '推演方案 ›' }}</button><span v-else class="head-dots">···</span></div>
          <div class="dispatch-route"><span><i class="route-pin"></i>{{ routeStatus?.from || dispatchOrigin }}</span><div class="route-link"><svg viewBox="0 0 80 28" aria-hidden="true"><circle cx="20" cy="18" r="6"/><circle cx="54" cy="18" r="6"/><path d="m20 18 9-15 11 15H20l9-15h15m-8 0 18 15M5 26h68m-6-5 6 5-6 5"/></svg></div><span><i class="route-pin gold"></i>{{ routeStatus?.to || dispatchDestination }}</span></div>
          <dl class="dispatch-facts"><div><dt>{{ mode === 'live' ? '调拨数量' : '当前动作' }}</dt><dd>{{ mode === 'live' ? (latestDispatch ? `${latestDispatch.qty} 辆` : '— 辆') : currentAction }}</dd></div><div><dt>更新时刻</dt><dd class="mono">{{ latestDispatch && mode === 'live' ? latestDispatch.t : (mode === 'replay' ? currentTime : '—:—') }}</dd></div><div><dt>任务状态</dt><dd class="status-value">{{ mode === 'live' ? routeStateText : (playing ? '回放中' : '已暂停') }}<i class="status-track"><b :style="{ width: `${routeStatus?.percent || 0}%` }"></b></i></dd></div></dl>
          <div v-if="routeStatus && routeStatus.phase !== 'blocked'" class="panel-foot route-caption"><span>路线演示 · {{ routeStatus.distance }} m</span><span>道路接驳 {{ routeStatus.access }} m<span v-if="routeStatus.queued"> · 待办 {{ routeStatus.queued }}</span></span></div>
        </section>

        <section class="panel-block trend-block">
          <div class="block-head"><h2>{{ mode === 'live' ? '借还动态' : '运营成本' }}</h2><span class="head-tag">{{ mode === 'live' ? '辆 / 分钟' : '元' }}</span></div>
          <template v-if="mode === 'live'">
            <div class="trend-kpis"><div><span>累计借出</span><b>{{ liveValue('rents') }}</b></div><div><span>累计归还</span><b>{{ liveValue('returns') }}</b></div><div><span>借车未满足</span><b :class="liveValue('rejected') > 0 ? 'danger-blink' : 'gold'">{{ liveValue('rejected') }}</b></div></div>
            <div v-if="trend.length" class="chart-box trend-chart"><EChart :option="trendOption" height="100%" /></div><div v-else class="panel-empty">等待本次连接后的借还变化</div>
          </template>
          <div v-else class="chart-box"><EChart :option="costOption" height="100%" /></div>
          <div class="panel-foot"><span>{{ mode === 'live' ? '本次连接 · 最近 20 分钟' : '不含短缺损失' }}</span><span>{{ mode === 'live' ? '当前分钟持续累加' : currentTime }}</span></div>
        </section>

        <section class="panel-block event-block">
          <div class="block-head"><h2>调度事件</h2><div class="event-tabs"><button :class="{ active: eventFilter === 'all' }" @click="eventFilter = 'all'">全部</button><button :class="{ active: eventFilter === 'alert' }" @click="eventFilter = 'alert'">告警</button><button v-if="mode === 'live'" :class="{ active: eventFilter === 'dispatch' }" @click="eventFilter = 'dispatch'">调拨</button></div></div>
          <div v-if="filteredEvents.length" class="event-list"><button v-for="e in filteredEvents.slice(0, 5)" :key="e.id" class="event-row" :class="[e.type, { alert: e.alert }]" @click="locateEvent(e)"><span class="event-time mono">{{ e.time }}</span><i class="event-node"></i><span class="event-copy">{{ e.label }}</span><span class="event-arrow">›</span></button></div>
          <div v-else class="panel-empty event-empty"><i class="empty-pulse"></i><b>暂无当前类型事件</b><span>借还、调拨与告警记录将在此更新</span></div>
          <div class="panel-foot"><span>{{ mode === 'live' ? '借还 · 调拨 · 告警' : '调度动作记录' }}</span><span>{{ mode === 'live' ? (live.connected ? '持续更新' : '等待连接') : currentTime }}</span></div>
        </section>
      </aside>

      
      <div v-if="mode === 'replay'" class="sim-badge"><i></i>模拟推演中 · 未下发真实指令</div>
      <div v-if="mode === 'live' && alertBanner" class="alert-strip"><i></i><b class="mono">{{ alertBanner.t }}</b><span>{{ alertBanner.note }}</span></div>

      <div v-if="heatMode !== 'off'" class="heat-legend" aria-label="分点需求热力图例"><div class="heat-tabs"><button :class="{ active: heatMode === 'demand' }" @click="heatMode = 'demand'">预计需求</button><button :class="{ active: heatMode === 'gap' }" @click="heatMode = 'gap'">预计缺口</button><small>30 分钟</small></div><template v-if="demandLoaded"><div class="heat-gradient"></div><div class="heat-scale"><span>0</span><span>{{ heatMax }} 辆</span></div><p>{{ stationDemand.covered_min === 0 ? '所选时间无运营需求' : heatMode === 'gap' ? '缺口 = max(需求 − 当前库存, 0)' : '各点位借车需求 · 模型估计' }}</p></template><p v-else>{{ demandError || '正在读取分点需求' }}</p></div>
      <div v-if="following" class="follow-hint">跟随运送车 <span>拖动地图退出跟随</span></div>
      <div v-if="dispatchToast" class="mission-toast" role="status">{{ dispatchToast }}</div>

      <footer class="command-footer">
        <div class="footer-counters">
          <div class="footer-metric"><svg viewBox="0 0 48 48" aria-hidden="true"><path d="M24 43s14-16 14-26a14 14 0 1 0-28 0c0 10 14 26 14 26Z"/><path d="M20 26V10h7a5 5 0 0 1 0 10h-7"/></svg><div><b>{{ serviceStations.length }}</b><span>停车点</span></div></div>
          <div class="footer-metric"><svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="12" cy="33" r="9"/><circle cx="37" cy="33" r="9"/><path d="m12 33 10-19 15 19H12l7-14h14m-7-11 11 25M16 8h10"/></svg><div><b>{{ totalBikes }}</b><span>初始车辆</span></div></div>
          <div class="footer-metric warning"><svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="19"/><path d="m11 11 26 26"/></svg><div><b>{{ noParkingZones.length }}</b><span>禁停区</span></div></div>
        </div>
        <nav v-if="!record" class="view-toolbar" aria-label="场景工具">
          <button :class="{ active: activeView === 'overview' }" @click="changeView('overview')"><span class="tool-mark">◇</span>校园总览</button>
          <button :class="{ active: following }" :disabled="!routeStatus || routeStatus.phase === 'blocked'" @click="sceneRef?.followTruck()"><span class="tool-mark">⌖</span>跟随运送车</button>
          <button :class="{ active: heatMode !== 'off' }" @click="toggleHeat"><span class="tool-mark">◉</span>热力</button>
          <button :class="{ active: showLabels }" @click="showLabels = !showLabels"><span class="tool-mark">▥</span>楼名</button>
          <button @click="toggleFullscreen"><span class="tool-mark">⛶</span>全屏</button>
          <button class="menu-toggle" :class="{ active: menuOpen }" @click="menuOpen = !menuOpen" aria-label="功能菜单">☰</button>
        </nav>
        <div v-else class="record-status"><i class="connection-dot online"></i>校园调度运行总览</div>
      </footer>

      <div v-if="!record" class="mode-switch" aria-label="数据模式"><button :class="{ active: mode === 'live' }" @click="setMode('live')">实时运行</button><button :class="{ active: mode === 'replay' }" @click="setMode('replay')">调度推演</button><button v-if="mode === 'replay' && steps.length" @click="togglePlay">{{ playing ? '暂停' : '播放' }}</button></div>
      <div v-if="mode === 'replay' && steps.length && !record" class="replay-seek"><span>{{ currentTime }}</span><input type="range" :max="maxStep" :value="currentStep" @input="onSeek" aria-label="推演进度"/><span>{{ maxStep }} 步</span><select :value="speed" @change="changeSpeed" aria-label="播放速度"><option :value="1">1×</option><option :value="2">2×</option><option :value="4">4×</option></select></div>

      <div v-if="selectedStation" class="point-detail"><button class="point-close" @click="selected = ''" aria-label="关闭点位详情">×</button><div class="point-kicker">停车点详情</div><h3>{{ selectedStation.id }} <span>{{ selectedStation.name }}</span></h3><div class="point-grid"><div><span>当前车辆</span><b>{{ Math.round(selectedInventory) }}</b></div><div><span>停车容量</span><b>{{ selectedStation.capacity }}</b></div><div><span>空间占用</span><b>{{ selectedRatio }}%</b></div></div><div class="point-demand"><span>30 分钟需求 <b>{{ selectedDemand?.d == null ? '—' : selectedDemand.d.toFixed(1) }}</b></span><span>预计缺口 <b>{{ selectedDemand?.gap == null ? '—' : selectedDemand.gap.toFixed(1) }}</b></span></div><div class="point-track"><i :style="{ width: `${selectedRatio}%` }"></i></div><div class="point-foot"><span :class="selectedStatusClass">{{ selectedStatus }}</span><button v-if="canEdit && mode === 'live' && !record" @click="openDispatch">下发调拨 ›</button></div></div>

      <div v-if="!loading && !serviceStations.length" class="empty-state"><h2>停车点位待标定</h2><p>校园场景已就绪，请先维护停车点位。</p><button v-if="canEdit" class="outline-action" @click="go('/app/stations')">进入点位管理</button></div>

      <transition name="fade"><div v-if="dispatchOpen" class="dispatch-mask" @click.self="dispatchOpen = false"><div class="dispatch-panel"><div class="dispatch-head"><div><span>调度工作台</span><h3>下发调拨指令</h3></div><button @click="dispatchOpen = false" aria-label="关闭调拨面板">×</button></div><p class="dispatch-note">选择起点、终点与数量后下发；三轮车按行程时间送达，途中车辆不可用，可连续执行多趟。</p><div class="dispatch-form"><label>起点 · 调出<select v-model="dispatchForm.from"><option v-for="s in dispatchCandidates" :key="s.id" :value="s.id">{{ s.id }} · {{ Math.round(s.n) }}/{{ s.cap }}</option></select></label><label>终点 · 调入<select v-model="dispatchForm.to"><option v-for="s in dispatchCandidates" :key="s.id" :value="s.id">{{ s.id }} · {{ Math.round(s.n) }}/{{ s.cap }}</option></select></label><label>数量 <span class="qty-val">{{ dispatchForm.qty }}</span> 辆<input type="range" min="1" max="20" step="1" v-model.number="dispatchForm.qty" /></label></div><div class="horizon-tabs"><span>预测时长</span><button v-for="h in [30, 60, 120]" :key="h" :class="{ active: dispatchForm.horizon === h }" @click="dispatchForm.horizon = h">{{ h }} 分钟</button><span class="ht-sep">需求压力</span><button v-for="k in [1, 1.5, 2]" :key="k" :class="{ active: dispatchForm.stress === k }" @click="dispatchForm.stress = k">{{ k }}×</button></div><div class="dispatch-eta"><span>直线距离 <b>{{ etaInfo.distance }} m</b></span><span>预计用时 <b>{{ etaInfo.eta }} 分钟</b></span><span>三轮车 <b>{{ truckText }}</b></span></div><div v-if="previewResult" class="preview-result"><div><span>不调度 · 短缺</span><b>{{ previewResult.env?.base?.shortage ?? '—' }}</b></div><div><span>按方案 · 短缺</span><b>{{ previewResult.env?.plan?.shortage ?? '—' }}</b></div><div><span>变化</span><b :class="(previewResult.env?.shortage_delta ?? 0) <= 0 ? 'good' : 'bad'">{{ (previewResult.env?.shortage_delta ?? 0) > 0 ? '+' : '' }}{{ previewResult.env?.shortage_delta ?? '—' }}</b></div></div><p v-if="previewResult" class="preview-note">服务率 {{ ((previewResult.env?.base?.service_rate ?? 0) * 100).toFixed(2) }}% → {{ ((previewResult.env?.plan?.service_rate ?? 0) * 100).toFixed(2) }}%；{{ previewResult.to_id }} 缺口 {{ previewResult.base_gap }} → {{ previewResult.shifted_gap }}；{{ previewResult.horizon_min }} 分钟 · 需求 {{ previewResult.env?.stress ?? 1 }}× · NoOp 基线</p><div class="dispatch-actions"><button class="outline-action" :disabled="previewing" @click="runPreview">{{ previewing ? '正在推演…' : (mode === 'replay' ? '开始推演' : '供需对照') }}</button><button class="primary-action" :disabled="dispatching || mode !== 'live'" @click="submitDispatch">{{ dispatching ? '正在下发…' : '确认下发' }}</button></div><p v-if="dispatchMsg" class="dispatch-msg" role="status">{{ dispatchMsg }}</p></div></div></transition>

      <transition name="fade"><div v-if="menuOpen && !record" class="menu-mask" @click.self="menuOpen = false"><div class="menu-panel"><div class="menu-head"><b>调度中心</b><button @click="menuOpen = false">关闭</button></div><button v-for="item in visibleNav" :key="item.path" @click="go(item.path)"><span>{{ item.label }}</span><i>›</i></button><button @click="go(screen ? '/app/dashboard' : '/screen')"><span>{{ screen ? '返回工作台' : '独立大屏' }}</span><i>›</i></button><button class="logout" @click="logout">退出登录</button></div></div></transition>
      <div v-if="showIntro" class="intro-overlay"><div class="intro-copy"><h1>西北某高校共享单车调度中心</h1></div><button v-if="!record" class="intro-skip" @click="finishIntro">跳过开场</button></div>
      <div v-if="loading" class="loading-mask"><i></i><span>正在装载校园数字沙盘</span></div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useLiveStore } from '../stores/live'
import { CAMPUS_CENTER } from '../config/map'
import TwinScene from '../components/twin/TwinScene.vue'
import EChart from '../components/EChart.vue'

const props = defineProps({
  screen: { type: Boolean, default: false },
  record: { type: Boolean, default: false }
})

const router = useRouter()
const auth = useAuthStore()
const live = useLiveStore()
const root = ref(null)
const sceneRef = ref(null)
const loading = ref(true)
const stations = ref([])
const steps = ref([])
const summary = ref({})
const demand = ref({ times: [], values: [] })
const currentStep = ref(0)
const playing = ref(false)
const speed = ref(1)
const selected = ref('')
const menuOpen = ref(false)
const now = ref('')
const showIntro = ref(false)
const mode = ref('live')
const theme = ref('night')
const showLabels = ref(false)
const dockCollapsed = ref(false)
const dateText = ref('')
const timeText = ref('')
const dispatchOpen = ref(false)
const dispatchForm = reactive({ from: '', to: '', qty: 10, horizon: 60, stress: 1 })
const previewResult = ref(null)
const previewing = ref(false)
const dispatching = ref(false)
const dispatchMsg = ref('')
let runLoading = false
let timer = null
let clockTimer = null
let introTimer = null
let cursorTimer = null

const nav = [
  { path: '/app/dashboard', label: '数字孪生' },
  { path: '/app/simulation', label: '实时推演' },
  { path: '/app/compare', label: '对比分析' },
  { path: '/app/stations', label: '点位管理' },
  { path: '/app/scenarios', label: '方案管理' },
  { path: '/app/night', label: '夜间调度' },
  { path: '/app/users', label: '用户管理', roles: ['admin'] },
  { path: '/app/settings', label: '系统设置', roles: ['admin'] },
  { path: '/app/logs', label: '日志审计', roles: ['admin'] }
]
const canEdit = computed(() => auth.role !== 'viewer')
const visibleNav = computed(() => nav.filter((item) => !item.roles || item.roles.includes(auth.role)))
const serviceStations = computed(() => stations.value.filter((s) => s.func !== 'nopark'))
const noParkingZones = computed(() => stations.value.filter((s) => s.func === 'nopark'))
const stepData = computed(() => steps.value[currentStep.value] || null)
const maxStep = computed(() => Math.max(steps.value.length - 1, 0))
const currentTime = computed(() => (stepData.value && stepData.value.time) || '06:30')
const currentAction = computed(() => (stepData.value && stepData.value.action && stepData.value.action.label) || '等待调度')
// 指标口径：优先当前帧的累计值（step.metrics 为“截至该步”的累计），不回退成全天结果
const currentMetrics = computed(() => (stepData.value && stepData.value.metrics) || {})
const serviceRate = computed(() => {
  const v = currentMetrics.value.service_rate
  return v == null ? null : Number(v)
})
const metricBasis = computed(() => (steps.value.length ? `截至 ${currentTime.value} 累计` : '初始库存场景'))
const totalBikes = computed(() => serviceStations.value.reduce((sum, s) => sum + Number(s.init_bikes || 0), 0))
const currentFleet = computed(() => {
  const inv = stepData.value && stepData.value.inventory
  if (Array.isArray(inv) && inv.length === serviceStations.value.length) {
    return Math.round(inv.reduce((sum, n) => sum + Number(n || 0), 0))
  }
  return totalBikes.value
})
const liveInventory = computed(() => serviceStations.value.map((s) => {
  const v = live.inventory[s.id]
  return v == null ? Number(s.init_bikes || 0) : Number(v)
}))
const frozenInventory = ref(null)
const activeStepData = computed(() => {
  const inventory = mode.value === 'live' ? liveInventory.value : (frozenInventory.value || liveInventory.value)
  return { inventory, action: { mode: 0, label: mode.value === 'live' ? '实时监测' : '推演基线' }, metrics: {} }
})
const fleetTotal = computed(() => live.inStation + live.riding + live.misplaced)
const arcFeed = ref([])
let arcSeq = 0
let lastEventId = 0
const coordMap = computed(() => {
  const map = {}
  serviceStations.value.forEach((s) => { map[s.id] = [Number(s.lng), Number(s.lat)] })
  return map
})
function pushArc(item) {
  arcSeq += 1
  arcFeed.value = [...arcFeed.value.slice(-39), { ...item, id: item.id || `a${arcSeq}` }]
}
watch(() => live.gen, () => {
  lastEventId = 0
  arcFeed.value = []
  lastOrder.value = null
})
watch(() => live.events[0]?.id, () => {
  const fresh = []
  for (const e of live.events) {
    if (e.id <= lastEventId) break
    fresh.push(e)
  }
  if (!fresh.length) return
  lastEventId = fresh[0].id
  fresh.reverse().forEach((e) => { if (e.type === 'dispatch') ingestDispatch(e) })
})
const latestAlertId = computed(() => (live.events.find((e) => e.alert) || {}).id || 0)
const alertBanner = ref(null)
let alertTimer = null
watch(latestAlertId, (id) => {
  if (!id) return
  alertBanner.value = live.events.find((e) => e.id === id) || null
  if (alertTimer) clearTimeout(alertTimer)
  alertTimer = setTimeout(() => { alertBanner.value = null }, 7000)
})
const dispatchCandidates = computed(() => serviceStations.value
  .map((s, i) => ({ id: s.id, n: liveInventory.value[i], cap: s.capacity }))
  .sort((a, b) => (a.n / Math.max(a.cap, 1)) - (b.n / Math.max(b.cap, 1)))
  )
const etaInfo = computed(() => {
  const a = serviceStations.value.find((x) => x.id === dispatchForm.from)
  const b = serviceStations.value.find((x) => x.id === dispatchForm.to)
  if (!a || !b || dispatchForm.from === dispatchForm.to) return { distance: '—', eta: '—' }
  const rad = Math.PI / 180
  const dLat = (b.lat - a.lat) * rad
  const dLng = (b.lng - a.lng) * rad
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2
  const d = 2 * 6371000 * Math.asin(Math.sqrt(h))
  const qty = Math.max(1, Number(dispatchForm.qty) || 1)
  return { distance: Math.round(d), eta: (d / 250 + qty * 0.5).toFixed(1) }
})
const truckText = computed(() => {
  const t = live.truck
  if (!t) return '—'
  return t.busy ? `忙碌 · ${t.free_in_min} 分钟后空闲` : '空闲'
})
const displayFleet = computed(() => mode.value === 'live' ? (live.source ? fleetTotal.value : totalBikes.value) : currentFleet.value)
function liveValue(key) { return live.source ? Number(live.stats[key] ?? 0) : 0 }
const fleetOption = computed(() => ({
  backgroundColor: 'transparent', animationDuration: 400,
  tooltip: { trigger: 'item', backgroundColor: palette.value.tipBg, borderColor: palette.value.tipBorder, textStyle: { color: palette.value.tipText } },
  series: [
    { type: 'pie', silent: true, radius: ['68%', '85%'], center: ['50%', '52%'], label: { show: false }, data: [{ value: 1, itemStyle: { color: palette.value.track } }], z: 0 },
    { type: 'pie', radius: ['63%', '80%'], center: ['50%', '48%'], label: { show: false }, labelLine: { show: false }, itemStyle: { borderWidth: 2, borderColor: theme.value === 'day' ? '#dfedf5' : '#061b2d' }, data: [
      { name: '可用车辆', value: mode.value === 'live' ? (live.source ? live.inStation : totalBikes.value) : currentFleet.value, itemStyle: { color: palette.value.cyan } },
      { name: '在途车辆', value: mode.value === 'live' ? live.riding : 0, itemStyle: { color: palette.value.blue } },
      { name: '待归位车辆', value: mode.value === 'live' ? live.misplaced : 0, itemStyle: { color: palette.value.amber } }
    ] }
  ]
}))
const selectedStation = computed(() => serviceStations.value.find((s) => s.id === selected.value) || null)
const selectedIndex = computed(() => serviceStations.value.findIndex((s) => s.id === selected.value))
const selectedInventory = computed(() => {
  if (!selectedStation.value) return 0
  const inventory = activeStepData.value && activeStepData.value.inventory
  return inventory && inventory[selectedIndex.value] != null ? Number(inventory[selectedIndex.value]) : Number(selectedStation.value.init_bikes || 0)
})
const selectedRatio = computed(() => selectedStation.value && selectedStation.value.capacity
  ? Math.min(100, Math.round(selectedInventory.value / selectedStation.value.capacity * 100))
  : 0)
const selectedStatus = computed(() => selectedRatio.value < 20 ? '库存偏低' : selectedRatio.value > 80 ? '库存偏高' : '库存正常')
const selectedStatusClass = computed(() => selectedRatio.value < 20 ? 'is-low' : selectedRatio.value > 80 ? 'is-high' : 'is-normal')
const truckPath = computed(() => {
  const path = []
  for (let i = 0; i <= currentStep.value; i += 1) {
    const truck = steps.value[i] && steps.value[i].truck
    if (truck && (path.length === 0 || path[path.length - 1] !== truck.station)) path.push(truck.station)
  }
  return path
})
const stationRank = computed(() => {
  const inventory = (activeStepData.value && activeStepData.value.inventory) || serviceStations.value.map((s) => s.init_bikes)
  return serviceStations.value.map((s, i) => {
    const n = inventory[i] != null ? Number(inventory[i]) : Number(s.init_bikes || 0)
    const ratio = s.capacity ? n / s.capacity : 0
    return { id: s.id, name: s.name, n, cap: s.capacity, statusClass: ratio < 0.2 ? 'low' : ratio > 0.8 ? 'high' : 'normal' }
  }).sort((a, b) => Math.abs(b.n / Math.max(b.cap, 1) - 0.5) - Math.abs(a.n / Math.max(a.cap, 1) - 0.5)).slice(0, 5)
})
const pressureBars = computed(() => {
  const inv = (activeStepData.value && activeStepData.value.inventory) || []
  return serviceStations.value
    .map((s, i) => {
      const n = inv[i] != null ? Number(inv[i]) : Number(s.init_bikes || 0)
      const ratio = s.capacity ? Math.max(0, Math.min(1, n / s.capacity)) : 0
      return { id: s.id, n, cap: s.capacity, ratio }
    })
    .sort((a, b) => a.ratio - b.ratio)
    .slice(0, 6)
})
const events = computed(() => {
  const list = []
  for (let i = currentStep.value; i >= 0 && list.length < 6; i -= 1) {
    const s = steps.value[i]
    if (s && s.action && s.action.mode !== 0 && s.action.label) list.push({ step: i, time: s.time, label: s.action.label, station: s.action.station })
  }
  return list
})

const palette = computed(() => (theme.value === 'day'
  ? {
      axis: '#6b8194', grid: 'rgba(18,52,80,.09)', text: '#33495c',
      cyan: '#0e7fa8', amber: '#c9780a', red: '#c8402f', blue: '#2f6fd0',
      tipBg: '#ffffff', tipBorder: 'rgba(18,52,80,.14)', tipText: '#12283a',
      track: 'rgba(18,52,80,.08)'
    }
  : {
      axis: '#9db8cc', grid: 'rgba(34,76,104,.28)', text: '#c3dced',
      cyan: '#38d9e8', amber: '#f5a623', red: '#ef5b5b', blue: '#3e8dff',
      tipBg: '#081c2c', tipBorder: '#2a5b78', tipText: '#dff8ff',
      track: 'rgba(96,160,200,.12)'
    }))
const axis = { color: '#7e9ab4', fontSize: 14 }
const demandOption = computed(() => ({
  backgroundColor: 'transparent',
  animation: false,
  grid: { left: 42, right: 14, top: 12, bottom: 24 },
  xAxis: { type: 'category', data: demand.value.times, axisLine: { lineStyle: { color: palette.value.grid } }, axisTick: { show: false }, axisLabel: { ...axis, color: palette.value.axis, fontSize: 11, interval: 'auto', hideOverlap: true } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: palette.value.grid } }, axisLabel: { ...axis, color: palette.value.axis, fontSize: 11, hideOverlap: true } },
  tooltip: { trigger: 'axis', backgroundColor: palette.value.tipBg, borderColor: palette.value.tipBorder, textStyle: { color: palette.value.tipText, fontSize: 14 } },
  series: [{
    type: 'line', data: demand.value.values, smooth: 0.35, showSymbol: false,
    lineStyle: { color: palette.value.cyan, width: 2 },
    areaStyle: {
      color: {
        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(61,228,244,.42)' },
          { offset: 1, color: 'rgba(61,228,244,0)' }
        ]
      }
    },
    markLine: mode.value === 'live'
      ? { silent: true, symbol: 'none', label: { show: false }, lineStyle: { color: palette.value.amber, width: 1 }, data: demand.value.times.length ? [{ xAxis: Math.max(0, demand.value.times.findIndex(t => { const [h,m] = t.split(':').map(Number); return h*60+m >= displayMinute.value })) }] : [] }
      : { silent: true, symbol: 'none', label: { show: false }, lineStyle: { color: '#f2b24b', width: 1 }, data: [{ xAxis: currentStep.value }] }
  }]
}))
const costOption = computed(() => {
  const m = currentMetrics.value || {}
  const coupon = Number(m.coupon_cost || m.coupon_cost_yuan || 0)
  const total = Number(m.total_cost_yuan || 0)
  return {
    backgroundColor: 'transparent', animation: false,
    grid: { left: 66, right: 50, top: 10, bottom: 18 },
    xAxis: { type: 'value', axisLabel: { ...axis, color: palette.value.axis, formatter: (v) => `¥${v}` }, splitLine: { lineStyle: { color: palette.value.grid } } },
    yAxis: { type: 'category', data: ['搬运', '激励'], axisLabel: { ...axis, color: palette.value.axis }, axisLine: { show: false }, axisTick: { show: false } },
    tooltip: { trigger: 'axis', backgroundColor: palette.value.tipBg, borderColor: palette.value.tipBorder, textStyle: { color: palette.value.tipText, fontSize: 14 }, valueFormatter: (v) => `¥ ${Number(v).toFixed(2)}` },
    series: [{ type: 'bar', barWidth: 20, data: [
      { value: Math.max(total - coupon, 0), itemStyle: { color: palette.value.blue, borderRadius: [0, 3, 3, 0] } },
      { value: coupon, itemStyle: { color: palette.value.cyan, borderRadius: [0, 3, 3, 0] } }
    ], label: { show: true, position: 'right', color: palette.value.text, fontSize: 14, formatter: (p) => Number(p.value).toFixed(2) } }]
  }
})

function pct(v) { return v == null ? '—' : `${(Number(v) * 100).toFixed(2)}%` }
function num(v, d = 1) { return v == null ? '—' : Number(v).toFixed(d) }
function toggleFullscreen() {
  if (!document.fullscreenElement) document.documentElement.requestFullscreen().catch(() => {})
  else document.exitFullscreen().catch(() => {})
}
const WEEK = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
function tick() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  dateText.value = `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 ${WEEK[d.getDay()]}`
  timeText.value = `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
  now.value = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${timeText.value}`
}
function pause() { playing.value = false; if (timer) clearInterval(timer); timer = null }
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
function onSeek(e) { pause(); currentStep.value = Number(e.target.value) }
function changeSpeed(e) { speed.value = Number(e.target.value); if (playing.value) startTimer() }
function toggleTheme() { theme.value = theme.value === 'day' ? 'night' : 'day' }
function focusStation(id) { selected.value = id; if (sceneRef.value) sceneRef.value.focusStation(id) }
function jumpEvent(e) { onSeek({ target: { value: e.step } }); const s = serviceStations.value[e.station]; if (s) focusStation(s.id) }
function finishIntro() { showIntro.value = false; if (introTimer) clearTimeout(introTimer) }
function go(path) { menuOpen.value = false; pause(); router.push(path) }
function logout() { pause(); auth.logout(); router.push('/login') }
function wakeCursor() {
  if (!props.record) return
  document.body.style.cursor = 'default'
  if (cursorTimer) clearTimeout(cursorTimer)
  cursorTimer = setTimeout(() => { document.body.style.cursor = 'none' }, 3000)
}

async function pickRun(count) {
  // 优先复用与当前点位规模一致的最近一次运行；打开展示页不再无条件写入新运行记录
  try {
    const res = await api.get('/simulations')
    const runs = (res.data || []).slice(0, 4)
    for (const run of runs) {
      const stepRes = await api.get(`/simulations/${run.id}/steps`)
      const list = stepRes.data || []
      const inv = list.length ? list[0].inventory : null
      if (Array.isArray(inv) && inv.length === count) {
        let detail = null
        try { detail = (await api.get(`/simulations/${run.id}`)).data } catch (e) { detail = null }
        return { steps: list, summary: (detail && detail.summary) || run.summary || {}, reused: true }
      }
    }
  } catch (e) {
    /* 历史读取失败时继续走新推演 */
  }
  const simRes = await api.post('/simulations', { policy: 'ppo', seed: 101 })
  return { steps: simRes.data.steps || [], summary: simRes.data.summary || {}, reused: false }
}

async function load() {
  loading.value = true
  try {
    const stationRes = await api.get('/stations')
    stations.value = stationRes.data || []
    try { const demandRes = await api.get('/demand-profile'); demand.value = demandRes.data || { times: [], values: [] } } catch (e) { demand.value = { times: [], values: [] } }
    const first = dispatchCandidates.value[0]
    if (first && !dispatchForm.station) {
      dispatchForm.station = first.id
    }
    await refreshStationDemand()
    steps.value = []
    summary.value = {}
  } catch (e) {
    stations.value = []
    steps.value = []
    summary.value = {}
  } finally {
    loading.value = false
    let seen = false
    try { seen = sessionStorage.getItem('twin-intro-seen') === '1' } catch (err) { seen = false }
    if (props.screen || !seen) {
      showIntro.value = true
      try { sessionStorage.setItem('twin-intro-seen', '1') } catch (err) { /* ignore */ }
      introTimer = setTimeout(finishIntro, 5200)
    }
  }
}

async function ensureRun() {
  if (steps.value.length || runLoading || serviceStations.value.length < 3) return
  runLoading = true
  try {
    const data = await pickRun(serviceStations.value.length)
    steps.value = data.steps || []
    summary.value = data.summary || {}
    currentStep.value = 0
    if (steps.value.length) startTimer()
  } catch (e) {
    steps.value = []
  } finally {
    runLoading = false
  }
}

function setMode(name) {
  mode.value = name
  eventFilter.value = 'all'
  if (name === 'live') {
    pause()
    frozenInventory.value = null
    return
  }
  // 推演：冻结当前库存作为基线，并自动切到缺口热力
  frozenInventory.value = [...liveInventory.value]
  steps.value = []
  previewResult.value = null
  if (heatMode.value === 'off') heatMode.value = 'gap'
}

function openDispatch() {
  dispatchMsg.value = ''
  previewResult.value = null
  const sorted = [...dispatchCandidates.value].sort((a, b) => b.n - a.n)
  const gapTop = pointDemandRank.value[0]
  const low = gapTop && gapTop.gap > 0 ? gapTop : dispatchCandidates.value[0]
  const high = sorted[0]
  dispatchForm.to = low ? low.id : ((serviceStations.value[0] && serviceStations.value[0].id) || '')
  dispatchForm.from = high ? high.id : dispatchForm.to
  if (dispatchForm.from === dispatchForm.to && dispatchCandidates.value[1]) {
    dispatchForm.from = dispatchCandidates.value[1].id
  }
  dispatchForm.qty = 10
  dispatchOpen.value = true
}

async function runPreview() {
  if (!dispatchForm.from || !dispatchForm.to) return
  previewing.value = true
  dispatchMsg.value = ''
  try {
    previewResult.value = await live.preview(dispatchForm.from, dispatchForm.to, dispatchForm.qty, dispatchForm.horizon, dispatchForm.stress)
  } catch (e) {
    dispatchMsg.value = (e.response && e.response.data && e.response.data.detail) || '供需对照暂不可用'
  } finally {
    previewing.value = false
  }
}

async function submitDispatch() {
  if (!dispatchForm.from || !dispatchForm.to) return
  dispatching.value = true
  try {
    const data = await live.dispatch(dispatchForm.from, dispatchForm.to, dispatchForm.qty)
    lastOrder.value = data.event || null
    ingestDispatch(data.event)
    dispatchMsg.value = `已下发：${dispatchForm.from} → ${dispatchForm.to} ${data.event?.qty ?? dispatchForm.qty} 辆，预计 ${data.event?.eta_min ?? etaInfo.value.eta} 分钟送达`
    dispatchToast.value = dispatchMsg.value
    if (toastTimer) clearTimeout(toastTimer)
    toastTimer = setTimeout(() => { dispatchToast.value = '' }, 5000)
    dispatchOpen.value = false
    previewResult.value = null

  } catch (e) {
    dispatchMsg.value = (e.response && e.response.data && e.response.data.detail) || '下发失败'
  } finally {
    dispatching.value = false
  }
}

onMounted(() => {
  tick()
  load()
  live.connect()
  live.start(1, null)
  clockTimer = setInterval(tick, 1000)
  wakeCursor()
})
onBeforeUnmount(() => {
  demandRequest += 1
  if (toastTimer) clearTimeout(toastTimer)
  live.disconnect()
  pause()
  if (clockTimer) clearInterval(clockTimer)
  if (introTimer) clearTimeout(introTimer)
  if (cursorTimer) clearTimeout(cursorTimer)
  if (alertTimer) clearTimeout(alertTimer)
  document.body.style.cursor = 'default'
})

// Per-station demand is read from the existing model. Inventory remains the live snapshot.
const stationDemand = ref({ items: [], covered_min: 0 })
const demandLoaded = ref(false)
const demandError = ref('')
const heatMode = ref('demand')
const routeStatus = ref(null)
const following = ref(false)
const eventFilter = ref('all')
const trend = ref([])
let trendPrevious = null
let demandRequest = 0
let toastTimer = null
const dispatchToast = ref('')
const seenDispatch = new Set()
const displayMinute = computed(() => {
  if (mode.value === 'live') return Math.max(0, Math.min(1439, Math.floor(Number(live.minute) || 390)))
  const [h, m] = currentTime.value.split(':').map(Number)
  return h * 60 + m
})
async function refreshStationDemand() {
  if (!serviceStations.value.length) return
  const seq = ++demandRequest
  try {
    const { data } = await api.get('/station-demand', { params: { minute: displayMinute.value, horizon_min: 30 } })
    if (seq !== demandRequest) return
    if (!Array.isArray(data.items)) throw Error('需求数据格式错误')
    stationDemand.value = data; demandLoaded.value = true; demandError.value = ''
  } catch (e) {
    if (seq === demandRequest) { demandError.value = '需求数据暂不可用'; demandLoaded.value = false; stationDemand.value = { items: [], covered_min: 0 } }
  }
}
watch(displayMinute, refreshStationDemand)
const supplyDemand = computed(() => {
  const demandMap = new Map(stationDemand.value.items.map(p => [p.station_id, Number(p.demand)]))
  const inv = activeStepData.value?.inventory || []
  return serviceStations.value.map((s, i) => {
    const n = Number(inv[i] ?? s.init_bikes ?? 0), d = demandMap.has(s.id) ? demandMap.get(s.id) : null
    return { ...s, n, cap: s.capacity, d, gap: d == null ? null : Math.max(0, d - n) }
  })
})
const pointDemandRank = computed(() => [...supplyDemand.value].sort((a, b) => (b.gap || 0) - (a.gap || 0) || a.n - b.n || a.id.localeCompare(b.id)).slice(0, 5))
const barScale = computed(() => Math.max(1, ...pointDemandRank.value.flatMap(s => [s.n, s.d || 0])))
const heatPoints = computed(() => supplyDemand.value.filter(s => s.d != null).map(s => ({ ...s, value: heatMode.value === 'gap' ? s.gap : s.d })))
const heatMax = computed(() => Math.max(0, ...heatPoints.value.map(s => s.value)).toFixed(1))
const topGap = computed(() => {
  const s = pointDemandRank.value[0]
  if (!s || !(s.gap > 0)) return null
  return { id: s.id, gap: Math.round(s.gap * 10) / 10 }
})
const demandTotal = computed(() => supplyDemand.value.reduce((n, s) => n + (s.d || 0), 0).toFixed(1))
const gapTotal = computed(() => supplyDemand.value.reduce((n, s) => n + (s.gap || 0), 0).toFixed(1))
const heatWindow = computed(() => {
  const start = Number(stationDemand.value.minute ?? displayMinute.value)
  const fmt = m => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
  return `${fmt(start)}–${fmt(start + 30)}`
})
const selectedDemand = computed(() => supplyDemand.value.find(s => s.id === selected.value))
function toggleHeat() { heatMode.value = heatMode.value === 'off' ? 'demand' : 'off'; if (heatMode.value !== 'off' && !demandLoaded.value) refreshStationDemand() }
function onFollowChange(value) { following.value = value; activeView.value = value ? 'follow' : 'manual' }
function ingestDispatch(event) {
  if (!event || seenDispatch.has(event.id)) return
  seenDispatch.add(event.id)
  ;(event.moves || []).forEach((m, i) => {
    const a = coordMap.value[m.from], b = coordMap.value[m.to]
    if (a && b && m.qty > 0) pushArc({ id: `d${event.id}-${i}`, from: a, to: b, fromId: m.from, toId: m.to, kind: 'dispatch', qty: m.qty })
  })
}
watch(() => [live.gen, mode.value], () => {
  seenDispatch.clear(); live.events.filter(e => e.type === 'dispatch').forEach(e => seenDispatch.add(e.id))
  routeStatus.value = null; arcFeed.value = []; trend.value = []; trendPrevious = null
})
watch(() => [live.minute, live.stats.rents, live.stats.returns], () => {
  if (!live.source || !live.connected) return
  const minute = Math.floor(live.minute), rents = Number(live.stats.rents || 0), returns = Number(live.stats.returns || 0)
  if (!trendPrevious || minute < trendPrevious.minute || rents < trendPrevious.rents || returns < trendPrevious.returns) {
    trendPrevious = { minute, rents, returns }; return
  }
  const last = trend.value.at(-1)
  let list = [...trend.value]
  if (minute - trendPrevious.minute > 1) list.push({ minute: minute - 1, rent: null, back: null })
  const rent = Math.max(0, rents - trendPrevious.rents), back = Math.max(0, returns - trendPrevious.returns)
  if (last?.minute === minute) list[list.length - 1] = { minute, rent: last.rent + rent, back: last.back + back }
  else list.push({ minute, rent, back })
  trend.value = list.slice(-20); trendPrevious = { minute, rents, returns }
})
watch(() => live.connected, connected => { if (!connected) trendPrevious = null })
const trendOption = computed(() => {
  const p = palette.value
  return {
    animation: false, backgroundColor: 'transparent',
    legend: { top: 0, right: 0, itemWidth: 10, itemHeight: 7, textStyle: { color: p.axis, fontSize: 10 }, data: ['借出', '归还'] },
    grid: { top: 27, bottom: 22, left: 29, right: 9 },
    tooltip: { trigger: 'axis', backgroundColor: p.tipBg, borderColor: p.tipBorder, textStyle: { color: p.tipText }, valueFormatter: v => v == null ? '—' : `${v} 辆` },
    xAxis: { type: 'category', data: trend.value.map(x => `${String(Math.floor(x.minute / 60)).padStart(2, '0')}:${String(x.minute % 60).padStart(2, '0')}`), axisTick: { show: false }, axisLine: { lineStyle: { color: p.grid } }, axisLabel: { color: p.axis, fontSize: 10, hideOverlap: true } },
    yAxis: { type: 'value', minInterval: 1, splitNumber: 3, splitLine: { lineStyle: { color: p.grid } }, axisLabel: { color: p.axis, fontSize: 10, hideOverlap: true } },
    series: [
      { name: '借出', type: 'bar', barMaxWidth: 10, itemStyle: { color: p.amber, borderRadius: [2, 2, 0, 0] }, data: trend.value.map(x => x.rent) },
      { name: '归还', type: 'line', symbol: 'circle', symbolSize: 4, connectNulls: false, lineStyle: { color: p.blue, width: 2 }, itemStyle: { color: p.blue }, data: trend.value.map(x => x.back) }
    ]
  }
})
const filteredEvents = computed(() => displayEvents.value.filter(e => eventFilter.value === 'all' || (eventFilter.value === 'alert' ? e.alert : e.type === 'dispatch')))
const routeStateText = computed(() => {
  const s = routeStatus.value
  if (!s) return latestDispatch.value ? '指令已记录' : '等待下发指令'
  if (s.phase === 'blocked') return s.message
  return `${s.phase === 'arrived' ? '到达接驳点' : s.phase === 'pickup' ? '前往取车' : '沿路运送'} · ${s.percent}%`
})

const activeView = ref('overview')
function changeView(id) { sceneRef.value?.setView(id); activeView.value = id }
const lastOrder = ref(null)
const latestDispatch = computed(() => [lastOrder.value, ...live.events.filter((e) => e.type === 'dispatch')].filter(Boolean).sort((a,b) => b.id-a.id)[0] || null)
const dispatchOrigin = computed(() => latestDispatch.value?.moves?.[0]?.from || (mode.value === 'replay' && steps.value.length ? '运维车' : '源点位'))
const dispatchDestination = computed(() => latestDispatch.value?.moves?.[0]?.to || (mode.value === 'replay' ? (serviceStations.value[stepData.value?.action?.station]?.id || '目标点位') : '目标点位'))
const displayEvents = computed(() => mode.value === 'live'
  ? live.events.map((e) => ({ id: e.id, type: e.type, time: e.t, label: e.note, station: e.station, alert: e.alert }))
  : events.value.map((e) => ({ ...e, id: e.step, time: e.time, station: serviceStations.value[e.station]?.id })))
function locateEvent(e) { if (e.station) focusStation(e.station); if (mode.value === 'replay' && e.step != null) onSeek({ target: { value: e.step } }) }
watch(() => [dispatchForm.from, dispatchForm.to, dispatchForm.qty], () => { previewResult.value = null })

</script>
<style scoped>
.preview-block .preview-chart { min-height: 84px; }
.twin-root{--side:clamp(260px,20vw,390px);--ink:#d8edfb;--muted:#89a9bf;--cyan:#26d3fa;--panel:rgba(5,24,41,.93);--line:#164663;--gold:#ffbb54;position:relative;width:100%;height:100dvh;min-height:620px;background:#061422;color:var(--ink);overflow:hidden;font-family:"Microsoft YaHei",sans-serif;font-size:14px}
.twin-root *{box-sizing:border-box}.twin-root button,.twin-root select{font:inherit}.twin-root button{cursor:pointer}.twin-root button:focus-visible,.twin-root select:focus-visible,.twin-root input:focus-visible{outline:2px solid var(--cyan);outline-offset:3px}.twin-root button:disabled{opacity:.5;cursor:wait}.twin-canvas{position:absolute;inset:0}.mono{font-family:Consolas,monospace;font-variant-numeric:tabular-nums}
.twin-header{position:absolute;inset:0 0 auto;height:82px;z-index:12;display:flex;align-items:center;justify-content:center;background:linear-gradient(180deg,rgba(1,11,22,.96),rgba(4,22,38,.75) 75%,transparent);pointer-events:none}.twin-header:after{content:"";position:absolute;bottom:13px;left:12%;right:12%;height:1px;background:linear-gradient(90deg,transparent,#1a6286 20%,#1796b9 50%,#1a6286 80%,transparent)}.banner-center{display:flex;align-items:center;gap:24px;position:relative;padding:10px 28px 20px;background:linear-gradient(180deg,rgba(10,53,81,.35),rgba(8,38,62,.7));clip-path:polygon(0 0,100% 0,95% 100%,5% 100%)}.banner-center:after{content:"";position:absolute;bottom:2px;left:25%;right:25%;height:2px;background:#29d9ff;box-shadow:0 0 12px #29d9ff}.banner-center h1{margin:0;color:#d8f1ff;font-size:clamp(23px,1.95vw,38px);font-weight:700;letter-spacing:.12em;text-shadow:0 0 16px #168bb744;white-space:nowrap}.banner-wing{display:block;width:clamp(25px,4vw,90px);height:20px;transform:skewX(38deg);border-top:2px solid #1c8cb4;border-bottom:1px solid #164c70;background:linear-gradient(90deg,transparent,#147ca344)}.banner-wing.right{transform:skewX(-38deg);background:linear-gradient(270deg,transparent,#147ca344)}.header-meta,.header-clock{position:absolute;top:22px;font-size:15px;color:var(--muted)}.header-meta{left:30px;display:flex;align-items:center;gap:9px}.header-clock{right:30px;display:flex;align-items:center;gap:15px}.header-clock b{font-weight:400;font-size:22px;letter-spacing:1px;color:#d6f2ff}.connection-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#668092}.connection-dot.online{background:#40dfbb;box-shadow:0 0 9px #40dfbb77}
.side-panel{position:absolute;z-index:10;top:90px;bottom:112px;width:var(--side);display:grid;gap:16px;grid-template-rows:1fr 1fr 1fr;pointer-events:none}.left-panel{left:18px}.right-panel{right:18px}.panel-block{position:relative;min-height:0;display:flex;flex-direction:column;padding:0 16px 8px;border:1px solid var(--line);background:linear-gradient(125deg,rgba(8,40,64,.9),var(--panel) 32%,rgba(3,18,32,.93));box-shadow:inset 0 0 24px #06111a66,0 8px 22px #0003;clip-path:polygon(10px 0,calc(100% - 10px) 0,100% 10px,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%,0 10px);pointer-events:auto}.panel-block:before{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(135deg,transparent 6px,#39cbed 6px,#39cbed 7px,transparent 7px) top left/20px 20px no-repeat,linear-gradient(-45deg,transparent 6px,#287fa5 6px,#287fa5 7px,transparent 7px) bottom right/20px 20px no-repeat}.block-head{display:flex;align-items:center;justify-content:space-between;flex:0 0 42px;margin:0 -5px 8px;border-bottom:1px solid #24577a55;background:linear-gradient(90deg,#0e3e6022,transparent)}.block-head h2{position:relative;margin:0;padding-left:13px;font-size:clamp(15px,1.04vw,20px);font-weight:600;letter-spacing:.07em;color:var(--ink)}.block-head h2:before{content:"";position:absolute;left:0;top:2px;bottom:2px;width:3px;background:var(--cyan);box-shadow:0 0 8px #27d6ff99}.head-dots{font-weight:700;letter-spacing:4px;color:var(--cyan)}.head-tag{color:var(--muted);font-size:12px}.head-action{border:0;background:none;color:var(--cyan);padding:4px 0 4px 8px}.panel-foot{display:flex;justify-content:space-between;gap:8px;margin-top:auto;padding-top:8px;color:var(--muted);font-size:11px;opacity:.8}.chart-box{min-height:0;flex:1;width:100%}.fleet-body{display:flex;align-items:center;min-height:0;flex:1;gap:10px}.fleet-donut{position:relative;min-width:0;width:53%;height:100%;min-height:120px;max-height:230px}.donut-center{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;align-items:center;pointer-events:none;padding-top:2px}.donut-center b{font:700 clamp(25px,2vw,40px)/1.2 Consolas,monospace;color:#e2f7ff}.donut-center span{font-size:12px;margin-top:5px;color:var(--muted)}.fleet-legend{flex:1;min-width:0;display:flex;flex-direction:column;gap:22px}.fleet-legend>div{display:flex;align-items:center;gap:7px;font-size:clamp(11px,.78vw,15px);white-space:nowrap}.fleet-legend b{margin-left:auto;font:500 17px Consolas,monospace;color:var(--ink)}.dot{display:inline-block;flex:0 0 6px;width:6px;height:6px;border-radius:50%}.dot.cyan{background:var(--cyan);box-shadow:0 0 6px #26d3fa44}.dot.blue{background:#4e9af4}.dot.amber{background:var(--gold)}.mini-legend{display:flex;align-items:center;gap:5px;color:var(--muted);font-size:10px}.mini-legend .dot+ .dot{margin-left:6px}.pressure-list{display:flex;flex-direction:column;justify-content:space-evenly;flex:1;min-height:0;gap:8px}.pressure-row{display:grid;grid-template-columns:38px minmax(0,1fr) 62px;align-items:center;gap:10px;border:0;background:transparent;color:var(--ink);padding:7px 0;text-align:left}.pressure-row:hover,.pressure-row.selected{background:#1c789522}.pressure-row>b{font:400 14px Consolas,monospace}.pressure-row>span{font:12px Consolas,monospace;text-align:right;white-space:nowrap}.pressure-track{height:9px;display:flex;overflow:hidden;border:1px solid #2c739355;background:#10344c}.pressure-track i{background:linear-gradient(90deg,#0571ab,#32dcf8);box-shadow:0 0 9px #32dcf877;transition:width .45s;min-width:0}.pressure-track em{background:linear-gradient(90deg,#d7902c,#ffce6c);opacity:.85;transition:width .45s;min-width:0}
.dispatch-route{display:flex;align-items:center;justify-content:space-between;padding:12px 10px;min-height:64px;border:1px solid #164c7080;background:#07315230;gap:7px}.dispatch-route>span{display:flex;align-items:center;justify-content:center;gap:9px;min-width:0;font-size:14px;white-space:nowrap}.route-pin{width:11px;height:15px;border:2px solid var(--cyan);border-radius:60% 60% 70% 70%;transform:rotate(-12deg);box-shadow:0 0 8px #26d3fa44;flex-shrink:0}.route-pin.gold{border-color:var(--gold)}.route-link{flex:1;min-width:42px;max-width:74px;color:var(--cyan)}.route-link svg{width:100%;height:32px;fill:none;stroke:currentColor;stroke-width:1.5;overflow:visible}.dispatch-facts{display:flex;flex:1;flex-direction:column;justify-content:space-evenly;gap:10px;margin:14px 0 4px;font-size:13px}.dispatch-facts>div{display:grid;grid-template-columns:86px 1fr;gap:10px;align-items:center;min-height:21px}.dispatch-facts dt{color:var(--muted)}.dispatch-facts dd{margin:0;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.status-value{display:flex;align-items:center;justify-content:flex-end;gap:10px;color:var(--cyan)}.status-track{display:block;width:60px;height:6px;background:#153750;border:1px solid #27627e}.status-track b{display:block;width:20%;height:100%;background:var(--cyan);box-shadow:0 0 7px #26d3fa66}.status-track b.ready{width:100%}.preview-empty{display:flex;flex:1;min-height:0;align-items:center;justify-content:center;flex-direction:column;text-align:center;gap:9px;padding:5px}.preview-empty>svg{width:65px;height:48px;stroke:#2e6584;stroke-width:2;fill:none}.preview-empty .preview-trend{stroke:var(--cyan)}.preview-empty>b{font-size:15px;font-weight:400;color:var(--ink)}.preview-empty>span{font-size:11px;color:var(--muted);line-height:1.5}.outline-action,.primary-action{border:1px solid #23769d;background:linear-gradient(180deg,#0a3c5866,#06243844);border-radius:3px;color:#bceeff;padding:9px 14px;transition:.2s}.outline-action:hover{border-color:var(--cyan);background:#0e526e55}.outline-action span{margin-left:10px}.primary-action{background:linear-gradient(180deg,#147b9f,#0a4b6c);border-color:#27acc8;color:white}.preview-summary{display:flex;gap:9px;align-items:center;justify-content:space-between;font-size:12px;padding:4px 0}.preview-summary>span{color:var(--muted)}.preview-summary>b{color:var(--cyan);font-family:Consolas,monospace}.preview-summary i{font-style:normal;color:var(--muted);padding:0 5px}.preview-summary button{border:0;background:none;color:var(--gold);padding:5px 0}.event-list{display:flex;flex:1;min-height:0;flex-direction:column;justify-content:space-evenly;overflow:hidden}.event-row{position:relative;display:grid;grid-template-columns:57px 10px minmax(0,1fr) 8px;gap:10px;align-items:center;min-height:32px;width:100%;border:0;background:transparent;text-align:left;color:var(--ink);padding:7px 0}.event-row+.event-row{border-top:1px solid #22547033}.event-row:hover{background:#14527122}.event-time{color:var(--muted);font-size:11px}.event-node{position:relative;width:6px;height:6px;border-radius:50%;background:var(--cyan);box-shadow:0 0 8px #26d3fa55}.event-node:after{content:"";position:absolute;width:1px;left:2.5px;top:9px;height:30px;background:#1e6e9455}.event-row:last-child .event-node:after{display:none}.event-copy{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px}.event-arrow{color:var(--muted)}.gap-banner{display:flex;align-items:center;gap:6px;margin:2px 0 6px;padding:6px 9px;border:1px solid #b8791f55;background:#b8791f18;font-size:12px;color:#ffd08a}.gap-banner b{font:600 15px Consolas,monospace;color:#ffb44d}.gap-banner em{font-style:normal;font-size:11px;color:var(--muted)}.dual-num{font-size:10px!important;color:var(--muted);text-align:right;white-space:nowrap}.dual-num b{margin:0 3px;color:var(--ink);font-family:Consolas,monospace}.danger-blink{color:#ff6b5e!important;animation:blinkWarn 1.3s infinite}@keyframes blinkWarn{0%,100%{opacity:1}50%{opacity:.35}}.event-row.dispatch .event-node{background:#3e8dff;box-shadow:0 0 8px #3e8dff88}.event-row.dispatch .event-copy{color:#bcd9ff}.event-row.truck_arrive .event-node{background:#39d98a;box-shadow:0 0 8px #39d98a88}.event-row.truck_arrive .event-copy{color:#b8f2d4}.event-row.return .event-node{background:#39d98a}.event-row.rent .event-node{background:#38d9e8}.event-row.geofence .event-node,.event-row.return_rejected .event-node{background:#ef5b5b;box-shadow:0 0 8px #ef5b5b88}.event-row.geofence .event-copy,.event-row.return_rejected .event-copy{color:#ffb3a7}.event-row.alert .event-node{background:var(--gold)}.event-row.alert .event-copy{color:#ffd090}.panel-empty{display:flex;align-items:center;justify-content:center;flex:1;color:var(--muted);font-size:13px}.event-empty{flex-direction:column;gap:11px}.event-empty b{font-weight:400;color:var(--ink)}.event-empty span{font-size:11px}.empty-pulse{width:9px;height:9px;border-radius:50%;background:#2285a2;box-shadow:0 0 0 6px #17647f22,0 0 0 13px #17647f11}
.command-footer{position:absolute;z-index:15;bottom:17px;left:18px;right:18px;height:76px;display:flex;align-items:center;justify-content:space-between;gap:22px;padding:10px 20px;border:1px solid #176088;background:linear-gradient(180deg,rgba(6,34,55,.98),rgba(2,16,30,.97));clip-path:polygon(8px 0,calc(100% - 8px) 0,100% 8px,100% 100%,0 100%,0 8px);box-shadow:inset 0 1px #3abaff22,0 -5px 35px #02101e66}.footer-counters{display:flex;align-items:center;flex:0 0 39%;height:100%}.footer-metric{display:flex;align-items:center;gap:14px;padding:0 28px;flex:1;height:75%;border-right:1px solid #226f8d66}.footer-metric:first-child{padding-left:0}.footer-metric:last-child{border:0}.footer-metric svg{width:34px;height:38px;fill:none;stroke:var(--cyan);stroke-width:2.7;filter:drop-shadow(0 0 5px #0cb5ff33);flex-shrink:0}.footer-metric.warning svg{stroke:#f5a738}.footer-metric>div{display:flex;flex-direction:column;gap:2px}.footer-metric b{font:700 clamp(23px,1.9vw,36px)/1 Consolas,monospace;color:var(--ink)}.footer-metric span{font-size:12px;color:var(--muted);white-space:nowrap}.view-toolbar{display:flex;align-items:center;justify-content:flex-end;gap:9px;min-width:0;flex:1}.view-toolbar button{display:flex;align-items:center;justify-content:center;gap:8px;height:44px;padding:0 16px;border:1px solid #1c5a7d;border-radius:4px;background:linear-gradient(135deg,#08365188,#031527aa);color:#b4d1e4;white-space:nowrap;font-size:13px;box-shadow:inset 0 1px #88d9ff11;transition:.2s}.view-toolbar button:hover{color:#edfcff;border-color:#229ec4;background:#0d405e}.view-toolbar button.active{color:#ddfaff;border-color:#26ccf6;background:linear-gradient(135deg,#08557c88,#032038);box-shadow:inset 0 0 12px #17c7ff33,0 0 9px #17c7ff33}.view-toolbar button.menu-toggle{padding:0 12px}.tool-mark{font-size:18px;color:var(--cyan);line-height:1}.scene-caption{position:absolute;top:93px;left:calc(var(--side) + 43px);z-index:9;color:#9fc4d8;display:flex;gap:10px;align-items:center;font-size:12px;pointer-events:none;opacity:.7}.caption-square{width:5px;height:5px;border:1px solid #36d2ee;transform:rotate(45deg)}.scene-caption small{font-size:10px;color:#648ca6;margin-left:8px}.mode-switch{position:absolute;z-index:12;bottom:110px;left:calc(var(--side) + 42px);display:flex;gap:2px;padding:3px;background:#031627bb;border:1px solid #1b4b66;border-radius:3px}.mode-switch button{border:0;background:none;padding:6px 12px;font-size:11px;color:var(--muted);border-radius:2px}.mode-switch button.active{color:var(--cyan);background:#0b547244}.replay-seek{position:absolute;bottom:111px;right:calc(var(--side) + 42px);z-index:12;display:flex;gap:8px;align-items:center;background:#031627d9;padding:4px 8px;font:11px Consolas,monospace;color:var(--muted);border:1px solid #1b4b66}.replay-seek input{width:135px;height:16px;accent-color:var(--cyan)}.replay-seek select{background:#082539;border:1px solid #1c5677;color:var(--ink)}.record-status{font-size:13px;color:var(--muted);display:flex;gap:10px;align-items:center}.alert-strip{position:absolute;z-index:15;bottom:160px;left:50%;transform:translateX(-50%);display:flex;align-items:center;gap:12px;padding:9px 18px;background:#402719dd;border:1px solid #b4813c66;color:#ffcc7e;font-size:12px;white-space:nowrap}.alert-strip i{height:6px;width:6px;border-radius:50%;background:#ffb64f}
.point-detail{position:absolute;z-index:16;left:50%;bottom:166px;transform:translateX(-50%);width:340px;border:1px solid #277494;background:#061f30f2;padding:18px 20px;box-shadow:0 12px 30px #0006}.point-close{position:absolute;right:8px;top:7px;border:0;background:none;color:var(--muted);font-size:22px}.point-kicker{font-size:10px;color:var(--cyan);letter-spacing:2px}.point-detail h3{font-size:18px;margin:7px 0 18px}.point-detail h3 span{font-size:13px;font-weight:400;color:var(--muted);margin-left:8px}.point-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.point-grid>div{display:flex;flex-direction:column;gap:7px}.point-grid span{font-size:11px;color:var(--muted)}.point-grid b{font:24px Consolas,monospace}.point-track{height:4px;margin:16px 0 12px;background:#12394e}.point-track i{display:block;height:100%;background:var(--cyan)}.point-foot{display:flex;justify-content:space-between;align-items:center;font-size:11px;color:var(--muted)}.point-foot button{border:0;background:none;color:var(--cyan)}.is-low{color:#ff8c82}.is-high{color:var(--gold)}
.dispatch-mask,.menu-mask{position:absolute;z-index:40;inset:0;display:flex;align-items:center;justify-content:center;background:#020b16aa;backdrop-filter:blur(4px)}.dispatch-panel{width:540px;max-width:90vw;padding:26px;border:1px solid #287b9d;background:linear-gradient(135deg,#0a2e45,#05192b);box-shadow:0 25px 80px #0008}.dispatch-head{display:flex;justify-content:space-between;align-items:flex-start}.dispatch-head span{font-size:10px;letter-spacing:2px;color:var(--cyan)}.dispatch-head h3{font-size:23px;margin:6px 0 0;font-weight:500}.dispatch-head>button{border:0;background:none;color:var(--muted);font-size:25px}.dispatch-note,.preview-note{font-size:12px;line-height:1.8;color:var(--muted);margin:16px 0}.dispatch-form{display:grid;grid-template-columns:1.35fr 1fr 1fr;gap:12px}.dispatch-form label{font-size:12px;color:var(--muted)}.dispatch-form select{width:100%;margin-top:8px;height:40px;padding:0 8px;color:var(--ink);background:#062033;border:1px solid #245976;border-radius:3px}.qty-val{color:var(--cyan);font:600 15px Consolas,monospace;margin:0 3px}.dispatch-form input[type=range]{width:100%;margin-top:14px;height:4px;-webkit-appearance:none;background:#17455f;border-radius:2px;border:0;padding:0}.dispatch-form input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:14px;height:14px;border-radius:50%;background:var(--cyan);box-shadow:0 0 8px #26d3fa88;cursor:pointer}.horizon-tabs{display:flex;align-items:center;gap:8px;margin-top:10px;font-size:12px;color:var(--muted)}.horizon-tabs button{border:1px solid #245976;background:#062033;color:var(--muted);padding:4px 10px;border-radius:3px;font-size:12px}.horizon-tabs button.active{border-color:var(--cyan);color:var(--cyan);background:#0b3f57}.ht-sep{margin-left:10px;color:var(--muted)}.dispatch-eta{display:flex;flex-wrap:wrap;gap:16px;margin-top:12px;padding:10px 12px;border:1px solid #164c7080;background:#07315230;font-size:12px;color:var(--muted)}.dispatch-eta b{color:var(--cyan);font-family:Consolas,monospace;margin-left:5px}.dispatch-form input{width:100%;margin-top:8px;height:40px;padding:0 10px;color:var(--ink);background:#062033;border:1px solid #245976;border-radius:3px;font:14px Consolas,monospace}.theme-day .dispatch-form input{background:#f1faff;color:#163c56;border-color:#8fb4c8}.preview-result{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;padding:18px 0 8px}.preview-result>div{display:flex;flex-direction:column;gap:10px}.preview-result span{font-size:11px;color:var(--muted)}.preview-result b.good{color:#3fe0a8}.preview-result b.bad{color:#ff8f7a}.preview-result b{font:20px Consolas,monospace;color:var(--cyan)}.dispatch-actions{display:flex;gap:12px;margin-top:22px}.dispatch-actions>button{flex:1}.dispatch-msg{font-size:13px;color:var(--cyan);margin:15px 0 0}.menu-mask{justify-content:flex-end;padding-right:24px}.menu-panel{width:300px;border:1px solid #29647f;background:#051b2bf7;padding:16px 22px}.menu-head{display:flex;justify-content:space-between;align-items:center;padding:8px 0 14px;border-bottom:1px solid #20516a}.menu-head button{font-size:11px;color:var(--muted);border:0;background:none}.menu-panel>button{display:flex;width:100%;align-items:center;justify-content:space-between;padding:13px 2px;border:0;border-bottom:1px solid #16415a55;background:none;color:var(--ink);text-align:left}.menu-panel>button:hover{color:var(--cyan)}.menu-panel>button i{font-style:normal;color:var(--muted)}.menu-panel>button.logout{color:#efa38e}.empty-state{position:absolute;z-index:11;left:50%;top:45%;transform:translate(-50%,-50%);text-align:center;padding:25px;background:#071e30ef;border:1px solid #215575}.empty-state h2{font-size:20px}.empty-state p{font-size:13px;color:var(--muted)}
.sim-badge{position:absolute;top:88px;left:50%;transform:translateX(-50%);z-index:13;display:flex;align-items:center;gap:8px;padding:6px 16px;border:1px solid #a06bff77;background:#3a1f6eaa;color:#e3d4ff;font-size:12px;letter-spacing:1px;border-radius:2px}.sim-badge i{width:6px;height:6px;border-radius:50%;background:#b98cff;box-shadow:0 0 8px #b98cff;animation:blinkWarn 1.6s infinite}.theme-day .sim-badge{background:#efe4ffdd;color:#4b2a86;border-color:#b9a0e0}.intro-overlay{position:absolute;inset:0;z-index:30;display:flex;align-items:center;justify-content:center;background:radial-gradient(ellipse,rgba(3,23,40,.84),rgba(2,10,20,.96));animation:intro-fade .8s 3.8s both}.intro-copy{text-align:center}.intro-copy>span{font-size:13px;color:var(--cyan);letter-spacing:8px}.intro-copy h1{font-size:clamp(28px,3.5vw,58px);letter-spacing:5px;font-weight:500;margin:25px 0}.intro-copy p{font-size:14px;color:var(--muted);letter-spacing:6px}.intro-skip{position:absolute;right:35px;bottom:35px;padding:9px 18px;border:1px solid #2a7998;background:none;color:var(--muted)}.loading-mask{position:absolute;z-index:35;inset:0;display:flex;align-items:center;justify-content:center;gap:12px;background:#061422cc;font-size:14px;color:var(--muted)}.loading-mask i{width:16px;height:16px;border-radius:50%;border:2px solid #28627c;border-top-color:var(--cyan);animation:spin 1s linear infinite}.fade-enter-active,.fade-leave-active{transition:opacity .2s}.fade-enter-from,.fade-leave-to{opacity:0}@keyframes spin{to{transform:rotate(360deg)}}@keyframes intro-fade{to{opacity:0;pointer-events:none}}
.theme-day{--ink:#12334a;--muted:#527486;--cyan:#078cb9;--panel:rgba(230,243,250,.95);--line:#8fb9cf;--gold:#bd7a14}.theme-day .panel-block{background:linear-gradient(125deg,#f0faffee,#dcecf6ee);box-shadow:0 8px 20px #244c6222}.theme-day .twin-header{background:linear-gradient(180deg,#dcebf5ee,#d4e8f499,transparent)}.theme-day .banner-center{background:#dceff5bb}.theme-day .banner-center h1{color:#17425d;text-shadow:none}.theme-day .command-footer{background:linear-gradient(180deg,#e8f7fcf7,#d7eaf5f5);border-color:#80b4cc}.theme-day .view-toolbar button{background:#e7f5fa;color:#315c75;border-color:#8cb9cc}.theme-day .view-toolbar button.active{color:#005d83;background:#c1e8f6;border-color:#1493b7}.theme-day .donut-center b{color:#13405b}.theme-day .dispatch-route{background:#a0d0e326;border-color:#a5c9db}.theme-day .pressure-track{background:#d2e3ed}.theme-day .outline-action{background:#cdebf555;color:#0c678d}.theme-day .mode-switch,.theme-day .replay-seek{background:#deeff7ec;border-color:#91bacb}.theme-day .point-detail,.theme-day .dispatch-panel,.theme-day .menu-panel{background:#eaf6fcf7;border-color:#6ea8c3}.theme-day .dispatch-form select{background:#f1faff;color:#163c56;border-color:#8fb4c8}.theme-day .scene-caption{color:#17496a}.theme-day .header-clock b{color:#16425c}.theme-day .intro-overlay{background:#d7edf6e8}.theme-day .intro-copy h1{color:#153e58}
@media(min-width:2300px){.side-panel{top:104px;bottom:125px;gap:22px}.command-footer{height:88px;bottom:18px}.block-head{flex-basis:49px}.panel-block{padding-left:22px;padding-right:22px}.fleet-legend>div{font-size:16px}.event-copy,.dispatch-facts{font-size:15px}.event-time,.panel-foot{font-size:13px}.view-toolbar button{height:50px;padding:0 21px;font-size:15px}.pressure-row{padding:12px 0}.mode-switch,.replay-seek{bottom:125px}}
@media(max-width:1450px){.twin-root{--side:clamp(238px,20vw,285px)}.side-panel{gap:12px;top:78px;bottom:100px}.left-panel{left:12px}.right-panel{right:12px}.panel-block{padding:0 12px 7px}.block-head{flex-basis:35px;margin-bottom:5px}.block-head h2{font-size:15px}.fleet-legend{gap:17px}.fleet-legend>div{font-size:10px;gap:5px}.fleet-legend b{font-size:14px}.fleet-body{gap:4px}.dispatch-route{padding:9px 6px;min-height:53px}.dispatch-route>span{font-size:12px;gap:5px}.dispatch-facts{font-size:11px;gap:6px;margin-top:10px}.dispatch-facts>div{grid-template-columns:65px 1fr}.status-track{width:35px}.status-value{gap:6px}.event-row{grid-template-columns:46px 6px minmax(0,1fr) 6px;gap:7px;min-height:26px}.event-copy,.event-time{font-size:10px}.panel-foot{font-size:9px}.command-footer{height:68px;left:12px;right:12px;bottom:13px;padding:8px 13px;gap:10px}.footer-metric{padding:0 16px;gap:10px}.footer-metric svg{width:26px;height:30px}.footer-metric span{font-size:10px}.view-toolbar{gap:6px}.view-toolbar button{font-size:11px;padding:0 10px;height:39px;gap:5px}.tool-mark{font-size:15px}.header-meta{font-size:10px;left:20px}.header-clock{right:20px;font-size:10px;gap:8px;flex-direction:column;align-items:flex-end;top:17px}.twin-header{height:72px}.mode-switch,.replay-seek{bottom:99px}.scene-caption{top:82px;left:calc(var(--side) + 29px)}.pressure-row{grid-template-columns:30px minmax(0,1fr) 49px;gap:6px;padding:5px 0}.pressure-row>b{font-size:12px}.pressure-row>span{font-size:10px}.preview-empty>span{font-size:10px}.preview-empty svg{height:35px}.preview-empty{gap:6px}.preview-empty .outline-action{font-size:11px;padding:7px 10px}}
@media(max-height:800px){.side-panel{top:76px;bottom:94px;gap:10px}.block-head{flex-basis:33px;margin-bottom:3px}.panel-foot{padding-top:4px}.fleet-donut{min-height:90px}.fleet-legend{gap:15px}.pressure-list{gap:4px}.pressure-row{padding:3px 0}.dispatch-route{min-height:45px;padding:6px 8px}.dispatch-facts{gap:5px;margin-top:8px;font-size:11px}.preview-empty svg{display:none}.preview-empty{gap:6px}.event-row{padding:4px 0;min-height:25px}.command-footer{height:65px;bottom:12px}.mode-switch,.replay-seek{bottom:93px}.scene-caption{top:80px}.preview-summary{font-size:10px}.point-detail{bottom:145px}}
@media(max-width:1100px){.twin-root{--side:220px}.header-meta{display:none}.header-clock{display:none}.banner-center h1{font-size:24px}.banner-wing{width:25px}.footer-counters{flex-basis:36%}.footer-metric{padding:0 9px;gap:7px}.footer-metric svg{width:23px}.footer-metric b{font-size:22px}.view-toolbar{gap:4px}.view-toolbar button{padding:0 8px;font-size:10px}.view-toolbar .tool-mark{display:none}.scene-caption small{display:none}.pressure-row{grid-template-columns:29px minmax(0,1fr) 45px}.mode-switch{left:calc(var(--side) + 26px)}.replay-seek input{width:65px}.replay-seek{right:calc(var(--side) + 25px)}}
@media(max-width:820px){.twin-root{--side:190px;min-height:600px}.side-panel{width:190px}.panel-block{padding-left:9px;padding-right:9px}.fleet-body{flex-direction:column}.fleet-donut{width:100%;height:60%;min-height:70px}.fleet-legend{width:100%;gap:4px;justify-content:center;flex:none}.fleet-legend>div{font-size:9px}.donut-center b{font-size:24px}.donut-center span{font-size:9px}.footer-metric svg{display:none}.footer-counters{flex:0 0 30%}.footer-metric{padding:0 8px}.view-toolbar button{padding:0 5px;font-size:9px}.view-toolbar{gap:3px}.mini-legend{font-size:8px}.panel-foot{font-size:8px}.scene-caption{display:none}.pressure-row{grid-template-columns:26px minmax(0,1fr) 42px;gap:4px}.pressure-row>span{font-size:9px}.header-meta,.header-clock{display:none}.banner-center h1{font-size:22px}.status-track{display:none}.mode-switch{bottom:94px}.replay-seek{bottom:130px;left:calc(var(--side) + 26px);right:auto}.point-detail{width:290px}}
@media(prefers-reduced-motion:reduce){.twin-root *{animation:none!important;transition:none!important}}

.panel-block{background:linear-gradient(125deg,rgba(17,57,81,.95),rgba(9,34,52,.95));box-shadow:inset 0 1px 0 #6392a51a,0 8px 22px #0002}
.demand-totals{display:flex;align-items:baseline;justify-content:space-between;gap:7px;font-size:11px;color:var(--muted);margin:1px 0 8px}.demand-totals b{font:500 19px Consolas,monospace;color:var(--cyan);margin-left:4px}.gold{color:var(--gold)!important}.demand-totals small{font-size:9px;white-space:nowrap}.demand-row{grid-template-columns:36px minmax(0,1fr) 80px;padding:4px 0}.demand-row>span{font-size:11px}.dual-track{display:flex;flex-direction:column;gap:4px;min-width:0}.dual-track i,.dual-track em{display:block;height:5px;min-width:0;transition:width .35s}.dual-track i{background:var(--cyan)}.dual-track em{background:var(--gold);opacity:.9}.pressure-list{gap:4px}
.trend-kpis{display:grid;grid-template-columns:1fr 1fr 1.15fr;gap:8px;margin:0 0 8px}.trend-kpis>div{display:flex;flex-direction:column;gap:5px;padding-left:8px;border-left:2px solid #2e748c55}.trend-kpis span{font-size:10px;color:var(--muted);white-space:nowrap}.trend-kpis b{font:500 23px Consolas,monospace;color:var(--cyan)}.trend-block .trend-chart{min-height:70px}.event-tabs{display:flex;gap:5px}.event-tabs button,.heat-tabs button{font-size:10px;border:0;background:none;color:var(--muted);padding:4px}.event-tabs button.active{color:var(--cyan);border-bottom:1px solid var(--cyan)}
.heat-legend{position:absolute;z-index:11;right:calc(var(--side) + 38px);bottom:157px;width:215px;padding:11px 13px;background:rgba(9,35,51,.94);border:1px solid #38677d99;border-radius:4px;box-shadow:0 7px 22px #0002}.heat-tabs{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:9px}.heat-tabs button{font-size:12px;padding:0 0 5px}.heat-tabs button.active{color:var(--ink);border-bottom:2px solid var(--cyan)}.heat-tabs small{font-size:10px;color:var(--muted)}.heat-gradient{height:7px;background:linear-gradient(90deg,#2ba4e5 0%,#2ba4e5 32%,#f5b83a 34%,#f5b83a 65%,#f8523e 67%,#f8523e 100%);border-radius:2px}.heat-scale{display:flex;justify-content:space-between;margin-top:4px;font:11px Consolas,monospace;color:var(--ink)}.heat-legend p{font-size:10px;color:var(--muted);line-height:1.5;margin:8px 0 0}.follow-hint{position:absolute;left:50%;bottom:155px;transform:translateX(-50%);z-index:11;background:#0a2c40eb;border:1px solid #b69454;padding:9px 17px;color:#ffcc7a;white-space:nowrap;font-size:13px}.follow-hint span{color:#a3bdcd;margin-left:16px;font-size:11px}.mission-toast{position:absolute;z-index:42;top:105px;left:50%;transform:translateX(-50%);background:#12445aed;border:1px solid #399db6;padding:12px 22px;color:#d9f6ff;font-size:13px;border-radius:3px}.point-demand{display:flex;justify-content:space-between;font-size:11px;color:var(--muted);margin:12px 0}.point-demand b{color:var(--gold);margin-left:7px}.route-caption{padding-top:5px}.status-track b{transition:width .2s}.view-toolbar button:disabled{cursor:default}
.theme-day .heat-legend,.theme-day .follow-hint{background:#e9f5fbea;border-color:#8db7cd}.theme-day .follow-hint{color:#955f0a}.theme-day .follow-hint span{color:#537488}.theme-day .mission-toast{background:#edfaff;color:#15516d;border-color:#4f9db5}
@media(max-width:1450px){.demand-totals{gap:3px;font-size:9px;margin-bottom:4px}.demand-totals b{font-size:15px;margin-left:2px}.demand-totals small{display:none}.demand-row{grid-template-columns:29px minmax(0,1fr) 64px}.demand-row>span{font-size:10px}.trend-kpis{gap:3px;margin-bottom:5px}.trend-kpis>div{padding-left:5px}.trend-kpis span{font-size:9px}.trend-kpis b{font-size:19px}.heat-legend{right:calc(var(--side) + 28px);bottom:136px;width:195px;padding:9px 11px}.follow-hint{bottom:137px;font-size:11px;padding:8px 12px}.follow-hint span{display:none}.event-tabs{gap:2px}.event-tabs button{font-size:9px;padding:3px}.point-demand{font-size:10px}.mission-toast{top:83px}}
@media(max-height:800px){.demand-totals{margin-bottom:3px}.demand-row{padding:2px 0}.dual-track{gap:3px}.dual-track i,.dual-track em{height:4px}.heat-legend{bottom:125px;padding:8px 10px}.follow-hint{bottom:126px}.trend-kpis b{font-size:18px}.trend-kpis span{font-size:9px}.trend-kpis{margin-bottom:3px}.dispatch-facts{margin-bottom:0}.route-caption{font-size:9px}}
@media(max-width:1100px){.heat-legend{width:170px;right:calc(var(--side) + 24px);bottom:139px}.heat-tabs button{font-size:10px}.heat-tabs small{font-size:8px}.follow-hint{bottom:248px}.demand-row{grid-template-columns:27px minmax(0,1fr) 63px}}
@media(max-height:800px){.pressure-list{gap:2px}.demand-row{padding:1px 0;line-height:1.15}.demand-row>b,.demand-row>span{line-height:1.15}.demand-totals{line-height:1.15}.panel-foot{flex-shrink:0;line-height:1.2}.dispatch-facts{margin-top:5px;gap:3px;min-height:0}.dispatch-facts>div{min-height:16px;line-height:1.15}.route-caption{padding-top:3px}}
@media(max-height:800px){.event-row{min-height:20px;padding:3px 0;line-height:1.2}.event-copy,.event-time{line-height:1.2}}

</style>
