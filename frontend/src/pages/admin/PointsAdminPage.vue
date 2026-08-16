<script setup lang="ts">
/**
 * 管理端积分管理页
 *
 * Tab1 概览：全局积分/用量看板（GET /admin/points/overview）
 * Tab2 用户积分：搜索用户 → 查看流水（Drawer）/ 调整积分（Modal）
 *      （GET /user/list/page、POST /admin/points/transactions、POST /admin/points/adjust）
 * Tab3 用量查询：按用户/模型/类别/时间分页（POST /admin/points/usage）
 */
import { ref, computed, onMounted } from 'vue'
import { message, Modal } from 'ant-design-vue'
import dayjs from 'dayjs'
import {
  WalletOutlined,
  TeamOutlined,
  FireOutlined,
  HistoryOutlined,
  ReloadOutlined,
  SearchOutlined,
  PlusOutlined,
} from '@ant-design/icons-vue'

import {
  getAdminPointsOverview,
  adminAdjustPoints,
  listAdminPointsUsage,
  listAdminPointsTransactions,
} from '@/api/pointsController'
import { listUsersByPage } from '@/api/userController.ts'

// ==================== Tab ====================
const activeTab = ref('overview')

// ==================== 概览 ====================
interface PointsOverview {
  userCount: number
  totalEarned: number
  totalConsumed: number
  totalBalance: number
  usageRecordCount: number
  totalCostPoints: number
  todayCheckinCount: number
  todayCheckinPoints: number
}
const overview = ref<PointsOverview | null>(null)
const overviewLoading = ref(false)

const overviewMetrics = computed(() => [
  { key: 'users', label: '积分账户', value: overview.value?.userCount ?? 0, icon: TeamOutlined },
  { key: 'earned', label: '累计发放积分', value: overview.value?.totalEarned ?? 0, icon: WalletOutlined },
  { key: 'consumed', label: '累计消耗积分', value: overview.value?.totalConsumed ?? 0, icon: FireOutlined },
  { key: 'balance', label: '全体余额合计', value: overview.value?.totalBalance ?? 0, icon: WalletOutlined },
  { key: 'usage', label: '用量记录条数', value: overview.value?.usageRecordCount ?? 0, icon: HistoryOutlined },
  { key: 'cost', label: '用量折算积分', value: overview.value?.totalCostPoints ?? 0, icon: FireOutlined },
  { key: 'checkin', label: '今日签到人数', value: overview.value?.todayCheckinCount ?? 0, icon: PlusOutlined },
  { key: 'checkinPoints', label: '今日签到发放', value: overview.value?.todayCheckinPoints ?? 0, icon: PlusOutlined },
])

const fetchOverview = async () => {
  overviewLoading.value = true
  try {
    const res = await getAdminPointsOverview()
    if (res.data.code === 0 && res.data.data) {
      overview.value = res.data.data as PointsOverview
    } else {
      message.error(res.data.message || '获取看板失败')
    }
  } catch (e: any) {
    message.error(e?.message || '获取看板失败')
  } finally {
    overviewLoading.value = false
  }
}

// ==================== 用户积分 ====================
interface UserRow {
  id: number
  userAccount: string
  userName?: string | null
  userRole: string
  points?: number | null
  quota?: number | null
  createTime: string
}
const users = ref<UserRow[]>([])
const userTotal = ref(0)
const userCurrent = ref(1)
const userPageSize = ref(10)
const userKeyword = ref('')
const userLoading = ref(false)

const fetchUsers = async () => {
  userLoading.value = true
  try {
    const res = await listUsersByPage({
      current: userCurrent.value,
      pageSize: userPageSize.value,
      userAccount: userKeyword.value || undefined,
    } as any)
    if (res.data.code === 0 && res.data.data) {
      users.value = (res.data.data.records as UserRow[]) ?? []
      userTotal.value = res.data.data.total ?? 0
    } else {
      message.error(res.data.message || '获取用户列表失败')
    }
  } catch (e: any) {
    message.error(e?.message || '获取用户列表失败')
  } finally {
    userLoading.value = false
  }
}

const userPagination = computed(() => ({
  current: userCurrent.value,
  pageSize: userPageSize.value,
  total: userTotal.value,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 人`,
}))

const doUserTableChange = (page: { current: number; pageSize: number }) => {
  userCurrent.value = page.current
  userPageSize.value = page.pageSize
  fetchUsers()
}

const doUserSearch = () => {
  userCurrent.value = 1
  fetchUsers()
}

const userColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 90 },
  { title: '账号', dataIndex: 'userAccount', key: 'userAccount' },
  { title: '用户名', dataIndex: 'userName', key: 'userName' },
  { title: '角色', dataIndex: 'userRole', key: 'userRole', width: 100 },
  { title: '积分', dataIndex: 'points', key: 'points', width: 100 },
  { title: '配额', dataIndex: 'quota', key: 'quota', width: 90 },
  { title: '操作', key: 'action', width: 180 },
]

// 查看流水
interface TxRow {
  id: number
  type: string
  amount: number
  balanceAfter: number
  description?: string | null
  createTime: string
}
const txDrawerOpen = ref(false)
const txUser = ref<UserRow | null>(null)
const txList = ref<TxRow[]>([])
const txTotal = ref(0)
const txCurrent = ref(1)
const txPageSize = ref(10)
const txLoading = ref(false)

const TX_TAG_COLOR: Record<string, string> = {
  REGISTER: 'green',
  SIGN_IN: 'cyan',
  USAGE_SETTLE: 'orange',
  ADMIN_ADJUST: 'purple',
}
const TX_TYPE_TEXT: Record<string, string> = {
  REGISTER: '注册赠送',
  SIGN_IN: '每日签到',
  USAGE_SETTLE: '创作消耗',
  ADMIN_ADJUST: '管理员调整',
}

const openTxDrawer = (record: UserRow) => {
  txUser.value = record
  txList.value = []
  txTotal.value = 0
  txCurrent.value = 1
  txDrawerOpen.value = true
  fetchUserTx()
}

const fetchUserTx = async () => {
  if (!txUser.value) return
  txLoading.value = true
  try {
    const res = await listAdminPointsTransactions({
      userId: txUser.value.id,
      current: txCurrent.value,
      pageSize: txPageSize.value,
    } as any)
    if (res.data.code === 0 && res.data.data) {
      txList.value = (res.data.data.records as TxRow[]) ?? []
      txTotal.value = res.data.data.total ?? 0
    } else {
      message.error(res.data.message || '获取流水失败')
    }
  } catch (e: any) {
    message.error(e?.message || '获取流水失败')
  } finally {
    txLoading.value = false
  }
}

const txPagination = computed(() => ({
  current: txCurrent.value,
  pageSize: txPageSize.value,
  total: txTotal.value,
  showTotal: (total: number) => `共 ${total} 条`,
}))

const doTxTableChange = (page: { current: number; pageSize: number }) => {
  txCurrent.value = page.current
  txPageSize.value = page.pageSize
  fetchUserTx()
}

// 调整积分
const adjustModalOpen = ref(false)
const adjustUser = ref<UserRow | null>(null)
const adjustAmount = ref<number>(0)
const adjustDesc = ref('')
const adjusting = ref(false)

const openAdjust = (record: UserRow) => {
  adjustUser.value = record
  adjustAmount.value = 0
  adjustDesc.value = ''
  adjustModalOpen.value = true
}

const doAdjust = async () => {
  if (!adjustUser.value) return
  if (!adjustAmount.value || adjustAmount.value === 0) {
    message.warning('调整积分不能为 0')
    return
  }
  if (!adjustDesc.value.trim()) {
    message.warning('请填写调整说明')
    return
  }
  adjusting.value = true
  try {
    const res = await adminAdjustPoints({
      userId: adjustUser.value.id,
      amount: adjustAmount.value,
      description: adjustDesc.value.trim(),
    } as any)
    if (res.data.code === 0) {
      message.success(`调整成功，该用户当前余额 ${res.data.data} 积分`)
      adjustModalOpen.value = false
      fetchUsers()
      if (activeTab.value === 'overview') fetchOverview()
    } else {
      message.error(res.data.message || '调整失败')
    }
  } catch (e: any) {
    message.error(e?.message || '调整失败')
  } finally {
    adjusting.value = false
  }
}

// ==================== 用量查询 ====================
interface UsageRow {
  id: number
  userId: number
  taskId?: string | null
  category: string
  provider: string
  model: string
  agentName?: string | null
  callCount: number
  inputTokens?: number | null
  outputTokens?: number | null
  imageCount?: number | null
  costPoints: number
  status: string
  createTime: string
}
const usageRows = ref<UsageRow[]>([])
const usageTotal = ref(0)
const usageCurrent = ref(1)
const usagePageSize = ref(10)
const usageUserId = ref<string | undefined>(undefined)
const usageModel = ref<string | undefined>(undefined)
const usageCategory = ref<string | undefined>(undefined)
const usageRange = ref<[dayjs.Dayjs, dayjs.Dayjs] | null>(null)
const usageLoading = ref(false)

const fetchUsage = async () => {
  usageLoading.value = true
  try {
    const body: any = {
      current: usageCurrent.value,
      pageSize: usagePageSize.value,
    }
    if (usageUserId.value) body.userId = Number(usageUserId.value)
    if (usageModel.value) body.model = usageModel.value
    if (usageCategory.value) body.category = usageCategory.value
    if (usageRange.value && usageRange.value[0] && usageRange.value[1]) {
      body.startTime = usageRange.value[0].format('YYYY-MM-DD 00:00:00')
      body.endTime = usageRange.value[1].format('YYYY-MM-DD 23:59:59')
    }
    const res = await listAdminPointsUsage(body)
    if (res.data.code === 0 && res.data.data) {
      usageRows.value = (res.data.data.records as UsageRow[]) ?? []
      usageTotal.value = res.data.data.total ?? 0
    } else {
      message.error(res.data.message || '获取用量失败')
    }
  } catch (e: any) {
    message.error(e?.message || '获取用量失败')
  } finally {
    usageLoading.value = false
  }
}

const usagePagination = computed(() => ({
  current: usageCurrent.value,
  pageSize: usagePageSize.value,
  total: usageTotal.value,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`,
}))

const doUsageTableChange = (page: { current: number; pageSize: number }) => {
  usageCurrent.value = page.current
  usagePageSize.value = page.pageSize
  fetchUsage()
}

const doUsageSearch = () => {
  usageCurrent.value = 1
  fetchUsage()
}

const usageColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: '用户ID', dataIndex: 'userId', key: 'userId', width: 90 },
  { title: '类别', dataIndex: 'category', key: 'category', width: 90 },
  { title: '提供商', dataIndex: 'provider', key: 'provider', width: 110 },
  { title: '模型', dataIndex: 'model', key: 'model' },
  { title: 'Agent', dataIndex: 'agentName', key: 'agentName', width: 140 },
  { title: '次数', dataIndex: 'callCount', key: 'callCount', width: 80 },
  { title: '输入token', dataIndex: 'inputTokens', key: 'inputTokens', width: 110 },
  { title: '输出token', dataIndex: 'outputTokens', key: 'outputTokens', width: 110 },
  { title: '图片', dataIndex: 'imageCount', key: 'imageCount', width: 70 },
  { title: '积分', dataIndex: 'costPoints', key: 'costPoints', width: 90 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '时间', dataIndex: 'createTime', key: 'createTime', width: 170 },
]

const formatTime = (v?: string | null) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '—')

onMounted(() => {
  fetchOverview()
  fetchUsers()
  fetchUsage()
})
</script>

<template>
  <div id="pointsAdminPage">
    <div class="page-head">
      <div class="page-head-inner">
        <h1 class="page-title">积分管理</h1>
        <p class="page-subtitle">全局积分看板、用户积分调整与模型用量查询</p>
        <a-button class="refresh-btn" @click="[fetchOverview(), fetchUsers(), fetchUsage()]">
          <ReloadOutlined /> 刷新
        </a-button>
      </div>
    </div>

    <div class="page-body">
      <a-tabs v-model:activeKey="activeTab">
        <!-- 概览 -->
        <a-tab-pane key="overview" tab="概览">
          <a-spin :spinning="overviewLoading">
            <div class="metrics-grid">
              <div v-for="m in overviewMetrics" :key="m.key" class="metric-card">
                <div class="metric-icon"><component :is="m.icon" /></div>
                <div class="metric-body">
                  <div class="metric-value">{{ m.value }}</div>
                  <div class="metric-label">{{ m.label }}</div>
                </div>
              </div>
            </div>
          </a-spin>
        </a-tab-pane>

        <!-- 用户积分 -->
        <a-tab-pane key="users" tab="用户积分">
          <div class="filter-bar">
            <a-input
              v-model:value="userKeyword"
              placeholder="按账号搜索"
              style="width: 220px"
              allow-clear
              @pressEnter="doUserSearch"
            />
            <a-button type="primary" @click="doUserSearch"><SearchOutlined /> 搜索</a-button>
          </div>
          <a-table
            :columns="userColumns"
            :data-source="users"
            :pagination="userPagination"
            :loading="userLoading"
            row-key="id"
            size="middle"
            @change="doUserTableChange"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'userRole'">
                <a-tag :color="record.userRole === 'admin' ? 'purple' : record.userRole === 'vip' ? 'gold' : 'green'">
                  {{ record.userRole === 'admin' ? '管理员' : record.userRole === 'vip' ? '会员' : '普通' }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'points'">
                <span :class="(record.points ?? 0) < 0 ? 'debt-text' : ''">{{ record.points ?? 0 }}</span>
              </template>
              <template v-else-if="column.key === 'action'">
                <a-space>
                  <a-button type="link" size="small" @click="openTxDrawer(record)">查看流水</a-button>
                  <a-button type="link" size="small" @click="openAdjust(record)">调整积分</a-button>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-tab-pane>

        <!-- 用量查询 -->
        <a-tab-pane key="usage" tab="用量查询">
          <div class="filter-bar">
            <a-input
              v-model:value="usageUserId"
              placeholder="用户ID"
              style="width: 120px"
              allow-clear
              @pressEnter="doUsageSearch"
            />
            <a-input
              v-model:value="usageModel"
              placeholder="模型名"
              style="width: 180px"
              allow-clear
              @pressEnter="doUsageSearch"
            />
            <a-select
              v-model:value="usageCategory"
              placeholder="类别"
              style="width: 120px"
              :allowClear="true"
            >
              <a-select-option value="LLM">LLM</a-select-option>
              <a-select-option value="IMAGE">IMAGE</a-select-option>
            </a-select>
            <a-range-picker v-model:value="usageRange" @change="doUsageSearch" />
            <a-button type="primary" @click="doUsageSearch"><SearchOutlined /> 查询</a-button>
          </div>
          <a-table
            :columns="usageColumns"
            :data-source="usageRows"
            :pagination="usagePagination"
            :loading="usageLoading"
            row-key="id"
            size="small"
            :scroll="{ x: 1200 }"
            @change="doUsageTableChange"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'createTime'">
                {{ formatTime(record.createTime) }}
              </template>
              <template v-else-if="column.key === 'status'">
                <a-tag :color="record.status === 'SUCCESS' ? 'green' : 'red'">{{ record.status }}</a-tag>
              </template>
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </div>

    <!-- 流水抽屉 -->
    <a-drawer
      :open="txDrawerOpen"
      :title="`${txUser?.userName || txUser?.userAccount || ''} 的积分流水`"
      width="720"
      @close="txDrawerOpen = false"
    >
      <a-table
        :columns="[
          { title: '时间', dataIndex: 'createTime', key: 'createTime', width: 180 },
          { title: '类型', dataIndex: 'type', key: 'type', width: 120 },
          { title: '变动', dataIndex: 'amount', key: 'amount', width: 100 },
          { title: '变动后余额', dataIndex: 'balanceAfter', key: 'balanceAfter', width: 120 },
          { title: '说明', dataIndex: 'description', key: 'description' },
        ]"
        :data-source="txList"
        :pagination="txPagination"
        :loading="txLoading"
        row-key="id"
        size="small"
        @change="doTxTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'type'">
            <a-tag :color="TX_TAG_COLOR[record.type] || 'default'">{{ TX_TYPE_TEXT[record.type] || record.type }}</a-tag>
          </template>
          <template v-else-if="column.key === 'amount'">
            <span :class="record.amount >= 0 ? 'amount-plus' : 'amount-minus'">
              {{ record.amount > 0 ? `+${record.amount}` : record.amount }}
            </span>
          </template>
          <template v-else-if="column.key === 'createTime'">
            {{ formatTime(record.createTime) }}
          </template>
        </template>
      </a-table>
    </a-drawer>

    <!-- 调整积分弹窗 -->
    <a-modal
      v-model:open="adjustModalOpen"
      title="调整用户积分"
      :confirm-loading="adjusting"
      @ok="doAdjust"
    >
      <p class="adjust-tip">
        目标用户：{{ adjustUser?.userName || adjustUser?.userAccount }}（当前 {{ adjustUser?.points ?? 0 }} 积分）
      </p>
      <a-form layout="vertical">
        <a-form-item label="调整积分（正=赠送，负=扣减）" required>
          <a-input-number v-model:value="adjustAmount" style="width: 100%" :precision="0" />
        </a-form-item>
        <a-form-item label="调整说明" required>
          <a-input v-model:value="adjustDesc" placeholder="如：活动赠送 / 违规扣减" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<style scoped>
#pointsAdminPage {
  min-height: 100vh;
  background: var(--color-background-secondary, #f8fafc);
  padding-bottom: 48px;
}

.page-head {
  background: #fff;
  border-bottom: 1px solid var(--color-border, #e2e8f0);
  padding: 28px 0;
}
.page-head-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}
.page-title {
  font-size: 26px;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--color-text, #1f2937);
  flex-basis: 100%;
}
.page-subtitle {
  font-size: 14px;
  color: var(--color-text-secondary, #475569);
  margin: 0;
  flex: 1;
}
.refresh-btn {
  margin-left: auto;
}

.page-body {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.metric-card {
  background: #fff;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: var(--radius-lg, 12px);
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 14px;
}
.metric-icon {
  width: 46px;
  height: 46px;
  border-radius: var(--radius-md, 10px);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: var(--color-primary-dark, #16a34a);
  background: rgba(34, 197, 94, 0.1);
  flex-shrink: 0;
}
.metric-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text, #1f2937);
  line-height: 1.1;
}
.metric-label {
  font-size: 12px;
  color: var(--color-text-muted, #6b7280);
  margin-top: 4px;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.debt-text {
  color: var(--color-error, #ef4444);
  font-weight: 600;
}
.amount-plus {
  color: var(--color-primary-dark, #16a34a);
  font-weight: 600;
}
.amount-minus {
  color: var(--color-error, #ef4444);
  font-weight: 600;
}
.adjust-tip {
  font-size: 14px;
  color: var(--color-text-secondary, #475569);
  background: var(--color-background-secondary, #f8fafc);
  border-radius: var(--radius-md, 8px);
  padding: 10px 12px;
}

@media (max-width: 992px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 576px) {
  .metrics-grid {
    grid-template-columns: 1fr;
  }
}
</style>