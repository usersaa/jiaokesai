<template>
  <div class="app-shell" :class="{ 'map-workspace': isMapWorkspace }">
    <aside v-if="!isMapWorkspace" class="sidebar">
      <div class="brand">
        <img src="/logo.png" alt="兰州交通大学" class="brand-logo" />
        <div>
          <div class="brand-name">共享单车调度中心</div>
          <div class="brand-sub">兰州交通大学</div>
        </div>
      </div>

      <div class="nav-scroll">
        <div v-for="group in visibleGroups" :key="group.label" class="nav-group">
          <div class="nav-group-title">{{ group.label }}</div>
          <router-link
            v-for="item in group.items"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            active-class="active"
          >
            <span class="nav-mark">{{ item.mark }}</span>
            <span class="nav-label">{{ item.label }}</span>
            <span class="nav-arrow"></span>
          </router-link>
        </div>
      </div>

      <div class="sidebar-foot">
        <div class="system-health"><i></i><span>调度服务运行正常</span></div>
        <div class="health-meta">数据更新于 {{ lastSync }}</div>
      </div>
    </aside>

    <div class="main">
      <header v-if="!isMapWorkspace" class="topbar">
        <div class="crumb">
          <span>调度控制台</span>
          <i>/</i>
          <b>{{ title }}</b>
        </div>
        <div class="topbar-actions">
          <button class="topbar-link" @click="goScreen">独立大屏</button>
          <button class="topbar-link" @click="showPwd = true">账号安全</button>
          <div class="user-block">
            <span class="avatar">{{ avatar }}</span>
            <div class="user-meta">
              <b>{{ auth.displayName }}</b>
              <small>{{ roleLabel }}</small>
            </div>
          </div>
          <button class="logout-btn" @click="logout">退出</button>
        </div>
      </header>

      <main class="content">
        <router-view />
      </main>
    </div>

    <div v-if="showPwd" class="modal-mask" @click.self="showPwd = false">
      <div class="modal pwd-modal">
        <div class="modal-head">
          <div><span>账号安全</span><h3>修改密码</h3></div>
          <button class="modal-close" @click="showPwd = false">关闭</button>
        </div>
        <div class="form-grid">
          <div>
            <label class="field">原密码</label>
            <input v-model="pwd.old_password" class="input w-full" type="password" />
          </div>
          <div>
            <label class="field">新密码</label>
            <input v-model="pwd.new_password" class="input w-full" type="password" />
          </div>
          <div>
            <label class="field">确认新密码</label>
            <input v-model="pwd.confirm" class="input w-full" type="password" />
          </div>
        </div>
        <p v-if="pwdError" class="err">{{ pwdError }}</p>
        <div class="row mt-24" style="justify-content:flex-end;">
          <button class="btn" @click="showPwd = false">取消</button>
          <button class="btn btn-primary" @click="savePwd">保存修改</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const navGroups = [
  {
    label: '调度运行',
    items: [
      { path: '/app/dashboard', label: '数字孪生', mark: '01' },
      { path: '/app/simulation', label: '实时推演', mark: '02' },
      { path: '/app/compare', label: '对比分析', mark: '03' }
    ]
  },
  {
    label: '资源管理',
    items: [
      { path: '/app/stations', label: '点位管理', mark: '04' },
      { path: '/app/scenarios', label: '方案管理', mark: '05' },
      { path: '/app/night', label: '夜间调度', mark: '06' }
    ]
  },
  {
    label: '系统管理',
    items: [
      { path: '/app/users', label: '用户管理', mark: '07', roles: ['admin'] },
      { path: '/app/settings', label: '系统设置', mark: '08', roles: ['admin'] },
      { path: '/app/logs', label: '日志审计', mark: '09', roles: ['admin'] }
    ]
  }
]

const visibleGroups = computed(() => navGroups.map((g) => ({
  ...g,
  items: g.items.filter((n) => !n.roles || n.roles.includes(auth.role))
})).filter((g) => g.items.length))
const title = computed(() => route.meta.title || '共享单车调度中心')
const isMapWorkspace = computed(() => !!route.meta.mapWorkspace)
const roleLabel = computed(() => ({ admin: '管理员', operator: '调度员', viewer: '观察者' }[auth.role] || '观察者'))
const avatar = computed(() => (auth.displayName || '管').slice(0, 1))
const lastSync = ref('')

function updateClock() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  lastSync.value = `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
let clockTimer = null

function goScreen() {
  router.push('/screen')
}

function logout() {
  auth.logout()
  router.push('/login')
}

const showPwd = ref(false)
const pwdError = ref('')
const pwd = reactive({ old_password: '', new_password: '', confirm: '' })

async function savePwd() {
  pwdError.value = ''
  if (pwd.new_password.length < 8) {
    pwdError.value = '新密码至少 8 位'
    return
  }
  if (pwd.new_password !== pwd.confirm) {
    pwdError.value = '两次输入的新密码不一致'
    return
  }
  try {
    await api.post('/auth/change-password', {
      old_password: pwd.old_password,
      new_password: pwd.new_password
    })
    showPwd.value = false
    pwd.old_password = ''
    pwd.new_password = ''
    pwd.confirm = ''
  } catch (e) {
    pwdError.value = (e.response && e.response.data && e.response.data.detail) || '修改失败'
  }
}

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 60000)
})
onBeforeUnmount(() => { if (clockTimer) clearInterval(clockTimer) })
</script>

<style scoped>
.sidebar {
  width: 236px;
  flex: 0 0 236px;
  background: #081726;
  border-right: 1px solid #17324b;
  display: flex;
  flex-direction: column;
}

.brand {
  height: 92px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid #17324b;
}

.brand-logo {
  width: 42px;
  height: 42px;
  padding: 3px;
  background: #fff;
  border-radius: 50%;
  object-fit: contain;
}

.brand-name { font-size: 16px; font-weight: 600; letter-spacing: .3px; color: #eaf6ff; }
.brand-sub { font-size: 14px; color: #6f8da9; margin-top: 2px; }

.nav-scroll { flex: 1; min-height: 0; overflow-y: auto; padding: 16px 12px 10px; }
.nav-group { margin-bottom: 20px; }
.nav-group-title { padding: 0 12px 7px; color: #5f7f9d; font-size: 14px; letter-spacing: 1px; }

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 44px;
  padding: 0 11px;
  margin-bottom: 2px;
  border-radius: 6px;
  border-left: 2px solid transparent;
  color: #9fb8d0;
  font-size: 15px;
  transition: background .16s ease-out, color .16s ease-out, border-color .16s ease-out;
}

.nav-item:hover { background: #10283d; color: #e6f1ff; }
.nav-item.active { background: #12314a; color: #effaff; border-left-color: #22d3ee; }
.nav-mark { width: 22px; color: #4e7a9c; font: 500 14px/1 Consolas, monospace; }
.nav-item.active .nav-mark { color: #59e6f4; }
.nav-label { flex: 1; }
.nav-arrow { width: 5px; height: 5px; border-top: 1px solid currentColor; border-right: 1px solid currentColor; transform: rotate(45deg); opacity: .45; }

.sidebar-foot { padding: 15px 18px 18px; border-top: 1px solid #17324b; }
.system-health { display: flex; align-items: center; gap: 8px; color: #9dc7c3; font-size: 14px; }
.system-health i { width: 7px; height: 7px; border-radius: 50%; background: #3dd49c; box-shadow: 0 0 8px rgba(61,212,156,.55); }
.health-meta { margin-top: 5px; color: #54718b; font-size: 14px; }

.main { flex: 1; min-width: 0; display: flex; flex-direction: column; }

.topbar {
  height: 68px;
  flex: 0 0 68px;
  padding: 0 26px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #17324b;
  background: #0a1929;
}

.crumb { display: flex; align-items: center; gap: 10px; color: #6f8da9; font-size: 15px; }
.crumb i { color: #34556f; font-style: normal; }
.crumb b { color: #dceeff; font-weight: 500; }

.topbar-actions { display: flex; align-items: center; gap: 10px; }
.topbar-link { height: 36px; padding: 0 13px; border: 1px solid #284860; border-radius: 6px; background: transparent; color: #a9c2d8; font-size: 14px; cursor: pointer; }
.topbar-link:hover { border-color: #3a86a8; color: #e3f8ff; }
.user-block { display: flex; align-items: center; gap: 9px; margin-left: 6px; padding-left: 14px; border-left: 1px solid #234158; }
.avatar { width: 34px; height: 34px; display: flex; align-items: center; justify-content: center; border-radius: 50%; background: #14445b; color: #8ff4ff; font-size: 16px; }
.user-meta b { display: block; color: #dceeff; font-size: 14px; font-weight: 500; }
.user-meta small { display: block; color: #6f8da9; font-size: 14px; }
.logout-btn { height: 36px; padding: 0 10px; border: 0; background: transparent; color: #849eb7; font-size: 14px; cursor: pointer; }
.logout-btn:hover { color: #ffadad; }

.content { flex: 1; min-height: 0; overflow: auto; background: #07111f; }
.map-workspace .content { overflow: hidden; }
.map-workspace .main { width: 100%; }
.err { color: #ff9b9b; font-size: 14px; margin-top: 12px; }

.pwd-modal { padding: 24px; }
.modal-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid #1e3a5f; }
.modal-head span { color: #5edce9; font-size: 14px; }
.modal-head h3 { margin: 5px 0 0; }
.modal-close { height: 32px; padding: 0 10px; border: 1px solid #2a4a73; border-radius: 5px; background: transparent; color: #9fb8d0; font-size: 14px; cursor: pointer; }

@media (max-width: 1180px) {
  .sidebar { width: 214px; flex-basis: 214px; }
  .brand-name { font-size: 15px; }
  .topbar-link { display: none; }
}
</style>
