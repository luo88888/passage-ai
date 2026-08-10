<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  RobotOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons-vue'
import dayjs from 'dayjs'

import {
  getExecutionLogs,
} from '@/api/articleController'

const props = defineProps<{
  taskId: string
  /** 文章当前状态，处于生成中时允许自动刷新日志 */
  articleStatus?: string
}>()

const activeKey = ref<string[]>([]) // 默认收起
const loading = ref(false)
const stats = ref<API.AgentExecutionStatsVO | null>(null)

// 智能体名称 -> 中文友好展示
const AGENT_NAME_LABEL: Record<string, string> = {
  agent1_generate_titles: '智能体一 · 生成标题方案',
  agent2_generate_outline: '智能体二 · 生成大纲',
  ai_modify_outline: '智能体二 · AI 修改大纲',
  agent3_generate_content: '智能体三 · 生成正文',
  agent4_analyze_image_requirements: '智能体四 · 分析配图需求',
  agent5_generate_images: '智能体五 · 生成配图',
  agent6_merge_content: '智能体六 · 合并内容',
}

const agentLabel = (name: string) => AGENT_NAME_LABEL[name] || name

// 状态 -> 配色/图标
const STATUS_META: Record<string, { color: string; text: string }> = {
  RUNNING: { color: '#3B82F6', text: '执行中' },
  SUCCESS: { color: '#22C55E', text: '成功' },
  FAILED: { color: '#EF4444', text: '失败' },
}
const statusMeta = (s: string) => STATUS_META[s] || { color: '#94A3B8', text: s || '未知' }

const sortedLogs = computed<API.AgentLogVO[]>(() => {
  return [...(stats.value?.logs || [])].sort((a, b) => {
    // 按开始时间升序，无开始时间兜底排到末尾
    const ta = a.startTime ? dayjs(a.startTime).valueOf() : 0
    const tb = b.startTime ? dayjs(b.startTime).valueOf() : 0
    return ta - tb
  })
})

const totalDurationText = computed(() => formatDuration(stats.value?.totalDurationMs || 0))

const overallStatusText = computed(() => {
  switch (stats.value?.overallStatus) {
    case 'SUCCESS':
      return '全部成功'
    case 'RUNNING':
      return '执行中'
    case 'FAILED':
      return '存在失败'
    case 'NOT_FOUND':
      return '暂无日志'
    default:
      return '-'
  }
})

const hasLogs = computed(() => (stats.value?.logs?.length || 0) > 0)

function formatDuration(ms?: number | null): string {
  if (ms == null) return '--'
  if (ms < 1000) return `${ms} ms`
  const s = ms / 1000
  if (s < 60) return `${s.toFixed(2)} s`
  const m = Math.floor(s / 60)
  const rest = (s - m * 60).toFixed(1)
  return `${m} 分 ${rest} s`
}

function formatTime(t?: string | null): string {
  return t ? dayjs(t).format('HH:mm:ss') : '--'
}

const fetchLogs = async () => {
  if (!props.taskId) return
  loading.value = true
  try {
    const res = await getExecutionLogs({ taskId: props.taskId })
    if (res.data?.code === 0 && res.data?.data) {
      stats.value = res.data.data
    }
  } catch (e) {
    console.warn('获取执行日志失败:', e)
  } finally {
    loading.value = false
  }
}

// 自动刷新逻辑：仅在生成中状态下，每 5 秒拉取一次
let autoTimer: ReturnType<typeof setInterval> | null = null
const startAutoRefresh = () => {
  stopAutoRefresh()
  const generating =
    props.articleStatus === 'PROCESSING' || props.articleStatus === 'PENDING'
  if (!generating) return
  autoTimer = setInterval(fetchLogs, 5000)
}
const stopAutoRefresh = () => {
  if (autoTimer) {
    clearInterval(autoTimer)
    autoTimer = null
  }
}

// 展开时才拉取日志（懒加载，避免详情页一进来就发请求）
watch(
  activeKey,
  (keys) => {
    if (keys && keys.length > 0) {
      if (!stats.value) fetchLogs()
      startAutoRefresh()
    } else {
      stopAutoRefresh()
    }
  }
)

// 文章状态变化时，同步启停自动刷新
watch(
  () => props.articleStatus,
  () => {
    if (stats.value) startAutoRefresh()
  }
)
</script>

<template>
  <a-collapse
    v-model:activeKey="activeKey"
    class="execution-log-panel"
    :bordered="false"
    expand-icon-position="end"
  >
    <a-collapse-panel key="logs" header="智能体执行日志">
      <template #extra>
        <span v-if="stats" class="panel-extra">
          <span class="extra-summary">
            <RobotOutlined />
            {{ stats.agentCount }} 个智能体
          </span>
          <span class="extra-summary">
            <ClockCircleOutlined />
            总耗时 {{ totalDurationText }}
          </span>
          <a-tag :color="statusMeta(stats.overallStatus).color" class="extra-tag">
            {{ overallStatusText }}
          </a-tag>
        </span>
      </template>

      <a-spin :spinning="loading" tip="加载中…">
        <div v-if="!hasLogs && !loading" class="empty-logs">
          暂无执行日志
        </div>

        <a-timeline v-else class="log-timeline">
          <a-timeline-item
            v-for="log in sortedLogs"
            :key="log.id"
            :color="statusMeta(log.status).color"
          >
            <template #dot>
              <LoadingOutlined v-if="log.status === 'RUNNING'" style="font-size: 16px" />
              <CheckCircleOutlined
                v-else-if="log.status === 'SUCCESS'"
                style="font-size: 16px"
              />
              <CloseCircleOutlined v-else style="font-size: 16px" />
            </template>

            <div class="log-item">
              <div class="log-row log-row--main">
                <span class="log-agent-name">{{ agentLabel(log.agentName) }}</span>
                <a-tag :color="statusMeta(log.status).color" class="log-status-tag">
                  {{ statusMeta(log.status).text }}
                </a-tag>
                <span class="log-duration">
                  <ClockCircleOutlined />
                  {{ formatDuration(log.durationMs) }}
                </span>
              </div>
              <div class="log-row log-row--time">
                <span>{{ formatTime(log.startTime) }}</span>
                <span class="time-sep">→</span>
                <span>{{ formatTime(log.endTime) }}</span>
              </div>
              <div v-if="log.status === 'FAILED' && log.errorMessage" class="log-error">
                <CloseCircleOutlined />
                <span>{{ log.errorMessage }}</span>
              </div>
            </div>
          </a-timeline-item>
        </a-timeline>
      </a-spin>
    </a-collapse-panel>
  </a-collapse>
</template>

<style scoped>
.execution-log-panel {
  margin-top: 16px;
  background: var(--color-background-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-light);
}

/* 让折叠面板整体走次级背景 */
.execution-log-panel :deep(.ant-collapse) {
  background: transparent;
}
.execution-log-panel :deep(.ant-collapse-header) {
  padding: 14px 18px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
}
.execution-log-panel :deep(.ant-collapse-content-box) {
  padding: 8px 32px 20px;
}

.panel-extra {
  display: inline-flex;
  align-items: center;
  gap: 14px;
  font-size: 13px;
  color: var(--color-text-secondary);
  font-weight: 400;
}
.extra-summary {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.extra-summary .anticon {
  color: var(--color-text-muted);
}
.extra-tag {
  margin: 0;
}

.empty-logs {
  text-align: center;
  color: var(--color-text-muted);
  padding: 24px 0;
  font-size: 14px;
}

.log-timeline {
  margin-top: 8px;
}

.log-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-bottom: 4px;
}
.log-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.log-row--main {
  flex-wrap: wrap;
}
.log-agent-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}
.log-status-tag {
  margin: 0;
}
.log-duration {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--color-text-muted);
}
.log-row--time {
  font-size: 12px;
  color: var(--color-text-muted);
  padding-left: 0;
}
.time-sep {
  color: var(--color-text-muted);
  margin: 0 4px;
}
.log-error {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12px;
  color: #EF4444;
  background: rgba(239, 68, 68, 0.08);
  border-radius: var(--radius-sm);
  padding: 6px 10px;
  margin-top: 4px;
  word-break: break-all;
}
.log-error .anticon {
  flex: none;
  margin-top: 2px;
}
</style>