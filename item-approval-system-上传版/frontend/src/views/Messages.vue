<template>
  <div class="page">
    <el-card shadow="never" class="block-card">
      <template #header>
        <div class="card-header">
          <div class="head-left">
            <div>
              <div class="section-label">INBOX</div>
              <h2 class="section-title">我的消息</h2>
            </div>
            <span v-if="unreadCount > 0" class="unread-pill">{{ unreadCount }} 条未读</span>
          </div>
          <div class="head-right">
            <span class="poll-tip"><span class="dot"></span>每 {{ POLL_INTERVAL / 1000 }} 秒自动刷新</span>
            <el-button text class="text-btn" @click="loadMessages">刷新</el-button>
            <el-button text class="text-btn accent" :disabled="unreadCount === 0" @click="handleReadAll">全部标记已读</el-button>
          </div>
        </div>
      </template>

      <el-table :data="messages" v-loading="loading" stripe empty-text="暂无消息">
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_read === 0" type="danger" size="small">未读</el-tag>
            <el-tag v-else type="info" size="small" effect="plain">已读</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="消息内容" min-width="420">
          <template #default="{ row }">
            <span :class="{ unread: row.is_read === 0 }">{{ row.content }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="180" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button v-if="row.is_read === 0" type="primary" link size="small" @click="handleRead(row)">
              标记已读
            </el-button>
            <span v-else class="read-text">—</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { messageApi } from '../api'

// 课程项目使用前端轮询（3-5 秒），不使用 WebSocket
const POLL_INTERVAL = 4000

const messages = ref([])
const loading = ref(false)
let timer = null

const unreadCount = computed(() => messages.value.filter((m) => m.is_read === 0).length)

async function loadMessages() {
  // 轮询静默加载，不显示全屏 loading（首次除外）
  const showLoading = messages.value.length === 0
  if (showLoading) loading.value = true
  try {
    messages.value = await messageApi.list()
  } catch (e) {
    /* 忽略轮询失败，下个周期重试 */
  } finally {
    if (showLoading) loading.value = false
  }
}

async function handleRead(row) {
  await messageApi.read(row.id)
  row.is_read = 1
  ElMessage.success('已标记为已读')
}

async function handleReadAll() {
  await messageApi.readAll()
  messages.value.forEach((m) => (m.is_read = 1))
  ElMessage.success('已全部标记为已读')
}

onMounted(() => {
  loadMessages()
  timer = setInterval(loadMessages, POLL_INTERVAL)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 40px 40px 0;
}
.block-card {
  border-radius: 14px;
  border: 1px solid var(--color-border);
}
.card-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
}
.head-left {
  display: flex;
  align-items: center;
  gap: 14px;
}
.section-label {
  font-size: 11px;
  letter-spacing: 0.22em;
  color: var(--color-primary);
  font-weight: 600;
  margin-bottom: 6px;
}
.section-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.01em;
}
.unread-pill {
  font-size: 12px;
  font-family: var(--font-mono);
  background: var(--color-danger);
  color: #fff;
  padding: 3px 10px;
  border-radius: 999px;
}
.head-right {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}
.poll-tip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-muted);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-success);
  animation: pulse 1.6s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
}
.text-btn {
  color: var(--color-muted);
  font-size: 13px;
}
.text-btn:hover {
  color: var(--color-text);
}
.text-btn.accent {
  color: var(--color-primary);
}
.unread {
  font-weight: 600;
  color: var(--color-text);
}
.read-text {
  color: #c0c4cc;
}
@media (max-width: 768px) {
  .page {
    padding: 20px 16px 0;
  }
  .poll-tip {
    display: none;
  }
}
</style>
