<template>
  <div class="page">
    <!-- 我的好友ID + 修改 -->
    <el-card shadow="never" class="block-card">
      <template #header>
        <div class="card-header">
          <div>
            <div class="section-label">MY ID</div>
            <h2 class="section-title">我的好友ID</h2>
          </div>
        </div>
      </template>
      <div class="uid-section">
        <div class="uid-display">
          <span class="uid-label">当前好友ID：</span>
          <span class="uid-value">{{ myUid || '加载中...' }}</span>
          <el-button link type="primary" :icon="CopyDocument" @click="copyUid" v-if="myUid">复制</el-button>
        </div>
        <el-button type="warning" plain :icon="Edit" @click="openEditUid">修改ID</el-button>
      </div>
      <p class="tip">将你的好友ID告诉别人，别人搜索后可向你发送好友申请。你同意后双方成为好友，提交申报后好友会第一时间收到推送。</p>
    </el-card>

    <!-- 好友申请（收到的） -->
    <el-card shadow="never" class="block-card">
      <template #header>
        <div class="card-header">
          <div class="head-left">
            <div>
              <div class="section-label">REQUESTS</div>
              <h2 class="section-title">好友申请</h2>
            </div>
            <span v-if="requests.length > 0" class="count-pill danger">{{ requests.length }} 条待处理</span>
          </div>
        </div>
      </template>
      <el-empty v-if="requests.length === 0" description="暂无待处理的好友申请" :image-size="50" />
      <div v-else class="request-list">
        <div v-for="req in requests" :key="req.id" class="request-item">
          <div class="request-info">
            <el-icon><User /></el-icon>
            <span class="request-username">{{ req.from_username }}</span>
            <el-tag size="small" type="info">ID: {{ req.from_uid }}</el-tag>
            <span class="request-time">{{ req.created_at }}</span>
          </div>
          <div class="request-actions">
            <el-button type="success" size="small" :icon="Check"
                       :loading="handlingId === req.id"
                       @click="handleAccept(req)">同意</el-button>
            <el-button type="danger" size="small" plain :icon="Close"
                       :loading="rejectingId === req.id"
                       @click="handleReject(req)">拒绝</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 搜索添加好友 -->
    <el-card shadow="never" class="block-card">
      <template #header>
        <div class="card-header">
          <div>
            <div class="section-label">DISCOVER</div>
            <h2 class="section-title">搜索添加好友</h2>
          </div>
        </div>
      </template>
      <div class="search-section">
        <el-input v-model="searchKey" placeholder="输入对方的好友ID搜索" :prefix-icon="Search"
                  clearable maxlength="20" style="width: 300px" @keyup.enter="handleSearch" />
        <el-button type="primary" :icon="Search" @click="handleSearch" :loading="searching">搜索</el-button>
      </div>
      <div v-if="searchResults.length > 0" class="search-results">
        <div v-for="item in searchResults" :key="item.id" class="search-item">
          <div class="search-item-info">
            <el-icon><User /></el-icon>
            <span class="search-username">{{ item.username }}</span>
            <el-tag size="small" type="info">ID: {{ item.uid }}</el-tag>
          </div>
          <el-button type="success" size="small" :icon="Plus"
                     :loading="addingId === item.id"
                     @click="handleSendRequest(item)">发送申请</el-button>
        </div>
      </div>
      <el-empty v-else-if="searched && searchResults.length === 0" description="未找到该好友ID的用户" :image-size="60" />
    </el-card>

    <!-- 好友列表 -->
    <el-card shadow="never" class="block-card">
      <template #header>
        <div class="card-header">
          <div class="head-left">
            <div>
              <div class="section-label">FRIENDS</div>
              <h2 class="section-title">我的好友</h2>
            </div>
            <span v-if="friends.length" class="count-pill">{{ friends.length }} 位</span>
          </div>
          <el-button text class="refresh-btn" @click="loadAll">刷新</el-button>
        </div>
      </template>
      <el-table :data="friends" v-loading="listLoading" stripe empty-text="暂无好友，快去搜索添加吧">
        <el-table-column label="用户名" min-width="150">
          <template #default="{ row }">
            <el-icon><User /></el-icon>
            <span style="margin-left: 6px">{{ row.username }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="uid" label="好友ID" width="150">
          <template #default="{ row }">
            <el-tag size="small">{{ row.uid }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="成为好友时间" width="180" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button type="danger" link size="small" @click="handleRemove(row)">删除好友</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 修改好友ID弹窗 -->
    <el-dialog v-model="editUidVisible" title="修改好友ID" width="420px">
      <el-form @submit.prevent>
        <el-form-item label="当前ID">
          <span class="uid-value">{{ myUid }}</span>
        </el-form-item>
        <el-form-item label="新好友ID">
          <el-input v-model="editUidForm" placeholder="4-20位字母或数字" maxlength="20" clearable
                    :prefix-icon="Postcard" />
        </el-form-item>
      </el-form>
      <p class="tip">修改后别人需要用你的新ID来搜索添加你。如果新ID已被他人使用将无法修改。</p>
      <template #footer>
        <el-button @click="editUidVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingUid" @click="handleSaveUid">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Edit, CopyDocument, Postcard, User, Check, Close } from '@element-plus/icons-vue'
import { friendApi, authApi } from '../api'

const myUid = ref('')
const friends = ref([])
const requests = ref([])
const listLoading = ref(false)
const searchKey = ref('')
const searchResults = ref([])
const searched = ref(false)
const searching = ref(false)
const addingId = ref(null)
const handlingId = ref(null)
const rejectingId = ref(null)
const editUidVisible = ref(false)
const editUidForm = ref('')
const savingUid = ref(false)

let pollTimer = null

async function loadMyUid() {
  const me = await authApi.me()
  myUid.value = me.uid || ''
}

async function loadFriends() {
  listLoading.value = true
  try {
    friends.value = await friendApi.list()
  } finally {
    listLoading.value = false
  }
}

async function loadRequests() {
  try {
    requests.value = await friendApi.requests()
  } catch (e) { /* 忽略轮询错误 */ }
}

function loadAll() {
  loadMyUid()
  loadFriends()
  loadRequests()
}

function copyUid() {
  navigator.clipboard.writeText(myUid.value).then(() => {
    ElMessage.success('好友ID已复制到剪贴板')
  }).catch(() => {
    ElMessage.warning('复制失败，请手动选中复制')
  })
}

function openEditUid() {
  editUidForm.value = ''
  editUidVisible.value = true
}

async function handleSaveUid() {
  if (!editUidForm.value || editUidForm.value.trim().length < 4) {
    ElMessage.warning('好友ID至少4位')
    return
  }
  savingUid.value = true
  try {
    const res = await friendApi.updateUid(editUidForm.value.trim())
    myUid.value = res.uid
    editUidVisible.value = false
    ElMessage.success('好友ID修改成功')
  } finally {
    savingUid.value = false
  }
}

async function handleSearch() {
  if (!searchKey.value.trim()) {
    ElMessage.warning('请输入好友ID')
    return
  }
  searching.value = true
  searched.value = true
  try {
    searchResults.value = await friendApi.search(searchKey.value.trim())
  } finally {
    searching.value = false
  }
}

async function handleSendRequest(user) {
  addingId.value = user.id
  try {
    const res = await friendApi.add(user.id)
    ElMessage.success(res.message)
    searchResults.value = []
    searchKey.value = ''
  } finally {
    addingId.value = null
  }
}

async function handleAccept(req) {
  handlingId.value = req.id
  try {
    await friendApi.accept(req.id)
    ElMessage.success('已同意好友申请')
    await loadAll()
  } finally {
    handlingId.value = null
  }
}

async function handleReject(req) {
  rejectingId.value = req.id
  try {
    await friendApi.reject(req.id)
    ElMessage.success('已拒绝好友申请')
    await loadRequests()
  } finally {
    rejectingId.value = null
  }
}

async function handleRemove(row) {
  try {
    await ElMessageBox.confirm(`确定要删除好友「${row.username}」吗？`, '删除好友', {
      type: 'warning',
      confirmButtonText: '确定删除',
      cancelButtonText: '取消'
    })
    await friendApi.remove(row.id)
    ElMessage.success('已删除好友')
    await loadFriends()
  } catch (e) { /* 用户取消 */ }
}

onMounted(() => {
  loadAll()
  // 4秒轮询好友申请
  pollTimer = setInterval(loadRequests, 4000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.page {
  max-width: 860px;
  margin: 0 auto;
  padding: 40px 40px 0;
}
.block-card {
  margin-bottom: 24px;
  border-radius: 14px;
  border: 1px solid var(--color-border);
}
.card-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
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
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.01em;
}
.count-pill {
  font-size: 12px;
  font-family: var(--font-mono);
  background: var(--color-accent-bg);
  color: var(--color-primary);
  padding: 3px 10px;
  border-radius: 999px;
}
.count-pill.danger {
  background: #fef2f2;
  color: var(--color-danger);
}
.refresh-btn {
  color: var(--color-muted);
}
.uid-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.uid-display {
  display: flex;
  align-items: center;
  gap: 8px;
}
.uid-label {
  color: var(--color-muted);
  font-size: 14px;
}
.uid-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text);
  font-family: var(--font-mono);
  letter-spacing: 2px;
}
.tip {
  color: var(--color-muted);
  font-size: 12px;
  margin: 12px 0 0;
}
.search-section {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.search-section :deep(.el-input__wrapper),
.uid-section :deep(.el-button) {
  border-radius: 8px;
}
.search-results {
  border: 1px solid var(--color-border);
  border-radius: 10px;
  overflow: hidden;
}
.search-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}
.search-item:last-child {
  border-bottom: none;
}
.search-item-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.search-username {
  font-weight: 600;
  color: var(--color-text);
}
.request-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.request-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-surface);
}
.request-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.request-username {
  font-weight: 600;
  color: var(--color-text);
}
.request-time {
  color: #c0c4cc;
  font-size: 12px;
}
.request-actions {
  display: flex;
  gap: 8px;
}
.request-actions :deep(.el-button) {
  border-radius: 999px;
}
@media (max-width: 768px) {
  .page {
    padding: 20px 16px 0;
  }
}
</style>
