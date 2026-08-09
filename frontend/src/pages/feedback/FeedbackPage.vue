<script setup lang="ts">
/**
 * 意见反馈页（M2）
 *
 * Tab1 提交反馈：类型 + 内容（1~2000 字）+ 联系方式（电话/邮箱，选填）+ 截图（最多 5 张，单张 ≤2MB）
 * Tab2 我的反馈：分页列表（类型/状态筛选）+ 详情抽屉（内容/截图/回复内容/处理进度）
 * 支持 ?activeId= 定位到某条反馈（站内信跳转回来）。
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  SendOutlined,
  UnorderedListOutlined,
  ReloadOutlined,
  PictureOutlined,
} from '@ant-design/icons-vue'

import {
  submitFeedback,
  pageMyFeedback,
  getFeedback,
  uploadFeedbackImage,
} from '@/api/feedbackController'

const route = useRoute()

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

// ==================== Tab ====================
const activeTab = ref('submit')

// ==================== 提交反馈 ====================
const submitting = ref(false)
const submitForm = ref<{ type?: string; content?: string; contact?: string }>({})
const uploadFileList = ref<any[]>([])

const MAX_IMAGE_COUNT = 5

const beforeUpload = (file: any) => {
  const allowed = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
  if (!allowed.includes(file.type)) {
    message.error('仅支持 JPG/PNG/WebP/GIF 格式的截图')
    return false
  }
  if (file.size / 1024 / 1024 > 2) {
    message.error('单张截图不能超过 2MB')
    return false
  }
  if (uploadFileList.value.length >= MAX_IMAGE_COUNT) {
    message.error(`最多上传 ${MAX_IMAGE_COUNT} 张截图`)
    return false
  }
  return true
}

const customUpload = async ({ file, onSuccess, onError }: any) => {
  try {
    const res = await uploadFeedbackImage(file as File)
    if (res.data.code === 0 && res.data.data) {
      file.url = res.data.data
      onSuccess(res.data.data)
    } else {
      message.error(res.data.message || '截图上传失败')
      onError(new Error(res.data.message || '截图上传失败'))
    }
  } catch (e: any) {
    message.error(e?.message || '截图上传失败')
    onError(e)
  }
}

// 提交反馈
const doSubmit = async () => {
  const type = submitForm.value.type
  const content = (submitForm.value.content || '').trim()
  const contact = (submitForm.value.contact || '').trim()

  if (!type) {
    message.warning('请选择反馈类型')
    return
  }
  if (!content) {
    message.warning('请填写反馈内容')
    return
  }
  if (content.length > 2000) {
    message.warning('反馈内容不能超过 2000 字')
    return
  }
  // 提交时以已成功上传的截图为准（移除上传失败/未完成的项）
  const urls = uploadFileList.value
    .filter((f) => f.status === 'done' && f.url)
    .map((f) => f.url)
    .slice(0, MAX_IMAGE_COUNT)

  submitting.value = true
  try {
    const res = await submitFeedback({
      type,
      content,
      contact: contact || undefined,
      imageUrls: urls.length ? urls : undefined,
    } as any)
    if (res.data.code === 0) {
      message.success('反馈提交成功，感谢您的建议')
      // 清空表单
      submitForm.value = {}
      uploadFileList.value = []
      activeTab.value = 'list'
      fetchList()
    } else {
      message.error(res.data.message || '提交失败')
    }
  } catch (e: any) {
    message.error(e?.message || '提交失败，请稍后再试')
  } finally {
    submitting.value = false
  }
}

// ==================== 我的反馈 ====================
interface FeedbackRow {
  id: number
  userId: number
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
const filterType = ref<string | undefined>(undefined)
const filterStatus = ref<string | undefined>(undefined)
const listLoading = ref(false)

const fetchList = async () => {
  listLoading.value = true
  try {
    const params: any = {
      current: current.value,
      pageSize: pageSize.value,
    }
    if (filterType.value) params.type = filterType.value
    if (filterStatus.value) params.status = filterStatus.value
    const res = await pageMyFeedback(params)
    if (res.data.code === 0 && res.data.data) {
      list.value = (res.data.data.records as FeedbackRow[]) ?? []
      total.value = res.data.data.total ?? 0
      // 支持 ?activeId= 定位：列表加载完成后自动打开对应反馈详情
      const activeId = Number(route.query.activeId)
      if (activeId) {
        const found = list.value.find((f) => f.id === activeId)
        if (found) {
          openDetail(found)
        } else {
          await openDetailById(activeId)
        }
      }
    } else {
      message.error(res.data.message || '获取反馈列表失败')
    }
  } catch (e: any) {
    message.error(e?.message || '获取反馈列表失败')
  } finally {
    listLoading.value = false
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

const openDetail = (row: FeedbackRow) => {
  detail.value = row
  detailOpen.value = true
}

const openDetailById = async (id: number) => {
  detailLoading.value = true
  detailOpen.value = true
  try {
    const res = await getFeedback(id)
    if (res.data.code === 0 && res.data.data) {
      detail.value = res.data.data as FeedbackRow
    } else {
      message.error(res.data.message || '获取反馈详情失败')
      detailOpen.value = false
    }
  } catch (e: any) {
    message.error(e?.message || '获取反馈详情失败')
    detailOpen.value = false
  } finally {
    detailLoading.value = false
  }
}

const typeLabel = (t: string) => TYPE_OPTIONS.find((o) => o.value === t)?.label || t
const typeColor = (t: string) => TYPE_TAG_COLOR[t] || 'default'
const statusLabel = (s: string) => STATUS_OPTIONS.find((o) => o.value === s)?.label || s
const statusColor = (s: string) => STATUS_TAG_COLOR[s] || 'default'

const formatTime = (v?: string | null) => {
  if (!v) return '—'
  return v.replace('T', ' ').slice(0, 19)
}

// 监听 ?activeId=：从站内信跳转过来时切到「我的反馈」并打开详情
watch(
  () => route.query.activeId,
  (val) => {
    if (val) {
      activeTab.value = 'list'
      current.value = 1
      fetchList()
    }
  },
  { immediate: true },
)

onMounted(() => {
  fetchList()
})
</script>

<template>
  <div id="feedbackPage">
    <div class="feedback-wrap">
      <a-tabs v-model:activeKey="activeTab" class="main-tabs">
        <!-- 提交反馈 -->
        <a-tab-pane key="submit" tab="提交反馈">
          <div class="panel-card">
            <div class="panel-head">
              <SendOutlined />
              <span>提交反馈</span>
            </div>
            <a-form layout="vertical" class="submit-form">
              <a-form-item label="反馈类型" required>
                <a-select v-model:value="submitForm.type" placeholder="请选择反馈类型" style="width: 280px">
                  <a-select-option v-for="o in TYPE_OPTIONS" :key="o.value" :value="o.value">
                    {{ o.label }}
                  </a-select-option>
                </a-select>
              </a-form-item>
              <a-form-item label="反馈内容" required>
                <a-textarea
                  v-model:value="submitForm.content"
                  :rows="6"
                  :maxlength="2000"
                  show-count
                  placeholder="请描述您遇到的问题或建议（1~2000 字）"
                />
              </a-form-item>
              <a-form-item label="联系方式（选填）">
                <a-input
                  v-model:value="submitForm.contact"
                  :maxlength="128"
                  placeholder="手机号或邮箱，便于我们与您联系"
                  style="max-width: 360px"
                />
              </a-form-item>
              <a-form-item label="截图（选填，最多 5 张，每张 ≤2MB）">
                <a-upload
                  v-model:file-list="uploadFileList"
                  list-type="picture-card"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  :before-upload="beforeUpload"
                  :custom-request="customUpload"
                >
                  <div v-if="uploadFileList.length < MAX_IMAGE_COUNT" class="upload-trigger">
                    <PictureOutlined />
                    <div class="upload-text">上传</div>
                  </div>
                </a-upload>
              </a-form-item>
              <a-form-item>
                <a-button type="primary" size="large" :loading="submitting" @click="doSubmit">
                  <SendOutlined /> 提交反馈
                </a-button>
              </a-form-item>
            </a-form>
          </div>
        </a-tab-pane>

        <!-- 我的反馈 -->
        <a-tab-pane key="list" tab="我的反馈">
          <div class="panel-card">
            <div class="panel-head">
              <UnorderedListOutlined />
              <span>我的反馈</span>
            </div>
            <div class="filter-bar">
              <a-select
                v-model:value="filterType"
                :allowClear="true"
                placeholder="全部类型"
                style="width: 150px"
                @change="doSearch"
              >
                <a-select-option v-for="o in TYPE_OPTIONS" :key="o.value" :value="o.value">
                  {{ o.label }}
                </a-select-option>
              </a-select>
              <a-select
                v-model:value="filterStatus"
                :allowClear="true"
                placeholder="全部状态"
                style="width: 150px"
                @change="doSearch"
              >
                <a-select-option v-for="o in STATUS_OPTIONS" :key="o.value" :value="o.value">
                  {{ o.label }}
                </a-select-option>
              </a-select>
              <a-button @click="doSearch"><ReloadOutlined /> 查询</a-button>
            </div>
            <a-table
              :columns="[
                { title: '类型', dataIndex: 'type', key: 'type', width: 100 },
                { title: '反馈内容', dataIndex: 'content', key: 'content', ellipsis: true },
                { title: '状态', dataIndex: 'status', key: 'status', width: 110 },
                { title: '提交时间', dataIndex: 'createTime', key: 'createTime', width: 170 },
                { title: '操作', key: 'action', width: 100 },
              ]"
              :data-source="list"
              :pagination="pagination"
              :loading="listLoading"
              row-key="id"
              size="middle"
              @change="doTableChange"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'type'">
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
                  <a-button type="link" size="small" @click="openDetail(record)">查看详情</a-button>
                </template>
              </template>
            </a-table>
          </div>
        </a-tab-pane>
      </a-tabs>

      <!-- 详情抽屉 -->
      <a-drawer
        v-model:open="detailOpen"
        title="反馈详情"
        :width="480"
        :loading="detailLoading"
      >
        <template v-if="detail">
          <div class="detail-block">
            <div class="detail-label">反馈类型</div>
            <a-tag :color="typeColor(detail.type)">{{ typeLabel(detail.type) }}</a-tag>
          </div>
          <div class="detail-block">
            <div class="detail-label">处理状态</div>
            <a-tag :color="statusColor(detail.status)">{{ statusLabel(detail.status) }}</a-tag>
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
                :width="90"
                :height="90"
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
            <div class="detail-label">管理员回复</div>
            <template v-if="detail.replyContent">
              <div class="reply-box">{{ detail.replyContent }}</div>
              <div class="detail-text reply-time">
                回复时间：{{ formatTime(detail.replyTime) }}
              </div>
            </template>
            <div v-else class="detail-text empty-reply">暂未回复，请耐心等待</div>
          </div>
        </template>
      </a-drawer>
    </div>
  </div>
</template>

<style scoped>
#feedbackPage {
  min-height: calc(100vh - 64px);
  padding: 32px 16px 48px;
  background: linear-gradient(180deg, rgba(34, 197, 94, 0.05) 0%, transparent 240px);
}

.feedback-wrap {
  width: 100%;
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.main-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 16px;
}

.panel-card {
  background: #fff;
  border: 1px solid var(--color-border-light, #e5e7eb);
  border-radius: var(--radius-lg, 16px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
  padding: 24px 28px;
}

.panel-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text, #0f172a);
  margin-bottom: 20px;
}
.panel-head .anticon {
  color: var(--color-primary, #22c55e);
}

.submit-form {
  max-width: 640px;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.content-cell {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-trigger {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: var(--color-text-secondary, #64748b);
}
.upload-text {
  font-size: 12px;
}

/* 详情 */
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
  margin-bottom: 8px;
}
.reply-time {
  font-size: 13px;
  color: var(--color-text-muted, #94a3b8);
}
.empty-reply {
  color: var(--color-text-muted, #94a3b8);
}
</style>
