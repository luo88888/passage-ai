<script setup lang="ts">
/**
 * 用户主页（个人详情页）
 *
 * 点击顶部头像进入，展示当前登录用户的基本信息与数据统计：
 * 头像/昵称/账号/简介/角色/VIP 状态/注册时间 + 积分/配额/创作数量/进行中任务。
 * 数据来源：GET /user/profile（后端聚合 user + user_points + article 统计）。
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  UserOutlined,
  CrownOutlined,
  ThunderboltOutlined,
  EditOutlined,
  UnorderedListOutlined,
  ClockCircleOutlined,
  SafetyCertificateOutlined,
  FireOutlined,
  FileTextOutlined,
  LoadingOutlined,
  WalletOutlined,
} from '@ant-design/icons-vue'

import { useLoginUserStore } from '@/stores/loginUser'
import { isVip as checkIsVip } from '@/utils/permission'
import { getUserProfile } from '@/api/userController'

const router = useRouter()
const loginUserStore = useLoginUserStore()

const loading = ref(true)
const profile = ref<API.UserProfileVO | null>(null)

const isVipUser = computed(() => checkIsVip(loginUserStore.loginUser))

onMounted(async () => {
  await Promise.all([fetchProfile(), loginUserStore.fetchLoginUser()])
})

const fetchProfile = async () => {
  loading.value = true
  try {
    const res = await getUserProfile()
    if (res.data.code === 0 && res.data.data) {
      profile.value = res.data.data
    } else {
      message.error(res.data.message || '获取用户信息失败')
    }
  } catch (e: any) {
    message.error(e?.message || '获取用户信息失败')
  } finally {
    loading.value = false
  }
}

// 角色徽章文案
const roleText = computed(() => {
  const role = profile.value?.userRole
  if (role === 'admin') return '管理员'
  if (role === 'vip') return '永久会员'
  return '普通用户'
})

const roleClass = computed(() => {
  const role = profile.value?.userRole
  if (role === 'admin') return 'role-admin'
  if (role === 'vip') return 'role-vip'
  return 'role-user'
})

// 昵称兜底
const displayName = computed(() => profile.value?.userName || '无名')

// 账号
const displayAccount = computed(() => {
  const acc = profile.value?.userAccount || ''
  return acc ? `@${acc}` : ''
})

// 时间格式化：YYYY-MM-DD
const formatDate = (value?: string | null) => {
  if (!value) return '—'
  try {
    const d = new Date(value)
    if (Number.isNaN(d.getTime())) return String(value)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  } catch {
    return String(value)
  }
}

const registerTime = computed(() => formatDate(profile.value?.createTime))
const vipTimeText = computed(() => formatDate(profile.value?.vipTime))

// 统计卡片
const statItems = computed(() => [
  // to：点击卡片跳转目标（points→积分中心；article/active→历史记录，active 带筛选参数自动设置“进行中”）
  { key: 'points', label: '积分余额', value: profile.value?.points ?? 0, icon: FireOutlined, unit: '积分', to: '/points' },
  { key: 'quota', label: '剩余配额', value: profile.value?.quota ?? 0, icon: SafetyCertificateOutlined, unit: '次' },
  { key: 'article', label: '创作文章', value: profile.value?.articleCount ?? 0, icon: FileTextOutlined, unit: '篇', to: '/article/list' },
  { key: 'active', label: '进行中任务', value: profile.value?.activeTaskCount ?? 0, icon: LoadingOutlined, unit: '个', to: '/article/list?status=ACTIVE' },
])

// 快捷入口
const quickActions = [
  { key: 'create', label: '去创作', icon: EditOutlined, to: '/create' },
  { key: 'list', label: '我的文章', icon: UnorderedListOutlined, to: '/article/list' },
  { key: 'points', label: '积分中心', icon: WalletOutlined, to: '/points' },
  { key: 'vip', label: '开通会员', icon: CrownOutlined, to: '/vip' },
]
</script>

<template>
  <div id="userProfilePage">
    <div class="profile-wrap">
      <a-spin :spinning="loading" size="large">
        <div v-if="profile" class="profile-body">
          <!-- 用户信息卡 -->
          <div class="profile-card user-card">
            <div class="user-main">
              <a-avatar :size="84" :src="profile.userAvatar" class="profile-avatar">
                <template #icon><UserOutlined /></template>
              </a-avatar>
              <div class="user-meta">
                <div class="name-row">
                  <span class="user-name">{{ displayName }}</span>
                  <span :class="['role-badge', roleClass]">{{ roleText }}</span>
                  <span v-if="isVipUser" class="vip-crown"><CrownOutlined /></span>
                </div>
                <div class="user-account">{{ displayAccount }}</div>
                <div v-if="profile.userProfile" class="user-profile">{{ profile.userProfile }}</div>
              </div>
            </div>
            <div class="user-foot">
              <div class="foot-item">
                <ClockCircleOutlined class="foot-icon" />
                <span>注册于 {{ registerTime }}</span>
              </div>
            </div>
          </div>

          <!-- 数据统计卡 -->
          <div class="stats-grid">
            <div
              v-for="item in statItems"
              :key="item.key"
              class="stat-card"
              :class="{ 'stat-card-link': !!item.to }"
              @click="item.to && router.push(item.to)"
            >
              <div class="stat-icon" :class="`stat-icon-${item.key}`">
                <component :is="item.icon" />
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ item.value }}<span class="stat-unit">{{ item.unit }}</span></div>
                <div class="stat-label">{{ item.label }}</div>
              </div>
            </div>
          </div>

          <!-- VIP 状态卡 -->
          <div v-if="isVipUser" class="profile-card vip-status-card">
            <div class="vip-status-head">
              <CrownOutlined class="crown" />
              <span>会员状态</span>
            </div>
            <div class="vip-status-body">
              <div class="vip-status-item">
                <span class="vip-status-label">会员身份</span>
                <span class="vip-status-value">{{ profile.userRole === 'admin' ? '管理员（享会员权益）' : '永久会员' }}</span>
              </div>
              <div v-if="vipTimeText && profile.userRole === 'vip'" class="vip-status-item">
                <span class="vip-status-label">开通时间</span>
                <span class="vip-status-value">{{ vipTimeText }}</span>
              </div>
            </div>
          </div>

          <!-- 快捷入口 -->
          <div class="quick-actions">
            <div
              v-for="action in quickActions"
              :key="action.key"
              class="quick-action"
              @click="router.push(action.to)"
            >
              <component :is="action.icon" class="quick-icon" />
              <span>{{ action.label }}</span>
            </div>
          </div>
        </div>
      </a-spin>
    </div>
  </div>
</template>

<style scoped>
#userProfilePage {
  min-height: calc(100vh - 64px);
  padding: 32px 16px 48px;
  background: linear-gradient(180deg, rgba(34, 197, 94, 0.05) 0%, transparent 240px);
}

.profile-wrap {
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.profile-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 卡片基础 */
.profile-card {
  background: #fff;
  border: 1px solid var(--color-border-light, #e5e7eb);
  border-radius: var(--radius-lg, 16px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
}

/* 用户信息卡 */
.user-card {
  padding: 28px 28px 20px;
}

.user-main {
  display: flex;
  align-items: center;
  gap: 20px;
}

.profile-avatar {
  flex-shrink: 0;
  border: 3px solid rgba(34, 197, 94, 0.25);
  box-shadow: var(--shadow-green, 0 4px 14px rgba(34, 197, 94, 0.25));
  background: var(--color-background-secondary, #f8fafc);
}

.user-meta {
  min-width: 0;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.user-name {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text, #1f2937);
}

.role-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: var(--radius-full, 9999px);
  font-size: 12px;
  font-weight: 600;
}

.role-admin {
  color: #7c3aed;
  background: rgba(124, 58, 237, 0.1);
}

.role-vip {
  color: #b45309;
  background: rgba(250, 204, 21, 0.18);
}

.role-user {
  color: var(--color-primary-dark, #16a34a);
  background: rgba(34, 197, 94, 0.1);
}

.vip-crown {
  color: #facc15;
  font-size: 16px;
}

.user-account {
  margin-top: 4px;
  font-size: 14px;
  color: var(--color-text-muted, #9ca3af);
}

.user-profile {
  margin-top: 10px;
  font-size: 14px;
  color: var(--color-text-secondary, #475569);
  line-height: 1.7;
  white-space: pre-wrap;
}

.user-foot {
  margin-top: 20px;
  padding-top: 14px;
  border-top: 1px dashed var(--color-border-light, #e5e7eb);
  display: flex;
  align-items: center;
}

.foot-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--color-text-muted, #6b7280);
}

.foot-icon {
  color: var(--color-primary, #22c55e);
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.stat-card {
  background: #fff;
  border: 1px solid var(--color-border-light, #e5e7eb);
  border-radius: var(--radius-lg, 14px);
  padding: 18px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.05);
  transition: transform var(--transition-fast, 150ms ease-out), box-shadow var(--transition-fast, 150ms ease-out);
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(34, 197, 94, 0.12);
}

/* 可点击卡片 */
.stat-card-link {
  cursor: pointer;
}
.stat-card-link:hover .stat-label {
  color: var(--color-primary-dark, #16a34a);
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md, 12px);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.stat-icon-points { color: #ea580c; background: rgba(234, 88, 12, 0.1); }
.stat-icon-quota { color: #2563eb; background: rgba(37, 99, 235, 0.1); }
.stat-icon-article { color: #16a34a; background: rgba(34, 197, 94, 0.1); }
.stat-icon-active { color: #7c3aed; background: rgba(124, 58, 237, 0.1); }

.stat-info {
  min-width: 0;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text, #1f2937);
  line-height: 1.2;
}

.stat-unit {
  margin-left: 3px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-muted, #9ca3af);
}

.stat-label {
  margin-top: 2px;
  font-size: 12px;
  color: var(--color-text-muted, #6b7280);
}

/* VIP 状态卡 */
.vip-status-card {
  padding: 16px 20px;
  background: rgba(34, 197, 94, 0.06);
  border-color: rgba(34, 197, 94, 0.2);
}

.vip-status-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-primary-dark, #16a34a);
  margin-bottom: 8px;
}

.vip-status-head .crown {
  color: #facc15;
}

.vip-status-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.vip-status-item {
  display: flex;
  gap: 12px;
  font-size: 14px;
}

.vip-status-label {
  color: var(--color-text-muted, #6b7280);
  flex-shrink: 0;
}

.vip-status-value {
  color: var(--color-text, #1f2937);
}

/* 快捷入口 */
.quick-actions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.quick-action {
  background: #fff;
  border: 1px solid var(--color-border-light, #e5e7eb);
  border-radius: var(--radius-lg, 14px);
  padding: 18px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text, #1f2937);
  cursor: pointer;
  transition: all var(--transition-fast, 150ms ease-out);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.05);
}

.quick-action:hover {
  transform: translateY(-2px);
  color: var(--color-primary-dark, #16a34a);
  border-color: rgba(34, 197, 94, 0.4);
  box-shadow: 0 8px 24px rgba(34, 197, 94, 0.12);
}

.quick-icon {
  font-size: 22px;
  color: var(--color-primary, #22c55e);
}

/* 响应式 */
@media (max-width: 640px) {
  .stats-grid,
  .quick-actions {
    grid-template-columns: repeat(2, 1fr);
  }

  .user-main {
    flex-direction: column;
    text-align: center;
  }

  .name-row {
    justify-content: center;
  }
}
</style>