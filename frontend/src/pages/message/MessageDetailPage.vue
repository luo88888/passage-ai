<script setup lang="ts">
/**
 * 站内信通知详情页（M3）
 *
 * 展示单条通知：类型 / 标题 / 时间，正文以 markdown 渲染（utils/markdown 封装，
 * marked + DOMPurify 净化）。进入页面时若未读则自动标记已读并刷新头部角标。
 */
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ArrowLeftOutlined,
  BellOutlined,
} from '@ant-design/icons-vue'

import { getMessageDetail, readMessage } from '@/api/messageController'
import { renderMarkdown } from '@/utils/markdown'

const route = useRoute()
const router = useRouter()

const TYPE_OPTIONS: Record<string, { label: string; color: string }> = {
  SYSTEM: { label: '系统通知', color: 'green' },
  FEEDBACK: { label: '反馈回复', color: 'cyan' },
  VIP: { label: '会员开通', color: 'gold' },
  POINTS: { label: '积分变动', color: 'lime' },
}

interface MessageDetail {
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

const messageId = Number(route.params.id)
const detail = ref<MessageDetail | null>(null)
const loading = ref(false)
const notFound = ref(false)

const bodyHtml = computed(() => renderMarkdown(detail.value?.content))
const typeMeta = computed(() => TYPE_OPTIONS[detail.value?.type || ''] || { label: detail.value?.type || '', color: 'default' })

const formatTime = (v?: string | null) => {
  if (!v) return '—'
  return v.replace('T', ' ').slice(0, 19)
}

const goBack = () => {
  // 返回上一页；无历史则回消息中心
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/message')
  }
}

const fetchDetail = async () => {
  loading.value = true
  try {
    const res = await getMessageDetail(messageId)
    if (res.data.code === 0 && res.data.data) {
      detail.value = res.data.data as MessageDetail
      // 未读自动标记已读
      if (!detail.value.isRead) {
        await readMessage({ ids: [messageId] } as any)
        detail.value.isRead = true
      }
    } else {
      notFound.value = true
    }
  } catch (e: any) {
    notFound.value = true
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDetail()
})
</script>

<template>
  <div id="messageDetailPage">
    <!-- 顶部绿色操作条 -->
    <div class="sub-bar">
      <div class="bar-container">
        <a-button class="back-btn" @click="goBack">
          <ArrowLeftOutlined />
          <span>返回</span>
        </a-button>
        <span class="bar-title">通知详情</span>
        <span class="bar-spacer"></span>
      </div>
    </div>

    <div class="detail-wrap">
      <a-spin :spinning="loading">
        <template v-if="detail">
          <div class="detail-card">
            <div class="detail-head">
              <a-tag :color="typeMeta.color">{{ typeMeta.label }}</a-tag>
              <span v-if="!detail.isRead" class="unread-tag">未读</span>
            </div>
            <h1 class="detail-title">{{ detail.title }}</h1>
            <div class="detail-meta">
              <span><BellOutlined /> {{ formatTime(detail.createTime) }}</span>
              <span v-if="detail.readTime">已读时间：{{ formatTime(detail.readTime) }}</span>
            </div>
            <a-divider />

            <!-- markdown 正文 -->
            <div v-if="bodyHtml" class="markdown-body" v-html="bodyHtml"></div>
            <div v-else class="empty-content">（无内容）</div>
          </div>
        </template>
        <a-empty v-else-if="!loading && notFound" description="消息不存在或已删除" />
      </a-spin>
    </div>
  </div>
</template>

<style scoped>
#messageDetailPage {
  min-height: calc(100vh - 64px);
  background: linear-gradient(180deg, rgba(34, 197, 94, 0.06) 0%, transparent 240px);
  padding-bottom: 60px;
}

/* 顶部操作条：浅绿 */
.sub-bar {
  position: sticky;
  top: 64px;
  z-index: 50;
  background: var(--gradient-hero, linear-gradient(135deg, #ecfdf5, #f0fdf4));
  padding: 14px 20px;
  border-bottom: 1px solid var(--color-border-light, #e5e7eb);
}
.bar-container {
  max-width: 860px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--color-border, #e5e7eb);
  background: rgba(255, 255, 255, 0.85);
  color: var(--color-primary-dark, #15803d);
}
.back-btn:hover {
  border-color: var(--color-primary, #22c55e);
  color: var(--color-primary-dark, #15803d);
}
.bar-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text, #0f172a);
}
.bar-spacer {
  width: 64px;
}

.detail-wrap {
  max-width: 860px;
  margin: 24px auto 0;
  padding: 0 16px;
}

.detail-card {
  background: #fff;
  border: 1px solid var(--color-border-light, #e5e7eb);
  border-radius: var(--radius-lg, 16px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
  padding: 28px 32px;
}

.detail-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.unread-tag {
  font-size: 12px;
  color: #fff;
  background: var(--color-primary, #22c55e);
  border-radius: 999px;
  padding: 1px 10px;
}
.detail-title {
  margin: 0 0 10px;
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text, #0f172a);
  line-height: 1.4;
}
.detail-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 13px;
  color: var(--color-text-muted, #94a3b8);
  flex-wrap: wrap;
}

.empty-content {
  padding: 40px 0;
  text-align: center;
  color: var(--color-text-muted, #94a3b8);
  font-size: 14px;
}

/* markdown 正文（与文章详情一致） */
.markdown-body {
  color: var(--color-text);
  font-size: 15px;
  line-height: 1.9;
}
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 22px 0 12px;
  font-weight: 700;
  color: var(--color-text);
}
.markdown-body :deep(h1) {
  font-size: 22px;
}
.markdown-body :deep(h2) {
  font-size: 19px;
}
.markdown-body :deep(h3) {
  font-size: 16px;
}
.markdown-body :deep(p) {
  margin: 12px 0;
}
.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: var(--radius-md);
  margin: 14px 0;
}
.markdown-body :deep(pre) {
  background: var(--color-background-tertiary);
  padding: 14px 16px;
  overflow: auto;
  border-radius: 8px;
}
.markdown-body :deep(code) {
  background: var(--color-background-tertiary);
  padding: 2px 6px;
  font-size: 0.9em;
}
.markdown-body :deep(blockquote) {
  border-left: 4px solid var(--color-primary);
  margin: 14px 0;
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  padding-left: 14px;
  color: var(--color-text-secondary);
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 22px;
  margin: 12px 0;
}
.markdown-body :deep(li) {
  margin-bottom: 4px;
}
.markdown-body :deep(a) {
  color: var(--color-primary-dark);
}
.markdown-body :deep(table) {
  border-collapse: collapse;
  margin: 14px 0;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid var(--color-border-light, #e5e7eb);
  padding: 6px 12px;
}
</style>
