<template>
  <div class="page">
    <el-card shadow="never" class="block-card">
      <template #header>
        <div class="card-header">
          <div>
            <div class="section-label">RECORDS</div>
            <h2 class="section-title">我的申请记录</h2>
          </div>
          <el-button class="refresh-btn" text @click="loadList">刷新</el-button>
        </div>
      </template>

      <el-table :data="list" v-loading="loading" stripe empty-text="暂无申请记录，去首页提交一条吧"
                :row-class-name="rowClass">
        <!-- 展开行：显示所有审批记录 -->
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand-content">
              <div v-if="row.approvals && row.approvals.length > 0">
                <div v-for="(ar, idx) in row.approvals" :key="idx" class="approval-item">
                  <el-tag :type="ar.action === 'approved' ? 'success' : 'danger'" size="small">
                    {{ ar.action === 'approved' ? '通过' : '驳回' }}
                  </el-tag>
                  <span class="approval-reviewer">{{ ar.reviewer_name }}</span>
                  <span class="approval-reason">{{ ar.reason }}</span>
                  <span class="approval-time">{{ ar.created_at }}</span>
                </div>
              </div>
              <el-empty v-else description="暂无审批记录" :image-size="40" />
            </div>
          </template>
        </el-table-column>

        <el-table-column label="图片" width="100">
          <template #default="{ row }">
            <el-image :src="row.image_path" :preview-src-list="[row.image_path]"
                      fit="cover" class="thumb" preview-teleported />
          </template>
        </el-table-column>
        <el-table-column prop="item_name" label="物品名称" min-width="120" show-overflow-tooltip />
        <el-table-column prop="price" label="价格(元)" width="100">
          <template #default="{ row }">{{ Number(row.price).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="140" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status].type">{{ statusMap[row.status].text }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="审批人数" width="100">
          <template #default="{ row }">
            <el-badge :value="row.approvals.length" :hidden="!row.approvals || row.approvals.length === 0" type="primary">
              <span class="approval-count">{{ row.approvals ? row.approvals.length : 0 }} 人</span>
            </el-badge>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="提交时间" width="170" />
      </el-table>

      <p class="tip">提示：点击左侧 <el-icon><ArrowRight /></el-icon> 展开行可查看每位用户的审批详情（多人审批，每人各审一次）。</p>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'
import { applyApi } from '../api'

const list = ref([])
const loading = ref(false)

const statusMap = {
  pending: { text: '待审批', type: 'warning' },
  approved: { text: '已通过', type: 'success' },
  rejected: { text: '已驳回', type: 'danger' }
}

function rowClass({ row }) {
  if (row.approvals && row.approvals.length > 0) {
    const hasReject = row.approvals.some(a => a.action === 'rejected')
    const hasApprove = row.approvals.some(a => a.action === 'approved')
    if (hasReject && hasApprove) return 'row-mixed'
    if (hasReject) return 'row-rejected'
    if (hasApprove) return 'row-approved'
  }
  return ''
}

async function loadList() {
  loading.value = true
  try {
    list.value = await applyApi.mine()
  } finally {
    loading.value = false
  }
}

onMounted(loadList)
</script>

<style scoped>
.page {
  max-width: 1200px;
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
.refresh-btn {
  color: var(--color-muted);
}
.thumb {
  width: 64px;
  height: 64px;
  border-radius: 6px;
}
.tip {
  color: var(--color-muted);
  font-size: 12px;
  margin: 12px 0 0;
  display: flex;
  align-items: center;
  gap: 4px;
}
.expand-content {
  padding: 12px 20px 12px 48px;
}
.approval-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border);
}
.approval-item:last-child {
  border-bottom: none;
}
.approval-reviewer {
  font-weight: 600;
  color: var(--color-text);
  min-width: 80px;
}
.approval-reason {
  color: var(--color-muted);
  flex: 1;
}
.approval-time {
  color: #c0c4cc;
  font-size: 12px;
  white-space: nowrap;
}
.approval-count {
  font-size: 14px;
  color: var(--color-text);
}
:deep(.row-approved) {
  background-color: #f0f9eb;
}
:deep(.row-rejected) {
  background-color: #fef0f0;
}
:deep(.row-mixed) {
  background-color: #fdf6ec;
}
@media (max-width: 768px) {
  .page {
    padding: 20px 16px 0;
  }
}
</style>
