<script setup lang="ts">
/**
 * 支付回跳结果页（Stripe 跳回的 success / cancel）
 *
 * Stripe 配置 stripe_success_url=/payment/success、stripe_cancel_url=/payment/cancel，
 * 真正发货由后端 webhook 异步处理，因此本页仅做结果展示并重新拉取登录用户信息，
 * 以最新 userRole/vipTime 为准确认会员身份（不能仅凭跳到 success 页就认为已开通）。
 */
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CheckCircleFilled, CloseCircleFilled, LoadingOutlined } from '@ant-design/icons-vue'
import { useLoginUserStore } from '@/stores/loginUser'

const route = useRoute()
const router = useRouter()
const loginUserStore = useLoginUserStore()

const isSuccess = computed(() => route.path.endsWith('/success'))
const isCancel = computed(() => route.path.endsWith('/cancel'))

const refreshing = ref(true)
const becameVip = ref(false)

onMounted(async () => {
  // webhook 异步发货可能滞后于跳回，轮询刷新一次登录用户信息
  if (loginUserStore.loginUser.id) {
    await loginUserStore.fetchLoginUser()
    becameVip.value =
      loginUserStore.loginUser.userRole === 'vip' ||
      loginUserStore.loginUser.userRole === 'admin'
  }
  refreshing.value = false
})

const goVip = () => router.push('/vip')
const goCreate = () => router.push('/create')
</script>

<template>
  <div id="paymentResultPage">
    <div class="result-card">
      <!-- 成功 -->
      <template v-if="isSuccess">
        <div class="result-icon success"><CheckCircleFilled /></div>
        <h2 class="result-title">支付成功</h2>
        <p v-if="refreshing" class="result-desc">
          <LoadingOutlined />
          正在确认会员开通状态…
        </p>
        <template v-else>
          <p v-if="becameVip" class="result-desc success">
            恭喜，您的永久会员已开通，全部高级功能已解锁！
          </p>
          <p v-else class="result-desc warn">
            支付成功，但会员身份尚未生效。客服正在处理，可稍后点击下方按钮刷新状态。
          </p>
        </template>
      </template>

      <!-- 取消 -->
      <template v-else-if="isCancel">
        <div class="result-icon cancel"><CloseCircleFilled /></div>
        <h2 class="result-title">支付已取消</h2>
        <p class="result-desc">您已取消本次支付，会员尚未开通，随时可重新开通。</p>
      </template>

      <div class="result-actions">
        <a-button v-if="isSuccess && !refreshing && !becameVip" @click="goVip">
          刷新会员状态
        </a-button>
        <a-button v-if="isCancel" type="primary" @click="goVip">重新开通会员</a-button>
        <a-button v-if="isSuccess && becameVip" type="primary" @click="goCreate">
          开始创作
        </a-button>
        <a-button @click="goVip">查看会员权益</a-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
#paymentResultPage {
  min-height: calc(100vh - 64px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.result-card {
  max-width: 440px;
  width: 100%;
  text-align: center;
  background: #fff;
  border: 1px solid var(--color-border-light, #e5e7eb);
  border-radius: var(--radius-lg, 16px);
  padding: 40px 28px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
}
.result-icon {
  font-size: 56px;
  line-height: 1;
}
.result-icon.success {
  color: var(--color-primary, #22c55e);
}
.result-icon.cancel {
  color: #ef4444;
}
.result-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text, #1f2937);
  margin: 16px 0 8px;
}
.result-desc {
  font-size: 14px;
  color: var(--color-text-muted, #6b7280);
  margin: 0;
  line-height: 1.6;
}
.result-desc.warn {
  color: #d97706;
}
.result-desc.success {
  color: var(--color-primary-dark, #16a34a);
}
.result-actions {
  margin-top: 24px;
  display: flex;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
}
</style>