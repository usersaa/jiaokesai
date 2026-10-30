import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import api from '../api/client'

const MAX_EVENTS = 60

export const useLiveStore = defineStore('live', () => {
  const connected = ref(false)
  const running = ref(false)
  const speed = ref(1)
  const time = ref('06:30')
  const minute = ref(0)
  const inventory = ref({})
  const bikes = ref([])
  const stats = ref({})
  const events = ref([])
  const source = ref(null)
  const error = ref('')
  const truck = ref(null)
  const gen = ref(0)

  let socket = null
  let retryTimer = null
  let retryMs = 1000

  const inStation = computed(() => Number(stats.value.in_station || 0))
  const riding = computed(() => Number(stats.value.riding || 0))
  const misplaced = computed(() => Number(stats.value.misplaced || 0))
  const alerts = computed(() => events.value.filter((e) => e.alert).slice(0, 6))

  function wsUrl() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const token = localStorage.getItem('token') || ''
    return `${proto}://${location.host}/ws/live?token=${encodeURIComponent(token)}`
  }

  function scheduleRetry() {
    if (retryTimer) return
    retryTimer = setTimeout(() => {
      retryTimer = null
      retryMs = Math.min(retryMs * 1.6, 8000)
      connect()
    }, retryMs)
  }

  function connect() {
    if (socket && (socket.readyState === 0 || socket.readyState === 1)) return
    try {
      socket = new WebSocket(wsUrl())
    } catch (e) {
      scheduleRetry()
      return
    }
    socket.onopen = () => {
      connected.value = true
      error.value = ''
      retryMs = 1000
      socket.send(JSON.stringify({ type: 'snapshot' }))
    }
    socket.onclose = () => {
      connected.value = false
      scheduleRetry()
    }
    socket.onerror = () => { connected.value = false }
    socket.onmessage = (raw) => {
      let msg = null
      try { msg = JSON.parse(raw.data) } catch (e) { return }
      handle(msg)
    }
  }

  function handle(msg) {
    const payload = msg.payload
    if (msg.type === 'snapshot') {
      if (!payload) return
      gen.value += 1
      time.value = payload.t
      minute.value = payload.minute
      inventory.value = payload.inventory || {}
      bikes.value = payload.bikes || []
      stats.value = payload.stats || {}
      truck.value = payload.truck || null
      source.value = payload.source || null
      if (payload.events && payload.events.length) events.value = payload.events.slice(0, MAX_EVENTS)
      return
    }
    if (msg.type === 'tick') {
      time.value = payload.t
      minute.value = payload.minute
      inventory.value = payload.inventory || {}
      bikes.value = payload.bikes || []
      stats.value = payload.stats || {}
      if (payload.truck) truck.value = payload.truck
      return
    }
    if (msg.type === 'events') {
      pushEvents(payload || [])
      return
    }
    if (msg.type === 'event') {
      pushEvents([payload])
      return
    }
    if (msg.type === 'status') {
      running.value = Boolean(payload && payload.running)
      if (payload && payload.speed) speed.value = payload.speed
      return
    }
    if (msg.type === 'error') {
      error.value = (payload && payload.message) || '实时流异常'
    }
  }

  function pushEvents(list) {
    if (!list.length) return
    const fresh = [...list].reverse()
    events.value = [...fresh, ...events.value].slice(0, MAX_EVENTS)
  }

  async function start(value = 1, startMinute = null) {
    error.value = ''
    try {
      const body = { speed: value }
      if (startMinute != null) body.start_minute = startMinute
      const { data } = await api.post('/live/start', body)
      if (data && data.snapshot) handle({ type: 'snapshot', payload: data.snapshot })
      running.value = true
    } catch (e) {
      error.value = (e.response && e.response.data && e.response.data.detail) || '实时流启动失败'
    }
  }

  async function pause() {
    await api.post('/live/pause')
    running.value = false
  }

  async function resume() {
    await api.post('/live/resume')
    running.value = true
  }

  async function stop() {
    await api.post('/live/stop')
    running.value = false
    inventory.value = {}
    bikes.value = []
    events.value = []
    stats.value = {}
  }

  async function setSpeed(value) {
    speed.value = value
    await api.post('/live/speed', { value })
  }

  async function dispatch(fromId, toId, qty) {
    const { data } = await api.post('/live/dispatch', { from_id: fromId, to_id: toId, qty })
    return data
  }

  async function preview(fromId, toId, qty, horizonMin = 60, stress = 1) {
    const { data } = await api.post('/live/preview', {
      from_id: fromId, to_id: toId, qty, horizon_min: horizonMin, stress
    })
    return data
  }

  function disconnect() {
    if (retryTimer) { clearTimeout(retryTimer); retryTimer = null }
    if (socket) { try { socket.close() } catch (e) { /* ignore */ } }
    socket = null
    connected.value = false
  }

  return {
    connected, running, speed, time, minute, inventory, bikes, stats, events, source, error, gen, truck,
    inStation, riding, misplaced, alerts,
    connect, disconnect, start, pause, resume, stop, setSpeed, dispatch, preview
  }
})
