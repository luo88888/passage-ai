<script setup lang="ts">
/**
 * 积分中心页
 *
 * 内容：余额卡片 + 每日签到、积分明细分页（类型/时间筛选）、各模型用量统计（表格 + ECharts）。
 * 数据来源：GET /points/balance、POST /points/checkin、POST /points/transactions、GET /points/usage/stats。
 */
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import {
  WalletOutlined,
  GiftOutlined,
  CheckCircleOutlined,
  ReloadOutlined,
  HistoryOutlined,
  BarChartOutlined,
} from '@ant-design/icons-vue'

import { useLoginUserStore } from '@/stores/loginUser'
import {
  getPointsBalance,
  checkin,
  listPointsTransactions,
  getPointsUsageStats,
} from '@/api/pointsController'

const loginUserStore = useLoginUserStore()

// ==================== 余额与签到 ====================
const balance = ref(0)
const totalEarned = ref(0)
const totalConsumed = ref(0)
const checkedInToday = ref(false)
const balanceLoading = ref(false)
const checkingIn = ref(false)

const fetchBalance = async () => {
  balanceLoading.value = true
  try {
    const res = await getPointsBalance()
    if (res.data.code === 0 && res.data.data) {
      balance.value = res.data.data.balance ?? 0
      totalEarned.value = res.data.data.totalEarned ?? 0
      totalConsumed.value = res.data.data.totalConsumed ?? 0
      checkedInToday.value = !!res.data.data.checkedInToday
    }
  } catch (e) {
    console.error('获取积分余额失败:', e)
  } finally {
    balanceLoading.value = false
  }
}

const doCheckin = async () => {
  if (checkedInToday.value) return
  checkingIn.value = true
  try {
    const res = await checkin()
    if (res.data.code === 0 && res.data.data) {
      checkedInToday.value = true
      message.success(`签到成功，+${res.data.data.gained} 积分`)
      await fetchBalance()
      await loginUserStore.fetchLoginUser()
      await fetchTransactions()
    } else {
      message.error(res.data.message || '签到失败')
    }
  } catch (e: any) {
    message.error(e?.message || '签到失败，请稍后再试')
  } finally {
    checkingIn.value = false
  }
}

// ==================== 积分明细 ====================
const TX_TYPE_OPTIONS = [
  { value: 'REGISTER', label: '注册赠送' },
  { value: 'SIGN_IN', label: '每日签到' },
  { value: 'USAGE_SETTLE', label: '创作消耗' },
  { value: 'ADMIN_ADJUST', label: '管理员调整' },
]
const TX_TAG_COLOR: Record<string, string> = {
  REGISTER: 'green',
  SIGN_IN: 'cyan',
  USAGE_SETTLE: 'orange',
  ADMIN_ADJUST: 'purple',
}

interface TransactionRow {
  id: number
  type: string
  amount: number
  balanceAfter: number
  description?: string | null
  createTime: string
}
interface UsageStatRow {
  category: string
  provider: string
  model: string
  callCount: number
  inputTokens: number
  outputTokens: number
  imageCount: number
  costPoints: number
}

const transactions = ref<TransactionRow[]>([])
const txTotal = ref(0)
const txCurrent = ref(1)
const txPageSize = ref(10)
const txType = ref<string | undefined>(undefined)
const txRange = ref<[dayjs.Dayjs, dayjs.Dayjs] | null>(null)
const txLoading = ref(false)

const fetchTransactions = async () => {
  txLoading.value = true
  try {
    const body: any = {
      current: txCurrent.value,
      pageSize: txPageSize.value,
    }
    if (txType.value) body.type = txType.value
    if (txRange.value && txRange.value[0] && txRange.value[1]) {
      body.startTime = txRange.value[0].format('YYYY-MM-DD 00:00:00')
      body.endTime = txRange.value[1].format('YYYY-MM-DD 23:59:59')
    }
    const res = await listPointsTransactions(body)
    if (res.data.code === 0 && res.data.data) {
      transactions.value = (res.data.data.records as TransactionRow[]) ?? []
      txTotal.value = res.data.data.total ?? 0
    } else {
      message.error(res.data.message || '获取积分明细失败')
    }
  } catch (e: any) {
    message.error(e?.message || '获取积分明细失败')
  } finally {
    txLoading.value = false
  }
}

const txPagination = computed(() => ({
  current: txCurrent.value,
  pageSize: txPageSize.value,
  total: txTotal.value,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`,
}))

const doTxTableChange = (page: { current: number; pageSize: number }) => {
  txCurrent.value = page.current
  txPageSize.value = page.pageSize
  fetchTransactions()
}

const doTxSearch = () => {
  txCurrent.value = 1
  fetchTransactions()
}

const txColumns = [
  { title: '时间', dataIndex: 'createTime', key: 'createTime', width: 180 },
  { title: '类型', dataIndex: 'type', key: 'type', width: 130 },
  { title: '变动', dataIndex: 'amount', key: 'amount', width: 110 },
  { title: '变动后余额', dataIndex: 'balanceAfter', key: 'balanceAfter', width: 130 },
  { title: '说明', dataIndex: 'description', key: 'description' },
]

// ==================== 用量统计 ====================
const usageStats = ref<UsageStatRow[]>([])
const usageLoading = ref(false)
let pieChart: echarts.ECharts | null = null
let barChart: echarts.ECharts | null = null

const fetchUsageStats = async () => {
  usageLoading.value = true
  try {
    const res = await getPointsUsageStats({})
    if (res.data.code === 0) {
      usageStats.value = (res.data.data as UsageStatRow[]) ?? []
      await nextTick()
      renderCharts()
    } else {
      message.error(res.data.message || '获取用量统计失败')
    }
  } catch (e: any) {
    message.error(e?.message || '获取用量统计失败')
  } finally {
    usageLoading.value = false
  }
}

const renderCharts = () => {
  const stats = usageStats.value
  // 1) 饼图：各模型消耗积分占比
  const pieEl = document.getElementById('points-pie-chart')
  if (pieEl) {
    if (pieChart) pieChart.dispose()
    pieChart = echarts.init(pieEl)
    const pieData = stats
      .filter((s) => s.costPoints > 0)
      .map((s) => ({ name: s.model, value: s.costPoints }))
    pieChart.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c} 积分 ({d}%)' },
      legend: { type: 'scroll', bottom: 0 },
      series: [
        {
          name: '消耗积分',
          type: 'pie',
          radius: ['42%', '68%'],
          center: ['50%', '45%'],
          avoidLabelOverlap: true,
          itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
          label: { show: false },
          emphasis: { label: { show: true, fontWeight: 'bold' } },
          data: pieData.length ? pieData : [{ name: '暂无消耗', value: 1 }],
        },
      ],
    })
  }
  // 2) 柱状图：各模型调用次数
  const barEl = document.getElementById('points-bar-chart')
  if (barEl) {
    if (barChart) barChart.dispose()
    barChart = echarts.init(barEl)
    const names = stats.map((s) => s.model)
    const calls = stats.map((s) => s.callCount)
    barChart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: names,
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
          name: '调用次数',
          type: 'bar',
          data: calls,
          barWidth: '45%',
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
}

const usageColumns = [
  { title: '模型', dataIndex: 'model', key: 'model' },
  { title: '类别', dataIndex: 'category', key: 'category', width: 90 },
  { title: '提供商', dataIndex: 'provider', key: 'provider', width: 110 },
  { title: '调用次数', dataIndex: 'callCount', key: 'callCount', width: 100 },
  { title: '输入 token', dataIndex: 'inputTokens', key: 'inputTokens', width: 120 },
  { title: '输出 token', dataIndex: 'outputTokens', key: 'outputTokens', width: 120 },
  { title: '图片数', dataIndex: 'imageCount', key: 'imageCount', width: 90 },
  { title: '消耗积分', dataIndex: 'costPoints', key: 'costPoints', width: 100 },
]

const txTypeText = (t: string) => {
  const found = TX_TYPE_OPTIONS.find((o) => o.value === t)
  return found ? found.label : t
}
const txTagColor = (t: string) => TX_TAG_COLOR[t] || 'default'
const txAmountText = (amount: number) => (amount > 0 ? `+${amount}` : String(amount))

onMounted(() => {
  fetchBalance()
  fetchTransactions()
  fetchUsageStats()
})

onBeforeUnmount(() => {
  pieChart?.dispose()
  barChart?.dispose()
})
</script>

<template>
  <div id="pointsPage">
    <div class="points-wrap">
      <!-- 余额卡 -->
      <div class="balance-card">
        <div class="balance-left">
          <div class="balance-label">
            <WalletOutlined />
            <span>我的积分</span>
          </div>
          <div class="balance-row">
            <span class="balance-num">{{ balance }}</span>
            <span class="balance-unit">积分</span>
          </div>
          <div class="balance-totals">
            <span>累计获得 {{ totalEarned }}</span>
            <span class="dot">·</span>
            <span>累计消耗 {{ totalConsumed }}</span>
          </div>
        </div>
        <div class="balance-right">
          <a-button
            type="primary"
            size="large"
            class="checkin-btn"
            :loading="checkingIn"
            :disabled="checkedInToday"
            @click="doCheckin"
          >
            <CheckCircleOutlined v-if="checkedInToday" />
            <GiftOutlined v-else />
            {{ checkedInToday ? '今日已签到' : '签到 +100' }}
          </a-button>
          <p class="checkin-tip">每日签到赠送 100 积分，欠费用户签到后即可继续创作</p>
        </div>
      </div>

      <!-- 积分明细 -->
      <div class="panel-card">
        <div class="panel-head">
          <HistoryOutlined />
          <span>积分明细</span>
        </div>
        <div class="filter-bar">
          <a-select
            v-model:value="txType"
            :allowClear="true"
            placeholder="全部类型"
            style="width: 160px"
            @change="doTxSearch"
          >
            <a-select-option v-for="o in TX_TYPE_OPTIONS" :key="o.value" :value="o.value">
              {{ o.label }}
            </a-select-option>
          </a-select>
          <a-range-picker v-model:value="txRange" @change="doTxSearch" />
          <a-button @click="doTxSearch"><ReloadOutlined /> 查询</a-button>
        </div>
        <a-table
          :columns="txColumns"
          :data-source="transactions"
          :pagination="txPagination"
          :loading="txLoading"
          row-key="id"
          size="middle"
          @change="doTxTableChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'type'">
              <a-tag :color="txTagColor(record.type)">{{ txTypeText(record.type) }}</a-tag>
            </template>
            <template v-else-if="column.key === 'amount'">
              <span :class="record.amount >= 0 ? 'amount-plus' : 'amount-minus'">
                {{ txAmountText(record.amount) }}
              </span>
            </template>
          </template>
        </a-table>
      </div>

      <!-- 用量统计 -->
      <div class="panel-card">
        <div class="panel-head">
          <BarChartOutlined />
          <span>模型用量统计</span>
        </div>
        <div class="stats-grid">
          <div class="chart-box" id="points-pie-chart"></div>
          <div class="chart-box" id="points-bar-chart"></div>
        </div>
        <a-table
          :columns="usageColumns"
          :data-source="usageStats"
          :loading="usageLoading"
          :pagination="false"
          row-key="model"
          size="middle"
          class="usage-table"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
#pointsPage {
  min-height: calc(100vh - 64px);
  padding: 32px 16px 48px;
  background: linear-gradient(180deg, rgba(34, 197, 94, 0.05) 0%, transparent 240px);
}

.points-wrap {
  width: 100%;
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 余额卡 */
.balance-card {
  background: #fff;
  border: 1px solid var(--color-border-light, #e5e7eb);
  border-radius: var(--radius-lg, 16px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
  padding: 24px 28px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}
.balance-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-secondary, #475569);
}
.balance-label .anticon {
  color: var(--color-primary, #22c55e);
}
.balance-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-top: 8px;
}
.balance-num {
  font-size: 44px;
  font-weight: 800;
  color: var(--color-primary-dark, #16a34a);
  line-height: 1;
}
.balance-unit {
  font-size: 14px;
  color: var(--color-text-muted, #9ca3af);
}
.balance-totals {
  margin-top: 8px;
  font-size: 13px;
  color: var(--color-text-muted, #6b7280);
  display: flex;
  gap: 8px;
}
.balance-totals .dot {
  color: var(--color-border, #e2e8f0);
}
.balance-right {
  text-align: right;
}
.checkin-btn.ant-btn {
  height: 44px;
  padding: 0 24px;
  font-size: 15px;
  font-weight: 600;
  border-radius: var(--radius-md, 10px);
}
.checkin-tip {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--color-text-muted, #9ca3af);
}

/* 面板卡 */
.panel-card {
  background: #fff;
  border: 1px solid var(--color-border-light, #e5e7eb);
  border-radius: var(--radius-lg, 16px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.05);
  padding: 20px 24px;
}
.panel-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text, #1f2937);
  margin-bottom: 16px;
}
.panel-head .anticon {
  color: var(--color-primary, #22c55e);
}
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.amount-plus {
  color: var(--color-primary-dark, #16a34a);
  font-weight: 600;
}
.amount-minus {
  color: var(--color-error, #ef4444);
  font-weight: 600;
}

/* 图表 */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.chart-box {
  width: 100%;
  height: 300px;
}
.usage-table {
  margin-top: 8px;
}

/* 响应式 */
@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
  .balance-card {
    flex-direction: column;
    align-items: flex-start;
  }
  .balance-right {
    text-align: left;
    width: 100%;
  }
}
</style>