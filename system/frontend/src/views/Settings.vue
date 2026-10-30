<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">系统设置</h1>
        <div class="page-sub">系统名称、注册开关、默认策略</div>
      </div>
      <button class="btn btn-primary" :disabled="saving" @click="save">保存设置</button>
    </div>

    <div v-if="loading" class="empty">正在加载设置…</div>
    <div v-else class="settings-layout">
      <div class="settings-main">
        <Panel title="系统信息">
          <div class="setting-grid">
            <div>
              <label class="field">系统名称</label>
              <input v-model.trim="settings.system_name" class="input w-full" />
              <p class="form-note">显示在系统标题和调度中心顶部。</p>
            </div>
            <div>
              <label class="field">地图样式</label>
              <select v-model="settings.map_style" class="select w-full">
                <option value="normal">标准底图</option>
                <option value="dark">深色底图</option>
              </select>
              <p class="form-note">标准底图道路与建筑标注更清晰。</p>
            </div>
          </div>
        </Panel>

        <Panel title="调度策略" class="mt-16">
          <div class="setting-grid">
            <div>
              <label class="field">默认调度策略</label>
              <select v-model="settings.default_policy" class="select w-full">
                <option value="ppo">PPO 策略</option>
                <option value="greedy">约束贪心</option>
                <option value="noop">不调度</option>
              </select>
              <p class="form-note">新建推演时优先使用的策略。</p>
            </div>
            <div>
              <label class="field">模型版本</label>
              <input class="input w-full" value="ppo_seed0" disabled />
              <p class="form-note">当前系统加载的调度模型版本。</p>
            </div>
          </div>
        </Panel>

        <Panel title="账号与注册" class="mt-16">
          <label class="switch-row">
            <div>
              <b>开放自助注册</b>
              <p class="form-note">新账号提交后进入待审核状态，由管理员启用。</p>
            </div>
            <input v-model="settings.self_registration" type="checkbox" />
          </label>
          <p v-if="saved" class="ok">设置已保存</p>
        </Panel>
      </div>

      <aside class="settings-side">
        <Panel title="运行状态">
          <div class="status-line"><i></i><span>调度服务正常</span></div>
          <div class="status-item"><span>数据存储</span><b>本地数据库</b></div>
          <div class="status-item"><span>地图服务</span><b>已连接</b></div>
          <div class="status-item"><span>账号注册</span><b>{{ settings.self_registration ? '开放' : '关闭' }}</b></div>
        </Panel>
        <Panel title="安全提示" class="mt-16">
          <p class="security-note">管理员账号拥有用户管理、系统设置和日志查看权限。建议定期更换密码，并及时审核新注册账号。</p>
        </Panel>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api/client'
import Panel from '../components/Panel.vue'

const loading = ref(true)
const saving = ref(false)
const saved = ref(false)
const settings = reactive({
  system_name: '校园共享电单车调度系统',
  self_registration: true,
  default_policy: 'ppo',
  map_style: 'normal'
})

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/settings')
    Object.keys(settings).forEach((key) => {
      if (data[key] !== undefined) settings[key] = data[key]
    })
    if (!['dark', 'normal'].includes(settings.map_style)) settings.map_style = 'normal'
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  saved.value = false
  try {
    await api.put('/settings', { ...settings })
    saved.value = true
    setTimeout(() => { saved.value = false }, 2400)
  } catch (e) {
    alert((e.response && e.response.data && e.response.data.detail) || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.settings-layout { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 18px; align-items: start; }
.settings-main { min-width: 0; }
.setting-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; }
.switch-row { display: flex; align-items: center; justify-content: space-between; gap: 24px; }
.switch-row b { display: block; color: #e2f1fe; font-size: 16px; font-weight: 500; }
.switch-row input { width: 20px; height: 20px; flex: 0 0 20px; accent-color: #22d3ee; }
.status-line { display: flex; align-items: center; gap: 9px; padding-bottom: 14px; color: #8ee8c3; font-size: 16px; border-bottom: 1px solid #17324b; }
.status-line i { width: 7px; height: 7px; border-radius: 50%; background: #3dd49c; box-shadow: 0 0 8px rgba(61,212,156,.55); }
.status-item { display: flex; justify-content: space-between; gap: 12px; padding-top: 13px; color: #8ba3c7; font-size: 15px; }
.status-item b { color: #dceeff; font-weight: 500; }
.security-note { color: #8ba3c7; font-size: 15px; line-height: 1.8; }
.ok { color: #9df0bd; font-size: 15px; margin-top: 16px; }
@media (max-width: 1280px) { .settings-layout { grid-template-columns: 1fr; } }
</style>
