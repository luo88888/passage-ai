<template>
  <a-layout-header class="header">
    <div class="header-container">
      <div class="header-left">
        <RouterLink to="/" class="logo-link">
          <div class="logo-wrapper">
            <img src="@/assets/logo.png" alt="Logo" class="logo-img" />
            <h1 class="site-title">AI文章创作平台</h1>
          </div>
        </RouterLink>
      </div>

      <!-- 中间：导航菜单 -->
      <nav class="nav-center">
        <RouterLink
          v-for="item in menuItems"
          :key="item.key"
          :to="item.key"
          :class="['nav-item', { active: selectedKeys.includes(item.key) }]"
        >
          <component :is="item.icon" class="nav-icon" />
          <span>{{ item.label }}</span>
        </RouterLink>

        <!-- 管理员菜单（合并为一个下拉，避免导航按钮过多） -->
        <a-dropdown v-if="isAdminUser" trigger="click" placement="bottom">
          <div class="nav-item admin-nav-trigger" :class="{ active: isAdminRoute }">
            <SettingOutlined class="nav-icon" />
            <span>管理</span>
            <DownOutlined class="admin-nav-arrow" />
          </div>
          <template #overlay>
            <a-menu class="admin-nav-menu" :selected-keys="adminSelectedKeys" @click="onAdminMenuClick">
              <a-menu-item v-for="item in adminMenuItems" :key="item.key">
                <component :is="item.icon" />
                <span>{{ item.label }}</span>
              </a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
      </nav>

      <!-- 右侧：用户操作区域 -->
      <div class="header-right">
        <div v-if="loginUserStore.loginUser.id" class="user-dropdown">
          <!-- 每日签到 -->
          <a-button
            class="checkin-btn"
            :loading="checkingIn"
            :disabled="checkedInToday"
            @click="doCheckin"
          >
            <CheckCircleOutlined v-if="checkedInToday" />
            <GiftOutlined v-else />
            <span>{{ checkedInToday ? '今日已签到' : '签到 +10' }}</span>
          </a-button>
          <!-- VIP 标识 -->
          <RouterLink v-if="!isVip" to="/vip" class="upgrade-vip-btn">
            <CrownOutlined />
            <span>升级 VIP</span>
          </RouterLink>
          <RouterLink v-else to="/vip" class="vip-badge">
            <CrownOutlined />
            <span>VIP</span>
          </RouterLink>

          <!-- 站内信铃铛 -->
          <a-dropdown trigger="click" placement="bottomRight" @visibleChange="onBellVisibleChange">
            <a-badge :count="unreadCount" :overflow-count="99" :offset="[2, 2]">
              <a-button class="bell-btn" type="text" aria-label="站内信">
                <BellOutlined class="bell-icon" />
              </a-button>
            </a-badge>
            <template #overlay>
              <div class="message-popover">
                <div class="message-popover-head">
                  <span>站内信</span>
                  <a class="message-popover-link" @click="goMessagePage">查看全部</a>
                </div>
                <a-spin :spinning="messagesLoading">
                  <div v-if="recentMessages.length" class="message-popover-list">
                    <div
                      v-for="msg in recentMessages"
                      :key="msg.id"
                      class="message-popover-item"
                      :class="{ unread: !msg.isRead }"
                      @click="openMessageFromHeader(msg)"
                    >
                      <div class="message-popover-title">
                        <span v-if="!msg.isRead" class="unread-dot"></span>
                        {{ msg.title }}
                      </div>
                      <div class="message-popover-desc">{{ msg.content || '' }}</div>
                      <div class="message-popover-time">{{ formatMessageTime(msg.createTime) }}</div>
                    </div>
                  </div>
                  <a-empty v-else-if="!messagesLoading" description="暂无消息" :image="simpleEmptyImage" />
                </a-spin>
                <div class="message-popover-foot">
                  <a-button type="link" size="small" :disabled="unreadCount === 0" @click="markAllReadFromHeader">
                    <CheckOutlined /> 全部已读
                  </a-button>
                </div>
              </div>
            </template>
          </a-dropdown>
          <a-dropdown>
            <a-space class="user-info">
              <a-avatar
                :src="loginUserStore.loginUser.userAvatar"
                :size="36"
                class="user-avatar"
                title="个人主页"
                @click.stop="router.push('/user/profile')"
              />
              <span class="user-name">
                {{ loginUserStore.loginUser.userName ?? '无名' }}
              </span>
            </a-space>
            <template #overlay>
              <a-menu class="dropdown-menu">
                <a-menu-item key="profile" class="dropdown-item" @click="router.push('/user/profile')">
                  <UserOutlined />
                  <span>个人主页</span>
                </a-menu-item>
                <a-menu-item key="points" class="dropdown-item" @click="router.push('/points')">
                  <WalletOutlined />
                  <span>积分中心</span>
                </a-menu-item>
                <a-menu-item key="feedback" class="dropdown-item" @click="router.push('/feedback')">
                  <MessageOutlined />
                  <span>意见反馈</span>
                </a-menu-item>
                <a-menu-item key="settings" class="dropdown-item" @click="router.push('/user/settings')">
                  <SettingOutlined />
                  <span>账号设置</span>
                </a-menu-item>
                <a-menu-divider />
                <a-menu-item v-if="isVip" key="vip-info" class="vip-info-item" @click="router.push('/vip')">
                  <CrownOutlined />
                  <span>永久会员权益</span>
                </a-menu-item>
                <a-menu-divider v-if="isVip" />
                <a-menu-item @click="doLogout" class="dropdown-item">
                  <LogoutOutlined />
                  <span>退出登录</span>
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
        <div v-else>
          <RouterLink to="/user/login" class="login-btn">登录</RouterLink>
        </div>
      </div>
    </div>
  </a-layout-header>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { message, Empty as AntEmpty } from 'ant-design-vue'
import { useLoginUserStore } from '@/stores/loginUser.ts'
import { userLogout } from '@/api/userController.ts'
import { getPointsBalance, checkin as pointsCheckin } from '@/api/pointsController.ts'
import { getMessageUnreadCount, pageMessage, readMessage } from '@/api/messageController.ts'
import {
  LogoutOutlined,
  UserOutlined,
  HomeOutlined,
  EditOutlined,
  UnorderedListOutlined,
  SettingOutlined,
  CrownOutlined,
  BarChartOutlined,
  GiftOutlined,
  CheckCircleOutlined,
  WalletOutlined,
  BellOutlined,
  MessageOutlined,
  CheckOutlined,
  DownOutlined
} from '@ant-design/icons-vue'
import { isVip as checkIsVip, isAdmin as checkIsAdmin } from '@/utils/permission'

const loginUserStore = useLoginUserStore()
const router = useRouter()
// 当前选中菜单
const selectedKeys = ref<string[]>(['/'])
// 监听路由变化：更新当前选中菜单，并刷新站内信未读角标
// （在消息详情页标记已读后返回列表，角标即时更新）
router.afterEach((to) => {
  selectedKeys.value = [to.path]
  refreshUnread()
})

// 判断是否为 VIP（管理员也视为 VIP）
const isVip = computed(() => checkIsVip(loginUserStore.loginUser))

// 签到状态
const checkedInToday = ref(false)
const checkingIn = ref(false)

// 刷新今日签到状态
const refreshCheckinStatus = async () => {
  try {
    const res = await getPointsBalance()
    if (res.data.code === 0 && res.data.data) {
      checkedInToday.value = !!res.data.data.checkedInToday
    }
  } catch (e) {
    // 未登录等场景静默处理
  }
}

// 每日签到：+10 积分，成功后刷新余额
const doCheckin = async () => {
  if (checkedInToday.value) return
  checkingIn.value = true
  try {
    const res = await pointsCheckin()
    if (res.data.code === 0 && res.data.data) {
      checkedInToday.value = true
      message.success(`签到成功，+${res.data.data.gained} 积分`)
      await loginUserStore.fetchLoginUser()
    } else {
      message.error(res.data.message || '签到失败')
      await refreshCheckinStatus()
    }
  } catch (e: any) {
    message.error(e?.message || '签到失败，请稍后再试')
  } finally {
    checkingIn.value = false
  }
}

// 登录用户就绪后刷新今日签到状态：页面刷新时 onMounted 早于路由守卫的
// fetchLoginUser 完成，此时 loginUser.id 尚为空会漏刷，导致刷新后签到按钮
// 误显示为可签到；改用 watch 等登录态就绪后再拉取。
watch(
  () => loginUserStore.loginUser.id,
  (id) => {
    if (id) {
      refreshCheckinStatus()
    }
  },
  { immediate: true },
)

// ==================== 站内信（铃铛角标 + 最近消息） ====================
const unreadCount = ref(0)
const recentMessages = ref<any[]>([])
const messagesLoading = ref(false)
const simpleEmptyImage = AntEmpty.PRESENTED_IMAGE_SIMPLE

const formatMessageTime = (v?: string | null) => {
  if (!v) return ''
  return v.replace('T', ' ').slice(0, 16)
}

// 刷新未读数（登录后 / 轮询 / 操作后调用）
const refreshUnread = async () => {
  if (!loginUserStore.loginUser.id) return
  try {
    const res = await getMessageUnreadCount()
    if (res.data.code === 0 && res.data.data) {
      unreadCount.value = res.data.data.count ?? 0
    }
  } catch (e) {
    // 未登录等场景静默处理
  }
}

// 拉取最近 5 条（铃铛下拉）
const loadRecentMessages = async () => {
  if (!loginUserStore.loginUser.id) return
  messagesLoading.value = true
  try {
    const res = await pageMessage({ current: 1, pageSize: 5 })
    if (res.data.code === 0 && res.data.data) {
      recentMessages.value = (res.data.data.records as any[]) ?? []
    }
  } catch (e) {
    // 静默处理
  } finally {
    messagesLoading.value = false
  }
}

// 铃铛展开时刷新
const onBellVisibleChange = (visible: boolean) => {
  if (visible) {
    refreshUnread()
    loadRecentMessages()
  }
}

// 点击单条：未读先标记已读；有 link 跳转，否则进消息中心
// 点击单条：直接进入通知详情页查看内容（不再按 link 跳转，避免看不到通知详情；详情页会自动标记已读）
const openMessageFromHeader = (msg: any) => {
  router.push(`/message/${msg.id}`)
}

// 全部已读
const markAllReadFromHeader = async () => {
  try {
    const res = await readMessage({ all: true } as any)
    if (res.data.code === 0) {
      unreadCount.value = 0
      recentMessages.value.forEach((m) => (m.isRead = true))
      message.success('已全部标记为已读')
    } else {
      message.error(res.data.message || '操作失败')
    }
  } catch (e: any) {
    message.error(e?.message || '操作失败')
  }
}

const goMessagePage = () => {
  router.push('/message')
}

// 登录就绪后拉取未读数；登出后清零
watch(
  () => loginUserStore.loginUser.id,
  (id) => {
    if (id) {
      refreshUnread()
    } else {
      unreadCount.value = 0
      recentMessages.value = []
    }
  },
  { immediate: true },
)

// 轮询刷新未读数（60s）
let unreadTimer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  unreadTimer = setInterval(() => {
    refreshUnread()
  }, 60000)
})
onUnmounted(() => {
  if (unreadTimer) clearInterval(unreadTimer)
})
// 菜单配置项
const originItems = [
  {
    key: '/',
    icon: HomeOutlined,
    label: '首页',
  },
  {
    key: '/create',
    icon: EditOutlined,
    label: '创作',
  },
  {
    key: '/article/list',
    icon: UnorderedListOutlined,
    label: '历史',
  },
  {
    key: '/admin/userManage',
    icon: SettingOutlined,
    label: '管理',
    admin: true,
  },
  {
    key: '/admin/statistics',
    icon: BarChartOutlined,
    label: '数据',
    admin: true,
  },
  {
    key: '/admin/points',
    icon: WalletOutlined,
    label: '积分管理',
    admin: true,
  },
  {
    key: '/admin/model-pricing',
    icon: SettingOutlined,
    label: '计价',
    admin: true,
  },
  {
    key: '/admin/feedback',
    icon: MessageOutlined,
    label: '反馈管理',
    admin: true,
  },
  {
    key: '/admin/message',
    icon: BellOutlined,
    label: '消息中心',
    admin: true,
  },
]

// 顶部导航仅展示非管理端入口（管理端入口合并进「管理」下拉）
const menuItems = computed(() => {
  return originItems.filter((item) => !item.admin)
})

// 管理员是否登录（控制「管理」下拉显隐）
const isAdminUser = computed(() => checkIsAdmin(loginUserStore.loginUser))

// 管理员菜单项（合并到「管理」下拉）
const adminMenuItems = computed(() => originItems.filter((item) => item.admin))

// 当前是否处于管理端路由（「管理」按钮高亮）
const isAdminRoute = computed(() => selectedKeys.value.some((k) => k.startsWith('/admin')))

// 下拉菜单中高亮当前管理页
const adminSelectedKeys = computed(() => {
  const path = selectedKeys.value[0] || ''
  const hit = adminMenuItems.value.find(
    (item) => path === item.key || path.startsWith(item.key + '/'),
  )
  return hit ? [hit.key] : []
})

// 点击管理员菜单项跳转
const onAdminMenuClick = ({ key }: { key: string }) => {
  router.push(key)
}

// 退出登录
const doLogout = async () => {
  const res = await userLogout()
  if (res.data.code === 0) {
    loginUserStore.setLoginUser({
      userName: '未登录',
    })
    message.success('退出登录成功')
    await router.push('/user/login')
  } else {
    message.error('退出登录失败，' + res.data.message)
  }
}
</script>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  padding: 0;
  height: 64px;
  line-height: 64px;
  border-bottom: 1px solid var(--color-border);
  transition: all var(--transition-normal);
  overflow: hidden;
}

.header-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
}

.header-left {
  display: flex;
  align-items: center;
}

.logo-link {
  display: block;
  transition: opacity var(--transition-fast);
}

.logo-link:hover {
  opacity: 0.8;
}

.logo-wrapper {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-img {
  width: 36px;
  height: 36px;
  object-fit: contain;
}

.site-title {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: var(--color-text);
  white-space: nowrap;
  letter-spacing: -0.3px;
}

/* 导航菜单 */
.nav-center {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-secondary);
  transition: all var(--transition-fast);
  text-decoration: none;
}

.nav-item:hover {
  color: var(--color-text);
  background: var(--color-background-secondary);
}

.nav-item.active {
  color: var(--color-primary-dark);
  background: rgba(34, 197, 94, 0.1);
}

.nav-icon {
  font-size: 16px;
}

/* 用户区域 */
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-dropdown {
  cursor: pointer;
  height: 64px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.checkin-btn.ant-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-primary-dark);
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.35);
  box-shadow: none;
  transition: all var(--transition-fast);

  &:hover:not(:disabled) {
    background: rgba(34, 197, 94, 0.16);
    border-color: var(--color-primary);
    color: var(--color-primary-dark);
  }

  &:disabled {
    background: var(--color-background-tertiary);
    border-color: var(--color-border);
    color: var(--color-text-muted);
    box-shadow: none;
  }

  .anticon {
    font-size: 13px;
  }
}

.upgrade-vip-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  background: transparent;
  color: var(--color-primary);
  text-decoration: none;
  transition: all var(--transition-fast);

  &:hover {
    background: rgba(34, 197, 94, 0.08);
    color: var(--color-primary-dark);
  }

  .anticon {
    font-size: 13px;
  }
}

.vip-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-primary);
  text-decoration: none;
  transition: all var(--transition-fast);

  &:hover {
    color: var(--color-primary-dark);
  }

  .anticon {
    font-size: 13px;
  }
}

.user-info {
  padding: 6px 12px;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
}

.user-info:hover {
  background: var(--color-background-secondary);
}

.user-avatar {
  border: 2px solid var(--color-border);
  cursor: pointer;
  transition: border-color var(--transition-fast), transform var(--transition-fast);
}

.user-avatar:hover {
  border-color: var(--color-primary);
  transform: scale(1.04);
}

.user-name {
  font-weight: 500;
  color: var(--color-text);
  font-size: 14px;
}

.login-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 38px;
  padding: 0 24px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 600;
  color: white;
  background: var(--gradient-primary);
  border: none;
  box-shadow: var(--shadow-green);
  transition: all var(--transition-normal);
  text-decoration: none;
}

.login-btn:hover {
  color: white;
  box-shadow: 0 6px 20px rgba(34, 197, 94, 0.35);
}

.dropdown-menu {
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow-lg);
  border: 1px solid var(--color-border);
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  transition: all var(--transition-fast);
}

.dropdown-item:hover {
  background: var(--color-background-secondary);
}

.vip-info-item {
  color: var(--color-primary-dark);
  background: rgba(34, 197, 94, 0.1);
  font-weight: 600;
  cursor: default;

  &:hover {
    background: rgba(34, 197, 94, 0.15);
  }
}

/* 响应式 */
@media (max-width: 768px) {
  .header-container {
    padding: 0 16px;
  }

  .site-title {
    display: none;
  }

  .nav-item span {
    display: none;
  }

  .nav-item {
    padding: 8px 12px;
  }

  .user-name {
    display: none;
  }
}
/* 站内信铃铛 */
.bell-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  transition: all var(--transition-fast);
}
.bell-btn:hover {
  color: var(--color-primary-dark);
  background: var(--color-background-secondary);
}
.bell-icon {
  font-size: 17px;
}

/* 铃铛下拉消息面板 */
.message-popover {
  width: 320px;
  background: #fff;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  border: 1px solid var(--color-border);
  overflow: hidden;
}
.message-popover-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  border-bottom: 1px solid var(--color-border-light, #e5e7eb);
}
.message-popover-link {
  font-size: 12px;
  color: var(--color-primary);
  cursor: pointer;
}
.message-popover-link:hover {
  color: var(--color-primary-dark);
}
.message-popover-list {
  max-height: 320px;
  overflow-y: auto;
}
.message-popover-item {
  padding: 10px 14px;
  cursor: pointer;
  border-bottom: 1px solid var(--color-border-light, #f1f5f9);
  transition: background var(--transition-fast);
}
.message-popover-item:hover {
  background: var(--color-background-secondary);
}
.message-popover-item.unread {
  background: rgba(34, 197, 94, 0.05);
}
.message-popover-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.unread-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--color-primary);
  flex-shrink: 0;
}
.message-popover-desc {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}
.message-popover-time {
  margin-top: 4px;
  font-size: 11px;
  color: var(--color-text-muted);
}
.message-popover-foot {
  display: flex;
  justify-content: flex-end;
  padding: 4px 8px;
  border-top: 1px solid var(--color-border-light, #e5e7eb);
}
/* 管理员下拉触发按钮 */
.admin-nav-trigger {
  cursor: pointer;
  user-select: none;
}
.admin-nav-arrow {
  font-size: 11px;
  margin-left: 2px;
  opacity: 0.75;
  transition: transform var(--transition-fast);
}
.admin-nav-trigger:hover .admin-nav-arrow {
  transform: translateY(1px);
}

/* 管理员下拉菜单 */
.admin-nav-menu {
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow-lg);
  border: 1px solid var(--color-border);
  min-width: 168px;
  padding: 4px;
}
.admin-nav-menu .ant-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  border-radius: var(--radius-sm);
  margin: 2px 0;
}
.admin-nav-menu .ant-menu-item .anticon {
  font-size: 15px;
}
</style>
