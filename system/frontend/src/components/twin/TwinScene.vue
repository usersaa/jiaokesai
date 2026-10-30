<template>
  <div ref="container" class="twin-scene">
    <div v-if="error" class="twin-error">{{ error }}</div>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { CSS2DObject, CSS2DRenderer } from 'three/addons/renderers/CSS2DRenderer.js'
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js'
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js'
import { Line2 } from 'three/addons/lines/Line2.js'
import { LineGeometry } from 'three/addons/lines/LineGeometry.js'
import { LineMaterial } from 'three/addons/lines/LineMaterial.js'
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js'
import { createRoadNetwork, sampleRoadRoute } from './roadNetwork'
import { CAMPUS_CENTER } from '../../config/map'

const props = defineProps({
  stations: { type: Array, default: () => [] },
  noParking: { type: Array, default: () => [] },
  stepData: { type: Object, default: null },
  truckPath: { type: Array, default: () => [] },
  bikes: { type: Array, default: () => [] },
  displayMode: { type: String, default: 'live' },
  sessionKey: { type: String, default: '' },
  heatPoints: { type: Array, default: () => [] },
  heatMode: { type: String, default: 'off' },
  arcs: { type: Array, default: () => [] },
  theme: { type: String, default: 'night' },
  showLabels: { type: Boolean, default: false },
  selected: { type: String, default: '' }
})
const emit = defineEmits(['ready', 'select', 'error', 'follow-change', 'route-status'])
const container = ref(null)
const error = ref('')

const CENTER_LNG = CAMPUS_CENTER[0]
const CENTER_LAT = CAMPUS_CENTER[1]
const MX = 111320 * Math.cos(CENTER_LAT * Math.PI / 180)
const MY = 110540
// 与决策模型 delta_critical=0.2 对齐：库存 <20% 偏低，剩余车位 <20%（即占用 >80%）偏高
const LOW_RATIO = 0.2
const HIGH_RATIO = 0.8
const PLATE_DEPTH = 48

let renderer = null
let labelRenderer = null
let scene = null
let camera = null
let controls = null
let raycaster = null
let pointer = null
let pointerDownPos = null
let composer = null
let bloom = null
let animationId = 0
let resizeObserver = null
let clock = null
let introActive = false
let introStart = 0
let introFrom = new THREE.Vector3()
let introTo = new THREE.Vector3()
let campusData = null
let buildingMesh = null
let buildingEdges = null
let boundaryMaterials = []
let stationObjects = new Map()
let stationGroup = null
let noParkingGroup = null
let truckGroup = null
let truckLabelEl = null
let routeLine = null
let plateTopMat = null
let plateSideMat = null
let buildingMat = null
let roadMat = null
let hemiLight = null
let dirLight = null
let fillLight = null
let themeName = 'night'
let surfaceGroup = null
let roadMesh = null
let roadCasingMesh = null
let roadCasingMat = null
let buildingShade = null
let buildingLabels = []
let labelGroup = null
const seenArcs = new Set()
let bikePoints = null
let bikeGeometry = null
let bikeOrder = []
const bikeState = new Map()
let campusBounds = null
let overviewPosition = new THREE.Vector3()
let overviewTarget = new THREE.Vector3()
let activeView = 'overview'
let userNavigated = false
let groundPlane = null
let landscape = null
let haloTexture = null
let labelFrame = 0
let roadNetwork = null
let tripQueue = []
let activeTrip = null
let following = false
let replayStation = null
let heatMesh = null
let heatSignature = ''

function beaconTexture() {
  if (haloTexture) return haloTexture
  const c = document.createElement('canvas')
  c.width = c.height = 64
  const ctx = c.getContext('2d')
  const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32)
  g.addColorStop(0, 'rgba(255,255,255,1)')
  g.addColorStop(.22, 'rgba(255,255,255,.8)')
  g.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = g; ctx.fillRect(0, 0, 64, 64)
  haloTexture = new THREE.CanvasTexture(c)
  return haloTexture
}

function project(lng, lat) {
  return new THREE.Vector3((lng - CENTER_LNG) * MX, 0, -(lat - CENTER_LAT) * MY)
}

function colorForStation(station, inventory) {
  const ratio = station.capacity ? inventory / station.capacity : 0
  const day = themeName === 'day'
  if (ratio < LOW_RATIO) return day ? 0xd64545 : 0xef5b5b
  if (ratio > HIGH_RATIO) return day ? 0xc97c15 : 0xf2b24b
  return day ? 0x1478a8 : 0x36dff2
}

function createLabel(html, className = 'twin-label') {
  const el = document.createElement('div')
  el.className = className
  el.innerHTML = html
  return new CSS2DObject(el)
}

function addBoundaryLine(points, color, width, opacity, yOffset = 1.4) {
  const flat = []
  const center = new THREE.Box3().setFromPoints(points).getCenter(new THREE.Vector3())
  const rim = points.map((p) => p.clone().sub(center).multiplyScalar(1.006).add(center))
  rim.forEach((p) => { flat.push(p.x, p.y + yOffset, p.z) })
  flat.push(rim[0].x, rim[0].y + yOffset, rim[0].z)
  const geometry = new LineGeometry()
  geometry.setPositions(flat)
  const material = new LineMaterial({
    color,
    linewidth: width,
    transparent: true,
    opacity,
    depthWrite: false
  })
  material.resolution.set(container.value.clientWidth, container.value.clientHeight)
  boundaryMaterials.push(material)
  const line = new Line2(geometry, material)
  line.computeLineDistances()
  scene.add(line)
}

// ---------------- 昼夜主题 ----------------
const THEMES = {
  night: {
    bg: 0x061422, fog: 0x061422, fogDensity: 0.00015,
    plateTop: 0x365660, plateTopEmissive: 0x06111a, plateTopEmissiveInt: 0.08,
    plateSide: 0x1b4662, plateSideEmissive: 0x0b2f4b, plateSideEmissiveInt: 0.55,
    roof: 0xc2e5ee, wall: 0x6290a6, buildEmissive: 0x071b29, buildEmissiveInt: 0.06,
    edge: 0xb1d5df, edgeOpacity: 0.24,
    road: 0x365867, roadCasing: 0x0e2533, roadOpacity: 0.92,
    boundaryInner: 0x9df6ff, boundaryMain: 0x37e6ff, boundaryHalo: 0x37e6ff, boundaryBottom: 0x1f8fb5,
    hemi: 1.1, hemiSky: 0xc6e6f4, hemiGround: 0x233848,
    dir: 2.9, dirColor: 0xe5f5ff, fill: 0.35,
    bloom: { strength: 0.22, radius: 0.35, threshold: 1.05 },
    exposure: 1.05, bike: 0xa8f6ff, bikeBlending: 'additive'
  },
  day: {
    bg: 0xc6d8e6, fog: 0xc6d8e6, fogDensity: 0.00016,
    plateTop: 0xa4bac3, plateTopEmissive: 0xffffff, plateTopEmissiveInt: 0,
    plateSide: 0x9db4c8, plateSideEmissive: 0x000000, plateSideEmissiveInt: 0,
    roof: 0xe8f2f5, wall: 0x7d9bad, buildEmissive: 0x000000, buildEmissiveInt: 0,
    edge: 0x3f6a86, edgeOpacity: 0.3,
    road: 0xffffff, roadCasing: 0xb0c2d2, roadOpacity: 1.0,
    boundaryInner: 0x0e5f80, boundaryMain: 0x1c86ad, boundaryHalo: 0x1c86ad, boundaryBottom: 0x5f93b0,
    hemi: 0.72, hemiSky: 0xffffff, hemiGround: 0xb9c9d6,
    dir: 1.95, dirColor: 0xffffff, fill: 0.32,
    bloom: { strength: 0.1, radius: 0.3, threshold: 0.95 },
    exposure: 1.0, bike: 0x0f5d8a, bikeBlending: 'normal'
  }
}

function paintBuildings(roofHex, wallHex) {
  if (!buildingMesh) return
  const geo = buildingMesh.geometry
  const normals = geo.attributes.normal
  const colors = geo.attributes.color
  if (!normals || !colors) return
  const roof = new THREE.Color(roofHex)
  const wall = new THREE.Color(wallHex)
  const shadeAttr = geo.attributes.shade
  for (let i = 0; i < normals.count; i += 1) {
    const isRoof = normals.getY(i) > 0.55
    const faceShade = isRoof ? 1 : 0.72 + 0.28 * Math.max(0, -normals.getX(i) * .8 + normals.getZ(i) * .6)
    const base = (isRoof ? roof : wall).clone().multiplyScalar(faceShade)
    const r = shadeAttr ? shadeAttr.getX(i) : 1
    const g = shadeAttr ? shadeAttr.getY(i) : 1
    const b2 = shadeAttr ? shadeAttr.getZ(i) : 1
    colors.setXYZ(i, Math.min(1, base.r * r), Math.min(1, base.g * g), Math.min(1, base.b * b2))
  }
  colors.needsUpdate = true
}

function applyTheme(name) {
  const t = THEMES[name] || THEMES.night
  themeName = name === 'day' ? 'day' : 'night'
  if (!scene) return
  scene.background = new THREE.Color(t.bg)
  if (scene.fog) {
    scene.fog.color.setHex(t.fog)
    scene.fog.density = t.fogDensity
  }
  if (renderer) renderer.toneMappingExposure = t.exposure
  if (plateTopMat) {
    plateTopMat.color.setHex(t.plateTop)
    plateTopMat.emissive.setHex(t.plateTopEmissive)
    plateTopMat.emissiveIntensity = t.plateTopEmissiveInt
  }
  if (plateSideMat) {
    plateSideMat.color.setHex(t.plateSide)
    plateSideMat.emissive.setHex(t.plateSideEmissive)
    plateSideMat.emissiveIntensity = t.plateSideEmissiveInt
  }
  paintBuildings(t.roof, t.wall)
  if (buildingMat) {
    buildingMat.emissive.setHex(t.buildEmissive)
    buildingMat.emissiveIntensity = t.buildEmissiveInt
  }
  if (buildingEdges) {
    buildingEdges.material.color.setHex(t.edge)
    buildingEdges.material.opacity = t.edgeOpacity
  }
  if (roadMat) {
    roadMat.color.setHex(t.road)
    roadMat.opacity = t.roadOpacity
  }
  if (roadCasingMat) {
    roadCasingMat.color.setHex(t.roadCasing)
  }
  if (boundaryMaterials.length >= 4) {
    boundaryMaterials[0].color.setHex(t.boundaryInner)
    boundaryMaterials[1].color.setHex(t.boundaryMain)
    boundaryMaterials[2].color.setHex(t.boundaryHalo)
    boundaryMaterials[3].color.setHex(t.boundaryBottom)
    boundaryMaterials[2].opacity = themeName === 'day' ? 0.05 : 0.03
  }
  applySurfaceColors()
  buildingLabels.forEach((obj) => obj.element.classList.toggle('night', themeName === 'night'))
  if (hemiLight) {
    hemiLight.intensity = t.hemi
    hemiLight.color.setHex(t.hemiSky)
    hemiLight.groundColor.setHex(t.hemiGround)
  }
  if (dirLight) {
    dirLight.intensity = t.dir
    dirLight.color.setHex(t.dirColor)
  }
  if (fillLight) fillLight.intensity = t.fill
  if (bloom) {
    bloom.strength = t.bloom.strength
    bloom.radius = t.bloom.radius
    bloom.threshold = t.bloom.threshold
  }
  if (bikePoints) {
    bikePoints.material.color.setHex(t.bike)
    bikePoints.material.blending = t.bikeBlending === 'additive' ? THREE.AdditiveBlending : THREE.NormalBlending
    bikePoints.material.needsUpdate = true
  }
  updateStationVisuals()
  if (groundPlane) groundPlane.material.color.setHex(themeName === 'day' ? 0x829daa : 0x071625)
}

function buildCampusGround() {
  const ring = campusData.boundary.slice(0, -1).map(([lng, lat]) => project(lng, lat))
  campusBounds = new THREE.Box3().setFromPoints(ring)
  campusBounds.max.y = Math.max(...campusData.buildings.map((b) => (b.h || 10) * 1.2)) + 18
  const shape = new THREE.Shape(ring.map((p) => new THREE.Vector2(p.x, -p.z)))
  shape.closePath()
  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth: PLATE_DEPTH, bevelEnabled: true, bevelSize: 1.8, bevelThickness: 1.2, bevelSegments: 1, steps: 1
  })
  geometry.rotateX(-Math.PI / 2); geometry.translate(0, -PLATE_DEPTH - 1.2, 0)
  plateTopMat = new THREE.MeshStandardMaterial({ color: 0x244552, roughness: .88, metalness: .08 })
  plateSideMat = new THREE.MeshStandardMaterial({ color: 0x0d293e, roughness: .6, metalness: .3 })
  const plate = new THREE.Mesh(geometry, [plateTopMat, plateSideMat])
  plate.receiveShadow = true; plate.castShadow = true; scene.add(plate)

  // A separate plinth and edge reveals make the ground read as a solid maquette.
  const baseGeo = new THREE.ExtrudeGeometry(shape, { depth: 7, bevelEnabled: false })
  baseGeo.rotateX(-Math.PI / 2); baseGeo.translate(0, -PLATE_DEPTH - 10, 0)
  const base = new THREE.Mesh(baseGeo, new THREE.MeshStandardMaterial({ color: 0x16394e, metalness: .4, roughness: .55 }))
  base.castShadow = true; base.receiveShadow = true; scene.add(base)
  addBoundaryLine(ring, 0xb7f5ff, .8, .9, 2.2)
  addBoundaryLine(ring, 0x26cceb, 2.4, .82, 2)
  addBoundaryLine(ring, 0x1597c4, 7, .12, 2)
  addBoundaryLine(ring, 0x2ab6de, 1.4, .65, -PLATE_DEPTH + 2)
  addBoundaryLine(ring, 0x268bb3, .8, .5, -PLATE_DEPTH - 9)
  const seams = []
  ring.forEach((a, i) => {
    const b = ring[(i + 1) % ring.length]
    const count = Math.ceil(a.distanceTo(b) / 38)
    for (let n = 1; n < count; n += 1) {
      const p = a.clone().lerp(b, n / count)
      seams.push(p.x, -6, p.z, p.x, -PLATE_DEPTH + 4, p.z)
    }
  })
  const seamGeo = new THREE.BufferGeometry()
  seamGeo.setAttribute('position', new THREE.Float32BufferAttribute(seams, 3))
  scene.add(new THREE.LineSegments(seamGeo, new THREE.LineBasicMaterial({ color: 0x59879a, transparent: true, opacity: .18 })))
  groundPlane = new THREE.Mesh(new THREE.PlaneGeometry(8000, 8000), new THREE.MeshStandardMaterial({ color: 0x071625, roughness: .95, metalness: .05 }))
  groundPlane.rotation.x = -Math.PI / 2; groundPlane.position.y = -PLATE_DEPTH - 14
  groundPlane.receiveShadow = true; scene.add(groundPlane)
}

function buildContactShadows() {
  const box = new THREE.Box3().setFromPoints(campusData.boundary.map((p) => project(...p)))
  box.expandByScalar(30)
  const size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3())
  const c = document.createElement('canvas'); c.width = c.height = 2048
  const ctx = c.getContext('2d')
  const x = (v) => (v - box.min.x) / size.x * c.width
  const z = (v) => (v - box.min.z) / size.z * c.height
  ctx.fillStyle = 'rgba(0,8,14,.72)'; ctx.shadowColor = 'rgba(0,5,10,.8)'; ctx.shadowBlur = 13
  campusData.buildings.forEach((b) => {
    ctx.beginPath()
    b.p.forEach((p, i) => { const v = project(...p); if (!i) ctx.moveTo(x(v.x), z(v.z)); else ctx.lineTo(x(v.x), z(v.z)) })
    ctx.closePath(); ctx.fill()
  })
  const tex = new THREE.CanvasTexture(c); tex.flipY = false
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, opacity: .65, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -1 })
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(size.x, size.z), mat)
  mesh.rotation.x = -Math.PI / 2; mesh.position.set(center.x, .08, center.z); scene.add(mesh)
}

function buildLandscape() {
  const positions = []
  ;(campusData.surfaces || []).filter((s) => s.k === 'green').forEach((s) => {
    const ring = s.p.map((p) => project(...p))
    ring.slice(0, -1).forEach((a, i) => {
      const b = ring[i + 1]; const count = Math.floor(a.distanceTo(b) / 13)
      for (let j = 1; j < count; j += 1) positions.push(a.clone().lerp(b, j / count))
    })
  })
  // Sparse planting is confined to the existing green-space boundaries.
  if (positions.length) {
    landscape = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(4.4, 0), new THREE.MeshStandardMaterial({ color: 0x2d785c, roughness: 1 }), positions.length)
    const dummy = new THREE.Object3D()
    positions.forEach((p, i) => {
      dummy.position.copy(p).setY(4.2)
      dummy.scale.set(1, 1.25 + (i % 3) * .12, 1); dummy.rotation.y = i * 1.7
      dummy.updateMatrix(); landscape.setMatrixAt(i, dummy.matrix)
    })
    landscape.receiveShadow = true; scene.add(landscape)
  }
  const lines = []
  ;(campusData.surfaces || []).filter((s) => s.k === 'pitch').forEach((s) => {
    const ring = s.p.slice(0, -1).map((p) => project(...p))
    if (ring.length !== 4) return
    const center = ring.reduce((v, p) => v.add(p), new THREE.Vector3()).multiplyScalar(.25)
    const inner = ring.map((p) => p.clone().lerp(center, .1).setY(.8))
    inner.forEach((p, i) => { const q = inner[(i + 1) % 4]; lines.push(p.x, p.y, p.z, q.x, q.y, q.z) })
    const a = inner[0].clone().lerp(inner[1], .5), b = inner[2].clone().lerp(inner[3], .5)
    lines.push(a.x, .8, a.z, b.x, .8, b.z)
  })
  const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.Float32BufferAttribute(lines, 3))
  scene.add(new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: 0xa4c9bc, transparent: true, opacity: .4 })))
}

function buildBuildings() {
  const geometries = []
  const edgeGeometries = []
  campusData.buildings.forEach((b) => {
    if (!b.p || b.p.length < 3) return
    const shape = new THREE.Shape()
    b.p.forEach(([lng, lat], index) => {
      const p = project(lng, lat)
      if (index === 0) shape.moveTo(p.x, -p.z)
      else shape.lineTo(p.x, -p.z)
    })
    shape.closePath()
    const geometry = new THREE.ExtrudeGeometry(shape, {
      depth: (b.h || 10) * 1.2,
      bevelEnabled: false,
      steps: 1
    })
    geometry.rotateX(-Math.PI / 2)
    geometry.computeVertexNormals()
    const normals = geometry.attributes.normal
    const colors = new Float32Array(normals.count * 3)
    const roof = new THREE.Color(0x86d2e6)
    const wall = new THREE.Color(0x1b4b64)
    for (let i = 0; i < normals.count; i += 1) {
      const isRoof = normals.getY(i) > 0.55
      const c = isRoof ? roof : wall
      colors[i * 3] = c.r
      colors[i * 3 + 1] = c.g
      colors[i * 3 + 2] = c.b
    }
    const h = Number(b.id) % 997
    const shade = 0.9 + (h / 997) * 0.18
    const TINTS = [[1, 1, 1], [0.94, 0.985, 1.05], [1.05, 1.0, 0.93]]
    const tint = TINTS[h % 3]
    const shades = new Float32Array(normals.count * 3)
    for (let k = 0; k < normals.count; k += 1) {
      shades[k * 3] = shade * tint[0]
      shades[k * 3 + 1] = shade * tint[1]
      shades[k * 3 + 2] = shade * tint[2]
    }
    geometry.setAttribute('shade', new THREE.BufferAttribute(shades, 3))
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    geometries.push(geometry)
    const edges = new THREE.EdgesGeometry(geometry, 28)
    edgeGeometries.push(edges)
  })
  if (!geometries.length) return
  const merged = mergeGeometries(geometries, false)
  buildingMat = new THREE.MeshStandardMaterial({
    color: 0xffffff,
    vertexColors: true,
    emissive: 0x0a3048,
    emissiveIntensity: 0.7,
    metalness: 0.12,
    roughness: 0.72,
    transparent: false
  })
  buildingMesh = new THREE.Mesh(merged, buildingMat)
  buildingMesh.castShadow = true
  buildingMesh.receiveShadow = true
  buildingMesh.position.y = 0
  scene.add(buildingMesh)
  geometries.forEach((g) => g.dispose())

  const mergedEdges = mergeGeometries(edgeGeometries, false)
  edgeGeometries.forEach((g) => g.dispose())
  if (mergedEdges) {
    buildingEdges = new THREE.LineSegments(mergedEdges, new THREE.LineBasicMaterial({
      color: 0x74cfe6, transparent: true, opacity: 0.55
    }))
    scene.add(buildingEdges)
  }
}

function buildOuterBuildings() {
  const list = campusData.outer || []
  if (!list.length) return
  const geometries = []
  list.forEach((b) => {
    if (!b.p || b.p.length < 3) return
    const shape = new THREE.Shape()
    b.p.forEach(([lng, lat], index) => {
      const p = project(lng, lat)
      if (index === 0) shape.moveTo(p.x, -p.z)
      else shape.lineTo(p.x, -p.z)
    })
    shape.closePath()
    const geometry = new THREE.ExtrudeGeometry(shape, {
      depth: Math.max(4, Math.min(b.h || 8, 24)),
      bevelEnabled: false,
      steps: 1
    })
    geometry.rotateX(-Math.PI / 2)
    geometry.computeVertexNormals()
    geometries.push(geometry)
  })
  if (!geometries.length) return
  const merged = mergeGeometries(geometries, false)
  geometries.forEach((g) => g.dispose())
  const mesh = new THREE.Mesh(merged, new THREE.MeshStandardMaterial({
    color: 0x102c3b,
    emissive: 0x07121c,
    emissiveIntensity: 0.08,
    metalness: 0.3,
    roughness: 0.7,
    transparent: true,
    opacity: 0.55
  }))
  scene.add(mesh)
}

function dotTexture() {
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 64
  const ctx = canvas.getContext('2d')
  const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32)
  grad.addColorStop(0, 'rgba(255,255,255,1)')
  grad.addColorStop(0.32, 'rgba(150,246,255,.95)')
  grad.addColorStop(1, 'rgba(60,200,255,0)')
  ctx.fillStyle = grad
  ctx.beginPath()
  ctx.arc(32, 32, 32, 0, Math.PI * 2)
  ctx.fill()
  return new THREE.CanvasTexture(canvas)
}

function buildBikeLayer() {
  if (bikePoints || !scene) return
  bikeGeometry = new THREE.BufferGeometry()
  bikeGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(600 * 3), 3))
  bikeGeometry.setDrawRange(0, 0)
  bikePoints = new THREE.Points(bikeGeometry, new THREE.PointsMaterial({
    size: 17,
    map: dotTexture(),
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    color: 0xa8f6ff,
    sizeAttenuation: true
  }))
  bikePoints.frustumCulled = false
  scene.add(bikePoints)
}

function updateBikes() {
  if (!bikeGeometry) return
  const list = props.bikes || []
  const attr = bikeGeometry.attributes.position
  const arr = attr.array
  const count = Math.min(list.length, 600)
  bikeOrder = []
  for (let i = 0; i < count; i += 1) {
    const b = list[i]
    const p = project(b.lng, b.lat)
    let st = bikeState.get(b.id)
    if (!st) { st = { x: p.x, z: p.z, tx: p.x, tz: p.z }; bikeState.set(b.id, st) }
    st.tx = p.x
    st.tz = p.z
    arr[i * 3] = st.x
    arr[i * 3 + 1] = 5
    arr[i * 3 + 2] = st.z
    bikeOrder.push(b.id)
  }
  bikeGeometry.setDrawRange(0, count)
  attr.needsUpdate = true
  if (bikeState.size > 700) {
    const keep = new Set(bikeOrder)
    for (const key of bikeState.keys()) if (!keep.has(key)) bikeState.delete(key)
  }
}


// ---------------- 路径与调度动效 ----------------
const SURFACE_COLORS = {
  day: { green: 0x9ccf94, pitch: 0x86c39c, water: 0x8ec0dd, pave: 0xd3dce3 },
  night: { green: 0x285740, pitch: 0x38675b, water: 0x23556d, pave: 0x3a525e }
}

function applySurfaceColors() {
  if (!surfaceGroup) return
  const pal = SURFACE_COLORS[themeName] || SURFACE_COLORS.night
  surfaceGroup.children.forEach((mesh) => {
    const c = pal[mesh.userData.kind] || pal.green
    mesh.material.color.setHex(c)
    mesh.material.needsUpdate = true
  })
}

function buildSurfaces() {
  const list = campusData.surfaces || []
  if (!list.length) return
  surfaceGroup = new THREE.Group()
  scene.add(surfaceGroup)
  list.forEach((item) => {
    if (!item.p || item.p.length < 3) return
    const shape = new THREE.Shape()
    item.p.forEach(([lng, lat], i) => {
      const p = project(lng, lat)
      if (i === 0) shape.moveTo(p.x, -p.z)
      else shape.lineTo(p.x, -p.z)
    })
    shape.closePath()
    const geo = new THREE.ShapeGeometry(shape)
    geo.rotateX(-Math.PI / 2)
    const mat = new THREE.MeshStandardMaterial({
      color: 0x000000, roughness: 1, metalness: 0,
      side: THREE.DoubleSide
    })
    const mesh = new THREE.Mesh(geo, mat)
    mesh.receiveShadow = true
    mesh.position.y = 0.5
    mesh.userData.kind = item.k
    surfaceGroup.add(mesh)
  })
  applySurfaceColors()
}

function insideCampus(point) {
  const ring = campusData.boundary.map((p) => project(...p))
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i], b = ring[j]
    if ((a.z > point.z) !== (b.z > point.z) && point.x < (b.x-a.x)*(point.z-a.z)/(b.z-a.z)+a.x) inside = !inside
  }
  return inside
}

function buildRoads() {
  const positions = []
  campusData.roads.forEach((road) => {
    const pts = road.p.map(([lng, lat]) => project(lng, lat))
    const w = Math.max(2.0, (road.w || 3) * 1.7)
    for (let i = 0; i < pts.length - 1; i += 1) {
      const a = pts[i]
      const b = pts[i + 1]
      if (!insideCampus(a.clone().lerp(b, .5))) continue
      const dx = b.x - a.x
      const dz = b.z - a.z
      const len = Math.hypot(dx, dz)
      if (len < 0.4) continue
      const nx = (-dz / len) * w / 2
      const nz = (dx / len) * w / 2
      const y = 0.9
      positions.push(a.x + nx, y, a.z + nz, a.x - nx, y, a.z - nz, b.x + nx, y, b.z + nz)
      positions.push(b.x + nx, y, b.z + nz, a.x - nx, y, a.z - nz, b.x - nx, y, b.z - nz)
    }
  })
  if (!positions.length) return
  const casing = []
  campusData.roads.forEach((road) => {
    const pts = road.p.map(([lng, lat]) => project(lng, lat))
    const w = Math.max(3.2, (road.w || 3) * 2.3)
    for (let i = 0; i < pts.length - 1; i += 1) {
      const a = pts[i]
      const b = pts[i + 1]
      if (!insideCampus(a.clone().lerp(b, .5))) continue
      const dx = b.x - a.x
      const dz = b.z - a.z
      const len = Math.hypot(dx, dz)
      if (len < 0.4) continue
      const nx = (-dz / len) * w / 2
      const nz = (dx / len) * w / 2
      const y = 0.72
      casing.push(a.x + nx, y, a.z + nz, a.x - nx, y, a.z - nz, b.x + nx, y, b.z + nz)
      casing.push(b.x + nx, y, b.z + nz, a.x - nx, y, a.z - nz, b.x - nx, y, b.z - nz)
    }
  })
  const casingGeo = new THREE.BufferGeometry()
  casingGeo.setAttribute('position', new THREE.Float32BufferAttribute(casing, 3))
  roadCasingMat = new THREE.MeshBasicMaterial({
    color: 0x9fb4c6, transparent: true, opacity: 0.95,
    side: THREE.DoubleSide, depthWrite: false
  })
  roadCasingMesh = new THREE.Mesh(casingGeo, roadCasingMat)
  roadCasingMesh.renderOrder = 1
  scene.add(roadCasingMesh)

  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.computeVertexNormals()
  roadMat = new THREE.MeshBasicMaterial({
    color: 0xffffff, transparent: true, opacity: 1.0,
    side: THREE.DoubleSide, depthWrite: false
  })
  roadMesh = new THREE.Mesh(geometry, roadMat)
  roadMesh.renderOrder = 2
  scene.add(roadMesh)
}

function buildLabels() {
  if (labelGroup) return
  labelGroup = new THREE.Group()
  scene.add(labelGroup)
  const list = campusData.labels || []
  list.forEach((item) => {
    const el = document.createElement('div')
    el.className = 'twin-building-label'
    el.textContent = item.name.replace('School of International Education', '国际教育学院')
    el.title = item.name
    const obj = new CSS2DObject(el)
    const p = project(item.lng, item.lat)
    obj.position.set(p.x, (item.h || 10) * 1.2 + 12, p.z)
    obj.userData.labelName = el.textContent
    obj.visible = props.showLabels
    labelGroup.add(obj)
    buildingLabels.push(obj)
  })
}

function clearStations() {
  stationObjects.forEach(({ label }) => {
    if (label && label.element && label.element.parentNode) label.element.parentNode.removeChild(label.element)
  })
  if (stationGroup) {
    scene.remove(stationGroup)
    stationGroup.traverse((obj) => {
      if (obj.geometry) obj.geometry.dispose()
      if (obj.material) {
        const mats = Array.isArray(obj.material) ? obj.material : [obj.material]
        mats.forEach((m) => { if (m.map) m.map.dispose() })
        if (Array.isArray(obj.material)) obj.material.forEach((m) => m.dispose())
        else obj.material.dispose()
      }
    })
  }
  stationGroup = new THREE.Group()
  scene.add(stationGroup)
  stationObjects.clear()
}

function rebuildStations() {
  if (!scene) return
  clearStations()
  props.stations.forEach((station) => {
    const position = project(station.lng, station.lat)
    const group = new THREE.Group()
    group.position.copy(position)
    const color = 0x36dff2
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(8, 11, 40),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.72, side: THREE.DoubleSide, depthWrite: false })
    )
    ring.rotation.x = -Math.PI / 2
    ring.position.y = 0.9
    group.add(ring)
    const pillar = new THREE.Mesh(
      new THREE.CylinderGeometry(1.6, 3.0, 18, 12, 1, true),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.55, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending })
    )
    pillar.position.y = 9
    group.add(pillar)
    const cap = new THREE.Mesh(
      new THREE.ConeGeometry(3.4, 9, 4),
      new THREE.MeshBasicMaterial({ color })
    )
    cap.position.y = 19
    group.add(cap)
    const hit = new THREE.Mesh(
      new THREE.SphereGeometry(22, 10, 10),
      new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false, colorWrite: false })
    )
    hit.position.y = 14
    group.add(hit)
    const label = createLabel('', 'twin-point-label')
    label.position.set(0, 31, 0)
    label.element.style.pointerEvents = 'auto'
    label.element.style.cursor = 'pointer'
    label.element.addEventListener('click', (event) => {
      event.stopPropagation()
      emit('select', station.id)
    })
    group.add(label)
    group.traverse((obj) => { obj.userData.stationId = station.id })
    stationGroup.add(group)
    const core = new THREE.Mesh(new THREE.CylinderGeometry(.6, .8, 18, 8, 1, true), new THREE.MeshBasicMaterial({ color: 0xc8ffff, transparent: true, opacity: .95, blending: THREE.AdditiveBlending, depthWrite: false }))
    core.position.y = 9; group.add(core)
    const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: beaconTexture(), color, transparent: true, opacity: .65, blending: THREE.AdditiveBlending, depthWrite: false }))
    halo.scale.set(17, 17, 1); halo.position.y = 19; group.add(halo)
    cap.geometry.dispose(); cap.geometry = new THREE.SphereGeometry(1.8, 10, 8)
    stationObjects.set(station.id, { group, ring, pillar, core, halo, cap, label, position })
  })
  updateStationVisuals()
}

function rebuildNoParking() {
  if (noParkingGroup) {
    noParkingGroup.traverse((obj) => {
      if (obj.element && obj.element.parentNode) obj.element.parentNode.removeChild(obj.element)
      if (obj.geometry) obj.geometry.dispose()
      if (obj.material) obj.material.dispose()
    })
    scene.remove(noParkingGroup)
  }
  noParkingGroup = new THREE.Group()
  scene.add(noParkingGroup)
  props.noParking.forEach((zone) => {
    const position = project(zone.lng, zone.lat)
    const group = new THREE.Group()
    group.position.copy(position)
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(14, 18, 40),
      new THREE.MeshBasicMaterial({ color: 0xef5b5b, transparent: true, opacity: 0.55, side: THREE.DoubleSide, depthWrite: false })
    )
    ring.rotation.x = -Math.PI / 2
    ring.position.y = 1
    group.add(ring)
    const disc = new THREE.Mesh(
      new THREE.CircleGeometry(14, 40),
      new THREE.MeshBasicMaterial({ color: 0xef5b5b, transparent: true, opacity: 0.1, side: THREE.DoubleSide, depthWrite: false })
    )
    disc.rotation.x = -Math.PI / 2
    disc.position.y = 0.8
    group.add(disc)
    const crossMat = new THREE.LineBasicMaterial({ color: 0xff9b9b, transparent: true, opacity: 0.9 })
    const cross1 = new THREE.Line(new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-10, 1.2, -10), new THREE.Vector3(10, 1.2, 10)
    ]), crossMat)
    const cross2 = new THREE.Line(new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-10, 1.2, 10), new THREE.Vector3(10, 1.2, -10)
    ]), crossMat)
    group.add(cross1, cross2)
    const label = createLabel(`<b>禁停</b><span>${zone.id}</span>`, 'twin-nopark-label')
    label.position.set(0, 24, 0)
    group.add(label)
    noParkingGroup.add(group)
  })
}

function updateStationVisuals() {
  const inventory = (props.stepData && props.stepData.inventory) || props.stations.map((s) => s.init_bikes)
  props.stations.forEach((station, index) => {
    const obj = stationObjects.get(station.id)
    if (!obj) return
    const n = inventory[index] != null ? Number(inventory[index]) : Number(station.init_bikes || 0)
    const color = props.selected === station.id ? 0xffc56b : colorForStation(station, n)
    obj.ring.material.color.setHex(color)
    obj.pillar.material.color.setHex(color)
    obj.cap.material.color.setHex(color)
    const ratio = station.capacity ? Math.max(0.08, Math.min(1, n / station.capacity)) : 0.3
    const height = 13 + ratio * 27
    obj.pillar.scale.y = height / 18
    obj.pillar.position.y = height / 2
    obj.core.scale.y = height / 18; obj.core.position.y = height / 2
    obj.halo.position.y = height; obj.halo.material.color.setHex(color)
    obj.cap.position.y = height
    obj.label.position.y = height + 13
    const selected = props.selected === station.id
    obj.ring.scale.setScalar(selected ? 1.35 : 1)
    const day = themeName === 'day'
    obj.ring.material.opacity = day ? 0.9 : 0.8
    obj.pillar.material.opacity = day ? 0.55 : 0.55
    const el = obj.label.element
    const priority = selected || ((ratio < LOW_RATIO || ratio > HIGH_RATIO) && index % 4 === 0)
    el.innerHTML = priority ? `<b>${station.id}</b><span>${Math.round(n)}</span>` : `<b>${Math.round(n)}</b>`
    el.classList.toggle('is-selected', selected)
    el.classList.toggle('is-low', ratio < LOW_RATIO)
    el.classList.toggle('is-high', ratio > HIGH_RATIO)
    el.classList.toggle('is-dim', !priority)
    obj.priority = priority
    obj.label.visible = selected || obj.priority
  })
}

function clearTruck() {
  if (truckLabelEl && truckLabelEl.parentNode) truckLabelEl.parentNode.removeChild(truckLabelEl)
  truckLabelEl = null
  if (truckGroup) {
    scene.remove(truckGroup)
    truckGroup.traverse((obj) => {
      if (obj.geometry) obj.geometry.dispose()
      if (obj.material) obj.material.dispose()
    })
  }
  truckGroup = new THREE.Group()
  scene.add(truckGroup)
  truckLabelEl = null
}

function rebuildTruck() {
  clearTruck()
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(2.2, 1.5, 4.5),
    new THREE.MeshStandardMaterial({ color: 0xf5ba59, emissive: 0x473113, emissiveIntensity: .25, metalness: 0.4, roughness: 0.3 })
  )
  body.position.y = 1.2
  truckGroup.add(body)
  const top = new THREE.Mesh(
    new THREE.BoxGeometry(2.05, 1.3, 1.5),
    new THREE.MeshStandardMaterial({ color: 0xc0e9f5, emissive: 0x183e4d, emissiveIntensity: .2 })
  )
  top.position.set(0, 2.1, 1.2)
  truckGroup.add(top)
  const wheelGeometry = new THREE.CylinderGeometry(.42, .42, .25, 12)
  const wheelMaterial = new THREE.MeshStandardMaterial({ color: 0x132530, roughness: .85 })
  for (const x of [-1.15, 1.15]) for (const z of [-1.4, 1.5]) {
    const wheel = new THREE.Mesh(wheelGeometry, wheelMaterial)
    wheel.rotation.z = Math.PI / 2; wheel.position.set(x, .4, z); truckGroup.add(wheel)
  }
  const label = createLabel('运送车', 'twin-truck-label')
  label.position.set(0, 6, 0)
  truckGroup.add(label)
  truckLabelEl = label.element
  truckGroup.visible = false
}

function clearRouteLine() {
  if (!routeLine) return
  scene.remove(routeLine); routeLine.geometry.dispose(); routeLine.material.dispose(); routeLine = null
}
function drawRoadRoute(points) {
  clearRouteLine()
  if (points.length < 2) return
  const geometry = new LineGeometry()
  geometry.setPositions(points.flatMap(p => [p[0], 1.5, p[1]]))
  const material = new LineMaterial({ color: 0xffc76b, linewidth: 3, transparent: true, opacity: .9, depthWrite: false })
  material.resolution.set(container.value.clientWidth, container.value.clientHeight)
  routeLine = new Line2(geometry, material); routeLine.renderOrder = 6; routeLine.computeLineDistances(); scene.add(routeLine)
}
function setFollowing(value) {
  following = value
  emit('follow-change', value)
  if (value) { introActive = false; controls.enabled = true; userNavigated = true; activeView = 'follow' }
}
function followTruck() {
  if (truckGroup?.visible) setFollowing(!following)
}
function routeFor(from, to) {
  if (!roadNetwork) return null
  const a = project(...from), b = project(...to)
  return roadNetwork.route([a.x, a.z], [b.x, b.z])
}
function queueDispatch(item) {
  if (!roadNetwork || !truckGroup || item.kind !== 'dispatch') return
  const route = routeFor(item.from, item.to)
  if (!route) { emit('route-status', { phase: 'blocked', message: '路网不连通，无法显示行驶路线' }); return }
  tripQueue.push({ ...item, route, phase: 'transport' })
  setFollowing(true)
  if (!activeTrip) startNextTrip()
}
function startNextTrip() {
  const next = tripQueue.shift()
  if (!next) return
  // A single truck travels empty to the next pickup; it never teleports between moves.
  if (truckGroup.visible) {
    const first = next.route.points[0]
    if (Math.hypot(truckGroup.position.x - first[0], truckGroup.position.z - first[1]) > 2) {
      const reposition = roadNetwork.route([truckGroup.position.x, truckGroup.position.z], first)
      if (!reposition) { emit('route-status', { phase: 'blocked', message: '接续道路不连通' }); return }
      tripQueue.unshift(next)
      activeTrip = { ...next, route: reposition, phase: 'pickup', qty: 0 }
    } else activeTrip = next
  } else activeTrip = next
  activeTrip.started = performance.now()
  activeTrip.duration = Math.max(4500, activeTrip.route.length / 18 * 1000)
  activeTrip.finished = false
  drawRoadRoute(activeTrip.route.points)
  const p = sampleRoadRoute(activeTrip.route.points, 0)
  truckGroup.position.set(p.x, 1, p.z); truckGroup.rotation.y = p.angle; truckGroup.visible = true
  if (activeTrip.autoFollow !== false) setFollowing(true)
  updateTripStatus(0)
}
function updateTripStatus(progress) {
  if (!activeTrip) return
  const t = activeTrip, percent = Math.round(progress * 100)
  if (t.lastPercent === percent) return
  t.lastPercent = percent
  if (truckLabelEl) truckLabelEl.textContent = `${t.phase === 'pickup' ? '前往取车' : '运送车'} · ${t.qty} 辆 · ${percent}%`
  emit('route-status', { phase: t.finished ? 'arrived' : t.phase, percent, distance: Math.round(t.route.length), from: t.fromId, to: t.toId, qty: t.qty, queued: tripQueue.length, access: Math.round(t.route.accessTo || 0) })
}
function animateTruck(now) {
  if (activeTrip && !activeTrip.finished) {
    const progress = Math.min(1, (now - activeTrip.started) / activeTrip.duration)
    const p = sampleRoadRoute(activeTrip.route.points, activeTrip.route.length * progress)
    truckGroup.position.set(p.x, 1, p.z); truckGroup.rotation.y = p.angle
    activeTrip.finished = progress >= 1
    updateTripStatus(progress)
  } else if (activeTrip?.finished && now - activeTrip.started > activeTrip.duration + 900 && tripQueue.length) {
    const keepFollowing = following
    activeTrip = null
    tripQueue[0].autoFollow = keepFollowing
    startNextTrip()
  }
  if (following && truckGroup?.visible) {
    const alpha = 1 - Math.exp(-Math.min(clock?.getDelta() || .016, .1) * 3)
    const target = truckGroup.position.clone().add(new THREE.Vector3(0, 4, 0))
    const position = target.clone().add(new THREE.Vector3(66, 100, 125))
    controls.target.lerp(target, alpha); camera.position.lerp(position, alpha)
  }
}
function resetTrips() {
  tripQueue = []; activeTrip = null; replayStation = null; setFollowing(false)
  seenArcs.clear()
  if (truckGroup) truckGroup.visible = false
  if (scene) clearRouteLine()
  if (campusBounds) setView('overview')
  emit('route-status', null)
}
function updateTruck() {
  if (props.displayMode !== 'replay' || !roadNetwork || !truckGroup) return
  const truck = props.stepData?.truck, station = props.stations[truck?.station]
  if (!station) return
  if (replayStation === station.id) return
  const previous = props.stations.find(s => s.id === replayStation)
  replayStation = station.id
  if (!previous) {
    const p = project(station.lng, station.lat), near = roadNetwork.nearest([p.x, p.z])
    if (near) { truckGroup.position.set(near.point[0], 1, near.point[1]); truckGroup.visible = true }
    return
  }
  const route = routeFor([previous.lng, previous.lat], [station.lng, station.lat])
  if (!route) return
  activeTrip = null; tripQueue = [{ route, fromId: previous.id, toId: station.id, qty: truck.load || 0, phase: 'transport', autoFollow: false }]
  startNextTrip()
  activeTrip.duration = 850
}
function updateRoute() { /* Route geometry follows the active road trip, not station-to-station chords. */ }

function updateHeatmap() {
  if (!scene || !campusData) return
  const signature = props.heatMode + props.heatPoints.map(p => `${p.id}:${p.lng},${p.lat},${p.value}`).join('|')
  if (signature === heatSignature) return
  heatSignature = signature
  if (heatMesh) { scene.remove(heatMesh); heatMesh.geometry.dispose(); heatMesh.material.map.dispose(); heatMesh.material.dispose(); heatMesh = null }
  if (props.heatMode === 'off' || !props.heatPoints.length) return
  const boundary = campusData.boundary.map(p => project(...p))
  const box = new THREE.Box3().setFromPoints(boundary), size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3())
  const canvas = document.createElement('canvas'); canvas.width = 1024; canvas.height = Math.ceil(1024 * size.z / size.x)
  const ctx = canvas.getContext('2d'), pixel = p => [(p.x - box.min.x) / size.x * canvas.width, (p.z - box.min.z) / size.z * canvas.height]
  const scale = canvas.width / size.x
  // Fixed zero and actual maximum; equal values retain equal colour, never invented hot spots.
  const max = Math.max(...props.heatPoints.map(p => p.value), 0)
  if (max <= 0) return
  ctx.save(); ctx.beginPath()
  boundary.forEach((p, i) => { const [x, y] = pixel(p); if (!i) ctx.moveTo(x, y); else ctx.lineTo(x, y) })
  ctx.closePath(); ctx.clip()
  props.heatPoints.forEach(item => {
    if (item.value <= 0) return
    const [x, y] = pixel(project(item.lng, item.lat)), ratio = item.value / max, radius = (22 + ratio * 14) * scale
    const rgb = ratio > .66 ? '248,82,62' : ratio > .33 ? '245,184,58' : '43,164,229'
    const g = ctx.createRadialGradient(x, y, 0, x, y, radius)
    g.addColorStop(0, `rgba(${rgb},.88)`); g.addColorStop(.4, `rgba(${rgb},.6)`); g.addColorStop(1, `rgba(${rgb},0)`)
    ctx.fillStyle = g; ctx.fillRect(x - radius, y - radius, radius * 2, radius * 2)
  })
  ctx.restore()
  const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace
  const geo = new THREE.PlaneGeometry(size.x, size.z); geo.rotateX(-Math.PI / 2)
  heatMesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ map: texture, transparent: true, opacity: .68, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 }))
  heatMesh.position.set(center.x, 1.1, center.z); heatMesh.renderOrder = 3; scene.add(heatMesh)
}

function pickStation(event) {
  if (!renderer || !camera || !stationGroup) return ''
  const rect = renderer.domElement.getBoundingClientRect()
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointer, camera)
  const hits = raycaster.intersectObjects(stationGroup.children, true)
  for (const hit of hits) {
    if (hit.object.userData.stationId) return hit.object.userData.stationId
  }
  return ''
}

function onPointerDown(event) {
  pointerDownPos = { x: event.clientX, y: event.clientY }
}

function onPointerUp(event) {
  if (!pointerDownPos) return
  const moved = Math.hypot(event.clientX - pointerDownPos.x, event.clientY - pointerDownPos.y)
  pointerDownPos = null
  if (moved > 6) return
  emit('select', pickStation(event))
}

function onPointerMove(event) {
  if (!renderer || !camera) return
  renderer.domElement.style.cursor = pickStation(event) ? 'pointer' : 'grab'
}

function setupScene() {
  const width = container.value.clientWidth
  const height = container.value.clientHeight
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x061422)
  scene.fog = new THREE.FogExp2(0x030b15, 0.00026)
  camera = new THREE.PerspectiveCamera(34, width / height, 1, 12000)
  camera.position.set(0, 1120, 1440)
  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' })
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFShadowMap
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
  renderer.setSize(width, height)
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.12
  container.value.appendChild(renderer.domElement)

  labelRenderer = new CSS2DRenderer()
  labelRenderer.setSize(width, height)
  labelRenderer.domElement.style.position = 'absolute'
  labelRenderer.domElement.style.inset = '0'
  labelRenderer.domElement.style.pointerEvents = 'none'
  container.value.appendChild(labelRenderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.06
  controls.target.set(0, 10, 0)
  controls.minDistance = 65
  controls.maxDistance = 6000
  controls.maxPolarAngle = Math.PI / 2.05
  controls.enablePan = true
  controls.autoRotate = false
  controls.addEventListener('start', () => { userNavigated = true; introActive = false; setFollowing(false) })
  raycaster = new THREE.Raycaster()
  pointer = new THREE.Vector2()
  renderer.domElement.addEventListener('pointerdown', onPointerDown)
  renderer.domElement.addEventListener('pointerup', onPointerUp)
  renderer.domElement.addEventListener('pointermove', onPointerMove)

  hemiLight = new THREE.HemisphereLight(0x4fbfe6, 0x050d16, 0.55)
  scene.add(hemiLight)
  dirLight = new THREE.DirectionalLight(0xbfeeff, 1.15)
  dirLight.position.set(-650, 1050, 450)
  dirLight.castShadow = true
  dirLight.shadow.mapSize.set(2048, 2048)
  dirLight.shadow.camera.left = -900
  dirLight.shadow.camera.right = 900
  dirLight.shadow.camera.top = 900
  dirLight.shadow.camera.bottom = -900
  dirLight.shadow.camera.near = 200
  dirLight.shadow.camera.far = 2600
  dirLight.shadow.bias = -0.00012
  dirLight.shadow.normalBias = 1.1
  dirLight.shadow.camera.updateProjectionMatrix()
  scene.add(dirLight)
  fillLight = new THREE.DirectionalLight(0x1f5d86, 0.5)
  fillLight.position.set(600, 500, -700)
  scene.add(fillLight)

  const grid = new THREE.GridHelper(1800, 45, 0x1c5d76, 0x0d3448)
  grid.position.y = -PLATE_DEPTH - 13.2
  grid.material.transparent = true
  grid.material.opacity = 0.17
  scene.add(grid)

  composer = new EffectComposer(renderer)
  composer.addPass(new RenderPass(scene, camera))
  bloom = new UnrealBloomPass(new THREE.Vector2(width, height), 0.5, 0.45, 0.55)
  composer.addPass(bloom)
  composer.addPass(new OutputPass())
  clock = new THREE.Timer()
  clock.connect(document)

  resizeObserver = new ResizeObserver(resize)
  resizeObserver.observe(container.value)
}

function fitOverview(direction = new THREE.Vector3(.32, 1.0, 1.25)) {
  if (!campusBounds || !camera || !container.value) return
  overviewTarget.copy(campusBounds.getCenter(new THREE.Vector3())).setY(8)
  direction.normalize()
  const corners = campusData.boundary.flatMap((p) => [project(...p), project(...p).setY(-PLATE_DEPTH - 10)])
  campusData.buildings.forEach((b) => b.p.forEach((p) => corners.push(project(...p).setY((b.h || 10) * 1.2))))
  let distance = 900
  const safeX = container.value.clientWidth < 1100 ? .43 : .55
  for (let i = 0; i < 90; i += 1) {
    camera.position.copy(overviewTarget).addScaledVector(direction, distance)
    camera.lookAt(overviewTarget); camera.updateMatrixWorld()
    const projected = corners.map((p) => p.clone().project(camera))
    if (projected.every((p) => Math.abs(p.x) < safeX && Math.abs(p.y) < .77)) break
    distance *= 1.025
  }
  overviewPosition.copy(camera.position)
}

function playIntro() {
  if (!camera || !controls || !campusBounds) return
  fitOverview(); introActive = true; userNavigated = false; introStart = performance.now()
  introTo.copy(overviewPosition)
  introFrom.copy(overviewTarget).add(overviewPosition.clone().sub(overviewTarget).multiplyScalar(1.5))
  introFrom.y += 450; camera.position.copy(introFrom)
  controls.target.copy(overviewTarget); controls.enabled = false
}

function setView(name) {
  if (!camera || !controls || !campusBounds) return
  activeView = name; userNavigated = false; introActive = false; controls.enabled = true
  fitOverview()
  controls.target.copy(overviewTarget)
  setFollowing(false)
  camera.position.copy(overviewPosition)
  controls.update()
}

function focusStation(id) {
  const station = props.stations.find((s) => s.id === id)
  if (!station || !camera || !controls) return
  setFollowing(false); userNavigated = true
  const p = project(station.lng, station.lat)
  controls.target.copy(p).setY(12)
  camera.position.copy(p).add(new THREE.Vector3(180, 280, 320))
  controls.update()
}

function resize() {
  if (!container.value || !renderer || !camera) return
  const width = container.value.clientWidth
  const height = container.value.clientHeight
  camera.aspect = width / height
  camera.setViewOffset(width, height, 0, height * .035, width, height)
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
  labelRenderer.setSize(width, height)
  composer.setSize(width, height)
  if (campusBounds && !introActive && !userNavigated && activeView === 'overview') {
    setView(activeView)
  }
  if (routeLine) routeLine.material.resolution.set(width, height)
  bloom.setSize(width, height)
  boundaryMaterials.forEach((m) => m.resolution.set(width, height))
}

function animate() {
  animationId = requestAnimationFrame(animate)
  if (clock) clock.update()
  const elapsed = clock ? clock.getElapsed() : 0
  if (introActive) {
    const t = Math.min((performance.now() - introStart) / 4200, 1)
    const e = 1 - Math.pow(1 - t, 3)
    camera.position.lerpVectors(introFrom, introTo, e)
    camera.lookAt(controls.target)
    if (t >= 1) {
      introActive = false
      controls.enabled = true
    }
  }
  animateTruck(performance.now())
  if (controls) controls.update()
  if (props.showLabels && camera && ++labelFrame % 8 === 0) {
    camera.updateMatrixWorld()
    const occupied = []
    const width = container.value.clientWidth, height = container.value.clientHeight
    const sorted = [...buildingLabels].sort((a, b) => Number(/图书馆|教学楼|餐厅/.test(b.userData.labelName)) - Number(/图书馆|教学楼|餐厅/.test(a.userData.labelName)))
    sorted.forEach((obj) => {
      const p = obj.position.clone().project(camera)
      const x = (p.x + 1) * width / 2, y = (1 - p.y) * height / 2
      const w = Math.min(150, obj.userData.labelName.length * 12 + 12)
      const box = { x: x - w/2, y: y - 12, w, h: 26 }
      obj.visible = p.z < 1 && y > 90 && y < height - 100 && !occupied.some((r) => box.x < r.x+r.w && box.x+box.w > r.x && box.y < r.y+r.h && box.y+box.h > r.y)
      if (obj.visible) occupied.push(box)
    })
  }
  if (stationObjects.size && camera && controls) {
    const distance = camera.position.distanceTo(controls.target)
    const showAllLabels = distance < 700
    stationObjects.forEach((obj) => {
      obj.group.scale.setScalar(THREE.MathUtils.clamp(distance / 700, .18, 1))
      obj.label.visible = showAllLabels || obj.priority
    })
  }
  if (bikePoints && bikeOrder.length) {
    const attr = bikeGeometry.attributes.position
    const arr = attr.array
    for (let i = 0; i < bikeOrder.length; i += 1) {
      const st = bikeState.get(bikeOrder[i])
      if (!st) continue
      st.x += (st.tx - st.x) * 0.14
      st.z += (st.tz - st.z) * 0.14
      arr[i * 3] = st.x
      arr[i * 3 + 2] = st.z
    }
    attr.needsUpdate = true
  }
  if (composer) composer.render()
  if (labelRenderer) labelRenderer.render(scene, camera)
}

async function loadData() {
  try {
    campusData = await fetch(`/data/campus-twin.json?ts=${Date.now()}`).then((r) => {
      if (!r.ok) throw new Error('校园建筑数据加载失败')
      return r.json()
    })
    buildCampusGround()
    buildOuterBuildings()
    buildBuildings()
    buildContactShadows()
    buildSurfaces()
    buildLandscape()
    buildRoads()
    roadNetwork = createRoadNetwork(campusData.roads, (lng, lat) => { const p = project(lng, lat); return [p.x, p.z] }, campusData.buildings.map(b => b.p))
    updateHeatmap()
    buildLabels()
    buildBikeLayer()
    updateBikes()
    rebuildStations()
    rebuildNoParking()
    rebuildTruck()
    updateTruck()
    updateRoute()
    applyTheme(props.theme)
    for (const item of props.arcs) if (!seenArcs.has(item.id)) { seenArcs.add(item.id); queueDispatch(item) }
    emit('ready')
  } catch (e) {
    error.value = e.message || '三维场景加载失败'
    emit('error', e)
  }
}

onMounted(async () => {
  await nextTick()
  setupScene()
  animate()
  await loadData()
  playIntro()
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animationId)
  if (clock) clock.dispose()
  if (renderer) {
    renderer.domElement.removeEventListener('pointerdown', onPointerDown)
    renderer.domElement.removeEventListener('pointerup', onPointerUp)
    renderer.domElement.removeEventListener('pointermove', onPointerMove)
  }
  if (resizeObserver) resizeObserver.disconnect()
  if (controls) controls.dispose()
  if (composer) composer.dispose()
  if (scene) {
    scene.traverse((obj) => {
      if (obj.geometry) obj.geometry.dispose()
      if (obj.material) {
        const mats = Array.isArray(obj.material) ? obj.material : [obj.material]
        mats.forEach((m) => { if (m.map) m.map.dispose() })
        if (Array.isArray(obj.material)) obj.material.forEach((m) => m.dispose())
        else obj.material.dispose()
      }
    })
  }
  if (renderer) renderer.dispose()
  if (labelRenderer && labelRenderer.domElement && labelRenderer.domElement.parentNode) {
    labelRenderer.domElement.parentNode.removeChild(labelRenderer.domElement)
  }
})

watch(() => props.stations, () => {
  if (scene) {
    rebuildStations()
    rebuildTruck()
    updateTruck()
    updateRoute()
  }
}, { deep: true })
watch(() => props.noParking, () => {
  if (scene) rebuildNoParking()
}, { deep: true })
watch(() => props.stepData, () => {
  updateStationVisuals()
  updateTruck()
  updateRoute()
})
watch(() => props.selected, updateStationVisuals)
watch(() => props.bikes, updateBikes)
watch(() => props.theme, applyTheme)
watch(() => props.showLabels, (v) => {
  buildingLabels.forEach((obj) => { obj.visible = Boolean(v) })
})
watch(() => props.arcs, (list) => {
  if (!roadNetwork || !list || !list.length) return
  for (const item of list.slice(-40)) {
    if (!item || seenArcs.has(item.id)) continue
    seenArcs.add(item.id)
    queueDispatch(item)
  }
  if (seenArcs.size > 800) seenArcs.clear()
})
watch(() => props.truckPath, updateRoute, { deep: true })

watch(() => props.sessionKey, resetTrips)
watch(() => [props.heatPoints, props.heatMode], updateHeatmap)
defineExpose({ playIntro, setView, focusStation, followTruck, resize })
</script>

<style>
.twin-scene { position: absolute; inset: 0; overflow: hidden; background: #030b15; }
.twin-scene canvas { display: block; }
.twin-error {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  color: #9fb8d0; font-size: 18px; background: #030b15; z-index: 5;
}
.twin-label, .twin-point-label, .twin-truck-label {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 4px 8px; border: 1px solid rgba(59, 176, 201, .55); border-radius: 4px;
  background: rgba(4, 18, 30, .9); color: #dff9ff; white-space: nowrap;
  font: 14px/1.25 "Microsoft YaHei", sans-serif; pointer-events: none;
}
.twin-point-label b, .twin-truck-label b { color: #69efff; font: 500 14px/1.2 Consolas, monospace; }
.twin-point-label span, .twin-truck-label span { color: #9fc2d8; font-size: 14px; }
.twin-point-label.is-low { border-color: rgba(239, 91, 91, .8); }
.twin-point-label.is-low b { color: #ff8a8a; }
.twin-point-label.is-high { border-color: rgba(242, 178, 75, .8); }
.twin-point-label.is-high b { color: #ffd078; }
.twin-point-label.is-selected { border-color: #ffcf7e; background: rgba(50, 34, 13, .96); }
.twin-point-label.is-selected b { color: #ffcf7e; }
.twin-point-label.is-dim { padding: 0; border: 0; background: transparent; opacity: .85; transform: none; text-shadow: 0 0 7px rgba(3,16,26,.95); }
.twin-point-label.is-dim b { color: #9fe6f4; font-size: 13px; }
.twin-building-label {
  padding: 1px 6px; color: #123849; white-space: nowrap; pointer-events: none;
  font: 500 13px/1.3 "Microsoft YaHei", sans-serif;
  text-shadow: 0 0 4px #fff, 0 0 8px #fff, 0 0 14px #fff;
  max-width: 150px; overflow: hidden; text-overflow: ellipsis;
}
.twin-building-label.night {
  color: #d9f4ff;
  text-shadow: 0 0 5px rgba(2, 16, 28, .95), 0 0 10px rgba(2, 16, 28, .85);
}
.twin-nopark-label {
  display: flex; flex-direction: row; align-items: center; gap: 5px;
  padding: 3px 6px; border: 1px solid rgba(239, 91, 91, .65); border-radius: 3px;
  background: rgba(45, 10, 14, .9); color: #ffb0b0; white-space: nowrap;
  font: 14px/1.25 "Microsoft YaHei", sans-serif; pointer-events: none;
}
.twin-nopark-label b { color: #ff8585; font-size: 11px; font-weight: 500; }
.twin-nopark-label span { color: #c98c8c; font-size: 11px; }
</style>
