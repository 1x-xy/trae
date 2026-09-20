<template>
  <div class="dashboard">
    <!-- ============ 顶部三张统计卡片 ============ -->
    <section class="stats-row">
      <div class="stat-card">
        <div class="stat-label">PENDING</div>
        <div class="stat-value">{{ String(stats.pending).padStart(2, '0') }}</div>
        <div class="stat-desc">条待我审批</div>
        <div class="stat-sub">来自其他用户，等待你的意见</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">SUBMITTED</div>
        <div class="stat-value">{{ String(stats.mine_total).padStart(2, '0') }}</div>
        <div class="stat-desc">条我的申请</div>
        <div class="stat-sub">含已通过 {{ stats.mine_approved }} 条 · 已驳回 {{ stats.mine_rejected }} 条</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">MESSAGES</div>
        <div class="stat-value">{{ String(stats.unread).padStart(2, '0') }}</div>
        <div class="stat-desc">条未读消息</div>
        <div class="stat-sub">审批结果通知，每 5 秒轮询更新</div>
      </div>
    </section>

    <!-- ============ 主体：左编目 + 右申报 ============ -->
    <section class="main-grid">
      <!-- 左侧：待我审批编目 -->
      <div class="catalogue">
        <div class="section-head">
          <div>
            <div class="section-label">CATALOGUE</div>
            <h2 class="section-title">待我审批编目</h2>
          </div>
          <div class="section-side">待审批</div>
        </div>

        <div v-if="pendingList.length === 0 && !listLoading" class="empty-state">
          <div class="empty-label">EMPTY</div>
          <p>暂无待审批申请</p>
          <p class="empty-sub">列表已过滤本人提交的记录</p>
        </div>

        <div v-for="(row, idx) in pendingList" :key="row.id" class="catalogue-item">
          <div class="item-main" @click="toggleExpand(row.id)">
            <span class="item-index">{{ String(idx + 1).padStart(2, '0') }}</span>
            <el-image :src="row.image_path" :preview-src-list="[row.image_path]" fit="cover" class="item-thumb" preview-teleported />
            <div class="item-info">
              <div class="item-name">{{ row.item_name }}</div>
              <div class="item-meta">
                {{ row.applicant_name }} · {{ formatDate(row.created_at) }}
                <span class="item-dot">·</span>
                <span class="item-desc">{{ row.description || '无描述' }}</span>
              </div>
            </div>
            <div class="item-price">¥{{ Number(row.price).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</div>
            <el-icon class="expand-icon" :class="{ open: expandedId === row.id }"><ArrowDown /></el-icon>
          </div>

          <!-- 内联审批面板 -->
          <div v-if="expandedId === row.id" class="review-panel">
            <div class="review-label">审批理由 <span class="required">*</span>（必填，提交后自动通知申请人）</div>
            <el-input
              :model-value="reviewForms[row.id]?.reason || ''"
              @update:model-value="(v) => setReviewReason(row.id, v)"
              type="textarea"
              :rows="2"
              placeholder="填写通过或驳回的理由..."
              maxlength="500"
              class="review-textarea"
            />
            <div class="review-actions">
              <el-button class="btn-pass" :loading="reviewingId === row.id" @click.stop="handleReview(row, 'approved')">通过</el-button>
              <el-button class="btn-reject" :loading="reviewingId === row.id" @click.stop="handleReview(row, 'rejected')">驳回</el-button>
            </div>
          </div>
        </div>

        <div v-if="pendingList.length > 0" class="catalogue-foot">
          列表已过滤本人提交的记录 · 点击条目展开审批面板
        </div>
      </div>

      <!-- 右侧：提交物品申报 -->
      <div class="declare">
        <div class="declare-card">
          <div class="section-label">DECLARE</div>
          <h2 class="section-title">提交物品申报</h2>

          <el-form ref="formRef" :model="form" :rules="formRules" class="declare-form" label-position="top">
            <el-form-item label="物品名称" prop="itemName">
              <el-input v-model="form.itemName" placeholder="例如：佳能 EOS R6 相机" maxlength="100" />
            </el-form-item>
            <el-form-item label="物品价格" prop="price">
              <div class="price-input">
                <span class="price-prefix">¥</span>
                <el-input-number v-model="form.price" :min="0" :precision="2" :controls="false" placeholder="0.00" />
              </div>
            </el-form-item>
            <el-form-item label="物品描述" prop="description">
              <el-input v-model="form.description" type="textarea" :rows="3" placeholder="用途、规格、采购理由..." maxlength="500" />
            </el-form-item>
            <el-form-item label="上传图片" prop="file">
              <el-upload
                :auto-upload="false"
                :on-change="onFileChange"
                :on-remove="onFileRemove"
                :limit="1"
                accept="image/png,image/jpeg,image/gif"
                list-type="picture-card"
                class="upload-area"
              >
                <el-icon class="upload-plus"><Plus /></el-icon>
              </el-upload>
              <div class="upload-tip">上传图片 · JPG/PNG/GIF · ≤2MB</div>
            </el-form-item>
            <el-button class="submit-btn" :loading="submitting" @click="handleSubmit">提交申报</el-button>
          </el-form>

          <div class="declare-note">
            <span class="note-bar"></span>
            提交后进入「待审批」队列，由其他用户审批；你无法审批自己提交的物品。
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 页脚 ============ -->
    <footer class="site-footer">
      <span>物品申报审批系统</span>
      <span class="footer-dot">·</span>
      <span>© 2026 · Catalogue of Declarations</span>
    </footer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, ArrowDown } from '@element-plus/icons-vue'
import { applyApi, statsApi } from '../api'

const formRef = ref()
const submitting = ref(false)
const listLoading = ref(false)
const pendingList = ref([])

// 统计卡片数据
const stats = reactive({ pending: 0, mine_total: 0, mine_approved: 0, mine_rejected: 0, unread: 0 })
let statsTimer = null

// 内联审批面板：当前展开的申请 id + 每条申请独立的理由草稿
const expandedId = ref(null)
const reviewForms = reactive({})
const reviewingId = ref(null)

const form = reactive({ itemName: '', price: 0, description: '', file: null })

// 图片在前端也做一次校验（后端仍会强制校验）
function validateImage(file) {
  const allowTypes = ['image/png', 'image/jpeg', 'image/gif']
  if (!allowTypes.includes(file.raw.type)) {
    ElMessage.error('仅支持 jpg、png、gif 格式图片')
    return false
  }
  if (file.raw.size > 2 * 1024 * 1024) {
    ElMessage.error('图片大小不能超过 2MB')
    return false
  }
  return true
}

function onFileChange(file) {
  if (!validateImage(file)) {
    form.file = null
    formRef.value?.clearValidate('file')
    return
  }
  form.file = file.raw
  formRef.value?.validateField('file')
}

function onFileRemove() {
  form.file = null
}

const formRules = {
  itemName: [{ required: true, message: '请输入物品名称', trigger: 'blur' }],
  price: [{ required: true, message: '请输入物品价格', trigger: 'change' }],
  file: [
    {
      validator: (_rule, _value, callback) => {
        if (!form.file) callback(new Error('请上传物品图片'))
        else callback()
      },
      trigger: 'change'
    }
  ]
}

async function handleSubmit() {
  await formRef.value.validate()
  const data = new FormData()
  data.append('item_name', form.itemName)
  data.append('price', form.price)
  data.append('description', form.description)
  data.append('image', form.file)

  submitting.value = true
  try {
    await applyApi.submit(data)
    ElMessage.success('申报提交成功，等待其他用户审批')
    resetForm()
  } finally {
    submitting.value = false
  }
}

function resetForm() {
  form.itemName = ''
  form.price = 0
  form.description = ''
  form.file = null
  formRef.value?.resetFields()
}

async function loadPending() {
  listLoading.value = true
  try {
    const res = await applyApi.pending()
    pendingList.value = res
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载待审批列表失败')
  } finally {
    listLoading.value = false
  }
}

async function refreshStats() {
  try {
    const res = await statsApi.get()
    Object.assign(stats, res)
  } catch (e) {
    /* 静默失败，不打断页面 */
  }
}

function formatDate(v) {
  if (!v) return ''
  return String(v).replace('T', ' ').slice(0, 16)
}

function toggleExpand(id) {
  expandedId.value = expandedId.value === id ? null : id
}

function setReviewReason(id, val) {
  if (!reviewForms[id]) reviewForms[id] = { reason: '' }
  reviewForms[id].reason = val
}

async function handleReview(row, action) {
  const formEntry = reviewForms[row.id]
  const reason = formEntry?.reason?.trim() || ''
  if (!reason) {
    ElMessage.warning('审批理由为必填项')
    return
  }
  const actionText = action === 'approved' ? '通过' : '驳回'
  reviewingId.value = row.id
  try {
    await applyApi.review(row.id, { action, reason })
    ElMessage.success(`已${actionText}「${row.item_name}」`)
    delete reviewForms[row.id]
    expandedId.value = null
    await loadPending()
    await refreshStats()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || `审批失败：${e.message}`)
  } finally {
    reviewingId.value = null
  }
}

onMounted(() => {
  loadPending()
  refreshStats()
  // 每 5 秒轮询统计卡片（含未读消息数），与课程项目的轮询方案一致
  statsTimer = setInterval(refreshStats, 5000)
})

onUnmounted(() => {
  if (statsTimer) clearInterval(statsTimer)
})
</script>

<style scoped>
.dashboard {
  max-width: 1280px;
  margin: 0 auto;
  padding: 40px 40px 0;
}

/* ============ 统计卡片 ============ */
.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 48px;
}
.stat-card {
  padding: 28px 32px 36px;
  border-right: 1px solid var(--color-border);
}
.stat-card:first-child {
  padding-left: 0;
}
.stat-card:last-child {
  border-right: none;
}
.stat-label {
  font-size: 11px;
  letter-spacing: 0.22em;
  color: var(--color-muted);
  margin-bottom: 10px;
}
.stat-value {
  font-family: var(--font-mono);
  font-size: 64px;
  font-weight: 800;
  line-height: 1;
  color: var(--color-text);
}
.stat-card:first-child .stat-value {
  color: var(--color-primary);
}
.stat-desc {
  margin-top: 10px;
  font-size: 14px;
  color: var(--color-text);
}
.stat-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-muted);
}

/* ============ 主体两栏 ============ */
.main-grid {
  display: grid;
  grid-template-columns: 1fr 480px;
  gap: 56px;
  align-items: start;
}

/* ============ 左侧编目 ============ */
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 20px;
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
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.01em;
}
.section-side {
  font-size: 12px;
  color: var(--color-muted);
  writing-mode: vertical-rl;
  letter-spacing: 0.3em;
}
.catalogue-item {
  border-top: 1px solid var(--color-border);
  padding: 18px 0;
}
.catalogue-item:last-of-type {
  border-bottom: 1px solid var(--color-border);
}
.item-main {
  display: flex;
  align-items: center;
  gap: 16px;
  cursor: pointer;
}
.item-index {
  font-family: var(--font-mono);
  font-size: 22px;
  font-weight: 700;
  color: #d4d4d8;
  width: 36px;
  flex-shrink: 0;
}
.item-thumb {
  width: 56px;
  height: 56px;
  border-radius: 6px;
  background: #fafafa;
  border: 1px solid var(--color-border);
  flex-shrink: 0;
}
.item-info {
  flex: 1;
  min-width: 0;
}
.item-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
}
.item-meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-muted);
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
}
.item-desc {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 240px;
}
.item-price {
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
  flex-shrink: 0;
}
.expand-icon {
  color: var(--color-muted);
  transition: transform 0.2s;
  flex-shrink: 0;
}
.expand-icon.open {
  transform: rotate(180deg);
}

/* 内联审批面板 */
.review-panel {
  margin: 14px 0 6px 52px;
  background: var(--color-accent-bg);
  border: 1px solid #dbe3ff;
  border-radius: 10px;
  padding: 16px;
}
.review-label {
  font-size: 12px;
  color: var(--color-muted);
  margin-bottom: 10px;
}
.required {
  color: var(--color-danger);
}
.review-textarea :deep(.el-textarea__inner) {
  background: #fff;
  border-radius: 8px;
}
.review-actions {
  margin-top: 12px;
  display: flex;
  gap: 10px;
}
.review-actions .el-button {
  border-radius: 999px;
  padding: 10px 24px;
  font-weight: 600;
}
.btn-pass {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}
.btn-pass:hover {
  opacity: 0.88;
  color: #fff;
}
.btn-reject {
  background: #fff;
  border-color: var(--color-danger);
  color: var(--color-danger);
}
.btn-reject:hover {
  background: #fef2f2;
  color: var(--color-danger);
}
.catalogue-foot {
  padding: 16px 0;
  font-size: 12px;
  color: var(--color-muted);
}
.empty-state {
  border-top: 1px solid var(--color-border);
  padding: 48px 0;
  text-align: center;
}
.empty-label {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.3em;
  color: #d4d4d8;
  margin-bottom: 8px;
}
.empty-state p {
  margin: 4px 0;
  color: var(--color-muted);
  font-size: 14px;
}
.empty-sub {
  font-size: 12px !important;
}

/* ============ 右侧申报表单 ============ */
.declare-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 14px;
  padding: 28px 28px 24px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  position: sticky;
  top: 88px;
}
.declare-form :deep(.el-form-item__label) {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  padding-bottom: 4px;
}
.declare-form :deep(.el-input__wrapper),
.declare-form :deep(.el-textarea__inner) {
  border-radius: 8px;
}
.price-input {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 0 12px;
  background: #fff;
}
.price-input:focus-within {
  border-color: var(--color-primary);
}
.price-prefix {
  color: var(--color-muted);
  font-weight: 600;
}
.price-input :deep(.el-input__wrapper) {
  box-shadow: none !important;
  padding: 0;
  background: transparent;
}
.upload-area :deep(.el-upload--picture-card) {
  width: 100%;
  height: 88px;
  border-radius: 10px;
  border-style: dashed;
}
.upload-plus {
  font-size: 20px;
  color: var(--color-muted);
}
.upload-tip {
  font-size: 12px;
  color: var(--color-muted);
  margin-top: 4px;
}
.submit-btn {
  width: 100%;
  height: 46px;
  border-radius: 999px;
  background: #1f2937;
  border-color: #1f2937;
  color: #fff;
  font-weight: 700;
  font-size: 15px;
  letter-spacing: 0.08em;
  margin-top: 8px;
}
.submit-btn:hover {
  background: #111827;
  border-color: #111827;
  color: #fff;
}
.declare-note {
  margin-top: 18px;
  font-size: 12px;
  color: var(--color-muted);
  line-height: 1.6;
  display: flex;
  gap: 8px;
}
.note-bar {
  width: 3px;
  background: var(--color-primary);
  border-radius: 2px;
  flex-shrink: 0;
}

/* ============ 页脚 ============ */
.site-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid var(--color-border);
  margin-top: 64px;
  padding: 20px 0 24px;
  font-size: 12px;
  color: var(--color-muted);
}
.footer-dot {
  margin: 0 8px;
}

/* ============ 手机适配 ============ */
@media (max-width: 768px) {
  .dashboard {
    padding: 20px 16px 0;
  }
  .stats-row {
    grid-template-columns: 1fr;
    margin-bottom: 28px;
  }
  .stat-card {
    border-right: none;
    border-bottom: 1px solid var(--color-border);
    padding: 18px 0 22px;
  }
  .stat-value {
    font-size: 44px;
  }
  .main-grid {
    grid-template-columns: 1fr;
    gap: 36px;
  }
  .declare-card {
    position: static;
  }
  .item-price {
    font-size: 14px;
  }
  .item-desc {
    display: none;
  }
  .review-panel {
    margin-left: 0;
  }
}
</style>
