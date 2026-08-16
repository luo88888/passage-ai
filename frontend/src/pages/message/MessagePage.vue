<script setup lang="ts">
/**
 * 站内信消息中心页
 *
 * 布局：分类 Tab（绿色下划线高亮）→ 操作栏（全选/标记已读/删除/全部已读）→
 *       消息列表（复选框 + 类型 + 标题/摘要 + 时间，未读加粗、已读置灰）→ 加载更多。
 * 交互：点击列表项标记已读并进入通知详情页（/message/:id，markdown 渲染正文）。
 * 说明：标题搜索按需求不实现；未读角标仅在「全部」Tab 显示总未读数。
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  BellOutlined,
  CheckOutlined,
  DeleteOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'

import {
  pageMessage,
  getMessageUnreadCount,
  readMessage,
  deleteMessage,
} from '@/api/messageController'

const router = useRouter()

// ==================== 常量 ====================
const TYPE_OPTIONS = [
  { value: 'SYSTEM', label: '系统通知' },
  { value: 'FEEDBACK', label: '反馈回复' },
  { value: 'VIP', label: '会员开通' },
  { value: 'POINTS', label: '积分变动' },
]
const TYPE_TAG_COLOR: Record<string, string> = {
  SYSTEM: 'green',
  FEEDBACK: 'cyan',
  VIP: 'gold',
  POINTS: 'lime',
}
const PAGE_SIZE = 20

// ==================== 数据 ====================
interface MessageRow {
  id: number
  type: string
  title: string
  content?: string | null
  link?: string | null
  relatedId?: number | null
  isRead: boolean
  readTime?: string | null
  createTime: string
}

const list = ref<MessageRow[]>([])
const total = ref(0)
const loading = ref(false)
const loadingMore = ref(false)
const hasMore = computed(() => list.value.length < total.value)
const activeType = ref<string | undefined>(undefined)
const unreadCount = ref(0)

// 勾选（当前已加载列表）
const selectedIds = ref<Set<number>>(new Set())
const allChecked = computed(
  () => list.value.length > 0 && list.value.every((m) => selectedIds.value.has(m.id)),
)
const someChecked = computed(
  () => list.value.some((m) => selectedIds.value.has(m.id)),
)

// ==================== 拉取 ====================
const fetchUnread = async () => {
  try {
    const res = await getMessageUnreadCount()
    if (res.data.code === 0 && res.data.data) {
      unreadCount.value = res.data.data.count ?? 0
    }
  } catch (e) {
    // 未登录等场景静默处理
  }
}

const fetchList = async (append = false) => {
  if (append && loadingMore.value) return
  append ? (loadingMore.value = true) : (loading.value = true)
  try {
    const params: any = {
      current: append ? Math.ceil(list.value.length / PAGE_SIZE) + 1 : 1,
      pageSize: PAGE_SIZE,
    }
    if (activeType.value) params.type = activeType.value
    const res = await pageMessage(params)
    if (res.data.code === 0 && res.data.data) {
      const records = (res.data.data.records as MessageRow[]) ?? []
      total.value = res.data.data.total ?? 0
      list.value = append ? [...list.value, ...records] : records
    } else {
      message.error(res.data.message || '获取消息失败')
    }
  } catch (e: any) {
    message.error(e?.message || '获取消息失败')
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

const refresh = () => {
  list.value = []
  selectedIds.value = new Set()
  fetchList()
  fetchUnread()
}

// ==================== Tab 筛选 ====================
const doTypeChange = (type?: string) => {
  activeType.value = type
  list.value = []
  selectedIds.value = new Set()
  fetchList()
}

const typeLabel = (t: string) => TYPE_OPTIONS.find((o) => o.value === t)?.label || t
const typeColor = (t: string) => TYPE_TAG_COLOR[t] || 'default'
const formatTime = (v?: string | null) => {
  if (!v) return '—'
  return v.replace('T', ' ').slice(0, 16)
}

// ==================== 选择 / 操作 ====================
const toggleAll = (checked: boolean) => {
  if (checked) {
    selectedIds.value = new Set(list.value.map((m) => m.id))
  } else {
    selectedIds.value = new Set()
  }
}

const toggleOne = (id: number, checked: boolean) => {
  const next = new Set(selectedIds.value)
  if (checked) next.add(id)
  else next.delete(id)
  selectedIds.value = next
}

const selectedList = computed(() => list.value.filter((m) => selectedIds.value.has(m.id)))

const markSelectedRead = async () => {
  const ids = [...selectedIds.value]
  if (!ids.length) return
  try {
    const res = await readMessage({ ids } as any)
    if (res.data.code === 0) {
      message.success(`已标记 ${res.data.data ?? ids.length} 条为已读`)
      list.value.forEach((m) => {
        if (selectedIds.value.has(m.id)) m.isRead = true
      })
      selectedIds.value = new Set()
      fetchUnread()
    } else {
      message.error(res.data.message || '操作失败')
    }
  } catch (e: any) {
    message.error(e?.message || '操作失败')
  }
}

const deleteSelected = () => {
  const ids = [...selectedIds.value]
  if (!ids.length) return
  Modal.confirm({
    title: '删除消息',
    content: `确定删除选中的 ${ids.length} 条消息吗？删除后不可恢复。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        const res = await deleteMessage({ ids } as any)
        if (res.data.code === 0) {
          message.success('删除成功')
          list.value = list.value.filter((m) => !selectedIds.value.has(m.id))
          total.value = Math.max(0, total.value - ids.length)
          selectedIds.value = new Set()
          fetchUnread()
        } else {
          message.error(res.data.message || '删除失败')
        }
      } catch (e: any) {
        message.error(e?.message || '删除失败')
      }
    },
  })
}

const markAllRead = async () => {
  try {
    const res = await readMessage({ all: true } as any)
    if (res.data.code === 0) {
      message.success('已全部标记为已读')
      list.value.forEach((m) => (m.isRead = true))
      unreadCount.value = 0
    } else {
      message.error(res.data.message || '操作失败')
    }
  } catch (e: any) {
    message.error(e?.message || '操作失败')
  }
}

// ==================== 进入详情 ====================
const openDetail = async (row: MessageRow) => {
  if (!row.isRead) {
    try {
      await readMessage({ ids: [row.id] } as any)
      row.isRead = true
      fetchUnread()
    } catch (e) {
      // 标记失败不阻塞跳转
    }
  }
  router.push(`/message/${row.id}`)
}

onMounted(() => {
  fetchList()
  fetchUnread()
})
</script>

<template>
  <div id="messagePage">
    <div class="message-wrap">
      <div class="panel-card">
        <!-- 标题栏 -->
        <div class="panel-head">
          <div class="panel-title">
            <BellOutlined />
            <span>消息中心</span>
          </div>
          <a-button size="small" @click="refresh"><ReloadOutlined /> 刷新</a-button>
        </div>

        <!-- 分类 Tab（绿色下划线） -->
        <div class="type-tabs">
          <div
            class="type-tab"
            :class="{ active: !activeType }"
            @click="doTypeChange(undefined)"
          >
            <span>全部</span>
            <a-badge
              v-if="unreadCount > 0"
              :count="unreadCount"
              color="green"
              :show-zero="false"
              class="tab-badge"
            />
          </div>
          <div
            v-for="o in TYPE_OPTIONS"
            :key="o.value"
            class="type-tab"
            :class="{ active: activeType === o.value }"
            @click="doTypeChange(o.value)"
          >
            <span>{{ o.label }}</span>
          </div>
        </div>

        <!-- 操作栏 -->
        <div class="action-bar">
          <a-space>
            <a-checkbox
              :checked="allChecked"
              :indeterminate="someChecked && !allChecked"
              @change="(e: any) => toggleAll(e.target.checked)"
            >
              全选
            </a-checkbox>
            <a-button
              size="small"
              :disabled="selectedIds.size === 0"
              @click="markSelectedRead"
            >
              <CheckOutlined /> 标记已读
            </a-button>
            <a-button
              size="small"
              danger
              :disabled="selectedIds.size === 0"
              @click="deleteSelected"
            >
              <DeleteOutlined /> 删除
            </a-button>
            <a-button size="small" @click="markAllRead">全部已读</a-button>
          </a-space>
          <span class="action-hint">
            {{ unreadCount > 0 ? `${unreadCount} 条未读` : '暂无未读消息' }}
          </span>
        </div>

        <!-- 列表 -->
        <a-spin :spinning="loading">
          <div v-if="list.length" class="msg-list">
            <div
              v-for="row in list"
              :key="row.id"
              class="msg-item"
              :class="{ unread: !row.isRead }"
              @click="openDetail(row)"
            >
              <div class="msg-check" @click.stop>
                <a-checkbox
                  :checked="selectedIds.has(row.id)"
                  @change="(e: any) => toggleOne(row.id, e.target.checked)"
                />
              </div>
              <div class="msg-type">
                <a-tag :color="typeColor(row.type)" class="type-tag">
                  {{ typeLabel(row.type) }}
                </a-tag>
              </div>
              <div class="msg-main">
                <div class="msg-title" :class="{ read: row.isRead }">{{ row.title }}</div>
                <div class="msg-desc" :class="{ read: row.isRead }">
                  {{ row.content || '（无内容）' }}
                </div>
              </div>
              <div class="msg-time" :class="{ read: row.isRead }">
                {{ formatTime(row.createTime) }}
              </div>
            </div>

            <!-- 加载更多（替代底部分页） -->
            <div v-if="hasMore" class="load-more">
              <a-button :loading="loadingMore" block @click="fetchList(true)">
                加载更多
              </a-button>
            </div>
            <div v-else-if="list.length" class="load-more end-tip">— 已加载全部消息 —</div>
          </div>
          <a-empty v-else :description="loading ? '加载中...' : '暂无消息'" />
        </a-spin>
      </div>
    </div>
  </div>
</template>

<style scoped>
#messagePage {
  min-height: calc(100vh - 64px);
  padding: 32px 16px 48px;
  background: linear-gradient(180deg, rgba(34, 197, 94, 0.06) 0%, transparent 240px);
}

.message-wrap {
  width: 100%;
  max-width: 860px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-card {
  background: #fff;
  border: 1px solid var(--color-border-light, #e5e7eb);
  border-radius: var(--radius-lg, 16px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
  padding: 20px 24px;
}

/* 标题栏 */
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text, #0f172a);
}
.panel-title .anticon {
  color: var(--color-primary, #22c55e);
}

/* 分类 Tab：绿色下划线 */
.type-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  border-bottom: 1px solid var(--color-border-light, #e5e7eb);
  margin-bottom: 12px;
}
.type-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-secondary, #475569);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all var(--transition-fast, 0.2s);
  user-select: none;
}
.type-tab:hover {
  color: var(--color-primary-dark, #15803d);
}
.type-tab.active {
  color: var(--color-primary-dark, #15803d);
  font-weight: 600;
  border-bottom-color: var(--color-primary, #22c55e);
}
.tab-badge {
  line-height: 1;
}

/* 操作栏 */
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 0 12px;
}
.action-hint {
  font-size: 12px;
  color: var(--color-text-muted, #94a3b8);
}

/* 消息列表 */
.msg-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.msg-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border: 1px solid var(--color-border-light, #e5e7eb);
  border-radius: 12px;
  cursor: pointer;
  transition: all var(--transition-fast, 0.2s);
  background: #fff;
}
.msg-item:hover {
  border-color: rgba(34, 197, 94, 0.5);
  box-shadow: 0 4px 14px rgba(34, 197, 94, 0.1);
  background: rgba(34, 197, 94, 0.03);
}
.msg-item.unread {
  background: rgba(34, 197, 94, 0.05);
  border-color: rgba(34, 197, 94, 0.3);
}

.msg-check {
  flex-shrink: 0;
}
.msg-type {
  flex-shrink: 0;
  width: 88px;
}
.type-tag {
  margin-inline-end: 0;
}
.msg-main {
  flex: 1;
  min-width: 0;
}
.msg-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text, #0f172a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.msg-title.read {
  font-weight: 400;
  color: var(--color-text-muted, #94a3b8);
}
.msg-desc {
  margin-top: 4px;
  font-size: 13px;
  color: var(--color-text-secondary, #475569);
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}
.msg-desc.read {
  color: var(--color-text-muted, #94a3b8);
}
.msg-time {
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-secondary, #475569);
}
.msg-time.read {
  font-weight: 400;
  color: var(--color-text-muted, #94a3b8);
}

/* 加载更多 */
.load-more {
  padding: 12px 0 4px;
  text-align: center;
}
.end-tip {
  font-size: 12px;
  color: var(--color-text-muted, #94a3b8);
}
</style>
