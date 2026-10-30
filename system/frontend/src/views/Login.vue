<template>
  <div class="login-page">
    <section class="brand">
      <img class="logo" src="/logo.png" alt="兰州交通大学" />
      <h1>共享单车<br />调度中心</h1>
      <svg class="route" viewBox="0 0 520 220" fill="none" aria-hidden="true">
        <path d="M20 170 L120 120 L210 150 L300 70 L400 110 L500 40"
              stroke="#2F81F7" stroke-width="2" stroke-linecap="round" opacity=".55" />
        <circle cx="20" cy="170" r="6" fill="#2F81F7" opacity=".8" />
        <circle cx="120" cy="120" r="6" fill="#2F81F7" opacity=".8" />
        <circle cx="210" cy="150" r="6" fill="#2F81F7" opacity=".8" />
        <circle cx="300" cy="70" r="6" fill="#2F81F7" opacity=".8" />
        <circle cx="400" cy="110" r="6" fill="#2F81F7" opacity=".8" />
        <circle cx="500" cy="40" r="6" fill="#2F81F7" opacity=".8" />
      </svg>
    </section>

    <section class="login-side">
      <div class="login-card">
        <div class="tabs">
          <button :class="{ active: tab === 'login' }" @click="switchTab('login')">登录</button>
          <button :class="{ active: tab === 'register' }" @click="switchTab('register')">注册</button>
          <button v-if="mustChange" :class="{ active: tab === 'change' }" @click="switchTab('change')">修改密码</button>
        </div>

        <form v-if="tab === 'login'" class="form" @submit.prevent="submitLogin">
          <label class="field" for="login-username">用户名</label>
          <input id="login-username" v-model.trim="loginForm.username" class="input" autocomplete="username" />
          <label class="field" for="login-password">密码</label>
          <input id="login-password" v-model="loginForm.password" class="input" type="password" autocomplete="current-password" />
          <button class="btn btn-primary submit" type="submit" :disabled="loading">
            {{ loading ? '正在登录' : '登 录' }}
          </button>
        </form>

        <form v-else-if="tab === 'register'" class="form" @submit.prevent="submitRegister">
          <label class="field" for="reg-username">用户名</label>
          <input id="reg-username" v-model.trim="regForm.username" class="input" autocomplete="username" />
          <label class="field" for="reg-name">显示名</label>
          <input id="reg-name" v-model.trim="regForm.display_name" class="input" />
          <label class="field" for="reg-password">密码</label>
          <input id="reg-password" v-model="regForm.password" class="input" type="password" autocomplete="new-password" />
          <label class="field" for="reg-confirm">确认密码</label>
          <input id="reg-confirm" v-model="regForm.confirm" class="input" type="password" autocomplete="new-password" />
          <button class="btn btn-primary submit" type="submit" :disabled="loading">
            {{ loading ? '正在提交' : '注 册' }}
          </button>
        </form>

        <form v-else class="form" @submit.prevent="submitChange">
          <label class="field" for="chg-old">原密码</label>
          <input id="chg-old" v-model="changeForm.old_password" class="input" type="password" />
          <label class="field" for="chg-new">新密码</label>
          <input id="chg-new" v-model="changeForm.new_password" class="input" type="password" />
          <label class="field" for="chg-confirm">确认新密码</label>
          <input id="chg-confirm" v-model="changeForm.confirm" class="input" type="password" />
          <button class="btn btn-primary submit" type="submit" :disabled="loading">
            {{ loading ? '正在保存' : '保存并进入' }}
          </button>
        </form>

        <p v-if="error" class="msg error">{{ error }}</p>
        <p v-if="success" class="msg ok">{{ success }}</p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const tab = ref('login')
const loading = ref(false)
const error = ref('')
const success = ref('')
const mustChange = ref(false)
const loginForm = reactive({ username: '', password: '' })
const regForm = reactive({ username: '', display_name: '', password: '', confirm: '' })
const changeForm = reactive({ old_password: '', new_password: '', confirm: '' })

function switchTab(next) {
  tab.value = next
  error.value = ''
  success.value = ''
}

async function submitLogin() {
  error.value = ''
  success.value = ''
  if (!loginForm.username || !loginForm.password) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  try {
    const user = await auth.login(loginForm.username, loginForm.password)
    if (user.must_change_password) {
      mustChange.value = true
      changeForm.old_password = loginForm.password
      tab.value = 'change'
      error.value = ''
      success.value = '首次登录，请先修改密码'
    } else {
      router.push('/app/dashboard')
    }
  } catch (e) {
    error.value = (e.response && e.response.data && e.response.data.detail) || '登录失败'
  } finally {
    loading.value = false
  }
}

async function submitChange() {
  error.value = ''
  success.value = ''
  if (changeForm.new_password.length < 8) {
    error.value = '新密码至少 8 位'
    return
  }
  if (changeForm.new_password !== changeForm.confirm) {
    error.value = '两次输入的新密码不一致'
    return
  }
  loading.value = true
  try {
    await api.post('/auth/change-password', {
      old_password: changeForm.old_password,
      new_password: changeForm.new_password
    })
    auth.user.must_change_password = false
    localStorage.setItem('user', JSON.stringify(auth.user))
    router.push('/app/dashboard')
  } catch (e) {
    error.value = (e.response && e.response.data && e.response.data.detail) || '修改失败'
  } finally {
    loading.value = false
  }
}

async function submitRegister() {
  error.value = ''
  success.value = ''
  if (!regForm.username || !regForm.password) {
    error.value = '请填写用户名和密码'
    return
  }
  if (regForm.password.length < 8) {
    error.value = '密码至少 8 位'
    return
  }
  if (regForm.password !== regForm.confirm) {
    error.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    await auth.register({
      username: regForm.username,
      display_name: regForm.display_name,
      password: regForm.password
    })
    success.value = '账号已提交，待管理员审核'
    tab.value = 'login'
    loginForm.username = regForm.username
    regForm.password = ''
    regForm.confirm = ''
  } catch (e) {
    error.value = (e.response && e.response.data && e.response.data.detail) || '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  height: 100%;
  display: grid;
  grid-template-columns: 1.05fr .95fr;
  background: var(--bg);
}

.brand {
  position: relative;
  padding: 0 8vw;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-right: 1px solid var(--border);
  overflow: hidden;
}

.logo {
  width: 112px;
  height: 112px;
  padding: 8px;
  background: #fff;
  border-radius: 50%;
  object-fit: contain;
  margin-bottom: 36px;
}

h1 {
  font-size: 44px;
  line-height: 1.3;
  font-weight: 500;
  letter-spacing: 1px;
}

.route {
  margin-top: 56px;
  width: 100%;
  max-width: 520px;
}

.login-side {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.login-card {
  width: min(440px, 100%);
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 34px 34px 30px;
}

.tabs {
  display: flex;
  gap: 32px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 26px;
}

.tabs button {
  height: 48px;
  padding: 0 4px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-2);
  font-size: 18px;
  cursor: pointer;
  transition: color .16s ease-out, border-color .16s ease-out;
}

.tabs button.active {
  color: var(--text);
  border-bottom-color: var(--accent);
}

.form { display: grid; }

.field {
  display: block;
  font-size: 16px;
  color: var(--text-2);
  margin: 14px 0 8px;
}

.input { height: 50px; }

.submit {
  margin-top: 26px;
  height: 50px;
  font-size: 17px;
}

.msg {
  margin-top: 18px;
  font-size: 14px;
  line-height: 1.6;
}

.msg.error { color: #ff9b9b; }
.msg.ok { color: #9df0bd; }
</style>
