<template>
  <div id="userLoginPage">
    <!-- 背景装饰：渐变光晕 + 漂浮圆球 + 点阵网格 -->
    <div class="bg-decor" aria-hidden="true">
      <div class="orb orb-one"></div>
      <div class="orb orb-two"></div>
      <div class="orb orb-three"></div>
      <div class="dot-grid"></div>
    </div>

    <div class="auth-shell">
      <!-- 左侧：平台介绍 -->
      <aside class="intro-panel">
        <div class="brand">
          <div class="brand-mark">
            <img src="@/assets/logo.png" alt="AI文章创作平台" />
          </div>
          <span class="brand-name">AI 文章创作平台</span>
        </div>

        <div class="intro-body">
          <h1 class="intro-title">
            欢迎回来，<br />
            继续<span class="accent">智能创作</span>之旅
          </h1>
          <p class="intro-desc">
            从选题研究、新闻采集、标题生成、大纲规划到正文创作与配图合成，
            全程人机协同、边生成边确认，让创作变得简单而高效。
          </p>

          <ul class="feature-list">
            <li class="feature-item">
              <div class="feature-icon"><RobotOutlined /></div>
              <div class="feature-text">
                <h3>多智能体协同</h3>
                <p>新闻采集 / 标题 / 大纲 / 正文 / 配图 / 合并，各司其职</p>
              </div>
            </li>
            <li class="feature-item">
              <div class="feature-icon"><ThunderboltOutlined /></div>
              <div class="feature-text">
                <h3>人机协同断点</h3>
                <p>标题、大纲确认与 AI 改大纲，边生成边把控</p>
              </div>
            </li>
            <li class="feature-item">
              <div class="feature-icon"><PictureOutlined /></div>
              <div class="feature-text">
                <h3>多源智能配图</h3>
                <p>Pexels 真实图片、AI 生图、SVG 示意图等</p>
              </div>
            </li>
            <li class="feature-item">
              <div class="feature-icon"><EyeOutlined /></div>
              <div class="feature-text">
                <h3>实时进度流</h3>
                <p>实时进度显示，正文与大纲流式输出</p>
              </div>
            </li>
          </ul>
        </div>

        <div class="intro-foot">
          <span class="dot"></span>
          <span>登录账号，继续你的图文创作</span>
        </div>
      </aside>

      <!-- 右侧：登录区域 -->
      <main class="form-panel">
        <header class="card-head">
          <h2 class="card-title">欢迎<span class="accent">回来</span></h2>
          <p class="card-subtitle">登录您的账号继续创作</p>
        </header>

        <a-form :model="formState" class="login-form" @finish="handleSubmit">
          <a-form-item name="userAccount" :rules="[{ required: true, message: '请输入账号' }]">
            <a-input
              v-model:value="formState.userAccount"
              placeholder="请输入账号"
              size="large"
            >
              <template #prefix><UserOutlined class="field-icon" /></template>
            </a-input>
          </a-form-item>
          <a-form-item
            name="userPassword"
            :rules="[
              { required: true, message: '请输入密码' },
              { min: 8, message: '密码长度不能小于 8 位' },
            ]"
          >
            <a-input-password
              v-model:value="formState.userPassword"
              placeholder="请输入密码"
              size="large"
            >
              <template #prefix><LockOutlined class="field-icon" /></template>
            </a-input-password>
          </a-form-item>
          <a-form-item class="submit-field">
            <a-button type="primary" html-type="submit" size="large" block class="submit-btn">
              登录
            </a-button>
          </a-form-item>
        </a-form>

        <div class="form-footer">
          <span>还没有账号？</span>
          <RouterLink to="/user/register" class="register-link">立即注册</RouterLink>
        </div>
      </main>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { reactive } from 'vue'
import { userLogin } from '@/api/userController.ts'
import { useLoginUserStore } from '@/stores/loginUser.ts'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  EyeOutlined,
  LockOutlined,
  PictureOutlined,
  RobotOutlined,
  ThunderboltOutlined,
  UserOutlined,
} from '@ant-design/icons-vue'

const formState = reactive<API.UserLoginRequest>({
  userAccount: '',
  userPassword: '',
})

const route = useRoute()
const router = useRouter()
const loginUserStore = useLoginUserStore()

const handleSubmit = async (values: any) => {
  const res = await userLogin(values)
  if (res.data.code === 0 && res.data.data) {
    await loginUserStore.fetchLoginUser()
    message.success('登录成功')
    // 深链断点续作：登录后回到被踢出前的页面（?redirect=），无 redirect 才回首页
    const redirect = route.query.redirect
    if (typeof redirect === 'string' && redirect.trim()) {
      let target = redirect.trim()
      try {
        target = decodeURIComponent(target)
      } catch {
        // 畸形编码：按原样跳转
      }
      if (target.startsWith('/')) {
        router.replace(target)
        return
      }
    }
    router.replace('/')
  } else {
    message.error('登录失败，' + res.data.message)
  }
}
</script>

<style scoped>
#userLoginPage {
  position: relative;
  min-height: calc(100vh - 150px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px 60px;
  overflow: hidden;
  background:
    radial-gradient(1200px 520px at 85% -10%, rgba(74, 222, 128, 0.18), transparent 60%),
    radial-gradient(900px 460px at 8% 110%, rgba(34, 197, 94, 0.14), transparent 55%),
    linear-gradient(180deg, #f3fbf6 0%, #ffffff 55%, #f6fbf8 100%);
}

/* ===== 背景装饰 ===== */
.bg-decor {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(70px);
  opacity: 0.55;
}

.orb-one {
  width: 420px;
  height: 420px;
  top: -120px;
  right: -80px;
  background: radial-gradient(circle at 30% 30%, rgba(74, 222, 128, 0.55), rgba(34, 197, 94, 0.1) 70%);
  animation: drift 16s ease-in-out infinite alternate;
}

.orb-two {
  width: 360px;
  height: 360px;
  bottom: -140px;
  left: -90px;
  background: radial-gradient(circle at 60% 40%, rgba(147, 197, 253, 0.45), rgba(59, 130, 246, 0.08) 70%);
  animation: drift 20s ease-in-out infinite alternate-reverse;
}

.orb-three {
  width: 220px;
  height: 220px;
  top: 38%;
  left: 10%;
  background: radial-gradient(circle at 50% 50%, rgba(253, 224, 71, 0.35), rgba(234, 179, 8, 0.06) 70%);
  animation: drift 24s ease-in-out infinite alternate;
}

.dot-grid {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(rgba(15, 23, 42, 0.07) 1px, transparent 1px);
  background-size: 24px 24px;
  -webkit-mask-image: radial-gradient(ellipse 70% 60% at 50% 40%, #000 30%, transparent 75%);
  mask-image: radial-gradient(ellipse 70% 60% at 50% 40%, #000 30%, transparent 75%);
}

@keyframes drift {
  from { transform: translate3d(0, 0, 0) scale(1); }
  to { transform: translate3d(40px, -30px, 0) scale(1.08); }
}

/* ===== 主容器：左右布局 ===== */
.auth-shell {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 1080px;
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  background: rgba(255, 255, 255, 0.78);
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: 28px;
  box-shadow:
    0 24px 60px -20px rgba(15, 23, 42, 0.18),
    0 8px 24px -12px rgba(34, 197, 94, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
  overflow: hidden;
  animation: card-in 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes card-in {
  from { opacity: 0; transform: translateY(18px) scale(0.985); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes rise-in {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ===== 左侧介绍面板 ===== */
.intro-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 44px 44px 36px;
  background:
    linear-gradient(160deg, rgba(34, 197, 94, 0.06) 0%, rgba(255, 255, 255, 0) 55%),
    linear-gradient(180deg, #f6fdf9 0%, #f1fbf5 100%);
  border-right: 1px solid var(--color-border-light);
  overflow: hidden;
}

.intro-panel::after {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 1px;
  background: linear-gradient(180deg, transparent, rgba(34, 197, 94, 0.25), transparent);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  animation: rise-in 0.6s 0.08s both;
}

.brand-mark {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid var(--color-border);
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px;
}

.brand-mark img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.brand-name {
  font-family: 'Outfit', sans-serif;
  font-weight: 600;
  font-size: 15px;
  letter-spacing: 0.02em;
  color: var(--color-secondary);
}

.intro-body {
  margin-top: 38px;
  flex: 1;
}

.intro-title {
  margin: 0 0 16px;
  font-size: 32px;
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.01em;
  color: var(--color-secondary);
  animation: rise-in 0.6s 0.16s both;
}

.intro-title .accent {
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.intro-desc {
  margin: 0 0 28px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-text-secondary);
  max-width: 440px;
  animation: rise-in 0.6s 0.22s both;
}

.feature-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.feature-item {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  animation: rise-in 0.6s both;
}

.feature-item:nth-child(1) { animation-delay: 0.28s; }
.feature-item:nth-child(2) { animation-delay: 0.34s; }
.feature-item:nth-child(3) { animation-delay: 0.40s; }
.feature-item:nth-child(4) { animation-delay: 0.46s; }

.feature-icon {
  flex: 0 0 40px;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: var(--color-primary);
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.1);
}

.feature-text h3 {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-secondary);
}

.feature-text p {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-text-secondary);
}

.intro-foot {
  margin-top: 32px;
  padding-top: 22px;
  border-top: 1px dashed var(--color-border);
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
  animation: rise-in 0.6s 0.52s both;
}

.intro-foot .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary);
  box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.15);
}

/* ===== 右侧表单面板 ===== */
.form-panel {
  padding: 56px 48px 44px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.card-head {
  margin-bottom: 28px;
  animation: rise-in 0.6s 0.16s both;
}

.card-title {
  margin: 0 0 8px;
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.01em;
  color: var(--color-secondary);
}

.card-title .accent {
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.card-subtitle {
  margin: 0;
  font-size: 14px;
  color: var(--color-text-secondary);
}

/* ===== 表单：扁平单框，不嵌套 ===== */
.login-form :deep(.ant-form-item) {
  margin-bottom: 20px;
}

/* 让 ant-input-affix-wrapper 直接作为单一边框输入框，不要嵌套边框 */
.login-form :deep(.ant-input-affix-wrapper) {
  padding: 0;
  background: transparent;
  border: none;
  box-shadow: none;
}

.login-form :deep(.ant-input-affix-wrapper .ant-input) {
  background: transparent;
  border: 1.5px solid var(--color-border);
  border-radius: 12px;
  min-height: 50px;
  padding: 0 14px;
  font-size: 15px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.login-form :deep(.ant-input-affix-wrapper .ant-input:hover) {
  border-color: var(--color-primary-light);
}

.login-form :deep(.ant-input-affix-wrapper-focused .ant-input),
.login-form :deep(.ant-input-affix-wrapper .ant-input:focus) {
  border-color: var(--color-primary) !important;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.12) !important;
}

.login-form :deep(.ant-input-affix-wrapper .ant-input-prefix) {
  margin: 0 10px 0 14px;
  color: var(--color-text-muted);
}

.login-form :deep(.ant-input-affix-wrapper-focused .ant-input-prefix) {
  color: var(--color-primary);
}

.field-icon {
  color: var(--color-text-muted);
  font-size: 15px;
  transition: color 0.2s ease;
}

.login-form :deep(.ant-form-item-explain-error) {
  font-size: 13px;
  margin-top: 2px;
}

/* 提交按钮 */
.submit-field {
  margin-top: 6px;
  margin-bottom: 0;
}

.submit-btn {
  height: 50px;
  border-radius: 12px;
  border: none;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.04em;
  background: var(--gradient-primary);
  box-shadow: 0 10px 24px -8px rgba(34, 197, 94, 0.55);
  transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease;
}

.submit-btn:not(:disabled):hover {
  transform: translateY(-2px);
  filter: brightness(1.05);
  box-shadow: 0 14px 30px -8px rgba(34, 197, 94, 0.6);
}

.submit-btn:not(:disabled):active {
  transform: translateY(0);
  filter: brightness(0.98);
}

/* ===== 页脚 ===== */
.form-footer {
  margin-top: 24px;
  text-align: center;
  font-size: 14px;
  color: var(--color-text-secondary);
  animation: rise-in 0.6s 0.42s both;
}

.register-link {
  margin-left: 4px;
  color: var(--color-primary-dark);
  font-weight: 600;
  transition: color 0.2s ease;
}

.register-link:hover {
  color: var(--color-primary);
  text-decoration: underline;
}

/* ===== 响应式 ===== */
@media (max-width: 880px) {
  .auth-shell {
    grid-template-columns: 1fr;
    max-width: 480px;
  }

  .intro-panel {
    border-right: none;
    border-bottom: 1px solid var(--color-border-light);
    padding: 32px 32px 28px;
  }

  .intro-panel::after { display: none; }

  .intro-body { margin-top: 24px; }

  .intro-title { font-size: 24px; }

  .feature-list { gap: 12px; }

  .form-panel { padding: 36px 32px 32px; }
}

@media (max-width: 520px) {
  #userLoginPage {
    padding: 24px 14px 44px;
  }

  .auth-shell { border-radius: 22px; }

  .intro-panel,
  .form-panel {
    padding: 28px 22px 24px;
  }

  .intro-title { font-size: 22px; }
  .card-title { font-size: 24px; }

  .feature-list {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .feature-item { gap: 10px; }

  .feature-icon {
    flex: 0 0 34px;
    width: 34px;
    height: 34px;
    font-size: 16px;
  }

  .feature-text h3 { font-size: 13px; }
  .feature-text p { font-size: 12px; }
}
</style>
