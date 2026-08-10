<script setup lang="ts">
/**
 * 管理端意见反馈处理页（M2）
 *
 * 顶部筛选（关键字/类型/状态/时间）+ 全量分页表格（用户、类型、内容摘要、状态、提交时间）；
 * 详情抽屉（含提交用户信息）+ 回复弹窗（回复内容 + 状态选择，默认 RESOLVED，保存后提示「已通知用户」）。
 */
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import {
  SearchOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'

import {
  adminPageFeedback,
  adminGetFeedback,
  adminReplyFeedback,
  adminUpdateFeedbackStatus,
} from '@/api/feedbackController'

// ==================== 常量 ====================
const TYPE_OPTIONS = [
  { value: 'BUG', label: 'BUG' },
  { value: 'FEATURE', label: '建议' },
  { value: 'COMPLAINT', label: '投诉' },
  { value: 'OTHER', label: '其他' },
]
const TYPE_TAG_COLOR: Record<string, string> = {
  BUG: 'red',
  FEATURE: 'blue',
  COMPLAINT: 'orange',
  OTHER: 'default',
}
const STATUS_OPTIONS = [
  { value: 'PENDING', label: '待处理' },
  { value: 'PROCESSING', label: '处理中' },
  { value: 'RESOLVED', label: '已解决' },
]
const STATUS_TAG_COLOR: Record<string, string> = {
  PENDING: 'orange',
  PROCESSING: 'blue',
  RESOLVED: 'green',
}

// ==================== 列表 ====================
interface FeedbackRow {
  id: number
  userId: number
  userAccount?: string | null
  userName?: string | null
  type: string
  content: string
  contact?: string | null
  imageUrls?: string[] | null
  status: string
  replyContent?: string | null
  replyTime?: string | null
  createTime: string
}
const list = ref<FeedbackRow[]>([])
const total = ref(0)
const current = ref(1)
const pageSize = ref(10)
const keyword = ref('')
const filterType = ref<string | undefined>(undefined)
const filterStatus = ref<string | undefined>(undefined)
const dateRange = ref<[dayjs.Dayjs, dayjs.Dayjs] | null>(null)
const loading = ref(false)

const fetchList = async () => {
  loading.value = true
  try {
    const params: any = {
      current: current.value,
      pageSize: pageSize.value,
    }
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    if (filterType.value) params.type = filterType.value
    if (filterStatus.value) params.status = filterStatus.value
    if (dateRange.value && dateRange.value[0] && dateRange.value[1]) {
      params.startTime = dateRange.value[0].format('YYYY-MM-DD 00:00:00')
      params.endTime = dateRange.value[1].format('YYYY-MM-DD 23:59:59')
    }
    const res = await adminPageFeedback(params)
    if (res.data.code === 0 && res.data.data) {
      list.value = (res.data.data.records as FeedbackRow[]) ?? []
      total.value = res.data.data.total ?? 0
    } else {
      message.error(res.data.message || '获取反馈列表失败')
    }
  } catch (e: any) {
    message.error(e?.message || '获取反馈列表失败')
  } finally {
    loading.value = false
  }
}

const pagination = computed(() => ({
  current: current.value,
  pageSize: pageSize.value,
  total: total.value,
  showSizeChanger: true,
  showTotal: (t: number) => `共 ${t} 条`,
}))

const doTableChange = (page: { current: number; pageSize: number }) => {
  current.value = page.current
  pageSize.value = page.pageSize
  fetchList()
}

const doSearch = () => {
  current.value = 1
  fetchList()
}

// ==================== 详情抽屉 ====================
const detailOpen = ref(false)
const detailLoading = ref(false)
const detail = ref<FeedbackRow | null>(null)

const openDetail = async (row: FeedbackRow) => {
  detail.value = row
  detailOpen.value = true
  detailLoading.value = true
  try {
    const res = await adminGetFeedback({ feedbackId: row.id })
    if (res.data.code === 0 && res.data.data) {
      detail.value = res.data.data as FeedbackRow
    } else {
      message.error(res.data.message || '获取反馈详情失败')
    }
  } catch (e: any) {
    message.error(e?.message || '获取反馈详情失败')
  } finally {
    detailLoading.value = false
  }
}

// ==================== 回复弹窗 ====================
const replyOpen = ref(false)
const replying = ref(false)
const replyForm = ref<{ id?: number; replyContent?: string; status: string }>({
  status: 'RESOLVED',
})

const openReply = (row: FeedbackRow) => {
  replyForm.value = {
    id: row.id,
    replyContent: row.replyContent || '',
    status: row.status || 'RESOLVED',
  }
  replyOpen.value = true
}

const doReply = async () => {
  if (!replyForm.value.id) return
  if (!(replyForm.value.replyContent || '').trim()) {
    message.warning('请填写回复内容')
    return
  }
  replying.value = true
  try {
    const res = await adminReplyFeedback({
      id: replyForm.value.id,
      replyContent: (replyForm.value.replyContent || '').trim(),
      status: replyForm.value.status,
    } as any)
    if (res.data.code === 0) {
      message.success('回复成功，已通知用户')
      replyOpen.value = false
      fetchList()
      if (detail.value && detail.value.id === replyForm.value.id) {
        detail.value = res.data.data as FeedbackRow
      }
    } else {
      message.error(res.data.message || '回复失败')
    }
  } catch (e: any) {
    message.error(e?.message || '回复失败')
  } finally {
    replying.value = false
  }
}

// ==================== 仅改状态 ====================
const changeStatus = async (row: FeedbackRow, status: string) => {
  try {
    const res = await adminUpdateFeedbackStatus({ id: row.id, status } as any)
    if (res.data.code === 0) {
      message.success('状态更新成功')
      row.status = status
      if (detail.value && detail.value.id === row.id) {
        detail.value.status = status
      }
    } else {
      message.error(res.data.message || '状态更新失败')
    }
  } catch (e: any) {
    message.error(e?.message || '状态更新失败')
  }
}

// ==================== 展示 ====================
const typeLabel = (t: string) => TYPE_OPTIONS.find((o) => o.value === t)?.label || t
const typeColor = (t: string) => TYPE_TAG_COLOR[t] || 'default'
const statusLabel = (s: string) => STATUS_OPTIONS.find((o) => o.value === s)?.label || s
const statusColor = (s: string) => STATUS_TAG_COLOR[s] || 'default'
const formatTime = (v?: string | null) => {
  if (!v) return '—'
  return v.replace('T', ' ').slice(0, 19)
}

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: '用户', key: 'user', width: 180 },
  { title: '类型', dataIndex: 'type', key: 'type', width: 100 },
  { title: '反馈内容', dataIndex: 'content', key: 'content', ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 110 },
  { title: '提交时间', dataIndex: 'createTime', key: 'createTime', width: 170 },
  { title: '操作', key: 'action', width: 200 },
]

onMounted(() => {
  fetchList()
})
</script>

<template>
  <div id="feedbackAdminPage">
    <div class="page-head">
      <div class="page-head-inner">
        <h1 class="page-title">意见反馈管理</h1>
        <p class="page-subtitle">集中查看、筛选与处理用户反馈，回复后自动发送站内信通知用户</p>
        <a-button class="refresh-btn" @click="fetchList"><ReloadOutlined /> 刷新</a-button>
      </div>
    </div>

    <div class="page-body">
      <div class="filter-bar">
        <a-input
          v-model:value="keyword"
          placeholder="关键字（账号/昵称/反馈内容）"
          style="width: 240px"
          allow-clear
          @pressEnter="doSearch"
        />
        <a-select
          v-model:value="filterType"
          :allowClear="true"
          placeholder="全部类型"
          style="width: 130px"
        >
          <a-select-option v-for="o in TYPE_OPTIONS" :key="o.value" :value="o.value">
            {{ o.label }}
          </a-select-option>
        </a-select>
        <a-select
          v-model:value="filterStatus"
          :allowClear="true"
          placeholder="全部状态"
          style="width: 130px"
        >
          <a-select-option v-for="o in STATUS_OPTIONS" :key="o.value" :value="o.value">
            {{ o.label }}
          </a-select-option>
        </a-select>
        <a-range-picker v-model:value="dateRange" />
        <a-button type="primary" @click="doSearch"><SearchOutlined /> 搜索</a-button>
      </div>

      <a-table
        :columns="columns"
        :data-source="list"
        :pagination="pagination"
        :loading="loading"
        row-key="id"
        size="middle"
        @change="doTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'user'">
            <div class="user-cell">
              <span class="user-name">{{ record.userName || record.userAccount || `#${record.userId}` }}</span>
              <span v-if="record.userAccount" class="user-account">{{ record.userAccount }}</span>
            </div>
          </template>
          <template v-else-if="column.key === 'type'">
            <a-tag :color="typeColor(record.type)">{{ typeLabel(record.type) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'content'">
            <span class="content-cell">{{ record.content }}</span>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'createTime'">
            {{ formatTime(record.createTime) }}
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="openDetail(record)">详情</a-button>
              <a-button type="link" size="small" @click="openReply(record)">回复</a-button>
              <a-dropdown>
                <a-button type="link" size="small">状态</a-button>
                <template #overlay>
                  <a-menu @click="({ key }: any) => changeStatus(record, key)">
                    <a-menu-item v-for="o in STATUS_OPTIONS" :key="o.value">{{ o.label }}</a-menu-item>
                  </a-menu>
                </template>
              </a-dropdown>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 详情抽屉 -->
    <a-drawer v-model:open="detailOpen" title="反馈详情" :width="520" :loading="detailLoading">
      <template v-if="detail">
        <div class="detail-block">
          <div class="detail-label">提交用户</div>
          <div class="detail-text">
            {{ detail.userName || '—' }}
            <span v-if="detail.userAccount" class="muted">（{{ detail.userAccount }}，ID: {{ detail.userId }}）</span>
          </div>
        </div>
        <div class="detail-block">
          <div class="detail-label">反馈类型 / 状态</div>
          <a-space>
            <a-tag :color="typeColor(detail.type)">{{ typeLabel(detail.type) }}</a-tag>
            <a-tag :color="statusColor(detail.status)">{{ statusLabel(detail.status) }}</a-tag>
          </a-space>
        </div>
        <div class="detail-block">
          <div class="detail-label">反馈内容</div>
          <div class="detail-text">{{ detail.content }}</div>
        </div>
        <div v-if="detail.contact" class="detail-block">
          <div class="detail-label">联系方式</div>
          <div class="detail-text">{{ detail.contact }}</div>
        </div>
        <div v-if="detail.imageUrls && detail.imageUrls.length" class="detail-block">
          <div class="detail-label">截图（{{ detail.imageUrls.length }}）</div>
          <div class="image-grid">
            <a-image
              v-for="(url, idx) in detail.imageUrls"
              :key="idx"
              :src="url"
              :width="100"
              :height="100"
              class="detail-img"
            />
          </div>
        </div>
        <div class="detail-block">
          <div class="detail-label">提交时间</div>
          <div class="detail-text">{{ formatTime(detail.createTime) }}</div>
        </div>
        <a-divider />
        <div class="detail-block">
          <div class="detail-label">回复内容</div>
          <div v-if="detail.replyContent" class="reply-box">{{ detail.replyContent }}</div>
          <div v-else class="muted">暂未回复</div>
          <div v-if="detail.replyTime" class="muted" style="margin-top: 6px">
            回复时间：{{ formatTime(detail.replyTime) }}
          </div>
        </div>
        <a-button type="primary" block @click="openReply(detail)">回复该反馈</a-button>
      </template>
    </a-drawer>

    <!-- 回复弹窗 -->
    <a-modal
      v-model:open="replyOpen"
      title="回复反馈"
      :confirm-loading="replying"
      ok-text="回复并通知用户"
      cancel-text="取消"
      @ok="doReply"
    >
      <a-form layout="vertical">
        <a-form-item label="回复内容" required>
          <a-textarea
            v-model:value="replyForm.replyContent"
            :rows="4"
            :maxlength="2000"
            show-count
            placeholder="请输入回复内容，提交后自动发送站内信通知用户"
          />
        </a-form-item>
        <a-form-item label="处理状态">
          <a-select v-model:value="replyForm.status" style="width: 200px">
            <a-select-option v-for="o in STATUS_OPTIONS" :key="o.value" :value="o.value">
              {{ o.label }}
            </a-select-option>
          </a-select>
          <div class="muted" style="margin-top: 4px">回复后默认置为「已解决」，可手动选择其他状态</div>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<style scoped>
#feedbackAdminPage {
  padding: 24px 32px 48px;
  max-width: 1280px;
  margin: 0 auto;
}

.page-head {
  margin-bottom: 20px;
}
.page-head-inner {
  display: flex;
  align-items: center;
  gap: 16px;
}
.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text, #0f172a);
}
.page-subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-text-secondary, #64748b);
}
.refresh-btn {
  margin-left: auto;
}

.page-body {
  background: #fff;
  border: 1px solid var(--color-border-light, #e5e7eb);
  border-radius: var(--radius-lg, 16px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
  padding: 20px 24px;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.user-cell {
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}
.user-name {
  font-weight: 500;
  color: var(--color-text, #0f172a);
}
.user-account {
  font-size: 12px;
  color: var(--color-text-muted, #94a3b8);
}

.content-cell {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-block {
  margin-bottom: 16px;
}
.detail-label {
  font-size: 13px;
  color: var(--color-text-secondary, #64748b);
  margin-bottom: 6px;
}
.detail-text {
  font-size: 14px;
  color: var(--color-text, #0f172a);
  white-space: pre-wrap;
  word-break: break-word;
}
.image-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.detail-img {
  border-radius: 8px;
  object-fit: cover;
  border: 1px solid var(--color-border-light, #e5e7eb);
}
.reply-box {
  background: rgba(34, 197, 94, 0.06);
  border-left: 3px solid var(--color-primary, #22c55e);
  border-radius: 6px;
  padding: 10px 14px;
  font-size: 14px;
  color: var(--color-text, #0f172a);
  white-space: pre-wrap;
  word-break: break-word;
}
.muted {
  font-size: 13px;
  color: var(--color-text-muted, #94a3b8);
}
</style>
