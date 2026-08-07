<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ArrowLeftOutlined,
  DownloadOutlined,
  FileTextOutlined,
  ClockCircleOutlined,
  PictureOutlined,
  OrderedListOutlined,
} from '@ant-design/icons-vue'
import dayjs from 'dayjs'

import { getArticle } from '@/api/articleController'
import { statusText, statusDotColor } from '@/utils/articleStatus'
import { renderMarkdown } from '@/utils/markdown'
import { exportMarkdown, exportHtml } from '@/utils/export'
import { useLoginUserStore } from '@/stores/loginUser'
import ExecutionLogPanel from '@/components/article/ExecutionLogPanel.vue'
import ResearchPanel from '@/components/article/ResearchPanel.vue'
import type { ResearchData } from '@/utils/sse'

const route = useRoute()
const router = useRouter()
const loginUserStore = useLoginUserStore()

const article = ref<API.ArticleVO | null>(null)
const loading = ref(false)

// 轮询句柄（生成中状态时自动刷新）
let pollTimer: ReturnType<typeof setInterval> | null = null

// 正文 markdown HTML（优先 fullContent，回退 content）
const bodyHtml = computed(() => {
  const md = article.value?.fullContent || article.value?.content || ''
  return renderMarkdown(md)
})

// 大纲折叠面板：默认收起，用户可手动展开
const outlineActiveKey = ref<string[]>([])

const outlineList = computed(() => {
  const o = article.value?.outline
  return Array.isArray(o) ? (o as Array<{ section: number; title: string; points: string[] }>) : []
})

const imageList = computed(() => {
  const imgs = article.value?.images
  return Array.isArray(imgs) ? (imgs as Array<{ position: number; url: string; description?: string }>) : []
})

// 信息采集结果（数据采集可视化）：新闻题材且已采集完成时展示
const researchData = computed<ResearchData | null>(() => {
  const rd = (article.value as any)?.researchData
  return rd && typeof rd === 'object' ? (rd as ResearchData) : null
})

const createTimeText = computed(() => {
  const t = article.value?.createTime
  return t ? dayjs(t).format('YYYY-MM-DD HH:mm:ss') : '--'
})

// 拉取详情
const fetchDetail = async () => {
  const taskId = route.params.taskId as string
  if (!taskId) return
  try {
    const res = await getArticle({ taskId })
    if (res.data?.code === 0 && res.data?.data) {
      article.value = res.data.data
      // 状态处理：生成中则启动轮询，完成/失败则停止
      handleStatusPolling()
    } else {
      message.error(res.data?.message || '获取文章详情失败')
      router.replace('/article/list')
    }
  } catch (e) {
    console.error('获取文章详情失败:', e)
  }
}

// 根据当前状态管理轮询
const handleStatusPolling = () => {
  const status = article.value?.status
  if (status === 'PROCESSING' || status === 'PENDING') {
    startPolling()
  } else {
    stopPolling()
  }
}

const startPolling = () => {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    const taskId = route.params.taskId as string
    try {
      const res = await getArticle({ taskId })
      if (res.data?.code === 0 && res.data?.data) {
        article.value = res.data.data
        if (article.value?.status === 'COMPLETED' || article.value?.status === 'FAILED') {
          stopPolling()
        }
      }
    } catch (e) {
      console.warn('轮询刷新失败:', e)
    }
  }, 5000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// 返回
const goBack = () => {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/article/list')
  }
}

// 跳创作页观察进度
const goObserve = () => {
  const taskId = route.params.taskId as string
  router.push(`/create?taskId=${taskId}`)
}

// 导出
const doExportMd = () => {
  const a = article.value
  if (!a) return
  const text = a.fullContent || a.content || ''
  if (!text) {
    message.warning('暂无可导出的内容')
    return
  }
  exportMarkdown(a.mainTitle || a.topic || 'article', text)
}
const doExportHtml = () => {
  const a = article.value
  if (!a) return
  const text = a.fullContent || a.content || ''
  if (!text) {
    message.warning('暂无可导出的内容')
    return
  }
  exportHtml(a.mainTitle || a.topic || 'article', text)
}

onMounted(() => {
  if (!loginUserStore.loginUser.id) {
    router.replace(`/user/login?redirect=${encodeURIComponent(route.fullPath)}`)
    return
  }
  loading.value = true
  fetchDetail().finally(() => {
    loading.value = false
  })
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<template>
  <div id="articleDetailPage">
    <!-- 次级操作栏 -->
    <div class="sub-bar">
      <div class="bar-container">
        <a-button class="back-btn" @click="goBack">
          <ArrowLeftOutlined />
          返回
        </a-button>
        <a-dropdown placement="bottomRight">
          <a-button type="primary" class="export-btn" :disabled="article?.status !== 'COMPLETED'">
            <DownloadOutlined />
            导出
          </a-button>
          <template #overlay>
            <a-menu>
              <a-menu-item @click="doExportMd">导出 Markdown</a-menu-item>
              <a-menu-item @click="doExportHtml">导出 HTML</a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
      </div>
    </div>

    <div class="container">
      <a-spin :spinning="loading" tip="加载中…">
        <div v-if="article" class="article-card">
          <!-- 标题区 -->
          <div class="title-area">
            <h1 class="main-title">{{ article.mainTitle || article.topic || '（标题生成中）' }}</h1>
            <p v-if="article.subTitle" class="sub-title">{{ article.subTitle }}</p>
            <div class="meta-row">
              <span class="status-badge">
                <span class="status-dot" :style="{ background: statusDotColor(article.status) }"></span>
                {{ statusText(article.status) }}
              </span>
              <span class="create-time">
                <ClockCircleOutlined />
                创建于 {{ createTimeText }}
              </span>
            </div>
            <a-divider />
          </div>

          <!-- 智能体执行日志（默认收起，展开后时间线展示） -->
          <ExecutionLogPanel
            v-if="route.params.taskId"
            :task-id="route.params.taskId as string"
            :article-status="article.status"
          />

          <!-- 信息采集结果（新闻题材，只读回看） -->
          <ResearchPanel v-if="researchData" :research="researchData" />

          <!-- 生成中态 -->
          <div v-if="article.status === 'PROCESSING' || article.status === 'PENDING'" class="status-notice">
            <a-alert
              message="文章生成中"
              description="AI 正在创作，页面会每 5 秒自动刷新，完成后将自动展示完整内容。"
              type="info"
              show-icon
            >
              <template #action>
                <a-button size="small" type="primary" @click="goObserve">去创作页观察进度</a-button>
              </template>
            </a-alert>
          </div>

          <!-- 失败态 -->
          <div v-else-if="article.status === 'FAILED'" class="status-notice">
            <a-alert
              message="文章生成失败"
              :description="article.errorMessage || '生成过程出现错误，请重新创作'"
              type="error"
              show-icon
            >
              <template #action>
                <a-button size="small" type="primary" @click="router.push('/create')">重新创作</a-button>
              </template>
            </a-alert>
          </div>

          <!-- 完成态：大纲 + 正文 + 配图 -->
          <template v-else>
            <!-- 文章大纲 -->
            <section v-if="outlineList.length" class="article-section">
              <!-- 文章大纲：默认收起，可点击展开 -->
              <a-collapse
                v-model:activeKey="outlineActiveKey"
                class="outline-collapse"
                :bordered="false"
                expand-icon-position="end"
              >
                <a-collapse-panel key="outline">
                  <template #header>
                    <span class="section-title">
                      <OrderedListOutlined />
                      文章大纲
                    </span>
                  </template>
                  <div class="outline-list">
                    <div v-for="item in outlineList" :key="item.section" class="outline-block">
                      <div class="outline-block-title">{{ item.section }}. {{ item.title }}</div>
                      <ul class="outline-points">
                        <li v-for="(p, i) in item.points" :key="i">{{ p }}</li>
                      </ul>
                    </div>
                  </div>
                </a-collapse-panel>
              </a-collapse>
            </section>

            <!-- 文章正文 -->
            <section v-if="bodyHtml" class="article-section">
              <h2 class="section-title">
                <FileTextOutlined />
                正文内容
              </h2>
              <div class="markdown-body" v-html="bodyHtml"></div>
            </section>

            <!-- 配图 Gallery -->
            <section v-if="imageList.length" class="article-section">
              <h2 class="section-title">
                <PictureOutlined />
                配图列表
              </h2>
              <div class="image-gallery">
                <div v-for="img in imageList" :key="img.position" class="gallery-item">
                  <a-image :src="img.url" class="gallery-img" :preview="{ src: img.url }" />
                  <p v-if="img.description" class="img-desc">{{ img.description }}</p>
                </div>
              </div>
            </section>

            <!-- 无内容兜底 -->
            <div v-if="!outlineList.length && !bodyHtml && !imageList.length" class="empty-content">
              暂无可显示的内容
            </div>
          </template>
        </div>
      </a-spin>
    </div>
  </div>
</template>

<style scoped>
#articleDetailPage {
  min-height: calc(100vh - 64px);
  background: #F4F6F8;
  padding-bottom: 60px;
}

/* 次级操作栏：浅绿条，吸附固定不随正文滚动 */
.sub-bar {
  position: sticky;
  top: 64px; /* 64px 全局顶部导航栏高度 */
  z-index: 50;
  background: var(--gradient-hero);
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border-light);
}
.bar-container {
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.7);
}
.export-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
}

.container {
  max-width: 960px;
  margin: 24px auto 0;
  padding: 0 20px;
}

/* 文章主卡片 */
.article-card {
  background: var(--color-background);
  border-radius: var(--radius-xl);
  padding: 40px 48px;
  box-shadow: var(--shadow-card);
}

/* 标题区 */
.title-area {
  text-align: center;
  margin-bottom: 8px;
}
.main-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 10px;
  line-height: 1.3;
}
.sub-title {
  font-size: 16px;
  color: var(--color-text-secondary);
  margin: 0 0 14px;
}
.meta-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
}
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 12px;
  background: rgba(34, 197, 94, 0.1);
  border-radius: var(--radius-full);
  font-size: 13px;
  color: var(--color-primary-dark);
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.create-time {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: var(--color-text-muted);
}

/* 状态提示 */
.status-notice {
  margin: 8px 0;
}

/* 章节 */
.article-section {
  margin-top: 28px;
}
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 16px;
}
.section-title .anticon {
  color: var(--color-primary);
}

/* 大纲折叠面板（默认收起） */
.outline-collapse {
  background: transparent;
}
.outline-collapse :deep(.ant-collapse-header) {
  align-items: center;
  padding: 0 0 16px;
}
.outline-collapse :deep(.ant-collapse-content-box) {
  padding: 0;
}
.outline-collapse .section-title {
  margin-bottom: 0;
}
.outline-collapse :deep(.ant-collapse-expand-icon) {
  color: var(--color-primary);
}

/* 大纲 */
.outline-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.outline-block {
  background: var(--color-background-secondary);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: 16px 18px;
}
.outline-block-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 10px;
}
.outline-points {
  margin: 0;
  padding-left: 22px;
  color: var(--color-text-secondary);
  font-size: 14px;
  line-height: 1.9;
}
.outline-points li {
  margin-bottom: 4px;
}

/* markdown 正文 */
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
  border-radius: var(--radius-md);
  overflow: auto;
}
.markdown-body :deep(code) {
  background: var(--color-background-tertiary);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.9em;
}
.markdown-body :deep(blockquote) {
  border-left: 4px solid var(--color-primary);
  margin: 14px 0;
  padding: 8px 16px;
  color: var(--color-text-secondary);
  background: var(--color-background-secondary);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 22px;
  margin: 12px 0;
}
.markdown-body :deep(li) {
  margin-bottom: 4px;
}

/* 配图 */
.image-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}
.gallery-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.gallery-img {
  width: 100%;
  height: 160px;
  object-fit: cover;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
}
.img-desc {
  font-size: 12px;
  color: var(--color-text-muted);
  margin: 0;
}

.empty-content {
  text-align: center;
  color: var(--color-text-muted);
  padding: 40px 0;
}

@media (max-width: 768px) {
  .article-card {
    padding: 24px 18px;
  }
  .main-title {
    font-size: 22px;
  }
}
</style>
