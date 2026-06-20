<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import * as echarts from 'echarts'
import {
  RocketOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  RiseOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import { getStatisticsOverview } from '@/api/statisticsController'

// 统计数据
interface StatisticsVO {
  todayCount: number
  weekCount: number
  monthCount: number
  totalCount: number
  successRate: number
  avgDurationMs: number
  activeUserCount: number
  totalUserCount: number
  vipUserCount: number
  quotaUsed: number
  totalQuota: number
}

const stats = ref<StatisticsVO | null>(null)
const loading = ref(false)

// 图表实例（便于销毁）
let trendChart: echarts.ECharts | null = null
let perfChart: echarts.ECharts | null = null
let userChart: echarts.ECharts | null = null
let quotaChart: echarts.ECharts | null = null

// 毫秒转可读时长
const formatDuration = (ms: number): string => {
  if (!ms || ms <= 0) return '--'
  const totalSec = ms / 1000
  if (totalSec < 60) return `${totalSec.toFixed(1)} 秒`
  const min = Math.floor(totalSec / 60)
  const sec = Math.round(totalSec % 60)
  return `${min} 分 ${sec} 秒`
}

// 加载统计数据
const loadStatistics = async () => {
  loading.value = true
  try {
    const res = await getStatisticsOverview()
    if (res.data.code === 0) {
      stats.value = res.data.data as StatisticsVO
      await nextTick()
      renderCharts()
    } else {
      message.error('获取统计数据失败：' + res.data.message)
    }
  } catch (error) {
    console.error('获取统计数据失败:', error)
    message.error('获取统计数据失败')
  } finally {
    loading.value = false
  }
}

// 初始化图表 DOM
const initChart = (el: HTMLElement | null): echarts.ECharts | null => {
  if (!el) return null
  const chart = echarts.init(el)
  return chart
}

// 渲染所有图表
const renderCharts = () => {
  const data = stats.value
  if (!data) return

  // 1. 创作趋势图（柱状图）
  const trendEl = document.getElementById('trend-chart')
  if (trendEl) {
    if (trendChart) trendChart.dispose()
    trendChart = initChart(trendEl)
    trendChart?.setOption({
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
      },
      legend: { data: ['创作数'], top: 10 },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: ['今日', '本周', '本月', '总计'],
        axisLine: { lineStyle: { color: '#cbd5e1' } },
        axisLabel: { color: '#64748b' },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#64748b' },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
      },
      series: [
        {
          name: '创作数',
          type: 'bar',
          data: [
            data.todayCount,
            data.weekCount,
            data.monthCount,
            data.totalCount,
          ],
          barWidth: '40%',
          itemStyle: {
            borderRadius: [8, 8, 0, 0],
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#4ADE80' },
              { offset: 1, color: '#16A34A' },
            ]),
          },
        },
      ],
    })
  }

  // 2. 性能统计图（平均耗时 + 成功率）
  const perfEl = document.getElementById('perf-chart')
  if (perfEl) {
    if (perfChart) perfChart.dispose()
    perfChart = initChart(perfEl)
    const avgSec = data.avgDurationMs ? +(data.avgDurationMs / 1000).toFixed(2) : 0
    perfChart?.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['平均耗时(秒)', '成功率(%)'], top: 10 },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: ['性能指标'],
        axisLine: { lineStyle: { color: '#cbd5e1' } },
        axisLabel: { color: '#64748b' },
      },
      yAxis: [
        {
          type: 'value',
          name: '耗时(秒)',
          position: 'left',
          axisLabel: { color: '#64748b' },
          splitLine: { lineStyle: { color: '#f1f5f9' } },
        },
        {
          type: 'value',
          name: '成功率(%)',
          position: 'right',
          min: 0,
          max: 100,
          axisLabel: { color: '#64748b', formatter: '{value}%' },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: '平均耗时(秒)',
          type: 'bar',
          barWidth: '30%',
          data: [avgSec],
          itemStyle: {
            borderRadius: [8, 8, 0, 0],
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#60A5FA' },
              { offset: 1, color: '#2563EB' },
            ]),
          },
        },
        {
          name: '成功率(%)',
          type: 'bar',
          barWidth: '30%',
          yAxisIndex: 1,
          data: [+data.successRate.toFixed(2)],
          itemStyle: {
            borderRadius: [8, 8, 0, 0],
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#FBBF24' },
              { offset: 1, color: '#D97706' },
            ]),
          },
        },
      ],
    })
  }

  // 3. 用户分析（扇形图，鼠标悬浮高亮）
  const userEl = document.getElementById('user-chart')
  if (userEl) {
    if (userChart) userChart.dispose()
    userChart = initChart(userEl)
    const otherUsers = Math.max(
      0,
      data.totalUserCount - data.vipUserCount - data.activeUserCount
    )
    userChart?.setOption({
      tooltip: {
        trigger: 'item',
        formatter: '{a} <br/>{b}: {c} ({d}%)',
      },
      legend: {
        orient: 'vertical',
        left: 'left',
        top: 'middle',
        textStyle: { color: '#64748b' },
      },
      series: [
        {
          name: '用户分布',
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['60%', '50%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 8,
            borderColor: '#fff',
            borderWidth: 2,
          },
          label: { show: false, position: 'center' },
          emphasis: {
            scale: true,
            scaleSize: 10,
            label: {
              show: true,
              fontSize: 16,
              fontWeight: 'bold',
              formatter: '{b}\n{c} 人',
            },
          },
          labelLine: { show: false },
          data: [
            { value: data.vipUserCount, name: 'VIP 用户', itemStyle: { color: '#F59E0B' } },
            { value: data.activeUserCount, name: '活跃用户', itemStyle: { color: '#22C55E' } },
            { value: otherUsers, name: '其它用户', itemStyle: { color: '#94A3B8' } },
          ],
        },
      ],
    })
  }

  // 4. 配额使用情况（扇形图）
  const quotaEl = document.getElementById('quota-chart')
  if (quotaEl) {
    if (quotaChart) quotaChart.dispose()
    quotaChart = initChart(quotaEl)
    const quotaRemaining = Math.max(0, data.totalQuota - data.quotaUsed)
    quotaChart?.setOption({
      tooltip: {
        trigger: 'item',
        formatter: '{a} <br/>{b}: {c} ({d}%)',
      },
      legend: {
        orient: 'vertical',
        left: 'left',
        top: 'middle',
        textStyle: { color: '#64748b' },
      },
      series: [
        {
          name: '配额分布',
          type: 'pie',
          radius: ['45%', '70%'],
          center: ['60%', '50%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 8,
            borderColor: '#fff',
            borderWidth: 2,
          },
          label: { show: false, position: 'center' },
          emphasis: {
            scale: true,
            scaleSize: 10,
            label: {
              show: true,
              fontSize: 16,
              fontWeight: 'bold',
              formatter: '{b}\n{c}',
            },
          },
          labelLine: { show: false },
          data: [
            { value: data.quotaUsed, name: '已使用', itemStyle: { color: '#EF4444' } },
            { value: quotaRemaining, name: '剩余配额', itemStyle: { color: '#22C55E' } },
          ],
        },
      ],
    })
  }
}

// 窗口尺寸变化时重绘图表
const handleResize = () => {
  trendChart?.resize()
  perfChart?.resize()
  userChart?.resize()
  quotaChart?.resize()
}

onMounted(() => {
  loadStatistics()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  perfChart?.dispose()
  userChart?.dispose()
  quotaChart?.dispose()
  trendChart = null
  perfChart = null
  userChart = null
  quotaChart = null
})
</script>

<template>
  <div id="statisticsPage">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-container">
        <div class="header-content">
          <div class="title-row">
            <div>
              <h1 class="page-title">数据分析</h1>
              <p class="page-subtitle">运营数据概览与统计分析</p>
            </div>
            <a-button type="primary" :loading="loading" @click="loadStatistics" class="refresh-btn">
              <template #icon>
                <ReloadOutlined />
              </template>
              刷新
            </a-button>
          </div>
        </div>
      </div>
    </div>

    <div class="container">
      <a-spin :spinning="loading">
        <!-- 顶部核心指标卡片 -->
        <div class="metrics-grid">
          <div class="metric-card metric-today">
            <div class="metric-icon">
              <RocketOutlined />
            </div>
            <div class="metric-body">
              <div class="metric-label">今日创作数</div>
              <div class="metric-value">{{ stats?.todayCount ?? '--' }}</div>
              <div class="metric-desc">篇</div>
            </div>
          </div>

          <div class="metric-card metric-week">
            <div class="metric-icon">
              <RiseOutlined />
            </div>
            <div class="metric-body">
              <div class="metric-label">本周创作数</div>
              <div class="metric-value">{{ stats?.weekCount ?? '--' }}</div>
              <div class="metric-desc">篇</div>
            </div>
          </div>

          <div class="metric-card metric-month">
            <div class="metric-icon">
              <ClockCircleOutlined />
            </div>
            <div class="metric-body">
              <div class="metric-label">本月创作数</div>
              <div class="metric-value">{{ stats?.monthCount ?? '--' }}</div>
              <div class="metric-desc">篇</div>
            </div>
          </div>

          <div class="metric-card metric-success">
            <div class="metric-icon">
              <CheckCircleOutlined />
            </div>
            <div class="metric-body">
              <div class="metric-label">创作成功率</div>
              <div class="metric-value">
                {{ stats ? stats.successRate.toFixed(1) : '--' }}<span class="metric-unit">%</span>
              </div>
              <div class="metric-desc">已完成 / 总创作</div>
            </div>
          </div>
        </div>

        <!-- 图表区域 -->
        <div class="charts-grid">
          <a-card :bordered="false" class="chart-card">
            <template #title>
              <span class="chart-title">创作趋势</span>
            </template>
            <div id="trend-chart" class="chart-box"></div>
          </a-card>

          <a-card :bordered="false" class="chart-card">
            <template #title>
              <span class="chart-title">性能统计</span>
            </template>
            <div id="perf-chart" class="chart-box"></div>
          </a-card>

          <a-card :bordered="false" class="chart-card">
            <template #title>
              <span class="chart-title">用户分析</span>
            </template>
            <div id="user-chart" class="chart-box"></div>
          </a-card>

          <a-card :bordered="false" class="chart-card">
            <template #title>
              <span class="chart-title">配额使用情况</span>
            </template>
            <div id="quota-chart" class="chart-box"></div>
          </a-card>
        </div>
      </a-spin>
    </div>
  </div>
</template>

<style scoped>
#statisticsPage {
  width: 100%;
  min-height: 100vh;
  background: var(--color-background-secondary);
}

.page-header {
  background: white;
  border-bottom: 1px solid var(--color-border);
  padding: 32px 0;
}

.header-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
}

.title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 8px;
  color: var(--color-text);
  letter-spacing: -0.5px;
}

.page-subtitle {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--gradient-primary) !important;
  border: none !important;
  box-shadow: var(--shadow-green) !important;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

/* 指标卡片 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 24px;
}

.metric-card {
  background: white;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  padding: 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: all var(--transition-normal);
  position: relative;
  overflow: hidden;
}

.metric-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
}

.metric-today::before { background: #22C55E; }
.metric-week::before { background: #3B82F6; }
.metric-month::before { background: #8B5CF6; }
.metric-success::before { background: #F59E0B; }

.metric-card:hover {
  box-shadow: var(--shadow-card-hover);
  transform: translateY(-2px);
}

.metric-icon {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  font-size: 26px;
  flex-shrink: 0;
}

.metric-today .metric-icon { background: rgba(34, 197, 94, 0.1); color: #16A34A; }
.metric-week .metric-icon { background: rgba(59, 130, 246, 0.1); color: #2563EB; }
.metric-month .metric-icon { background: rgba(139, 92, 246, 0.1); color: #7C3AED; }
.metric-success .metric-icon { background: rgba(245, 158, 11, 0.1); color: #D97706; }

.metric-body {
  flex: 1;
  min-width: 0;
}

.metric-label {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-bottom: 6px;
}

.metric-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text);
  line-height: 1;
  letter-spacing: -0.5px;
}

.metric-unit {
  font-size: 18px;
  font-weight: 500;
  margin-left: 2px;
}

.metric-desc {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 6px;
}

/* 图表区 */
.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.chart-card {
  border-radius: var(--radius-lg) !important;
  border: 1px solid var(--color-border) !important;
}

.chart-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
}

.chart-box {
  width: 100%;
  height: 340px;
}

/* 响应式 */
@media (max-width: 992px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .charts-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 576px) {
  .metrics-grid {
    grid-template-columns: 1fr;
  }

  .metric-value {
    font-size: 26px;
  }

  .title-row {
    flex-direction: column;
    gap: 16px;
  }
}
</style>