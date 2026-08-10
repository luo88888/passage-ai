<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  PlusOutlined,
  SearchOutlined,
  EyeOutlined,
  DownloadOutlined,
  DeleteOutlined,
  FileTextOutlined,
} from '@ant-design/icons-vue'
import dayjs from 'dayjs'

import { listArticle, deleteArticle, getArticle } from '@/api/articleController'
import { statusText, statusDotColor } from '@/utils/articleStatus'
import { exportMarkdown } from '@/utils/export'
import { useLoginUserStore } from '@/stores/loginUser'

const router = useRouter()
const route = useRoute()
const loginUserStore = useLoginUserStore()

// 列数据
const columns = [
  { title: '选题', dataIndex: 'topic', ellipsis: true },
  { title: '标题', key: 'title', width: 320 },
  { title: '状态', dataIndex: 'status', width: 120 },
  { title: '创建时间', dataIndex: 'createTime', width: 170 },
  { title: '操作', key: 'action', width: 220 },
]

// 展示数据
const data = ref<API.ArticleVO[]>([])
const total = ref(0)
const loading = ref(false)

// 搜索条件（字段对齐后端 ArticleQueryRequest：current / pageSize）
const searchParams = reactive<API.ArticleQueryRequest>({
  current: 1,
  pageSize: 10,
  topic: '',
  status: undefined,
})

// 状态下拉选项
const statusOptions = [
  { label: '全部状态', value: '' },
  // “进行中”为复合筛选：等待中(PENDING) + 生成中(PROCESSING)，后端通过 statuses 列表接受
  { label: '进行中', value: 'ACTIVE' },
  { label: '已完成', value: 'COMPLETED' },
  { label: '生成中', value: 'PROCESSING' },
  { label: '等待中', value: 'PENDING' },
  { label: '失败', value: 'FAILED' },
]

// 分页配置
const pagination = computed(() => ({
  current: searchParams.current ?? 1,
  pageSize: searchParams.pageSize ?? 10,
  total: total.value,
  showSizeChanger: true,
  showTotal: (t: number) => `共 ${t} 篇文章`,
}))

// 拉取列表
const fetchData = async () => {
  loading.value = true
  try {
    // 构建查询参数：“进行中”(ACTIVE) 映射为多状态列表，后端用 statuses 接受
    const params: Record<string, any> = {
      current: searchParams.current,
      pageSize: searchParams.pageSize,
      // 空字符串视为不筛选，避免后端按精确空值匹配
      topic: searchParams.topic || undefined,
    }
    if (searchParams.status === 'ACTIVE') {
      params.statuses = ['PENDING', 'PROCESSING']
    } else {
      params.status = searchParams.status || undefined
    }
    const res = await listArticle(params)
    const d = res.data?.data
    if (d) {
      data.value = (d.records as API.ArticleVO[]) ?? []
      total.value = d.total ?? 0
    } else {
      message.error('获取文章列表失败，' + res.data?.message)
    }
  } catch (e) {
    console.error('获取文章列表失败:', e)
  } finally {
    loading.value = false
  }
}

// 翻页
const doTableChange = (page: { current: number; pageSize: number }) => {
  searchParams.current = page.current
  searchParams.pageSize = page.pageSize
  fetchData()
}

// 搜索
const doSearch = () => {
  searchParams.current = 1
  fetchData()
}

// 跳转创作页
const goCreate = () => router.push('/create')

// 查看详情
const goDetail = (record: API.ArticleVO) => {
  router.push(`/article/${record.taskId}`)
}

// 行内导出：拉详情取 fullContent 后导出
const doExport = async (record: API.ArticleVO) => {
  if (!record.taskId) return
  try {
    const res = await getArticle({ taskId: record.taskId })
    const a = res.data?.data
    const text = a?.fullContent || a?.content || ''
    if (!text) {
      message.warning('该文章暂无可导出的内容')
      return
    }
    exportMarkdown(a?.mainTitle || record.topic || 'article', text)
    message.success('导出成功')
  } catch {
    message.error('导出失败')
  }
}

// 删除
const doDelete = async (id: number | string) => {
  if (!id) return
  const res = await deleteArticle({ id: Number(id) })
  if (res.data.code === 0) {
    message.success('删除成功')
    fetchData()
  } else {
    message.error('删除失败，' + res.data.message)
  }
}

// 状态筛选变更：重新查询 + 同步 URL（支持从个人中心等入口带参数跳转）
const onStatusChange = () => {
  doSearch()
  router.replace({
    path: '/article/list',
    query: searchParams.status ? { status: searchParams.status } : {},
  })
}

onMounted(() => {
  // 登录态兜底
  if (!loginUserStore.loginUser.id) {
    router.replace(`/user/login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`)
    return
  }
  // 支持 /article/list?status=ACTIVE|PENDING|PROCESSING|COMPLETED|FAILED 自动设置筛选
  const qStatus = route.query.status
  if (typeof qStatus === 'string' && qStatus) {
    const valid = ['ACTIVE', 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'].includes(qStatus)
    if (valid) {
      searchParams.status = qStatus as any
    }
  }
  fetchData()
})
</script>

<template>
  <div id="articleListPage">
    <!-- 页头：渐变背景 -->
    <div class="page-header">
      <div class="header-container">
        <div class="header-content">
          <h1 class="page-title">历史记录</h1>
          <p class="page-subtitle">管理您创作的所有文章</p>
        </div>
        <a-button type="primary" size="large" class="create-btn" @click="goCreate">
          <PlusOutlined />
          创作新文章
        </a-button>
      </div>
    </div>

    <div class="container">
      <a-card :bordered="false" class="content-card">
        <!-- 筛选栏 -->
        <div class="search-section">
          <a-input
            v-model:value="searchParams.topic"
            placeholder="搜索文章标题…"
            allow-clear
            class="search-input"
            @pressEnter="doSearch"
          >
            <template #prefix>
              <SearchOutlined />
            </template>
          </a-input>
          <a-select
            v-model:value="searchParams.status"
            class="status-select"
            :options="statusOptions"
            @change="onStatusChange"
          />
          <a-button type="primary" class="search-btn" @click="doSearch">
            <SearchOutlined />
            搜索
          </a-button>
          <span class="total-info">{{ total }} 篇文章</span>
        </div>

        <a-divider />

        <!-- 表格 -->
        <a-table
          :columns="columns"
          :data-source="data"
          :pagination="pagination"
          :loading="loading"
          row-key="id"
          class="article-table"
          @change="doTableChange"
        >
          <template #bodyCell="{ column, record }">
            <!-- 标题列 -->
            <template v-if="column.key === 'title'">
              <div class="title-cell">
                <div class="row-main-title">{{ record.mainTitle || '（标题生成中）' }}</div>
                <div class="row-sub-title">{{ record.subTitle || record.topic }}</div>
              </div>
            </template>
            <!-- 状态列 -->
            <template v-else-if="column.dataIndex === 'status'">
              <span class="status-badge">
                <span class="status-dot" :style="{ background: statusDotColor(record.status) }"></span>
                {{ statusText(record.status) }}
              </span>
            </template>
            <!-- 创建时间 -->
            <template v-else-if="column.dataIndex === 'createTime'">
              <span class="time-text">
                {{ dayjs(record.createTime).format('YYYY-MM-DD HH:mm') }}
              </span>
            </template>
            <!-- 操作列 -->
            <template v-else-if="column.key === 'action'">
              <a-space :size="4">
                <a-button type="link" size="small" class="op-btn view" @click="goDetail(record)">
                  <EyeOutlined /> 查看
                </a-button>
                <a-button
                  type="link"
                  size="small"
                  class="op-btn"
                  :disabled="record.status !== 'COMPLETED'"
                  @click="doExport(record)"
                >
                  <DownloadOutlined /> 导出
                </a-button>
                <a-popconfirm
                  title="确定删除该文章？此操作不可恢复"
                  ok-text="确定"
                  cancel-text="取消"
                  @confirm="doDelete(record.id)"
                >
                  <a-button type="link" size="small" danger class="op-btn">
                    <DeleteOutlined /> 删除
                  </a-button>
                </a-popconfirm>
              </a-space>
            </template>
            <!-- 选题列空态占位 -->
            <template v-else-if="column.dataIndex === 'topic'">
              <span class="topic-text">{{ record.topic || '-' }}</span>
            </template>
          </template>

          <!-- 空数据 -->
          <template #emptyText>
            <div class="empty-state">
              <FileTextOutlined class="empty-icon" />
              <p>还没有创作记录，点击右上角开始第一篇吧</p>
              <a-button type="primary" @click="goCreate">
                <PlusOutlined />
                创作新文章
              </a-button>
            </div>
          </template>
        </a-table>
      </a-card>
    </div>
  </div>
</template>

<style scoped>
#articleListPage {
  background: var(--color-background-secondary);
  min-height: calc(100vh - 64px);
  padding-bottom: 60px;
}

.page-header {
  background: var(--gradient-hero);
  padding: 36px 20px;
  margin-bottom: 24px;
}
.header-container {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}
.page-title {
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--color-text);
}
.page-subtitle {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
}
.create-btn {
  height: 42px !important;
  padding: 0 22px !important;
  font-weight: 600 !important;
  border-radius: var(--radius-md) !important;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}
.content-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}

/* 筛选栏 */
.search-section {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.search-input {
  width: 280px;
}
.status-select {
  width: 150px;
}
.search-btn {
  display: flex;
  align-items: center;
  gap: 6px;
}
.total-info {
  margin-left: auto;
  color: var(--color-text-muted);
  font-size: 13px;
}

/* 表格单元格 */
.title-cell {
  display: flex;
  flex-direction: column;
}
.row-main-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}
.row-sub-title {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.topic-text {
  font-size: 14px;
  color: var(--color-text-secondary);
}
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.time-text {
  font-size: 13px;
  color: var(--color-text-secondary);
}

/* 操作按钮 */
.op-btn {
  padding: 0 6px !important;
  font-size: 13px !important;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.op-btn.view {
  color: var(--color-primary) !important;
}
.op-btn.view:hover {
  color: var(--color-primary-dark) !important;
}

/* 空状态 */
.empty-state {
  padding: 48px 20px;
  text-align: center;
  color: var(--color-text-muted);
}
.empty-icon {
  font-size: 48px;
  color: var(--color-border);
  margin-bottom: 12px;
}
.empty-state p {
  margin: 0 0 16px;
  font-size: 14px;
}
</style>