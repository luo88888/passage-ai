<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  GlobalOutlined,
  LinkOutlined,
  LoadingOutlined,
  TagsOutlined,
  FieldTimeOutlined,
} from '@ant-design/icons-vue'
import type { ResearchData } from '@/utils/sse'

/**
 * 信息采集结果面板（数据采集可视化）
 *
 * 展示新闻题材信息采集的结构化结果：搜索词 + 新闻条目卡片（标题/来源/时间/摘要/标签/原文链接）。
 * 支持「采集中」loading 态与空态；默认折叠，标题显示条数。
 */
const props = withDefaults(
  defineProps<{
    /** 采集结果；null 表示尚未有结果 */
    research: ResearchData | null
    /** 采集中（新闻题材、RESEARCH_COMPLETE 未到达） */
    loading?: boolean
    /** 默认是否折叠 */
    collapsed?: boolean
  }>(),
  {
    loading: false,
    collapsed: false,
  }
)

const activeKey = ref<string[]>(props.collapsed ? [] : ['research'])

const articleCount = computed(() => props.research?.articles?.length ?? 0)
const queries = computed(() => props.research?.searchQueriesUsed ?? [])
const hasData = computed(() => articleCount.value > 0 || queries.value.length > 0)
</script>

<template>
  <a-collapse
    v-model:activeKey="activeKey"
    class="research-panel"
    :bordered="false"
    expand-icon-position="end"
  >
    <a-collapse-panel key="research" header="信息采集">
      <template #extra>
        <span v-if="props.loading" class="panel-extra panel-extra--loading">
          <LoadingOutlined spin />
          采集中…
        </span>
        <span v-else-if="articleCount" class="panel-extra">
          <GlobalOutlined />
          {{ articleCount }} 条
        </span>
      </template>

      <!-- 采集中占位 -->
      <div v-if="props.loading" class="research-state">
        <a-spin size="small" />
        <span>正在采集相关新闻资讯…</span>
      </div>

      <!-- 空态：采集完成但无结果 / 非新闻题材无数据 -->
      <div v-else-if="!hasData" class="research-state">
        <span>本次未采集到相关信息</span>
      </div>

      <div v-else class="research-body">
        <!-- 搜索词 -->
        <div v-if="queries.length" class="query-block">
          <div class="query-label">
            <TagsOutlined />
            搜索词
          </div>
          <div class="query-chips">
            <a-tag v-for="(q, i) in queries" :key="i" class="query-chip">{{ q }}</a-tag>
          </div>
        </div>

        <!-- 新闻条目 -->
        <div class="article-list">
          <div v-for="(item, i) in props.research?.articles || []" :key="i" class="article-card">
            <div class="article-head">
              <a
                class="article-title"
                :href="item.url"
                target="_blank"
                rel="noopener noreferrer"
              >{{ item.title }}</a>
              <span v-if="item.source" class="article-source">{{ item.source }}</span>
            </div>
            <div v-if="item.publishTime || item.author" class="article-meta">
              <span v-if="item.publishTime" class="meta-item">
                <FieldTimeOutlined />
                {{ item.publishTime }}
              </span>
              <span v-if="item.author" class="meta-item">{{ item.author }}</span>
            </div>
            <p class="article-summary">{{ item.summary }}</p>
            <div class="article-foot">
              <div v-if="item.tags?.length" class="article-tags">
                <a-tag v-for="(t, ti) in item.tags" :key="ti" class="article-tag">{{ t }}</a-tag>
              </div>
              <a
                v-if="item.url"
                class="article-link"
                :href="item.url"
                target="_blank"
                rel="noopener noreferrer"
              >
                <LinkOutlined />
                阅读原文
              </a>
            </div>
          </div>
        </div>
      </div>
    </a-collapse-panel>
  </a-collapse>
</template>

<style scoped>
.research-panel {
  margin-top: 16px;
  background: var(--color-background-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-light);
}
.research-panel :deep(.ant-collapse) {
  background: transparent;
}
.research-panel :deep(.ant-collapse-header) {
  padding: 14px 18px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
}
.research-panel :deep(.ant-collapse-content-box) {
  padding: 8px 32px 20px;
}

.panel-extra {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: var(--color-text-secondary);
  font-weight: 400;
}
.panel-extra--loading {
  color: var(--color-primary);
}

.research-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--color-text-muted);
  padding: 24px 0;
  font-size: 14px;
}

.research-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 搜索词 */
.query-block {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.query-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: var(--color-text-muted);
  white-space: nowrap;
  margin-top: 2px;
}
.query-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.query-chip {
  margin: 0;
  background: rgba(34, 197, 94, 0.08);
  border-color: rgba(34, 197, 94, 0.2);
  color: var(--color-primary-dark);
  border-radius: var(--radius-full);
}

/* 新闻条目 */
.article-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.article-card {
  background: var(--color-background);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: 14px 16px;
}
.article-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.article-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  line-height: 1.5;
  text-decoration: none;
}
.article-title:hover {
  color: var(--color-primary);
}
.article-source {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--color-primary-dark);
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.2);
  border-radius: var(--radius-full);
  padding: 1px 10px;
  white-space: nowrap;
}
.article-meta {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--color-text-muted);
}
.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.article-summary {
  margin: 10px 0 0;
  font-size: 13px;
  line-height: 1.8;
  color: var(--color-text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.article-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 10px;
}
.article-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.article-tag {
  margin: 0;
  font-size: 12px;
  border-radius: var(--radius-full);
}
.article-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--color-primary);
  text-decoration: none;
  white-space: nowrap;
}
.article-link:hover {
  color: var(--color-primary-dark);
}
</style>
