<template>
  <div class="map-wrap" :style="{ height }">
    <div ref="el" class="map" :class="{ 'is-dense': stations.length > 30 }"></div>
    <div v-if="loading && !error" class="map-state">
      <span class="loader-line"></span>
      <span>正在连接校园地图</span>
    </div>
    <div v-if="error" class="map-state map-error">
      <strong>地图暂时无法显示</strong>
      <span>{{ error }}</span>
      <button class="map-retry" @click="reload">重新加载</button>
    </div>
    <div v-if="!loading && !error && showLegend" class="legend">
      <span><i class="dot red"></i>库存偏低</span>
      <span><i class="dot blue"></i>正常</span>
      <span><i class="dot amber"></i>库存偏高</span>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  CAMPUS_BOUNDARY,
  CAMPUS_CENTER,
  CAMPUS_MASK_OUTER,
  CAMPUS_ZOOM,
  LANDMARKS
} from '../config/map'

const props = defineProps({
  stations: { type: Array, default: () => [] },
  stepData: { type: Object, default: null },
  truckPath: { type: Array, default: () => [] },
  selected: { type: String, default: '' },
  height: { type: String, default: '100%' },
  viewMode: { type: String, default: '2D' },
  satellite: { type: Boolean, default: false },
  editMode: { type: Boolean, default: false },
  showLegend: { type: Boolean, default: true },
  showLandmarks: { type: Boolean, default: true },
  showMask: { type: Boolean, default: false },
  introMode: { type: Boolean, default: false },
  center: { type: Array, default: () => CAMPUS_CENTER },
  boundary: { type: Array, default: () => CAMPUS_BOUNDARY },
  boundaryIds: { type: Array, default: () => [] }
})

const emit = defineEmits(['select', 'map-click', 'ready', 'error'])
const el = ref(null)
const error = ref('')
const loading = ref(true)
let map = null
let amap = null
let markers = {}
let landmarkMarkers = []
let truckMarker = null
let routeLine = null
let routeGlow = null
let campusMask = null
let campusOutline = null
let satelliteLayer = null
let loaderPromise = null
let mounted = false
let loadTimer = null

function waitLoader() {
  if (window.AMapLoader) return Promise.resolve(true)
  return new Promise((resolve) => {
    let n = 0
    const timer = setInterval(() => {
      n += 1
      if (window.AMapLoader) {
        clearInterval(timer)
        resolve(true)
      } else if (n > 100) {
        clearInterval(timer)
        resolve(false)
      }
    }, 100)
  })
}

async function loadAmap() {
  if (amap) return amap
  if (loaderPromise) return loaderPromise
  loaderPromise = (async () => {
    const ok = await waitLoader()
    if (!ok) throw new Error('地图组件连接超时')
    return window.AMapLoader.load({
      key: 'c747dded701673039c2f37176a2b47c9',
      version: '2.0',
      plugins: ['AMap.Scale', 'AMap.ToolBar']
    })
  })()
  try {
    amap = await loaderPromise
    return amap
  } catch (e) {
    loaderPromise = null
    throw e
  }
}

function clearBusinessLayers() {
  Object.values(markers).forEach((m) => m.setMap(null))
  markers = {}
  landmarkMarkers.forEach((m) => m.setMap(null))
  landmarkMarkers = []
  if (truckMarker) truckMarker.setMap(null)
  if (routeLine) routeLine.setMap(null)
  if (routeGlow) routeGlow.setMap(null)
  if (campusMask) campusMask.setMap(null)
  if (campusOutline) campusOutline.setMap(null)
  truckMarker = null
  routeLine = null
  routeGlow = null
  campusMask = null
  campusOutline = null
}

function currentView() {
  if (!map) return { center: props.center || CAMPUS_CENTER, zoom: CAMPUS_ZOOM }
  try {
    const c = map.getCenter()
    return { center: [c.getLng(), c.getLat()], zoom: map.getZoom() }
  } catch (e) {
    return { center: props.center || CAMPUS_CENTER, zoom: CAMPUS_ZOOM }
  }
}

async function buildMap(preserve = false) {
  if (!mounted || !el.value) return
  loading.value = true
  error.value = ''
  const view = preserve ? currentView() : { center: props.center || CAMPUS_CENTER, zoom: CAMPUS_ZOOM }
  if (map) {
    clearBusinessLayers()
    map.destroy()
    map = null
  }
  try {
    const AMap = await loadAmap()
    if (!mounted || !el.value) return
    map = new AMap.Map(el.value, {
      viewMode: props.viewMode,
      pitch: props.viewMode === '3D' ? 48 : 0,
      rotation: props.viewMode === '3D' ? -8 : 0,
      zoom: view.zoom,
      center: view.center,
      mapStyle: 'amap://styles/normal',
      resizeEnable: true,
      zooms: [14, 20],
      features: ['bg', 'road', 'building', 'point'],
      showLabel: true,
      showBuildingBlock: true,
      buildingColor: '#12304a',
      wallColor: '#173b58',
      roofColor: '#1b4666',
      WebGLParams: { antialias: true }
    })
    map.addControl(new AMap.Scale({ position: { bottom: '16px', left: '16px' } }))
    if (props.showMask) applyLimitBounds()
    map.on('click', (e) => {
      if (!props.editMode) return
      emit('map-click', {
        lng: Number(e.lnglat.getLng().toFixed(6)),
        lat: Number(e.lnglat.getLat().toFixed(6))
      })
    })
    let firstComplete = true
    map.on('complete', () => {
      if (firstComplete) {
        firstComplete = false
        // 容器尺寸确定后再校正一次视野，避免初始化时按 0 尺寸取到最小缩放
        try { map.setZoomAndCenter(view.zoom, view.center) } catch (e) { /* ignore */ }
      }
      loading.value = false
      emit('ready')
    })
    map.on('zoomend', toggleLandmarkVisibility)
    applyBaseLayer()
    renderCampusMask(AMap)
    renderLandmarks()
    renderMarkers(false)
    update()
    if (loadTimer) clearTimeout(loadTimer)
    loadTimer = setTimeout(() => { loading.value = false }, 8000)
  } catch (e) {
    loading.value = false
    error.value = '请检查网络连接与地图服务配置'
    emit('error', e)
    console.error('[CampusMap]', e)
  }
}

function applyBaseLayer() {
  if (!map || !amap) return
  if (props.satellite && props.viewMode === '2D') {
    satelliteLayer = new amap.TileLayer.Satellite()
    map.setLayers([satelliteLayer])
  } else {
    map.setMapStyle('amap://styles/normal')
  }
}

function stationInventory() {
  return (props.stepData && props.stepData.inventory) || props.stations.map((s) => s.init_bikes)
}

function activeStationId() {
  const a = props.stepData && props.stepData.action
  if (!a || !a.mode) return ''
  return (props.stations[a.station] || {}).id || ''
}

function markerHtml(s, n, index = 0) {
  const ratio = s.capacity ? n / s.capacity : 0
  const status = ratio < 0.2 ? 'low' : ratio > 0.8 ? 'high' : 'normal'
  const classes = [
    'station-marker',
    `is-${status}`,
    props.selected === s.id ? 'is-selected' : '',
    activeStationId() === s.id ? 'is-active' : '',
    props.introMode ? 'intro-enter' : ''
  ].filter(Boolean).join(' ')
  return `<div class="station-pin ${classes}" style="--delay:${index * 90}ms">
    <div class="station-orbit"></div>
    <div class="station-core">${Math.round(n)}</div>
    <div class="station-label"><b>${s.id}</b><span>${escapeHtml(s.name || '')}</span></div>
  </div>`
}

function currentBoundary() {
  return props.boundary && props.boundary.length >= 3 ? props.boundary : CAMPUS_BOUNDARY
}

function applyLimitBounds() {
  if (!map || !amap) return
  const points = currentBoundary()
  const lngs = points.map((p) => Number(p[0]))
  const lats = points.map((p) => Number(p[1]))
  const padLng = 0.0012
  const padLat = 0.0010
  map.setLimitBounds(new amap.Bounds(
    [Math.min(...lngs) - padLng, Math.min(...lats) - padLat],
    [Math.max(...lngs) + padLng, Math.max(...lats) + padLat]
  ))
}

function renderCampusMask(AMap) {
  if (!map) return
  if (!props.showMask) return
  applyLimitBounds()
  const boundary = currentBoundary()
  campusMask = new AMap.Polygon({
    path: [CAMPUS_MASK_OUTER, boundary],
    fillColor: '#07111f',
    fillOpacity: 0.96,
    strokeOpacity: 0,
    zIndex: 25,
    bubble: true,
    clickable: false
  })
  campusOutline = new AMap.Polyline({
    path: boundary,
    strokeColor: '#2fd9ea',
    strokeWeight: 2,
    strokeOpacity: 0.9,
    lineJoin: 'round',
    zIndex: 35,
    bubble: true
  })
  map.add([campusMask, campusOutline])
}

function updateCampusMask() {
  if (!map || !amap) return
  if (campusMask) campusMask.setMap(null)
  if (campusOutline) campusOutline.setMap(null)
  campusMask = null
  campusOutline = null
  if (props.showMask) renderCampusMask(amap)
}

function renderLandmarks() {
  if (!map || !amap || !props.showLandmarks) return
  landmarkMarkers.forEach((m) => m.setMap(null))
  landmarkMarkers = LANDMARKS.map((item) => {
    const marker = new amap.Marker({
      position: [item.lng, item.lat],
      content: `<div class="landmark-marker ${item.tone === 'key' ? 'is-key' : ''}"><span></span><b>${item.name}</b></div>`,
      offset: new amap.Pixel(-6, -6),
      zIndex: 60,
      map
    })
    return marker
  })
  toggleLandmarkVisibility()
}

function toggleLandmarkVisibility() {
  if (!map) return
  const visible = map.getZoom() >= 16.4
  landmarkMarkers.forEach((m) => { if (visible) m.show(); else m.hide() })
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]))
}

function renderMarkers(fit = false) {
  if (!map || !amap) return
  Object.values(markers).forEach((m) => m.setMap(null))
  markers = {}
  const inv = stationInventory()
  const hidden = new Set(props.boundaryIds || [])
  props.stations.forEach((s, i) => {
    if (hidden.has(s.id)) return
    const n = inv[i] != null ? inv[i] : s.init_bikes
    const marker = new amap.Marker({
      position: [s.lng, s.lat],
      content: markerHtml(s, n, i),
      offset: new amap.Pixel(-24, -24),
      zIndex: props.selected === s.id ? 130 : 100,
      map
    })
    marker.on('click', () => emit('select', s.id))
    markers[s.id] = marker
  })
  if (fit && Object.keys(markers).length) fitView()
}

function update() {
  if (!map || !amap || !props.stations.length) return
  const inv = stationInventory()
  const hidden = new Set(props.boundaryIds || [])
  props.stations.forEach((s, i) => {
    if (hidden.has(s.id)) return
    const marker = markers[s.id]
    if (!marker) return
    const n = inv[i] != null ? inv[i] : s.init_bikes
    marker.setContent(markerHtml(s, n, i))
    marker.setPosition([s.lng, s.lat])
    marker.setzIndex(props.selected === s.id ? 130 : 100)
  })
  updateTruck()
  updateRoute()
}

function updateTruck() {
  const truck = props.stepData && props.stepData.truck
  if (!truck || !props.stations[truck.station]) {
    if (truckMarker) truckMarker.hide()
    return
  }
  const s = props.stations[truck.station]
  const position = [s.lng, s.lat]
  const html = `<div class="truck-pin"><span class="truck-signal"></span><div class="truck-core">运<br><b>${truck.load}</b></div><div class="truck-label">调度三轮车</div></div>`
  if (!truckMarker) {
    truckMarker = new amap.Marker({
      position,
      content: html,
      offset: new amap.Pixel(-24, -24),
      zIndex: 220,
      map
    })
  } else {
    truckMarker.show()
    truckMarker.setContent(html)
    if (typeof truckMarker.moveTo === 'function') {
      truckMarker.moveTo(position, { duration: 760, autoRotation: false })
    } else {
      truckMarker.setPosition(position)
    }
  }
}

function updateRoute() {
  const path = (props.truckPath || [])
    .map((idx) => props.stations[idx])
    .filter(Boolean)
    .map((s) => [s.lng, s.lat])
  if (path.length < 2) {
    if (routeGlow) routeGlow.hide()
    if (routeLine) routeLine.hide()
    return
  }
  if (!routeGlow) {
    routeGlow = new amap.Polyline({
      path, strokeColor: '#22D3EE', strokeWeight: 10, strokeOpacity: 0.12,
      lineJoin: 'round', lineCap: 'round', zIndex: 40, map
    })
  }
  if (!routeLine) {
    routeLine = new amap.Polyline({
      path, strokeColor: '#42E8FF', strokeWeight: 3, strokeOpacity: 0.95,
      showDir: true, lineJoin: 'round', lineCap: 'round', zIndex: 45, map
    })
  }
  routeGlow.show()
  routeLine.show()
  routeGlow.setPath(path)
  routeLine.setPath(path)
}

function fitView() {
  if (!map) return
  const list = Object.values(markers)
  if (list.length) map.setFitView(list, false, [90, 90, 90, 90], 17.2)
  else resetView()
}

function resetView() {
  if (map) map.setZoomAndCenter(CAMPUS_ZOOM, props.center || CAMPUS_CENTER, false, 420)
}

function setCamera(center, zoom, duration = 420) {
  if (map) map.setZoomAndCenter(zoom, center, false, duration)
}

function focusStation(id) {
  const s = props.stations.find((item) => item.id === id)
  if (s && map) map.setZoomAndCenter(Math.max(map.getZoom(), 17), [s.lng, s.lat], false, 350)
}

function resize() {
  if (map) map.resize()
}

function reload() {
  buildMap(true)
}

defineExpose({ fitView, resetView, setCamera, focusStation, resize, reload })

onMounted(async () => {
  mounted = true
  await nextTick()
  buildMap(false)
})

onBeforeUnmount(() => {
  mounted = false
  if (loadTimer) clearTimeout(loadTimer)
  if (map) {
    clearBusinessLayers()
    map.destroy()
    map = null
  }
})

watch(() => props.stepData, update)
watch(() => props.selected, update)
watch(() => props.stations, () => { renderMarkers(false); update() }, { deep: true })
watch(() => props.showLandmarks, renderLandmarks)
watch(() => props.introMode, () => update())
watch(() => props.boundary, updateCampusMask, { deep: true })
watch(() => props.viewMode, () => buildMap(true))
watch(() => props.satellite, () => buildMap(true))
watch(() => props.editMode, (value) => {
  if (map) map.setDefaultCursor(value ? 'crosshair' : 'default')
})
</script>

<style scoped>
.map-wrap {
  position: relative;
  width: 100%;
  min-height: 240px;
  overflow: hidden;
  background: #07111f;
}
.map { width: 100%; height: 100%; }
.map-state {
  position: absolute;
  inset: 0;
  z-index: 500;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #b8cbe4;
  font-size: 17px;
  background: #07111f;
}
.map-error strong { color: #e6f1ff; font-size: 22px; font-weight: 500; }
.map-retry {
  height: 42px;
  padding: 0 20px;
  border: 1px solid #2f81f7;
  border-radius: 8px;
  background: #12233a;
  color: #e6f1ff;
  cursor: pointer;
}
.loader-line { width: 180px; height: 2px; background: #1e3a5f; position: relative; overflow: hidden; }
.loader-line::after {
  content: '';
  position: absolute;
  width: 60px;
  height: 2px;
  background: #22d3ee;
  animation: loading 1.4s ease-in-out infinite;
}
.legend {
  position: absolute;
  right: 18px;
  top: 18px;
  z-index: 80;
  display: flex;
  gap: 16px;
  padding: 9px 14px;
  background: rgba(7, 17, 31, .92);
  border: 1px solid rgba(76, 125, 174, .45);
  border-radius: 8px;
  font-size: 14px;
  color: #b8cbe4;
  pointer-events: none;
}
.legend span { display: inline-flex; align-items: center; gap: 7px; }
.dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.dot.red { background: #ef4444; }
.dot.blue { background: #2f81f7; }
.dot.amber { background: #f59e0b; }
@keyframes loading { from { left: -60px; } to { left: 180px; } }

:deep(.landmark-marker) {
  display: flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
  padding: 4px 7px 4px 5px;
  border: 1px solid rgba(70, 129, 173, .5);
  border-radius: 4px;
  background: rgba(5, 17, 30, .9);
  color: #c7d9eb;
  font-size: 14px;
  box-shadow: 0 2px 9px rgba(0,0,0,.35);
  pointer-events: none;
}
:deep(.landmark-marker span) { width: 5px; height: 5px; border: 1px solid #4dd9e9; transform: rotate(45deg); }
:deep(.landmark-marker b) { font-weight: 400; }
:deep(.landmark-marker.is-key) { border-color: rgba(34,211,238,.7); color: #e3fbff; background: rgba(6, 38, 51, .94); }
:deep(.landmark-marker.is-key span) { background: #22d3ee; box-shadow: 0 0 8px rgba(34,211,238,.7); }
:deep(.station-pin) { position: relative; width: 48px; height: 48px; }
:deep(.map.is-dense .station-pin) { width: 34px; height: 34px; }
:deep(.map.is-dense .station-core) { font-size: 13px; }
:deep(.map.is-dense .station-label) { display: none; }
:deep(.map.is-dense .station-marker.is-selected .station-label) { display: flex; top: 38px; }
:deep(.station-core) {
  position: absolute;
  inset: 5px;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid rgba(255,255,255,.9);
  border-radius: 50%;
  background: #2f81f7;
  color: #fff;
  font: 600 15px/1 Consolas, monospace;
  box-shadow: 0 3px 14px rgba(0,0,0,.48);
  transition: transform .18s ease-out;
}
:deep(.station-marker.is-low .station-core) { background: #ef4444; }
:deep(.station-marker.is-high .station-core) { background: #f59e0b; }
:deep(.station-marker.is-selected .station-core) { transform: scale(1.16); border-color: #8ff4ff; }
:deep(.station-orbit) {
  position: absolute;
  inset: 0;
  border: 1px solid transparent;
  border-radius: 50%;
}
:deep(.station-marker.is-selected .station-orbit) { border-color: #22d3ee; }
:deep(.station-pin.intro-enter) { animation: station-enter .55s cubic-bezier(.2,.7,.3,1) both; animation-delay: var(--delay, 0ms); }
:deep(.station-marker.is-active .station-orbit) {
  border-color: #22d3ee;
  animation: station-pulse 1.6s ease-out infinite;
}
:deep(.station-label) {
  position: absolute;
  left: 50%;
  top: 50px;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  padding: 3px 7px;
  border: 1px solid rgba(70, 121, 171, .5);
  border-radius: 4px;
  background: rgba(5, 14, 27, .9);
  color: #dcecff;
  font-size: 14px;
  line-height: 1.3;
  box-shadow: 0 2px 8px rgba(0,0,0,.3);
}
:deep(.station-label b) { color: #6cecff; font-family: Consolas, monospace; font-weight: 600; }
:deep(.station-label span) { display: none; max-width: 130px; overflow: hidden; text-overflow: ellipsis; }
:deep(.station-marker.is-selected .station-label span) { display: inline; }
:deep(.truck-pin) { position: relative; width: 48px; height: 48px; }
:deep(.truck-core) {
  position: absolute;
  inset: 3px;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  border: 2px solid #c2fbff;
  border-radius: 10px;
  background: #0d9eb5;
  color: #fff;
  font-size: 14px;
  line-height: 1.05;
  box-shadow: 0 0 20px rgba(34,211,238,.45);
}
:deep(.truck-core b) { font: 600 16px/1 Consolas, monospace; }
:deep(.truck-signal) { position: absolute; inset: -5px; border: 1px solid #22d3ee; border-radius: 14px; animation: truck-pulse 1.8s ease-out infinite; }
:deep(.truck-label) {
  position: absolute;
  top: 52px;
  left: 50%;
  transform: translateX(-50%);
  white-space: nowrap;
  padding: 3px 7px;
  border-radius: 4px;
  background: rgba(5,14,27,.92);
  color: #8ff4ff;
  font-size: 14px;
}
@keyframes station-enter { 0% { transform: scale(.2); opacity: 0; } 70% { transform: scale(1.12); opacity: 1; } 100% { transform: scale(1); opacity: 1; } }
@keyframes station-pulse { 0% { transform: scale(.8); opacity: 1; } 100% { transform: scale(1.8); opacity: 0; } }
@keyframes truck-pulse { 0% { transform: scale(.85); opacity: .9; } 100% { transform: scale(1.35); opacity: 0; } }
@media (prefers-reduced-motion: reduce) {
  :deep(.station-orbit), :deep(.truck-signal), .loader-line::after { animation: none !important; }
}
</style>
