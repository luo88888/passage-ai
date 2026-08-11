<script setup lang="ts">
/**
 * 账号设置页（个人中心）
 *
 * 支持修改：头像 / 昵称 / 用户简介（基本信息卡片）+ 修改密码（密码卡片）。
 * 头像：本地选择 -> 预览 -> 保存时先上传（POST /user/avatar/upload）再更新资料。
 * 修改密码成功后后端清除会话，前端跳转登录页重新登录。
 */
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ArrowLeftOutlined,
  UserOutlined,
  CameraOutlined,
  SafetyCertificateOutlined,
  IdcardOutlined,
  LockOutlined,
} from '@ant-design/icons-vue'

import { useLoginUserStore } from '@/stores/loginUser'
import {
  updateUserProfile,
  changePassword,
  uploadUserAvatar,
} from '@/api/userController'

const router = useRouter()
const loginUserStore = useLoginUserStore()

const loading = ref(true)
const savingProfile = ref(false)
const savingPassword = ref(false)

// ==================== 基本信息 ====================
const profileForm = reactive({
  userName: '',
  userAvatar: '',
  userProfile: '',
})
// 待上传的头像文件（选择后仅本地预览，保存时才上传）
const avatarFile = ref<File | null>(null)
const avatarPreview = ref('')

onMounted(async () => {
  loading.value = true
  try {
    await loginUserStore.fetchLoginUser()
    const u = loginUserStore.loginUser
    profileForm.userName = u?.userName ?? ''
    profileForm.userAvatar = u?.userAvatar ?? ''
    profileForm.userProfile = u?.userProfile ?? ''
    avatarPreview.value = u?.userAvatar ?? ''
  } finally {
    loading.value = false
  }
})

/** 选择头像：校验格式与大小，仅本地预览（返回 false 阻止 a-upload 自动上传） */
const onBeforeAvatarSelect = (file: File) => {
  const allowed = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
  if (!allowed.includes(file.type)) {
    message.error('仅支持 JPG/PNG/WebP/GIF 格式的头像')
    return false
  }
  if (file.size > 2 * 1024 * 1024) {
    message.error('头像大小不能超过 2MB')
    return false
  }
  avatarFile.value = file
  const reader = new FileReader()
  reader.onload = () => {
    avatarPreview.value = String(reader.result || '')
  }
  reader.readAsDataURL(file)
  return false
}

const saveProfile = async () => {
  const name = profileForm.userName.trim()
  if (!name) {
    message.warning('昵称不能为空')
    return
  }
  savingProfile.value = true
  try {
    // 1) 有新头像则先上传，拿到 URL
    let avatarUrl = profileForm.userAvatar
    if (avatarFile.value) {
      const upRes = await uploadUserAvatar({} as API.BodyUploadAvatarApiUserAvatarUploadPost, avatarFile.value)
      if (upRes.data.code !== 0 || !upRes.data.data) {
        message.error(upRes.data.message || '头像上传失败')
        return
      }
      avatarUrl = upRes.data.data
    }
    // 2) 更新资料（昵称/头像/简介）
    const res = await updateUserProfile({
      userName: name,
      userAvatar: avatarUrl,
      userProfile: profileForm.userProfile,
    })
    if (res.data.code === 0 && res.data.data) {
      // 3) 同步刷新登录态（Pinia + 本地表单/预览）
      loginUserStore.setLoginUser(res.data.data)
      profileForm.userAvatar = res.data.data.userAvatar ?? ''
      avatarPreview.value = res.data.data.userAvatar ?? ''
      profileForm.userName = res.data.data.userName ?? ''
      profileForm.userProfile = res.data.data.userProfile ?? ''
      avatarFile.value = null
      message.success('资料更新成功')
    } else {
      message.error(res.data.message || '资料更新失败')
    }
  } catch (e: any) {
    message.error(e?.message || '资料更新失败')
  } finally {
    savingProfile.value = false
  }
}

// ==================== 修改密码 ====================
const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  checkPassword: '',
})

const savePassword = async () => {
  const { oldPassword, newPassword, checkPassword } = passwordForm
  if (!oldPassword || !newPassword || !checkPassword) {
    message.warning('请填写完整的密码信息')
    return
  }
  if (newPassword.length < 8) {
    message.warning('新密码长度不能小于 8 位')
    return
  }
  if (newPassword !== checkPassword) {
    message.warning('两次输入的新密码不一致')
    return
  }
  savingPassword.value = true
  try {
    const res = await changePassword({ oldPassword, newPassword, checkPassword })
    if (res.data.code === 0) {
      message.success('密码修改成功，请重新登录')
      loginUserStore.setLoginUser({ userName: '未登录' })
      router.push(`/user/login?redirect=${encodeURIComponent('/user/profile')}`)
    } else {
      message.error(res.data.message || '密码修改失败')
    }
  } catch (e: any) {
    message.error(e?.message || '密码修改失败')
  } finally {
    savingPassword.value = false
  }
}
</script>

<template>
  <div id="userSettingsPage">
    <div class="settings-wrap">
      <!-- 顶部标题栏 -->
      <div class="settings-header">
        <a-button class="back-btn" @click="router.push('/user/profile')">
          <ArrowLeftOutlined />
          返回个人主页
        </a-button>
        <div class="header-title">
          <h2>账号设置</h2>
          <span>管理你的个人资料与账号安全</span>
        </div>
      </div>

      <a-spin :spinning="loading" size="large">
        <div class="settings-body">
          <!-- 基本信息 -->
          <div class="settings-card">
            <div class="card-head">
              <IdcardOutlined class="card-icon" />
              <span>基本信息</span>
            </div>
            <div class="card-body">
              <div class="avatar-row">
                <a-upload
                  :show-upload-list="false"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  :before-upload="onBeforeAvatarSelect"
                >
                  <div class="avatar-uploader">
                    <a-avatar :size="96" :src="avatarPreview" class="avatar-img">
                      <template #icon><UserOutlined /></template>
                    </a-avatar>
                    <div class="avatar-mask">
                      <CameraOutlined />
                      <span>更换头像</span>
                    </div>
                  </div>
                </a-upload>
                <div class="avatar-tip">
                  <p>支持 JPG / PNG / WebP / GIF</p>
                  <p>大小不超过 2MB</p>
                </div>
              </div>

              <div class="form-item">
                <label class="form-label">昵称</label>
                <a-input
                  v-model:value="profileForm.userName"
                  :maxlength="256"
                  placeholder="请输入昵称"
                  class="form-input"
                />
              </div>

              <div class="form-item">
                <label class="form-label">简介</label>
                <a-textarea
                  v-model:value="profileForm.userProfile"
                  :maxlength="512"
                  :rows="3"
                  :show-count="true"
                  placeholder="介绍一下自己吧（选填）"
                  class="form-input"
                />
              </div>

              <div class="form-actions">
                <a-button
                  type="primary"
                  class="save-btn"
                  :loading="savingProfile"
                  @click="saveProfile"
                >
                  保存资料
                </a-button>
              </div>
            </div>
          </div>

          <!-- 修改密码 -->
          <div class="settings-card">
            <div class="card-head">
              <LockOutlined class="card-icon" />
              <span>修改密码</span>
            </div>
            <div class="card-body">
              <div class="form-item">
                <label class="form-label">原密码</label>
                <a-input-password
                  v-model:value="passwordForm.oldPassword"
                  placeholder="请输入原密码"
                  class="form-input"
                />
              </div>
              <div class="form-item">
                <label class="form-label">新密码</label>
                <a-input-password
                  v-model:value="passwordForm.newPassword"
                  placeholder="请输入新密码（至少 8 位）"
                  class="form-input"
                />
              </div>
              <div class="form-item">
                <label class="form-label">确认新密码</label>
                <a-input-password
                  v-model:value="passwordForm.checkPassword"
                  placeholder="请再次输入新密码"
                  class="form-input"
                />
              </div>
              <div class="form-actions">
                <a-button
                  type="primary"
                  class="save-btn"
                  :loading="savingPassword"
                  @click="savePassword"
                >
                  修改密码
                </a-button>
              </div>
              <div class="form-tip">
                <SafetyCertificateOutlined class="tip-icon" />
                <span>修改密码成功后需要重新登录</span>
              </div>
            </div>
          </div>
        </div>
      </a-spin>
    </div>
  </div>
</template>

<style scoped>
#userSettingsPage {
  min-height: 100vh;
  background: var(--color-background-secondary, #f8fafc);
}

.settings-wrap {
  max-width: 720px;
  margin: 0 auto;
  padding: 40px 24px 60px;
}

.settings-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.back-btn.ant-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: var(--radius-md, 10px);
  font-weight: 500;
  color: var(--color-text-secondary, #475569);
  background: #fff;
  border: 1px solid var(--color-border-light, #e5e7eb);
}

.back-btn.ant-btn:hover {
  color: var(--color-primary-dark, #16a34a);
  border-color: rgba(34, 197, 94, 0.4);
}

.header-title h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text, #1f2937);
}

.header-title span {
  font-size: 13px;
  color: var(--color-text-muted, #9ca3af);
}

.settings-body {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.settings-card {
  background: #fff;
  border: 1px solid var(--color-border-light, #e5e7eb);
  border-radius: var(--radius-lg, 14px);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.05);
  overflow: hidden;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 24px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text, #1f2937);
  border-bottom: 1px solid var(--color-border-light, #e5e7eb);
}

.card-icon {
  color: var(--color-primary, #22c55e);
  font-size: 16px;
}

.card-body {
  padding: 24px;
}

/* 头像上传 */
.avatar-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.avatar-uploader {
  position: relative;
  width: 96px;
  height: 96px;
  border-radius: var(--radius-full, 9999px);
  overflow: hidden;
  cursor: pointer;
  border: 2px dashed var(--color-border, #d1d5db);
  transition: border-color var(--transition-fast, 150ms ease-out);
}

.avatar-uploader:hover {
  border-color: var(--color-primary, #22c55e);
}

.avatar-img {
  width: 100%;
  height: 100%;
  font-size: 40px;
}

.avatar-mask {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: #fff;
  background: rgba(0, 0, 0, 0.45);
  font-size: 12px;
  opacity: 0;
  transition: opacity var(--transition-fast, 150ms ease-out);
}

.avatar-uploader:hover .avatar-mask {
  opacity: 1;
}

.avatar-tip {
  font-size: 13px;
  color: var(--color-text-muted, #9ca3af);
  line-height: 1.7;
}

.avatar-tip p {
  margin: 0;
}

/* 表单 */
.form-item {
  margin-bottom: 20px;
}

.form-label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-secondary, #475569);
}

.form-input.ant-input,
.form-input.ant-input-affix-wrapper,
.form-input.ant-input-textarea {
  border-radius: var(--radius-md, 10px);
  border-color: var(--color-border-light, #e5e7eb);
}

.form-input.ant-input:focus,
.form-input.ant-input-affix-wrapper:focus,
.form-input.ant-input-focused,
.form-input.ant-input-textarea:focus-within {
  border-color: var(--color-primary, #22c55e);
  box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.12);
}

.form-actions {
  margin-top: 8px;
}

.save-btn.ant-btn-primary {
  height: 40px;
  padding: 0 28px;
  border-radius: var(--radius-md, 10px);
  font-weight: 600;
  background: var(--gradient-primary, linear-gradient(135deg, #22c55e, #16a34a));
  border: none;
  box-shadow: var(--shadow-green, 0 4px 14px rgba(34, 197, 94, 0.25));
}

.save-btn.ant-btn-primary:hover {
  opacity: 0.92;
}

.form-tip {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--color-text-muted, #9ca3af);
}

.tip-icon {
  color: var(--color-primary, #22c55e);
}

@media (max-width: 640px) {
  .settings-wrap {
    padding: 24px 16px 40px;
  }

  .settings-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .card-body {
    padding: 20px 16px;
  }
}
</style>
