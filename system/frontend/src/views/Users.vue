<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">用户管理</h1>
        <div class="page-sub">账号、角色与审核</div>
      </div>
      <button class="btn btn-primary" @click="openCreate">新建账号</button>
    </div>

    <div v-if="loading" class="empty">正在加载用户…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <template v-else>
      <div class="stat-grid">
        <div class="stat-card"><span>账号总数</span><b>{{ users.length }}</b><small>系统内全部账号</small></div>
        <div class="stat-card"><span>待审核</span><b>{{ pendingCount }}</b><small>需要管理员处理</small></div>
        <div class="stat-card"><span>调度员</span><b>{{ operatorCount }}</b><small>可运行推演与维护点位</small></div>
        <div class="stat-card"><span>已启用</span><b>{{ activeCount }}</b><small>当前可登录账号</small></div>
      </div>

      <Panel title="用户列表">
        <div class="toolbar">
          <div class="toolbar-left">
            <input v-model.trim="keyword" class="search-input" placeholder="搜索用户名或显示名" />
            <select v-model="roleFilter" class="select filter-select">
              <option value="">全部角色</option>
              <option value="admin">管理员</option>
              <option value="operator">调度员</option>
              <option value="viewer">观察者</option>
            </select>
          </div>
          <div class="toolbar-right"><span class="form-note">共 {{ filteredUsers.length }} 个账号</span></div>
        </div>
        <table class="table">
          <thead>
            <tr><th>账号</th><th>角色</th><th>状态</th><th>创建时间</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="u in filteredUsers" :key="u.id">
              <td>
                <div class="identity">
                  <span class="identity-avatar">{{ (u.display_name || u.username).slice(0, 1) }}</span>
                  <div class="identity-name"><b>{{ u.display_name || u.username }}</b><small>{{ u.username }}</small></div>
                </div>
              </td>
              <td>
                <select
                  class="select role-select"
                  :value="u.role"
                  @change="updateRole(u, $event.target.value)"
                >
                  <option value="admin">管理员</option>
                  <option value="operator">调度员</option>
                  <option value="viewer">观察者</option>
                </select>
              </td>
              <td><span class="tag" :class="statusClass(u)">{{ statusLabel(u) }}</span></td>
              <td class="mono time-cell">{{ formatTime(u.created_at) }}</td>
              <td>
                <div class="row-actions">
                  <button v-if="u.approval_status === 'pending'" class="btn btn-sm" @click="approve(u)">通过</button>
                  <button v-if="u.approval_status === 'pending'" class="btn btn-sm btn-danger" @click="reject(u)">拒绝</button>
                  <button class="btn btn-sm" @click="resetPassword(u)">重置密码</button>
                  <button class="btn btn-sm btn-danger" @click="remove(u)">删除</button>
                </div>
              </td>
            </tr>
            <tr v-if="!filteredUsers.length"><td colspan="5" class="empty">没有符合条件的账号</td></tr>
          </tbody>
        </table>
      </Panel>
    </template>

    <div v-if="modal" class="modal-mask" @click.self="modal = false">
      <div class="modal">
        <h3>新建账号</h3>
        <div class="form-grid">
          <div>
            <label class="field">用户名</label>
            <input v-model.trim="form.username" class="input w-full" />
          </div>
          <div>
            <label class="field">显示名</label>
            <input v-model.trim="form.display_name" class="input w-full" />
          </div>
          <div>
            <label class="field">初始密码</label>
            <input v-model="form.password" class="input w-full" type="password" />
          </div>
          <div>
            <label class="field">角色</label>
            <select v-model="form.role" class="select w-full">
              <option value="operator">调度员</option>
              <option value="viewer">观察者</option>
              <option value="admin">管理员</option>
            </select>
          </div>
        </div>
        <p v-if="modalError" class="err">{{ modalError }}</p>
        <div class="row mt-24" style="justify-content:flex-end;">
          <button class="btn" @click="modal = false">取消</button>
          <button class="btn btn-primary" :disabled="saving" @click="create">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api/client'
import Panel from '../components/Panel.vue'

const users = ref([])
const loading = ref(true)
const error = ref('')
const modal = ref(false)
const saving = ref(false)
const modalError = ref('')
const form = reactive({ username: '', display_name: '', password: '', role: 'operator' })
const keyword = ref('')
const roleFilter = ref('')
const pendingCount = computed(() => users.value.filter((u) => u.approval_status === 'pending').length)
const operatorCount = computed(() => users.value.filter((u) => u.role === 'operator').length)
const activeCount = computed(() => users.value.filter((u) => u.is_active && u.approval_status === 'approved').length)
const filteredUsers = computed(() => {
  const q = keyword.value.toLowerCase()
  return users.value.filter((u) => {
    const matchKeyword = !q || [u.username, u.display_name].some((v) => String(v || '').toLowerCase().includes(q))
    return matchKeyword && (!roleFilter.value || u.role === roleFilter.value)
  })
})

function formatTime(t) {
  if (!t) return '—'
  return String(t).replace('T', ' ').slice(0, 19)
}

function statusLabel(u) {
  if (u.approval_status === 'pending') return '待审核'
  if (u.approval_status === 'rejected') return '已拒绝'
  return u.is_active ? '已启用' : '已停用'
}

function statusClass(u) {
  if (u.approval_status === 'pending') return 'tag-amber'
  if (u.approval_status === 'rejected') return 'tag-red'
  return u.is_active ? 'tag-green' : 'tag-blue'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/users')
    users.value = data
  } catch (e) {
    error.value = (e.response && e.response.data && e.response.data.detail) || '加载失败'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  modalError.value = ''
  Object.assign(form, { username: '', display_name: '', password: '', role: 'operator' })
  modal.value = true
}

async function create() {
  if (!form.username || !form.password) {
    modalError.value = '请填写用户名和初始密码'
    return
  }
  saving.value = true
  modalError.value = ''
  try {
    await api.post('/users', { ...form })
    modal.value = false
    await load()
  } catch (e) {
    modalError.value = (e.response && e.response.data && e.response.data.detail) || '创建失败'
  } finally {
    saving.value = false
  }
}

async function approve(u) {
  await api.post(`/users/${u.id}/approve`)
  await load()
}

async function reject(u) {
  await api.post(`/users/${u.id}/reject`)
  await load()
}

async function updateRole(u, role) {
  try {
    await api.put(`/users/${u.id}`, { role })
    await load()
  } catch (e) {
    alert((e.response && e.response.data && e.response.data.detail) || '修改失败')
  }
}

async function resetPassword(u) {
  if (!confirm(`确定重置 ${u.username} 的密码？`)) return
  const { data } = await api.post(`/users/${u.id}/reset-password`)
  alert(`临时密码：${data.temporary_password}`)
}

async function remove(u) {
  if (!confirm(`确定删除用户 ${u.username}？`)) return
  try {
    await api.delete(`/users/${u.id}`)
    await load()
  } catch (e) {
    alert((e.response && e.response.data && e.response.data.detail) || '删除失败')
  }
}

onMounted(load)
</script>

<style scoped>
.err { color: #ff9b9b; font-size: 14px; margin-top: 12px; }
.filter-select { width: 140px; height: 38px; font-size: 15px; }
.role-select { width: 112px; height: 34px; font-size: 14px; }
.time-cell { color: #8ba3c7; font-size: 14px; }
</style>
