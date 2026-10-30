<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">实时推演</h1>
        <div class="page-sub">服务端逐帧推送 · 可暂停 / 单步 / 倍速</div>
      </div>
      <div class="row">
        <span class="tag" :class="wsReady ? 'tag-green' : 'tag-amber'">{{ wsReady ? '已连接' : '本地回放' }}</span>
        <button class="btn btn-primary" :disabled="loading" @click="run">应用并运行</button>
      </div>
    </div>

    <div v-if="error" class="empty">{{ error }}</div>

    <div class="sim-grid">
      <div class="col-left">
        <Panel title="推演参数">
          <div class="param-grid">
            <div>
              <label class="field">调度策略</label>
              <select v-model="policy" class="select w-full">
                <option value="ppo">PPO 策略</option>
                <option value="greedy">约束贪心</option>
                <option value="noop">不调度</option>
              </select>
            </div>
            <div>
              <label class="field">随机种子</label>
              <input v-model.number="seed" class="input w-full" type="number" />
            </div>
            <div class="param-row">
              <label>移步衰减 λ</label>
              <input v-model.number="lambdaValue" class="input" type="number" step="0.01" />
            </div>
            <div class="param-row">
              <label>时间价值 VOT</label>
              <input v-model.number="vot" class="input" type="number" step="0.05" />
            </div>
            <div class="param-row">
              <label>单次用户占比 γ</label>
              <input v-model.number="gamma" class="input" type="number" step="0.05" />
            </div>
            <div class="param-row">
              <label>可用率 ρ</label>
              <input v-model.number="rho" class="input" type="number" step="0.05" />
            </div>
          </div>
        </Panel>

        <Panel title="当前动作" class="mt-16">
          <div class="action-main">{{ currentAction }}</div>
          <div class="action-sub">时刻 {{ currentTime }} · 第 {{ currentStep }} 步</div>
          <div class="action-sub">奖励：{{ rewardText }}</div>
        </Panel>
      </div>

      <div class="col-center">
        <div v-if="loading" class="empty">正在生成调度推演…</div>
        <template v-else>
          <MapPanel
            :stations="stations"
            :step-data="stepData"
            :truck-path="truckPath"
            :selected="selected"
            height="540px"
            @select="selected = $event"
          />
          <Panel class="mt-16" body-padding="14px 20px">
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
          </Panel>
        </template>
      </div>

      <div class="col-right">
        <div class="kpi-mini">
          <KpiCard label="服务率" :value="pct(summary.service_rate)" color="var(--success)" />
          <KpiCard label="总短缺" :value="num(summary.total_shortage, 1)" color="var(--danger)" />
          <KpiCard label="单位成本" :value="num(summary.unit_service_cost, 3)" color="var(--accent-2)" />
          <KpiCard label="搬运趟次" :value="num(summary.truck_trips, 0)" />
        </div>

        <Panel title="事件日志" class="mt-16">
          <div class="events">
            <div v-for="(e, i) in events" :key="i" class="event">
              <span class="event-time mono">{{ e.time }}</span>
              <span class="event-text">{{ e.label }}</span>
            </div>
            <div v-if="!events.length" class="empty">当前时段暂无调度动作</div>
          </div>
        </Panel>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/client'
import Panel from '../components/Panel.vue'
import KpiCard from '../components/KpiCard.vue'
import MapPanel from '../components/MapPanel.vue'
import Timeline from '../components/Timeline.vue'

const route = useRoute()
const loading = ref(false)
const error = ref('')
const policy = ref('ppo')
const seed = ref(101)
const lambdaValue = ref(0.15)
const vot = ref(0.5)
const gamma = ref(0.35)
const rho = ref(0.85)
const runId = ref(null)
const stations = ref([])
const steps = ref([])
const summary = ref({})
const currentStep = ref(0)
const playing = ref(false)
const speed = ref(1)
const selected = ref('')
const wsReady = ref(false)
const scenarioId = ref(route.query.scenario ? Number(route.query.scenario) : null)
let ws = null
let timer = null

const stepData = computed(() => steps.value[currentStep.value] || null)
const maxStep = computed(() => Math.max(steps.value.length - 1, 0))
const currentTime = computed(() => (stepData.value && stepData.value.time) || '06:30')
const endTime = computed(() => (steps.value.length ? steps.value[steps.value.length - 1].time : '23:30'))
const currentAction = computed(() => (stepData.value && stepData.value.action && stepData.value.action.label) || '等待')
const rewardText = computed(() => {
  const r = stepData.value && stepData.value.reward
  if (!r) return '—'
  return Object.entries(r).filter(([k]) => k !== 'total').map(([k, v]) => `${k} ${Number(v).toFixed(2)}`).join(' · ')
})

const truckPath = computed(() => {
  const path = []
  for (let i = 0; i <= currentStep.value; i += 1) {
    const t = steps.value[i] && steps.value[i].truck
    if (t && (path.length === 0 || path[path.length - 1] !== t.station)) path.push(t.station)
  }
  return path
})

const events = computed(() => {
  const list = []
  for (let i = currentStep.value; i >= 0 && list.length < 8; i -= 1) {
    const s = steps.value[i]
    if (s && s.action && s.action.mode !== 0 && s.action.label) {
      list.push({ time: s.time, label: s.action.label })
    }
  }
  return list
})

function pct(v) { return v == null ? '—' : `${(Number(v) * 100).toFixed(2)}%` }
function num(v, d = 1) { return v == null ? '—' : Number(v).toFixed(d) }

function stopTimer() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

function startLocal() {
  stopTimer()
  timer = setInterval(() => {
    if (currentStep.value >= maxStep.value) {
      playing.value = false
      stopTimer()
      return
    }
    currentStep.value += 1
  }, 1000 / Math.max(speed.value, 0.1))
}

function connectWs() {
  if (!runId.value) return
  if (ws) {
    try { ws.close() } catch (e) { /* noop */ }
  }
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const token = encodeURIComponent(localStorage.getItem('token') || '')
  ws = new WebSocket(`${proto}://${location.host}/ws/simulations/${runId.value}?token=${token}`)
  ws.onopen = () => { wsReady.value = true }
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data)
    if (msg.type === 'state') {
      currentStep.value = msg.payload.step
      playing.value = !!msg.payload.playing
    } else if (msg.type === 'done') {
      playing.value = false
    }
  }
  ws.onerror = () => { wsReady.value = false }
  ws.onclose = () => { wsReady.value = false }
}

function send(type, payload) {
  if (ws && wsReady.value && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type, payload }))
    return true
  }
  return false
}

async function run() {
  loading.value = true
  error.value = ''
  playing.value = false
  stopTimer()
  try {
    const { data } = await api.post('/simulations', {
      policy: policy.value,
      seed: Number(seed.value),
      scenario_id: scenarioId.value || null,
      overrides: {
        lambda_per_min: Number(lambdaValue.value),
        vot_yuan_per_min: Number(vot.value),
        gamma_single_ride: Number(gamma.value),
        rho_soc: Number(rho.value)
      }
    })
    runId.value = data.run_id
    stations.value = data.stations
    steps.value = data.steps
    summary.value = data.summary
    currentStep.value = 0
    selected.value = data.stations.length ? data.stations[0].id : ''
    connectWs()
  } catch (e) {
    error.value = (e.response && e.response.data && e.response.data.detail) || '运行失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function togglePlay() {
  if (playing.value) {
    playing.value = false
    stopTimer()
    send('pause')
  } else {
    if (currentStep.value >= maxStep.value) currentStep.value = 0
    playing.value = true
    if (!send('start')) startLocal()
  }
}

function stepBy(n) {
  playing.value = false
  stopTimer()
  if (!send('step', { n })) {
    currentStep.value = Math.min(Math.max(currentStep.value + n, 0), maxStep.value)
  }
}

function onSeek(v) {
  playing.value = false
  stopTimer()
  if (!send('seek', { step: Number(v) })) currentStep.value = Number(v)
}

function changeSpeed(v) {
  speed.value = v
  if (send('speed', { speed: v }) && playing.value) {
    send('pause')
    send('start')
  } else if (playing.value) {
    startLocal()
  }
}

async function loadStations() {
  try {
    const { data } = await api.get('/stations')
    const list = (data || []).filter((s) => s.func !== 'nopark')
    if (!stations.value.length) stations.value = list
  } catch (e) {
    /* 点位读取失败时保留空状态，不影响后续手动运行 */
  }
}

onMounted(async () => {
  await loadStations()
  if (scenarioId.value) run()
})

onBeforeUnmount(() => {
  stopTimer()
  if (ws) {
    try { ws.close() } catch (e) { /* noop */ }
  }
})
</script>

<style scoped>
.sim-grid {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr) 360px;
  gap: 16px;
  align-items: start;
}

.col-left, .col-center, .col-right { min-width: 0; }

.param-grid { display: grid; gap: 14px; }

.param-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.param-row label { font-size: 15px; color: var(--text-2); }
.param-row .input { width: 120px; }

.kpi-mini { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }

.action-main { font-size: 26px; font-weight: 500; line-height: 1.4; }
.action-sub { font-size: 15px; color: var(--text-2); margin-top: 8px; }

.events { display: grid; gap: 10px; max-height: 320px; overflow: auto; }
.event { display: flex; gap: 10px; font-size: 14px; }
.event-time { color: var(--accent-2); min-width: 48px; }
.event-text { color: var(--text); }
</style>
