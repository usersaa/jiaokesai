import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', component: () => import('../views/Login.vue'), meta: { public: true } },
  {
    path: '/screen',
    component: () => import('../views/Screen.vue'),
    meta: { screen: true }
  },
  {
    path: '/app',
    component: () => import('../layouts/AppLayout.vue'),
    redirect: '/app/dashboard',
    children: [
      { path: 'dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '数字孪生大屏', mapWorkspace: true } },
      { path: 'simulation', component: () => import('../views/Simulation.vue'), meta: { title: '实时推演' } },
      { path: 'compare', component: () => import('../views/Compare.vue'), meta: { title: '对比分析' } },
      { path: 'stations', component: () => import('../views/Stations.vue'), meta: { title: '点位管理' } },
      { path: 'scenarios', component: () => import('../views/Scenarios.vue'), meta: { title: '方案管理' } },
      { path: 'night', component: () => import('../views/Night.vue'), meta: { title: '夜间调度' } },
      {
        path: 'users',
        component: () => import('../views/Users.vue'),
        meta: { title: '用户管理', roles: ['admin'] }
      },
      {
        path: 'settings',
        component: () => import('../views/Settings.vue'),
        meta: { title: '系统设置', roles: ['admin'] }
      },
      {
        path: 'logs',
        component: () => import('../views/Logs.vue'),
        meta: { title: '日志审计', roles: ['admin'] }
      }
    ]
  },
  { path: '/', redirect: '/app/dashboard' },
  { path: '/:pathMatch(.*)*', redirect: '/app/dashboard' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.public) {
    if (auth.isLoggedIn) return '/app/dashboard'
    return true
  }
  if (!auth.isLoggedIn) return '/login'
  if (to.meta.roles && !to.meta.roles.includes(auth.role)) return '/app/dashboard'
  return true
})

export default router
