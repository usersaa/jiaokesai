<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">方案管理</h1>
        <div class="page-sub">保存参数、种子与模型版本，随时回看</div>
      </div>
      <button v-if="canEdit" class="btn btn-primary" @click="openCreate">新建方案</button>
    </div>

    <div v-if="loading" class="empty">正在加载方案…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <template v-else>
      <div class="stat-grid">
        <div class="stat-card"><span>方案总数</span><b>{{ scenarios.length }}</b><small>可复用的调度配置</small></div>
        <div class="stat-card"><span>PPO 方案</span><b>{{ ppoCount }}</b><small>使用当前调度模型</small></div>
        <div class="stat-card"><span>最近更新</span><b class="recent-value">{{ latestName }}</b><small>{{ latestTime }}</small></div>
        <div class="stat-card"><span>模型版本</span><b class="model-value">seed0</b><small>ppo_seed0</small></div>
      </div>

      <Panel title="方案列表">
        <table class="table">
          <thead>
            <tr><th>方案名称</th><th>策略</th><th>随机种子</th><th>模型版本</th><th>创建时间</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="s in scenarios" :key="s.id">
              <td><b class="scenario-name">{{ s.name }}</b></td>
              <td><span class="tag" :class="(s.config_json && s.config_json.policy) === 'ppo' ? 'tag-blue' : ''">{{ policyLabel(s.config_json && s.config_json.policy) }}</span></td>
              <td class="mono">{{ s.seed }}</td>
              <td class="mono model-cell">{{ s.model_version }}</td>
              <td class="mono time-cell">{{ formatTime(s.created_at) }}</td>
              <td>
                <div class="row-actions">
                  <button class="btn btn-sm" @click="runScenario(s)">运行</button>
                  <button v-if="canEdit" class="btn btn-sm" @click="openEdit(s)">编辑</button>
                  <button v-if="canEdit" class="btn btn-sm btn-danger" @click="remove(s)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </Panel>
    </template>

    <div v-if="modal" class="modal-mask" @click.self="modal = false">
      <div class="modal">
        <h3>{{ editing ? '编辑方案' : '新建方案' }}</h3>
        <div class="form-grid">
          <div>
            <label class="field">方案名称</label>
            <input v-model.trim="form.name" class="input w-full" />
          </div>
          <div>
            <label class="field">调度策略</label>
            <select v-model="form.policy" class="select w-full">
              <option value="ppo">PPO 策略</option>
              <option value="greedy">约束贪心</option>
              <option value="noop">不调度</option>
            </select>
          </div>
          <div>
            <label class="field">随机种子</label>
            <input v-model.number="form.seed" class="input w-full" type="number" />
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
import { useRouter } from 'vue-router'
import api from '../api/client'
import Panel from '../components/Panel.vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const canEdit = computed(() => auth.role !== 'viewer')
const scenarios = ref([])
const loading = ref(true)
const error = ref('')
const modal = ref(false)
const editing = ref(null)
const saving = ref(false)
const modalError = ref('')
const form = reactive({ name: '', policy: 'ppo', seed: 101 })
const ppoCount = computed(() => scenarios.value.filter((s) => (s.config_json && s.config_json.policy) === 'ppo').length)
const latest = computed(() => [...scenarios.value].sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')))[0] || {})
const latestName = computed(() => latest.value.name || '暂无')
const latestTime = computed(() => formatTime(latest.value.created_at))

function policyLabel(p) {
  return { ppo: 'PPO 策略', greedy: '约束贪心', noop: '不调度' }[p] || p || '—'
}

function formatTime(t) {
  if (!t) return '—'
  return String(t).replace('T', ' ').slice(0, 19)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/scenarios')
    scenarios.value = data
  } catch (e) {
    error.value = (e.response && e.response.data && e.response.data.detail) || '加载失败'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  modalError.value = ''
  Object.assign(form, { name: '', policy: 'ppo', seed: 101 })
  modal.value = true
}

function openEdit(s) {
  editing.value = s
  modalError.value = ''
  Object.assign(form, {
    name: s.name,
    policy: (s.config_json && s.config_json.policy) || 'ppo',
    seed: s.seed
  })
  modal.value = true
}

async function save() {
  if (!form.name) {
    modalError.value = '请填写方案名称'
    return
  }
  saving.value = true
  modalError.value = ''
  const payload = {
    name: form.name,
    config_json: { policy: form.policy, seed: Number(form.seed) },
    seed: Number(form.seed),
    model_version: 'ppo_seed0'
  }
  try {
    if (editing.value) await api.put(`/scenarios/${editing.value.id}`, payload)
    else await api.post('/scenarios', payload)
    modal.value = false
    await load()
  } catch (e) {
    modalError.value = (e.response && e.response.data && e.response.data.detail) || '保存失败'
  } finally {
    saving.value = false
  }
}

async function remove(s) {
  if (!confirm(`确定删除方案「${s.name}」？`)) return
  try {
    await api.delete(`/scenarios/${s.id}`)
    await load()
  } catch (e) {
    alert((e.response && e.response.data && e.response.data.detail) || '删除失败')
  }
}

function runScenario(s) {
  router.push({ path: '/app/simulation', query: { scenario: s.id } })
}

onMounted(load)
</script>

<style scoped>
.err { color: #ff9b9b; font-size: 14px; margin-top: 12px; }
.scenario-name { color: #e2f1fe; font-weight: 500; }
.model-cell { color: #79b6d5; }
.time-cell { color: #7895b2; font-size: 14px; }
.recent-value { font-family: var(--font); font-size: 20px; }
.model-value { font-size: 22px; }
</style>
