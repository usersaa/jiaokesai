<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">点位管理</h1>
        <div class="page-sub">P 点坐标、容量、功能与初始库存</div>
      </div>
      <div class="row" v-if="canEdit">
        <label class="btn" style="display:inline-flex;align-items:center;">
          导入 CSV
          <input type="file" accept=".csv" style="display:none" @change="importCsv" />
        </label>
        <label class="btn" style="display:inline-flex;align-items:center;">
          导入 JSON
          <input type="file" accept=".json" style="display:none" @change="importJson" />
        </label>
        <button class="btn" @click="exportCsv">导出 CSV</button>
        <button class="btn" @click="exportJson">导出 JSON</button>
        <button class="btn btn-primary" @click="openCreate">新增点位</button>
      </div>
    </div>

    <div v-if="loading" class="empty">正在加载点位…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <template v-else>
      <div class="stat-grid">
        <div class="stat-card"><span>停车点总数</span><b>{{ parkingCount }}</b><small>另有 {{ noParkCount }} 个禁停区</small></div>
        <div class="stat-card"><span>总停车容量</span><b>{{ totalCapacity }}</b><small>辆</small></div>
        <div class="stat-card"><span>初始投放车辆</span><b>{{ totalBikes }}</b><small>辆</small></div>
        <div class="stat-card"><span>平均占用率</span><b>{{ avgOccupancy }}%</b><small>初始车辆 / 容量</small></div>
      </div>

      <Panel title="点位台账">
        <div class="toolbar">
          <div class="toolbar-left">
            <input v-model.trim="keyword" class="search-input" placeholder="搜索编号或点位名称" />
            <select v-model="funcFilter" class="select filter-select">
              <option value="">全部功能</option>
              <option v-for="f in funcOptions" :key="f.value" :value="f.value">{{ f.label }}</option>
            </select>
          </div>
          <div class="toolbar-right"><span class="form-note">显示 {{ filteredStations.length }} 个点位</span></div>
        </div>
        <table class="table">
          <thead>
            <tr>
              <th>点位</th><th>功能</th><th>容量</th><th>初始车辆</th><th>占用状态</th>
              <th>坐标</th><th v-if="canEdit">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in filteredStations" :key="s.id">
              <td>
                <div class="point-cell">
                  <span class="point-code mono">{{ s.id }}</span>
                  <div><b>{{ s.name }}</b><small>{{ Number(s.lng).toFixed(5) }}, {{ Number(s.lat).toFixed(5) }}</small></div>
                </div>
              </td>
              <td><span class="tag">{{ funcLabel(s.func) }}</span></td>
              <td class="mono">{{ s.capacity }}</td>
              <td class="mono">{{ s.init_bikes }}</td>
              <td>
                <div class="occ-cell">
                  <span class="tag" :class="statusClass(s)">{{ statusLabel(s) }}</span>
                  <div class="occ-track"><i :style="{ width: occupancy(s) + '%' }"></i></div>
                  <small>{{ occupancy(s) }}%</small>
                </div>
              </td>
              <td class="coord-cell mono">{{ Number(s.lng).toFixed(5) }}<br>{{ Number(s.lat).toFixed(5) }}</td>
              <td v-if="canEdit">
                <div class="row-actions">
                  <button class="btn btn-sm" @click="openEdit(s)">编辑</button>
                  <button class="btn btn-sm btn-danger" @click="remove(s)">删除</button>
                </div>
              </td>
            </tr>
            <tr v-if="!filteredStations.length"><td :colspan="canEdit ? 7 : 6" class="empty">没有符合条件的点位</td></tr>
          </tbody>
        </table>
      </Panel>
    </template>

    <div v-if="modal" class="modal-mask" @click.self="modal = false">
      <div class="modal">
        <h3>{{ editing ? '编辑点位' : '新增点位' }}</h3>
        <div class="form-grid">
          <div>
            <label class="field">编号</label>
            <input v-model.trim="form.id" class="input w-full" :disabled="!!editing" placeholder="P13" />
          </div>
          <div>
            <label class="field">名称</label>
            <input v-model.trim="form.name" class="input w-full" />
          </div>
          <div>
            <label class="field">功能</label>
            <select v-model="form.func" class="select w-full">
              <option v-for="f in funcOptions" :key="f.value" :value="f.value">{{ f.label }}</option>
            </select>
          </div>
          <div class="grid grid-2">
            <div>
              <label class="field">经度</label>
              <input v-model.number="form.lng" class="input w-full" type="number" step="0.000001" />
            </div>
            <div>
              <label class="field">纬度</label>
              <input v-model.number="form.lat" class="input w-full" type="number" step="0.000001" />
            </div>
          </div>
          <div class="grid grid-2">
            <div>
              <label class="field">容量</label>
              <input v-model.number="form.capacity" class="input w-full" type="number" />
            </div>
            <div>
              <label class="field">初始车辆</label>
              <input v-model.number="form.init_bikes" class="input w-full" type="number" />
            </div>
          </div>
        </div>
        <p v-if="modalError" class="err">{{ modalError }}</p>
        <div class="row mt-24" style="justify-content:flex-end;">
          <button class="btn" @click="modal = false">取消</button>
          <button class="btn btn-primary" :disabled="saving" @click="save">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api/client'
import Panel from '../components/Panel.vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const canEdit = computed(() => auth.role !== 'viewer')
const stations = ref([])
const loading = ref(true)
const error = ref('')
const modal = ref(false)
const editing = ref(null)
const saving = ref(false)
const modalError = ref('')
const keyword = ref('')
const funcFilter = ref('')
const parkingCount = computed(() => stations.value.filter((s) => s.func !== 'nopark').length)
const noParkCount = computed(() => stations.value.filter((s) => s.func === 'nopark').length)
const totalCapacity = computed(() => stations.value.reduce((sum, s) => sum + Number(s.capacity || 0), 0))
const totalBikes = computed(() => stations.value.reduce((sum, s) => sum + Number(s.init_bikes || 0), 0))
const avgOccupancy = computed(() => totalCapacity.value ? Math.round(totalBikes.value / totalCapacity.value * 100) : 0)
const filteredStations = computed(() => {
  const q = keyword.value.toLowerCase()
  return stations.value.filter((s) => {
    const matchKeyword = !q || [s.id, s.name].some((v) => String(v || '').toLowerCase().includes(q))
    return matchKeyword && (!funcFilter.value || s.func === funcFilter.value)
  })
})

const funcOptions = [
  { value: 'dorm', label: '宿舍区' },
  { value: 'teach', label: '教学区' },
  { value: 'canteen', label: '食堂' },
  { value: 'library', label: '图书馆' },
  { value: 'gate', label: '校门' },
  { value: 'sport', label: '运动场' },
  { value: 'nopark', label: '禁停区' },
  { value: 'other', label: '其他' }
]

const form = reactive({
  id: '', name: '', lng: 103.723371, lat: 36.105326,
  capacity: 30, func: 'other', attraction: 0.5, init_bikes: 0, target_bikes: 0
})

function funcLabel(f) {
  return (funcOptions.find((x) => x.value === f) || {}).label || '其他'
}

function occupancy(s) {
  return s.capacity ? Math.min(100, Math.round(Number(s.init_bikes || 0) / Number(s.capacity) * 100)) : 0
}

function statusLabel(s) {
  if (s.func === 'nopark') return '禁停区'
  const ratio = occupancy(s)
  if (ratio < 20) return '库存偏低'
  if (ratio > 80) return '库存偏高'
  return '库存正常'
}

function statusClass(s) {
  if (s.func === 'nopark') return 'tag-red'
  const ratio = occupancy(s)
  if (ratio < 20) return 'tag-red'
  if (ratio > 80) return 'tag-amber'
  return 'tag-green'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/stations')
    stations.value = data
  } catch (e) {
    error.value = (e.response && e.response.data && e.response.data.detail) || '加载失败'
  } finally {
    loading.value = false
  }
}

function resetForm() {
  Object.assign(form, {
    id: '', name: '', lng: 103.723371, lat: 36.105326,
    capacity: 30, func: 'other', attraction: 0.5, init_bikes: 0, target_bikes: 0
  })
}

function openCreate() {
  editing.value = null
  modalError.value = ''
  resetForm()
  modal.value = true
}

function openEdit(s) {
  editing.value = s
  modalError.value = ''
  Object.assign(form, {
    id: s.id, name: s.name, lng: s.lng, lat: s.lat,
    capacity: s.capacity, func: s.func, attraction: s.attraction,
    init_bikes: s.init_bikes, target_bikes: s.target_bikes
  })
  modal.value = true
}

async function save() {
  if (!form.id || !form.name) {
    modalError.value = '编号和名称不能为空'
    return
  }
  saving.value = true
  modalError.value = ''
  try {
    if (editing.value) {
      await api.put(`/stations/${editing.value.id}`, { ...form })
    } else {
      await api.post('/stations', { ...form })
    }
    modal.value = false
    await load()
  } catch (e) {
    modalError.value = (e.response && e.response.data && e.response.data.detail) || '保存失败'
  } finally {
    saving.value = false
  }
}

async function remove(s) {
  if (!confirm(`确定删除 ${s.id} · ${s.name}？`)) return
  try {
    await api.delete(`/stations/${s.id}`)
    await load()
  } catch (e) {
    alert((e.response && e.response.data && e.response.data.detail) || '删除失败')
  }
}

async function importCsv(ev) {
  const file = ev.target.files && ev.target.files[0]
  if (!file) return
  const fd = new FormData()
  fd.append('file', file)
  try {
    await api.post('/stations/import', fd)
    await load()
  } catch (e) {
    alert((e.response && e.response.data && e.response.data.detail) || '导入失败')
  }
  ev.target.value = ''
}

async function exportCsv() {
  try {
    const res = await api.get('/stations/export', { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = 'stations.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    alert('导出失败')
  }
}

async function importJson(ev) {
  const file = ev.target.files && ev.target.files[0]
  if (!file) return
  try {
    const obj = JSON.parse(await file.text())
    const list = Array.isArray(obj) ? obj : obj.stations
    if (!Array.isArray(list)) throw new Error('文件中未找到点位数据')
    for (const s of list) {
      const payload = {
        id: s.id, name: s.name || s.id, lng: Number(s.lng), lat: Number(s.lat),
        capacity: Number(s.capacity || 30), func: s.func || 'other', attraction: Number(s.attraction || 0.5),
        init_bikes: Number(s.init_bikes != null ? s.init_bikes : (s.count || 0)),
        target_bikes: Number(s.target_bikes || 0)
      }
      if (stations.value.some((item) => item.id === payload.id)) await api.put(`/stations/${payload.id}`, payload)
      else await api.post('/stations', payload)
    }
    await load()
    alert(`已导入 ${list.length} 个点位`)
  } catch (e) {
    alert((e.response && e.response.data && e.response.data.detail) || e.message || '导入失败')
  }
  ev.target.value = ''
}

function exportJson() {
  const payload = {
    meta: { campus: '兰州交通大学', coordSys: 'GCJ-02（高德坐标系）', count: stations.value.length },
    stations: stations.value
  }
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = 'stations.json'
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(load)
</script>

<style scoped>
.err { color: #ff9b9b; font-size: 14px; margin-top: 12px; }
.filter-select { width: 142px; height: 38px; font-size: 15px; }
.point-cell { display: flex; align-items: center; gap: 11px; }
.point-code { width: 42px; height: 30px; display: flex; align-items: center; justify-content: center; border: 1px solid #24526b; border-radius: 5px; background: #0c2a3d; color: #68e5f2; font-size: 14px; }
.point-cell b { display: block; font-weight: 500; color: #e2f1fe; }
.point-cell small { display: block; color: #5f7f9d; font-size: 14px; }
.occ-cell { display: grid; grid-template-columns: 48px 88px 38px; align-items: center; gap: 8px; }
.occ-track { height: 4px; background: #17344f; border-radius: 2px; overflow: hidden; }
.occ-track i { display: block; height: 100%; background: #22d3ee; }
.occ-cell small { color: #8ba3c7; font-size: 14px; }
.coord-cell { color: #7895b2; font-size: 14px; line-height: 1.5; }
</style>
