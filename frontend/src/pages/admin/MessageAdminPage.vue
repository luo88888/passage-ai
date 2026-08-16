<script setup lang="ts">
/**
 * 管理端站内信管理页
 *
 * Tab1 发送消息：收件人类型（单用户/批量/全体）+ 用户搜索选择 + 类型/标题/内容/链接；
 *       ALL 写时展开为每个用户一行。
 * Tab2 已发列表：分页表格（senderId 非空 = 管理员主动发信）。
 */
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  SendOutlined,
  UnorderedListOutlined,
  SearchOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'

import { adminSendMessage, adminPageMessage } from '@/api/messageController'
import { listUsersByPage } from '@/api/userController'

// ==================== 常量 ====================
const TYPE_OPTIONS = [
  { value: 'SYSTEM', label: '系统通知' },
  { value: 'FEEDBACK', label: '反馈回复' },
  { value: 'VIP', label: '会员开通' },
  { value: 'POINTS', label: '积分变动' },
]
const TYPE_TAG_COLOR: Record<string, string> = {
  SYSTEM: 'blue',
  FEEDBACK: 'green',
  VIP: 'gold',
  POINTS: 'purple',
}
const TARGET_OPTIONS = [
  { value: 'SINGLE', label: '单用户' },
  { value: 'BATCH', label: '批量用户' },
  { value: 'ALL', label: '全体用户' },
]

// ==================== Tab ====================
const activeTab = ref('send')

// ==================== 发送 ====================
interface UserOption {
  id: number
  userAccount: string
  userName?: string | null
}
const userOptions = ref<UserOption[]>([])
const searchingUser = ref(false)
const sendForm = ref<{
  targetType: string
  userIds: number[]
  type: string
  title?: string
  content?: string
  link?: string
}>({
  targetType: 'SINGLE',
  userIds: [],
  type: 'SYSTEM',
})

const searchUsers = async (keyword?: string) => {
  searchingUser.value = true
  try {
    const res = await listUsersByPage({
      current: 1,
      pageSize: 20,
      userAccount: keyword || undefined,
    } as any)
    if (res.data.code === 0 && res.data.data) {
      userOptions.value = ((res.data.data.records as any[]) ?? []).map((u: any) => ({
        value: u.id,
        label: `${u.userName || u.userAccount}（${u.userAccount}）`,
        id: u.id,
        userAccount: u.userAccount,
        userName: u.userName,
      }))
    }
  } catch (e: any) {
    message.error(e?.message || '搜索用户失败')
  } finally {
    searchingUser.value = false
  }
}

// 单选模式 a-select 绑定的是单个值，多选才是数组；统一规范化为数组，避免校验/发送拿不到 userIds
const onUserIdsChange = (val: any) => {
  sendForm.value.userIds = Array.isArray(val) ? val : val != null ? [val] : []
}

// 切换收件人类型时清空已选用户，避免 SINGLE/BATCH 值类型混乱
const onTargetTypeChange = () => {
  sendForm.value.userIds = []
}

const onUserSearch = (keyword: string) => {
  searchUsers(keyword)
}

const sending = ref(false)
const doSend = async () => {
  const form = sendForm.value
  if (form.targetType !== 'ALL' && (!form.userIds || form.userIds.length === 0)) {
    message.warning('请选择收件用户')
    return
  }
  if (form.targetType === 'SINGLE' && form.userIds.length !== 1) {
    message.warning('单用户发送请选择 1 个用户')
    return
  }
  if (!form.title || !form.title.trim()) {
    message.warning('请填写标题')
    return
  }
  sending.value = true
  try {
    const body: any = {
      targetType: form.targetType,
      type: form.type,
      title: form.title.trim(),
    }
    if (form.targetType !== 'ALL') body.userIds = form.userIds
    if (form.content && form.content.trim()) body.content = form.content.trim()
    if (form.link && form.link.trim()) body.link = form.link.trim()
    const res = await adminSendMessage(body)
    if (res.data.code === 0) {
      message.success(`发送成功，共写入 ${res.data.data} 条消息`)
      sendForm.value = { targetType: 'SINGLE', userIds: [], type: 'SYSTEM' }
      userOptions.value = []
      activeTab.value = 'sent'
      fetchSentList()
    } else {
      message.error(res.data.message || '发送失败')
    }
  } catch (e: any) {
    message.error(e?.message || '发送失败')
  } finally {
    sending.value = false
  }
}

// ==================== 已发列表 ====================
interface SentRow {
  id: number
  userId: number
  type: string
  title: string
  content?: string | null
  link?: string | null
  createTime: string
}
const sentList = ref<SentRow[]>([])
const sentTotal = ref(0)
const sentCurrent = ref(1)
const sentPageSize = ref(10)
const sentType = ref<string | undefined>(undefined)
const sentKeyword = ref('')
const sentLoading = ref(false)

const fetchSentList = async () => {
  sentLoading.value = true
  try {
    const params: any = {
      current: sentCurrent.value,
      pageSize: sentPageSize.value,
    }
    if (sentType.value) params.type = sentType.value
    if (sentKeyword.value.trim()) params.keyword = sentKeyword.value.trim()
    const res = await adminPageMessage(params)
    if (res.data.code === 0 && res.data.data) {
      sentList.value = (res.data.data.records as SentRow[]) ?? []
      sentTotal.value = res.data.data.total ?? 0
    } else {
      message.error(res.data.message || '获取已发列表失败')
    }
  } catch (e: any) {
    message.error(e?.message || '获取已发列表失败')
  } finally {
    sentLoading.value = false
  }
}

const sentPagination = computed(() => ({
  current: sentCurrent.value,
  pageSize: sentPageSize.value,
  total: sentTotal.value,
  showSizeChanger: true,
  showTotal: (t: number) => `共 ${t} 条`,
}))

const doSentTableChange = (page: { current: number; pageSize: number }) => {
  sentCurrent.value = page.current
  sentPageSize.value = page.pageSize
  fetchSentList()
}

const doSentSearch = () => {
  sentCurrent.value = 1
  fetchSentList()
}

const typeLabel = (t: string) => TYPE_OPTIONS.find((o) => o.value === t)?.label || t
const typeColor = (t: string) => TYPE_TAG_COLOR[t] || 'default'
const formatTime = (v?: string | null) => {
  if (!v) return '—'
  return v.replace('T', ' ').slice(0, 19)
}

const sentColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 90 },
  { title: '类型', dataIndex: 'type', key: 'type', width: 110 },
  { title: '标题', dataIndex: 'title', key: 'title', width: 220 },
  { title: '内容', dataIndex: 'content', key: 'content', ellipsis: true },
  { title: '收件人ID', dataIndex: 'userId', key: 'userId', width: 110 },
  { title: '发送时间', dataIndex: 'createTime', key: 'createTime', width: 170 },
]

onMounted(() => {
  searchUsers()
  fetchSentList()
})
</script>

<template>
  <div id="messageAdminPage">
    <div class="page-head">
      <div class="page-head-inner">
        <h1 class="page-title">站内信管理</h1>
        <p class="page-subtitle">向单个 / 批量 / 全体用户发送系统通知与公告，并查看已发消息</p>
        <a-button class="refresh-btn" @click="[searchUsers(), fetchSentList()]">
          <ReloadOutlined /> 刷新
        </a-button>
      </div>
    </div>

    <div class="page-body">
      <a-tabs v-model:activeKey="activeTab">
        <!-- 发送消息 -->
        <a-tab-pane key="send" tab="发送消息">
          <a-form layout="vertical" style="max-width: 640px">
            <a-form-item label="收件人类型" required>
              <a-radio-group v-model:value="sendForm.targetType" @change="onTargetTypeChange">
                <a-radio-button v-for="o in TARGET_OPTIONS" :key="o.value" :value="o.value">
                  {{ o.label }}
                </a-radio-button>
              </a-radio-group>
              <div class="muted" style="margin-top: 4px">
                全体用户广播将对所有注册用户各写入一条消息
              </div>
            </a-form-item>

            <a-form-item
              v-if="sendForm.targetType !== 'ALL'"
              :label="sendForm.targetType === 'SINGLE' ? '收件用户' : '收件用户（可多选）'"
              required
            >
              <a-select
                v-model:value="sendForm.userIds"
                @change="onUserIdsChange"
                :mode="sendForm.targetType === 'SINGLE' ? undefined : 'multiple'"
                :options="userOptions"
                :loading="searchingUser"
                :filter-option="false"
                :show-search="true"
                placeholder="输入账号搜索用户"
                option-filter-prop="userAccount"
                @search="onUserSearch"
                @focus="searchUsers()"
              >
                <template #option="{ label, value }">
                  <div class="user-option">
                    <span>{{ label }}</span>
                    <span class="muted" style="margin-left: 8px">ID: {{ value }}</span>
                  </div>
                </template>
              </a-select>
            </a-form-item>

            <a-form-item label="消息类型">
              <a-select v-model:value="sendForm.type" style="width: 200px">
                <a-select-option v-for="o in TYPE_OPTIONS" :key="o.value" :value="o.value">
                  {{ o.label }}
                </a-select-option>
              </a-select>
            </a-form-item>

            <a-form-item label="标题" required>
              <a-input
                v-model:value="sendForm.title"
                :maxlength="200"
                show-count
                placeholder="消息标题（1~200 字）"
              />
            </a-form-item>

            <a-form-item label="内容">
              <a-textarea
                v-model:value="sendForm.content"
                :rows="4"
                :maxlength="5000"
                show-count
                placeholder="消息正文（选填）"
              />
            </a-form-item>

            <a-form-item label="跳转链接（选填）">
              <a-input
                v-model:value="sendForm.link"
                :maxlength="512"
                placeholder="如 /feedback?activeId=123 或 /points"
              />
            </a-form-item>

            <a-form-item>
              <a-button type="primary" size="large" :loading="sending" @click="doSend">
                <SendOutlined /> 发送
              </a-button>
            </a-form-item>
          </a-form>
        </a-tab-pane>

        <!-- 已发列表 -->
        <a-tab-pane key="sent" tab="已发列表">
          <div class="filter-bar">
            <a-select
              v-model:value="sentType"
              :allowClear="true"
              placeholder="全部类型"
              style="width: 150px"
              @change="doSentSearch"
            >
              <a-select-option v-for="o in TYPE_OPTIONS" :key="o.value" :value="o.value">
                {{ o.label }}
              </a-select-option>
            </a-select>
            <a-input
              v-model:value="sentKeyword"
              placeholder="关键字（标题/内容）"
              style="width: 220px"
              allow-clear
              @pressEnter="doSentSearch"
            />
            <a-button type="primary" @click="doSentSearch"><SearchOutlined /> 搜索</a-button>
          </div>
          <a-table
            :columns="sentColumns"
            :data-source="sentList"
            :pagination="sentPagination"
            :loading="sentLoading"
            row-key="id"
            size="middle"
            @change="doSentTableChange"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'type'">
                <a-tag :color="typeColor(record.type)">{{ typeLabel(record.type) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'content'">
                <span class="content-cell">{{ record.content || '（无内容）' }}</span>
              </template>
              <template v-else-if="column.key === 'createTime'">
                {{ formatTime(record.createTime) }}
              </template>
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<style scoped>
#messageAdminPage {
  padding: 24px 32px 48px;
  max-width: 1280px;
  margin: 0 auto;
}

.page-head {
  margin-bottom: 20px;
}
.page-head-inner {
  display: flex;
  align-items: center;
  gap: 16px;
}
.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text, #0f172a);
}
.page-subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-text-secondary, #64748b);
}
.refresh-btn {
  margin-left: auto;
}

.page-body {
  background: #fff;
  border: 1px solid var(--color-border-light, #e5e7eb);
  border-radius: var(--radius-lg, 16px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
  padding: 20px 24px;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.user-option {
  display: flex;
  align-items: center;
}

.content-cell {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.muted {
  font-size: 13px;
  color: var(--color-text-muted, #94a3b8);
}
</style>
