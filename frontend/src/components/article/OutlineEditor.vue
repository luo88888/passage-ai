<script setup lang="ts">
/**
 * 大纲编辑器（多阶段创作 - 阶段2：编辑大纲）
 *
 * 支持三种编辑方式：
 * 1. 手动编辑：章节标题/要点文本可改，章节与要点均可新增、删除
 * 2. 拖拽排序：章节、要点均支持拖拽调整顺序（vuedraggable@4）
 * 3. AI 助手：用自然语言描述修改意图，后端 AI 返回新大纲整体替换
 *
 * 数据结构（与后端 OutlineSection 对齐）：
 *   { section: number, title: string, points: string[], word_count?: number }
 *   注：后端 OutlineSection.model_dump() 无 alias，落库/SSE 下发为 snake_case word_count；
 *   提交确认时回传 wordCount(camel)，Pydantic 经 populate_by_name 兼容。
 *
 * 与父组件约定：
 *   - v-model:outline 双向同步大纲数据
 *   - v-model:aiModifying 双向同步 AI 修改 loading 态（由父组件 SSE handler 关闭）
 *   - @ai-modify 父组件据此调 aiModifyOutline（fire-and-forget），大纲由 SSE 回填
 *   - :clear-input-signal 计数器 prop，父组件 SSE 成功后 ++ 触发本组件清空建议输入
 *   - @confirm 父组件据此调用 confirmOutline 并推进到正文生成阶段
 *
 * 注：AI 修改大纲已改为 fire-and-forget + SSE（不再从 HTTP 响应取大纲）。
 */
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import draggable from 'vuedraggable'
import {
  PlusOutlined,
  DeleteOutlined,
  HolderOutlined,
  RobotOutlined,
  CheckOutlined,
  CrownOutlined,
} from '@ant-design/icons-vue'

import type { OutlineSection } from '@/utils/sse'

const router = useRouter()

const props = defineProps<{
  outline: OutlineSection[]
  taskId: string
  isVip?: boolean
  clearInputSignal?: number
}>()

// AI 修改 loading 态由父组件托管（SSE 回填后再关），通过 v-model:aiModifying 双向
const aiModifying = defineModel<boolean>('aiModifying', { default: false })

const emit = defineEmits<{
  (e: 'update:outline', outline: OutlineSection[]): void
  (e: 'ai-modify', modifySuggestion: string): void
  (e: 'confirm'): void
}>()

// ---------- 本地编辑态 ----------
// 要点改用 { id, text } 对象列表、章节附加稳定 key，供 vuedraggable item-key 做可靠 diff，
// 避免旧实现 item-key 恒为索引/占位导致拖拽后输入框内容串位、渲染错乱（P0-2）。
interface LocalPoint {
  id: string
  text: string
}
interface LocalSection {
  /** 本地稳定唯一 key（crypto.randomUUID），仅用于拖拽 diff，不上行提交 */
  key: string
  section: number
  title: string
  points: LocalPoint[]
  word_count?: number
  wordCount?: number
}

/** 生成本地稳定唯一 id（crypto.randomUUID 兜底自增） */
let localIdSeed = 0
function newLocalId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  localIdSeed += 1
  return `local_${Date.now()}_${localIdSeed}`
}

// 本地可编辑副本：通过 v-model 与父组件同步（持有稳定 key，供拖拽 diff）
const localOutline = ref<LocalSection[]>(cloneOutline(props.outline))

// 最近一次上行同步的 outline（JSON 序列化），用于区分「自身编辑回显」与「外部更新」：
// v-model:outline 会把我们的编辑原样回显给 props.outline，若此时重新 cloneOutline 会生成全新 key，
// 导致整棵 draggable 列表重建、输入框失焦（每敲一个字都要重新点击）。仅当外部更新
// （AI 修改 SSE 回填 / 断点恢复）与上次上行内容不同时才重建本地副本。
let lastEmittedOutline = ''
function serializeOutline(list: OutlineSection[]): string {
  return JSON.stringify(list || [])
}

// 父组件 outline 由外部更新时（AI 修改成功后/重连恢复时），重新同步本地副本
watch(
  () => props.outline,
  (v) => {
    if (serializeOutline(v) === lastEmittedOutline) return
    localOutline.value = cloneOutline(v)
  },
)

/** OutlineSection[] → LocalSection[]：为每个章节/要点补稳定 key */
function cloneOutline(list: OutlineSection[]): LocalSection[] {
  // 保留 word_count（SSE 下发 snake_case）与 wordCount（前端编辑写入 camel）
  return (list || []).map((s) => ({
    key: newLocalId(),
    section: s.section,
    title: s.title,
    points: (s.points || []).map((p) => ({ id: newLocalId(), text: p })),
    word_count: s.word_count ?? s.wordCount,
    wordCount: s.wordCount ?? s.word_count,
  }))
}

/** LocalSection[] → OutlineSection[]：去除本地 key，要点 map 回字符串数组 */
function toOutline(list: LocalSection[]): OutlineSection[] {
  return list.map((s) => ({
    section: s.section,
    title: s.title,
    points: s.points.map((p) => p.text),
    word_count: s.word_count ?? s.wordCount,
    wordCount: s.wordCount ?? s.word_count,
  }))
}

// 任何本地改动都同步回父组件（v-model 上行），并记录快照供回显去重
function syncUp() {
  const next = toOutline(localOutline.value)
  lastEmittedOutline = serializeOutline(next)
  emit('update:outline', next)
}

// vuedraggable 拖动结束回调：仅同步，section 编号在确认时统一重排
const onDragChange = () => syncUp()

// ==================== 手动编辑 ====================
// 新增章节：section 暂用占位（当前长度+1），确认前会统一重排为 1..n
const addSection = () => {
  localOutline.value.push({
    key: newLocalId(),
    section: localOutline.value.length + 1,
    title: '',
    points: [{ id: newLocalId(), text: '' }],
    wordCount: undefined,
  })
  syncUp()
}

// 删除章节
const removeSection = (idx: number) => {
  localOutline.value.splice(idx, 1)
  syncUp()
}

// 新增要点
const addPoint = (sIdx: number) => {
  localOutline.value[sIdx].points.push({ id: newLocalId(), text: '' })
  syncUp()
}

// 删除要点
const removePoint = (sIdx: number, pIdx: number) => {
  localOutline.value[sIdx].points.splice(pIdx, 1)
  syncUp()
}

// 输入框内容变更同步（v-model 已改本地值，这里只做上行同步）
const onFieldChange = () => syncUp()

// ==================== AI 助手修改 ====================
// AI 修改大纲为会员/管理员专属（后端 service 校验），非会员触发跳转开通页
const aiUnlocked = computed(() => props.isVip === true)
const modifySuggestion = ref('')

// 父组件 SSE 成功回填大纲后 ++ clearInputSignal，触发本组件清空建议输入
watch(
  () => props.clearInputSignal,
  () => {
    modifySuggestion.value = ''
  },
)

const aiModify = () => {
  if (!aiUnlocked.value) {
    message.warning('AI 修改大纲为会员专属功能，开通会员后可使用')
    router.push('/vip')
    return
  }
  if (!modifySuggestion.value.trim()) {
    message.warning('请输入修改建议')
    return
  }
  if (aiModifying.value) return
  // fire-and-forget：交父组件调 aiModifyOutline + 托管 loading；大纲/成功提示由 SSE 回填
  emit('ai-modify', modifySuggestion.value.trim())
}

// ==================== 确认大纲 ====================
const confirming = ref(false)

// 校验：每章标题非空、至少 1 个非空要点
const validationError = computed(() => {
  if (!localOutline.value.length) return '大纲不能为空'
  for (let i = 0; i < localOutline.value.length; i++) {
    const s = localOutline.value[i]
    if (!s.title.trim()) return `第 ${i + 1} 章标题不能为空`
    const validPoints = s.points.filter((p) => p.text.trim())
    if (!validPoints.length) return `第 ${i + 1} 章至少需要一个要点`
  }
  return ''
})

const canConfirm = computed(() => !validationError.value && !confirming.value)

const handleConfirm = () => {
  if (validationError.value) {
    message.warning(validationError.value)
    return
  }
  // 提交前统一重排 section 编号为 1..n（拖拽/增删后编号可能乱序），
  // 要点 map 回字符串数组；本地副本重挂稳定 key 供渲染
  const normalized = localOutline.value.map((s, i) => ({
    section: i + 1,
    title: s.title.trim(),
    points: s.points.map((p) => p.text.trim()).filter((p) => p),
  }))
  localOutline.value = cloneOutline(normalized)
  lastEmittedOutline = serializeOutline(normalized)
  emit('update:outline', normalized)
  confirming.value = true
  // 交给父组件：调用 confirmOutline + ensureSse + 推进到正文生成
  emit('confirm')
}

// 父组件可调用以重置确认 loading（confirmOutline 失败时）
defineExpose({
  resetConfirming: () => {
    confirming.value = false
  },
})
</script>

<template>
  <div class="outline-editor">
    <!-- 操作说明 -->
    <div class="editor-hint">
      <CheckOutlined />
      <span>大纲已生成，你可以：拖拽调整顺序、直接编辑标题与要点、或用 AI 助手自然语言修改</span>
    </div>

    <!-- 章节列表（可拖拽排序） -->
    <draggable
      v-model="localOutline"
      item-key="key"
      handle=".drag-handle"
      :animation="200"
      class="section-list"
      @change="onDragChange"
    >
      <template #item="{ element, index }">
        <div class="section-card">
          <!-- 卡片头部：拖拽手柄 + 编号 + 标题输入 + 删除 -->
          <div class="section-head">
            <span class="drag-handle" title="拖拽调整章节顺序"><HolderOutlined /></span>
            <span class="section-no">{{ index + 1 }}</span>
            <a-input
              v-model:value="element.title"
              class="section-title-input"
              placeholder="请输入章节标题"
              @change="onFieldChange"
            />
            <!-- 本章目标字数（可选，驱动正文逐章篇幅） -->
            <div class="section-word-count">
              <span class="word-label">字数</span>
              <a-input-number
                v-model:value="element.wordCount"
                class="word-input"
                :min="50"
                :max="10000"
                :step="50"
                :precision="0"
                placeholder="目标字数"
                @change="onFieldChange"
              />
            </div>
            <a-button
              type="text"
              danger
              class="section-del"
              title="删除该章节"
              @click="removeSection(index)"
            >
              <DeleteOutlined />
            </a-button>
          </div>

          <!-- 要点列表（可拖拽排序） -->
          <div class="points-area">
            <draggable
              v-model="element.points"
              item-key="id"
              handle=".point-handle"
              :animation="200"
              class="points-list"
              @change="onDragChange"
            >
              <template #item="{ element: point, index: pIdx }">
                <div class="point-row">
                  <span class="point-handle" title="拖拽调整要点顺序"><HolderOutlined /></span>
                  <span class="point-dot">•</span>
                  <a-textarea
                    v-model:value="point.text"
                    class="point-input"
                    placeholder="请输入要点"
                    :auto-size="{ minRows: 1, maxRows: 6 }"
                    @change="onFieldChange"
                  />
                  <a-button
                    type="text"
                    danger
                    class="point-del"
                    title="删除该要点"
                    @click="removePoint(index, pIdx)"
                  >
                    <DeleteOutlined />
                  </a-button>
                </div>
              </template>
            </draggable>

            <a-button type="dashed" size="small" class="add-point-btn" @click="addPoint(index)">
              <PlusOutlined /> 添加要点
            </a-button>
          </div>
        </div>
      </template>
    </draggable>

    <!-- 新增章节 -->
    <a-button type="dashed" block class="add-section-btn" @click="addSection">
      <PlusOutlined /> 新增章节
    </a-button>

    <!-- AI 助手修改 -->
    <div class="ai-assistant" :class="{ 'ai-assistant-locked': !aiUnlocked }">
      <div class="ai-head">
        <RobotOutlined />
        <span>AI 助手修改</span>
        <span v-if="!aiUnlocked" class="ai-vip-mark" @click="router.push('/vip')" title="开通会员解锁">
          <CrownOutlined /> 会员专属
        </span>
      </div>
      <a-textarea
        v-model:value="modifySuggestion"
        class="ai-input"
        :disabled="!aiUnlocked"
        :placeholder="aiUnlocked
          ? '用自然语言描述你想怎么改，如：把第三章拆成两章并加入实战案例；增加一个总结章节；语言更轻松一些'
          : 'AI 修改大纲为会员专属功能，开通会员后可使用'"
        :auto-size="{ minRows: 2, maxRows: 4 }"
        :maxlength="500"
      />
      <div class="ai-action">
        <a-button
          type="primary"
          :loading="aiModifying"
          :disabled="!aiUnlocked || !modifySuggestion.trim()"
          @click="aiModify"
        >
          <RobotOutlined v-if="!aiModifying" />
          AI 修改大纲
        </a-button>
        <span class="ai-tip">{{ aiUnlocked ? '可多次修改，每次基于当前大纲调整' : '开通会员解锁 AI 修改大纲' }}</span>
      </div>
    </div>

    <!-- 确认按钮 -->
    <div class="confirm-bar">
      <a-button
        type="primary"
        size="large"
        block
        :loading="confirming"
        :disabled="!canConfirm && !confirming"
        @click="handleConfirm"
      >
        <CheckOutlined v-if="!confirming" />
        确认大纲并生成正文
      </a-button>
      <p v-if="validationError" class="valid-tip">{{ validationError }}</p>
    </div>
  </div>
</template>

<style scoped>
.outline-editor {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.editor-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.2);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--color-primary-dark);
}
.editor-hint .anticon {
  color: var(--color-primary);
}

/* 章节列表 */
.section-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.section-card {
  background: var(--color-background-secondary);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: 14px 16px;
}
.section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.drag-handle {
  cursor: grab;
  color: var(--color-text-muted);
  font-size: 16px;
  padding: 2px;
  flex-shrink: 0;
}
.drag-handle:active {
  cursor: grabbing;
}
.section-no {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-primary);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.section-title-input {
  flex: 1;
  font-weight: 600;
}
.section-word-count {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 4px;
}
.section-word-count .word-label {
  font-size: 12px;
  color: var(--color-text-muted);
  white-space: nowrap;
}
.section-word-count .word-input {
  width: 96px;
}
.section-del {
  flex-shrink: 0;
}

/* 要点 */
.points-area {
  padding-left: 40px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.points-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.point-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.point-handle {
  cursor: grab;
  color: var(--color-text-muted);
  font-size: 13px;
  flex-shrink: 0;
}
.point-handle:active {
  cursor: grabbing;
}
.point-dot {
  color: var(--color-text-muted);
  flex-shrink: 0;
}
.point-input {
  flex: 1;
}
.point-input :deep(textarea) {
  /* 多行要点：左侧对齐基线与单行一致，自适应高度时保持紧凑行高 */
  resize: none;
}
.point-del {
  flex-shrink: 0;
}
.add-point-btn {
  align-self: flex-start;
}

/* 新增章节 */
.add-section-btn {
  height: 42px;
}

/* AI 助手 */
.ai-assistant {
  background: var(--color-background-secondary);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ai-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}
.ai-head .anticon {
  color: var(--color-primary);
}
.ai-vip-mark {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-inline-start: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #f59e0b;
  cursor: pointer;
  user-select: none;
}
.ai-vip-mark:hover {
  color: #d97706;
}
.ai-assistant-locked {
  background: rgba(245, 158, 11, 0.05);
  border-color: rgba(245, 158, 11, 0.25);
}
.ai-input {
  border-radius: var(--radius-md);
}
.ai-action {
  display: flex;
  align-items: center;
  gap: 12px;
}
.ai-tip {
  font-size: 12px;
  color: var(--color-text-muted);
}

/* 确认栏 */
.confirm-bar {
  margin-top: 4px;
}
.confirm-bar .ant-btn {
  height: 46px !important;
  font-size: 16px !important;
  font-weight: 600 !important;
  border-radius: var(--radius-md) !important;
}
.valid-tip {
  margin: 8px 0 0;
  color: var(--color-error);
  font-size: 13px;
  text-align: center;
}
</style>
