<script setup lang="ts">
/**
 * 开通会员页面
 *
 * 展示会员价格与特权，提供 Stripe 支付跳转、已是会员时展示会员状态与退款入口。
 * 支付成功靠后端 Stripe webhook 异步发货，回跳页（/payment/success）会拉取最新用户信息。
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  CrownOutlined,
  CheckCircleFilled,
  ThunderboltFilled,
  ReloadOutlined,
} from '@ant-design/icons-vue'

import { useLoginUserStore } from '@/stores/loginUser'
import { isVip } from '@/utils/permission'
import {
  getVipPlans,
  createVipSession,
  refundPayment,
  type VipPlanVO,
} from '@/api/paymentController'

const router = useRouter()
const loginUserStore = useLoginUserStore()

const plans = ref<VipPlanVO[]>([])
const loadingPlans = ref(false)
const paying = ref(false)
const refunding = ref(false)

// 当前用户是否已享受会员权益（VIP 或管理员）
const isVipUser = computed(() => isVip(loginUserStore.loginUser))

onMounted(async () => {
  // 会员信息为公开接口，未登录也可查看价格与特权
  await fetchPlans()
})

const fetchPlans = async () => {
  loadingPlans.value = true
  try {
    const res = await getVipPlans()
    if (res.data.code === 0 && Array.isArray(res.data.data)) {
      plans.value = res.data.data
    } else {
      message.error(res.data.message || '获取会员套餐失败')
    }
  } catch (e: any) {
    message.error(e?.message || '获取会员套餐失败')
  } finally {
    loadingPlans.value = false
  }
}

// 价格展示
const priceText = computed(() => {
  const p = plans.value[0]
  if (!p) return ''
  const symbol = p.currency?.toLowerCase() === 'usd' ? '$' : ''
  return `${symbol}${p.price}`
})

const plan = computed(() => plans.value[0])
const privileges = computed(() => plan.value?.privileges || [])

// 开通：创建 Stripe 支付会话并跳转
const startPay = async () => {
  if (!loginUserStore.loginUser.id) {
    router.push(`/user/login?redirect=${encodeURIComponent('/vip')}`)
    return
  }
  if (isVipUser.value) {
    message.info('您已是会员，无需重复开通')
    return
  }
  paying.value = true
  try {
    const res = await createVipSession()
    if (res.data.code !== 0 || !res.data.data) {
      message.error(res.data.message || '创建支付会话失败')
      return
    }
    // data 为 Stripe 支付页 URL，跳转离开本站
    window.location.href = res.data.data
  } catch (e: any) {
    message.error(e?.message || '创建支付会话失败')
  } finally {
    paying.value = false
  }
}

// 退款：仅真实 VIP（userRole==vip）可调，管理员无支付记录
const doRefund = () => {
  Modal.confirm({
    title: '申请退款',
    content: '退款后将撤销永久会员身份，相关高级功能将不再可用，确定继续吗？',
    okText: '确认退款',
    okType: 'danger',
    cancelText: '再想想',
    onOk: async () => {
      refunding.value = true
      try {
        const res = await refundPayment()
        if (res.data.code === 0 && res.data.data) {
          message.success('退款成功，会员身份已撤销')
          await loginUserStore.fetchLoginUser()
        } else {
          message.error(res.data.message || '退款失败')
        }
      } catch (e: any) {
        message.error(e?.message || '退款失败')
      } finally {
        refunding.value = false
      }
    },
  })
}

// 会员开通时间（已是会员时展示）
const vipTimeText = computed(() => {
  const t = loginUserStore.loginUser.vipTime as unknown as string | undefined
  if (!t) return ''
  try {
    const d = new Date(t)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  } catch {
    return String(t)
  }
})

// 退款按钮仅对真实购买会员（userRole===vip）开放，管理员不展示退款
const canRefund = computed(
  () => loginUserStore.loginUser.userRole === 'vip'
)
</script>

<template>
  <div id="vipPage">
    <div class="vip-wrap">
      <!-- 头部 -->
      <div class="vip-head">
        <div class="head-icon"><CrownOutlined /></div>
        <h1 class="head-title">开通永久会员</h1>
        <p class="head-subtitle">一次买断，解锁全部高级功能，永久有效</p>
      </div>

      <!-- 价格卡片 -->
      <a-spin :spinning="loadingPlans">
        <div v-if="plan" class="price-card">
          <div class="price-top">
            <span class="price-currency">$</span>
            <span class="price-amount">{{ plan.price }}</span>
            <span class="price-unit">USD</span>
          </div>
          <div class="price-title">{{ plan.title }}</div>
          <div class="price-desc">{{ plan.description }}</div>

          <!-- 特权列表 -->
          <div class="privileges">
            <div class="privileges-title">会员特权</div>
            <ul class="privilege-list">
              <li v-for="(p, i) in privileges" :key="i" class="privilege-item">
                <CheckCircleFilled class="privilege-icon" />
                <span>{{ p }}</span>
              </li>
            </ul>
          </div>

          <!-- 开通按钮 -->
          <div class="action-bar">
            <a-button
              v-if="!isVipUser"
              type="primary"
              size="large"
              block
              :loading="paying"
              class="pay-btn"
              @click="startPay"
            >
              <ThunderboltFilled v-if="!paying" />
              立即开通（{{ priceText }}）
            </a-button>
            <a-button v-else size="large" block disabled class="pay-btn">
              <CrownOutlined />
              您已是会员
            </a-button>
            <p class="action-tip" v-if="!isVipUser">支付完成后将自动开通，如未刷新请退出重新登录</p>
          </div>
        </div>
      </a-spin>

      <!-- 已是会员：会员状态卡 -->
      <div v-if="isVipUser" class="status-card">
        <div class="status-card-head">
          <CrownOutlined class="crown" />
          <span class="status-title">会员状态</span>
        </div>
        <a-descriptions :column="1" size="small" class="status-desc">
          <a-descriptions-item label="会员身份">{{ loginUserStore.loginUser.userRole === 'admin' ? '管理员（享会员权益）' : '永久会员' }}</a-descriptions-item>
          <a-descriptions-item v-if="vipTimeText" label="开通时间">{{ vipTimeText }}</a-descriptions-item>
        </a-descriptions>
        <div class="status-actions">
          <a-button :loading="refunding" danger ghost @click="doRefund" v-if="canRefund">
            申请退款
          </a-button>
          <a-button @click="loginUserStore.fetchLoginUser()">
            <ReloadOutlined /> 刷新会员状态
          </a-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
#vipPage {
  min-height: calc(100vh - 64px);
  display: flex;
  justify-content: center;
  padding: 32px 16px 48px;
  background: linear-gradient(180deg, rgba(34, 197, 94, 0.05) 0%, transparent 240px);
}
.vip-wrap {
  width: 100%;
  max-width: 560px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 头部 */
.vip-head {
  text-align: center;
  margin-bottom: 4px;
}
.head-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 12px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--gradient-primary, linear-gradient(135deg, #22c55e, #16a34a));
  color: #fff;
  font-size: 30px;
  box-shadow: 0 6px 20px rgba(34, 197, 94, 0.3);
}
.head-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--color-text, #1f2937);
  margin: 0;
}
.head-subtitle {
  font-size: 14px;
  color: var(--color-text-muted, #6b7280);
  margin: 6px 0 0;
}

/* 价格卡片 */
.price-card {
  background: #fff;
  border: 1px solid var(--color-border-light, #e5e7eb);
  border-radius: var(--radius-lg, 16px);
  padding: 28px 24px 20px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
}
.price-top {
  display: flex;
  align-items: baseline;
  gap: 4px;
  justify-content: center;
}
.price-currency {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-primary, #22c55e);
}
.price-amount {
  font-size: 52px;
  font-weight: 800;
  line-height: 1;
  color: var(--color-primary, #22c55e);
}
.price-unit {
  font-size: 14px;
  color: var(--color-text-muted, #9ca3af);
  align-self: flex-end;
  margin-bottom: 6px;
}
.price-title {
  text-align: center;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text, #1f2937);
  margin-top: 8px;
}
.price-desc {
  text-align: center;
  font-size: 13px;
  color: var(--color-text-muted, #6b7280);
  margin-top: 4px;
}

/* 特权 */
.privileges {
  margin-top: 22px;
  padding-top: 18px;
  border-top: 1px dashed var(--color-border-light, #e5e7eb);
}
.privileges-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text, #374151);
  margin-bottom: 10px;
}
.privilege-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.privilege-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--color-text, #374151);
}
.privilege-icon {
  color: var(--color-primary, #22c55e);
  font-size: 16px;
  flex-shrink: 0;
}

/* 开通按钮 */
.action-bar {
  margin-top: 24px;
}
.pay-btn.ant-btn {
  height: 48px !important;
  font-size: 16px !important;
  font-weight: 600 !important;
  border-radius: var(--radius-md, 10px) !important;
}
.action-tip {
  text-align: center;
  font-size: 12px;
  color: var(--color-text-muted, #9ca3af);
  margin: 10px 0 0;
}

/* 已是会员状态卡 */
.status-card {
  background: rgba(34, 197, 94, 0.06);
  border: 1px solid rgba(34, 197, 94, 0.2);
  border-radius: var(--radius-md, 12px);
  padding: 16px 20px;
}
.status-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-primary-dark, #16a34a);
  margin-bottom: 8px;
}
.status-card-head .crown {
  color: #facc15;
}
.status-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 12px;
}
</style>