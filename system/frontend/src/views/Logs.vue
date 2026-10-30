<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">日志审计</h1>
        <div class="page-sub">登录、操作与调度记录</div>
      </div>
      <button class="btn" :disabled="loading" @click="load(page)">刷新</button>
    </div>

    <div v-if="loading" class="empty">正在加载日志…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <template v-else>
      <div class="stat-grid">
        <div class="stat-card"><span>日志总数</span><b>{{ total }}</b><small>系统操作与登录记录</small></div>
        <div class="stat-card"><span>当前页</span><b>{{ page }}</b><small>每页 {{ pageSize }} 条</small></div>
        <div class="stat-card"><span>本页记录</span><b>{{ items.length }}</b><small>按时间倒序排列</small></div>
        <div class="stat-card"><span>审计状态</span><b class="ok-text">正常</b><small>记录持续写入</small></div>
      </div>

      <Panel title="日志列表">
        <table class="table">
          <thead>
            <tr><th>时间</th><th>用户</th><th>操作</th><th>对象</th><th>IP</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in items" :key="r.id">
              <td class="mono log-time">{{ formatTime(r.created_at) }}</td>
              <td><span class="log-user">{{ r.username || '系统' }}</span></td>
              <td><span class="action-tag">{{ actionLabel(r.action) }}</span></td>
              <td class="log-target">{{ r.target || '—' }}</td>
              <td class="mono log-ip">{{ r.ip || '—' }}</td>
            </tr>
            <tr v-if="!items.length">
              <td colspan="5" class="empty">暂无日志</td>
            </tr>
          </tbody>
        </table>

        <div class="row-between log-foot">
          <span class="form-note">共 {{ total }} 条记录</span>
          <div class="row">
            <button class="btn btn-sm" :disabled="page <= 1" @click="load(page - 1)">上一页</button>
            <span class="page-no mono">{{ page }}</span>
            <button class="btn btn-sm" :disabled="page * pageSize >= total" @click="load(page + 1)">下一页</button>
          </div>
        </div>
      </Panel>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api/client'
import Panel from '../components/Panel.vue'

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(true)
const error = ref('')

function formatTime(t) {
  if (!t) return '—'
  return String(t).replace('T', ' ').slice(0, 19)
}

function actionLabel(a) {
  return {
    login: '登录', register: '注册', change_password: '修改密码',
    create_user: '创建用户', update_user: '修改用户', delete_user: '删除用户',
    approve_user: '审核通过', reject_user: '审核拒绝', reset_password: '重置密码',
    create_station: '新增点位', update_station: '修改点位', delete_station: '删除点位',
    import_stations: '导入点位',
    create_scenario: '新建方案', update_scenario: '修改方案', delete_scenario: '删除方案',
    run_simulation: '运行推演', night_solve: '夜间调度',
    update_settings: '修改设置'
  }[a] || a
}

async function load(p = 1) {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/logs', { params: { page: p, page_size: pageSize } })
    items.value = data.items
    total.value = data.total
    page.value = data.page
  } catch (e) {
    error.value = (e.response && e.response.data && e.response.data.detail) || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => load(1))
</script>

<style scoped>
.ok-text { color: #63dca8; font-size: 24px; }
.log-time { color: #7895b2; font-size: 14px; }
.log-user { color: #dceeff; }
.action-tag { display: inline-flex; padding: 3px 8px; border: 1px solid #27506b; border-radius: 4px; background: #0d2a3d; color: #9fc3dc; font-size: 14px; }
.log-target { color: #a9c2d8; }
.log-ip { color: #6f8da9; font-size: 14px; }
.log-foot { padding: 14px 18px; border-top: 1px solid #17324b; background: #0a1a2a; }
.page-no { min-width: 30px; text-align: center; color: #8ff4ff; font-size: 15px; }
</style>
