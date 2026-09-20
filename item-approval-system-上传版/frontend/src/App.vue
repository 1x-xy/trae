<template>
  <el-container class="app-container">
    <!-- 登录/注册页不显示顶部导航 -->
    <el-header v-if="!isPublicPage" class="app-header" height="64px">
      <div class="logo" @click="router.push('/')">
        <span class="logo-text">物品申报审批系统</span>
      </div>

      <nav class="nav-menu">
        <router-link to="/" class="nav-item" :class="{ active: route.path === '/' }">首页</router-link>
        <router-link to="/my" class="nav-item" :class="{ active: route.path === '/my' }">我的申请</router-link>
        <router-link to="/messages" class="nav-item" :class="{ active: route.path === '/messages' }">我的消息</router-link>
        <router-link to="/friends" class="nav-item" :class="{ active: route.path === '/friends' }">我的好友</router-link>
      </nav>

      <div class="header-right">
        <span v-if="unreadCount > 0" class="unread-badge">{{ unreadCount }} 条未读</span>
        <div class="user-info">
          <div class="avatar">{{ avatarChar }}</div>
          <span class="username">{{ username }}</span>
        </div>
        <el-button text class="logout-btn" @click="logout">退出</el-button>
      </div>
    </el-header>

    <el-main :class="{ 'no-padding': isPublicPage }">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { messageApi } from './api'

const route = useRoute()
const router = useRouter()

const isPublicPage = computed(() => !!route.meta.public)
const user = ref(JSON.parse(localStorage.getItem('user') || '{}'))
const username = computed(() => user.value.username || '')
const avatarChar = computed(() => (username.value ? username.value.charAt(0).toUpperCase() : 'U'))
const unreadCount = ref(0)
let timer = null

async function fetchUnreadCount() {
  if (!localStorage.getItem('token')) return
  try {
    const res = await messageApi.unreadCount()
    unreadCount.value = res.count
  } catch (e) {
    /* 忽略轮询错误 */
  }
}

function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.replace('/login')
}

onMounted(() => {
  // 全局每 4 秒轮询一次未读消息数（课程项目使用轮询，不使用 WebSocket）
  fetchUnreadCount()
  timer = setInterval(fetchUnreadCount, 4000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style>
* {
  box-sizing: border-box;
}
:root {
  --color-bg: #f4f4ef;
  --color-surface: #ffffff;
  --color-text: #111111;
  --color-muted: #6b7280;
  --color-border: #e5e5e5;
  --color-primary: #1d4ed8;
  --color-success: #15803d;
  --color-danger: #dc2626;
  --color-accent-bg: #eef2ff;
  --font-sans: 'Inter', 'Helvetica Neue', Helvetica, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --font-mono: 'SF Mono', 'JetBrains Mono', 'Fira Code', Consolas, 'Courier New', monospace;
}
body {
  margin: 0;
  background-color: var(--color-bg);
  background-image: radial-gradient(circle, #d4d4d8 1px, transparent 1px);
  background-size: 24px 24px;
  font-family: var(--font-sans);
  color: var(--color-text);
  -webkit-font-smoothing: antialiased;
}
</style>

<style scoped>
.app-container {
  min-height: 100vh;
}
.app-header {
  display: flex;
  align-items: center;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 0 40px;
  position: sticky;
  top: 0;
  z-index: 100;
}
.logo {
  cursor: pointer;
  font-weight: 700;
  font-size: 15px;
  letter-spacing: -0.01em;
  white-space: nowrap;
  margin-right: 48px;
}
.nav-menu {
  flex: 1;
  display: flex;
  gap: 32px;
}
.nav-item {
  font-size: 14px;
  color: var(--color-muted);
  text-decoration: none;
  padding: 8px 0;
  border-bottom: 2px solid transparent;
  transition: color 0.15s, border-color 0.15s;
}
.nav-item:hover {
  color: var(--color-text);
}
.nav-item.active {
  color: var(--color-text);
  border-bottom-color: var(--color-primary);
}
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
  white-space: nowrap;
}
.unread-badge {
  font-size: 12px;
  font-family: var(--font-mono);
  background: var(--color-primary);
  color: #fff;
  padding: 3px 10px;
  border-radius: 999px;
  letter-spacing: 0.02em;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--color-text);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
}
.username {
  font-size: 14px;
}
.logout-btn {
  color: var(--color-muted) !important;
  font-size: 13px;
  padding: 4px 8px;
}
.logout-btn:hover {
  color: var(--color-danger) !important;
}
.no-padding {
  padding: 0;
}

/* ===== 手机 / 窄屏适配（≤768px）===== */
@media (max-width: 768px) {
  .app-header {
    padding: 0 16px;
    height: 56px;
  }
  .logo {
    margin-right: 16px;
    font-size: 14px;
  }
  .nav-menu {
    gap: 16px;
    overflow-x: auto;
  }
  .nav-item {
    font-size: 13px;
    white-space: nowrap;
  }
  .username {
    display: none;
  }
  .el-main {
    padding: 12px;
  }
}
</style>
