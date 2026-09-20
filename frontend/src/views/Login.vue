<template>
  <div class="login-page">
    <el-card class="login-card">
      <div class="brand">
        <div class="brand-label">WELCOME · 申报与审批</div>
        <h2 class="brand-title">物品申报审批系统</h2>
        <p class="brand-sub">提交申报 · 审批协作 · 消息通知</p>
      </div>

      <el-tabs v-model="activeTab" stretch>
        <!-- 登录 -->
        <el-tab-pane label="登录" name="login">
          <el-form ref="loginFormRef" :model="loginForm" :rules="rules" @submit.prevent>
            <el-form-item prop="username">
              <el-input v-model="loginForm.username" placeholder="用户名（至少3位）" :prefix-icon="User" size="large" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="loginForm.password" type="password" placeholder="密码（至少6位）"
                        :prefix-icon="Lock" size="large" show-password @keyup.enter="handleLogin" />
            </el-form-item>
            <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="handleLogin">
              登 录
            </el-button>
          </el-form>
        </el-tab-pane>

        <!-- 注册 -->
        <el-tab-pane label="注册" name="register">
          <el-form ref="registerFormRef" :model="registerForm" :rules="rules" @submit.prevent>
            <el-form-item prop="username">
              <el-input v-model="registerForm.username" placeholder="设置用户名（至少3位）" :prefix-icon="User" size="large" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="registerForm.password" type="password" placeholder="设置密码（至少6位）"
                        :prefix-icon="Lock" size="large" show-password />
            </el-form-item>
            <el-form-item prop="confirmPassword">
              <el-input v-model="registerForm.confirmPassword" type="password" placeholder="再次输入密码"
                        :prefix-icon="Lock" size="large" show-password @keyup.enter="handleRegister" />
            </el-form-item>
            <el-button type="success" size="large" style="width: 100%" :loading="loading" @click="handleRegister">
              注 册
            </el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <p class="tip">所有用户身份平等：既能提交申报，也可以审批他人的申请</p>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { authApi } from '../api'

const router = useRouter()
const route = useRoute()
const activeTab = ref('login')
const loading = ref(false)
const loginFormRef = ref()
const registerFormRef = ref()

const loginForm = reactive({ username: '', password: '' })
const registerForm = reactive({ username: '', password: '', confirmPassword: '' })

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度为 3-50 位', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度为 6-64 位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== registerForm.password) callback(new Error('两次输入的密码不一致'))
        else callback()
      },
      trigger: 'blur'
    }
  ]
}

function saveAuthAndJump(res) {
  localStorage.setItem('token', res.token)
  localStorage.setItem('user', JSON.stringify(res.user))
  ElMessage.success('登录成功')
  router.replace(route.query.redirect || '/')
}

async function handleLogin() {
  await loginFormRef.value.validate()
  loading.value = true
  try {
    const res = await authApi.login({ ...loginForm })
    saveAuthAndJump(res)
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  await registerFormRef.value.validate()
  loading.value = true
  try {
    await authApi.register({
      username: registerForm.username,
      password: registerForm.password
    })
    ElMessage.success('注册成功，正在自动登录...')
    const res = await authApi.login({
      username: registerForm.username,
      password: registerForm.password
    })
    saveAuthAndJump(res)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.login-card {
  width: 420px;
  padding: 36px 36px 28px;
  border-radius: 14px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}
.brand {
  text-align: left;
  margin-bottom: 8px;
}
.brand-label {
  font-size: 11px;
  letter-spacing: 0.22em;
  color: var(--color-primary);
  font-weight: 600;
  margin-bottom: 6px;
}
.brand-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--color-text);
}
.brand-sub {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--color-muted);
}
.login-card :deep(.el-tabs__nav-wrap::after) {
  display: none;
}
.login-card :deep(.el-tabs__item) {
  font-size: 15px;
  color: var(--color-muted);
}
.login-card :deep(.el-tabs__item.is-active) {
  color: var(--color-text);
  font-weight: 600;
}
.login-card :deep(.el-tabs__active-bar) {
  background-color: var(--color-primary);
}
.login-card :deep(.el-input__wrapper) {
  border-radius: 8px;
}
.login-card :deep(.el-button) {
  border-radius: 999px;
  font-weight: 700;
  letter-spacing: 0.08em;
}
.tip {
  text-align: center;
  color: var(--color-muted);
  font-size: 12px;
  margin: 16px 0 0;
}
</style>
