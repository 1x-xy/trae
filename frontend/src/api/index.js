import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

// axios 实例：开发环境走 Vite 代理（baseURL 为空），
// 生产环境通过 .env.production 的 VITE_API_BASE 指向云端后端地址
const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/',
  timeout: 15000
})

// 请求拦截器：自动携带 Token
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：统一错误处理；401/403 清理登录态并跳登录页
request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail || '请求失败，请稍后重试'
    if (status === 401 || status === 403) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (router.currentRoute.value.path !== '/login') {
        ElMessage.warning('登录已失效，请重新登录')
        router.replace('/login')
      }
    } else {
      ElMessage.error(typeof detail === 'string' ? detail : '请求失败')
    }
    return Promise.reject(error)
  }
)

// ---------------- 认证相关 ----------------
export const authApi = {
  register: (data) => request.post('/api/auth/register', data),
  login: (data) => request.post('/api/auth/login', data),
  me: () => request.get('/api/auth/me')
}

// ---------------- 物品申报 ----------------
export const applyApi = {
  // FormData：item_name / price / description / image
  submit: (formData) =>
    request.post('/api/applications', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),
  mine: () => request.get('/api/applications/mine'),
  pending: () => request.get('/api/applications/pending'),
  review: (id, data) => request.post(`/api/applications/${id}/review`, data)
}

// ---------------- 首页统计 ----------------
export const statsApi = {
  get: () => request.get('/api/stats')
}

// ---------------- 消息通知 ----------------
export const messageApi = {
  list: () => request.get('/api/messages'),
  unreadCount: () => request.get('/api/messages/unread-count'),
  read: (id) => request.post(`/api/messages/${id}/read`),
  readAll: () => request.post('/api/messages/read-all')
}

// ---------------- 好友功能 ----------------
export const friendApi = {
  updateUid: (uid) => request.put('/api/user/uid', { uid }),
  search: (q) => request.get('/api/users/search', { params: { q } }),
  list: () => request.get('/api/friends'),
  add: (userId) => request.post(`/api/friends/${userId}`),
  remove: (userId) => request.delete(`/api/friends/${userId}`),
  requests: () => request.get('/api/friend-requests'),
  requestCount: () => request.get('/api/friend-requests/count'),
  accept: (reqId) => request.post(`/api/friend-requests/${reqId}/accept`),
  reject: (reqId) => request.post(`/api/friend-requests/${reqId}/reject`)
}

export default request
