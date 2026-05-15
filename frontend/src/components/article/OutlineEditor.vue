<script setup lang="ts">
/**
 * 大纲编辑器（多阶段创作 - 阶段2：编辑大纲）
 *
 * 支持三种编辑方式：
 * 1. 手动编辑：章节标题/要点文本可改，章节与要点均可新增、删除
 * 2. 拖拽排序：章节、要点均支持拖拽调整顺序（vuedraggable@4）
 * 3. AI 助手：用自然语言描述修改意图，后端 AI 返回新大纲整体替换
 *
 * 数据结构（与后端 OutlineSection 对齐，snake_case）：
 *   { section: number, title: string, points: string[] }
 *
 * 与父组件约定：
 *   - v-model:outline 双向同步大纲数据
 *   - @confirm 父组件据此调用 confirmOutline 并推进到正文生成阶段
 *   - AI 修改在本组件内调用 aiModifyOutline（需 taskId），成功后整体替换本地大纲
 */
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import draggable from 'vuedraggable'
import {
  PlusOutlined,
  DeleteOutlined,
  HolderOutlined,
  RobotOutlined,
  CheckOutlined,
} from '@ant-design/icons-vue'

import { aiModifyOutline } from '@/api/articleController'
import type { OutlineSection } from '@/utils/sse'

const props = defineProps<{
  outline: OutlineSection[]
  taskId: string
}>()

const emit = defineEmits<{
  (e: 'update:outline', outline: OutlineSection[]): void
  (e: 'confirm'): void
}>()

// 本地可编辑副本：通过 v-model 与父组件同步
const localOutline = ref<OutlineSection[]>(cloneOutline(props.outline))

function cloneOutline(list: OutlineSection[]): OutlineSection[] {
  return (list || []).map((s) => ({ section: s.section, title: s.title, points: [...(s.points || [])] }))
}

// 任何本地改动都同步回父组件（v-model 上行）
function syncUp() {
  emit('update:outline', cloneOutline(localOutline.value))
}

// vuedraggable 拖动结束回调：仅同步，section 编号在确认时统一重排
const onDragChange = () => syncUp()

// ==================== 手动编辑 ====================
// 新增章节：section 暂用占位（当前长度+1），确认前会统一重排为 1..n
const addSection = () => {
  localOutline.value.push({
    section: localOutline.value.length + 1,
    title: '',
    points: [''],
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
  localOutline.value[sIdx].points.push('')
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
const modifySuggestion = ref('')
const aiModifying = ref(false)

const aiModify = async () => {
  if (!modifySuggestion.value.trim()) {
    message.warning('请输入修改建议')
    return
  }
  aiModifying.value = true
  try {
    const res = await aiModifyOutline({
      taskId: props.taskId,
      modifySuggestion: modifySuggestion.value.trim(),
    } as any)
    if (res.data.code !== 0 || !res.data.data) {
      message.error(res.data.message || 'AI 修改大纲失败')
      return
    }
    // 后端返回 snake_case 大纲数组，整体替换本地
    const newOutline = (res.data.data as any[]).map((s) => ({
      section: Number(s.section),
      title: String(s.title || ''),
      points: Array.isArray(s.points) ? s.points.map(String) : [],
    })) as OutlineSection[]
    localOutline.value = newOutline
    syncUp()
    modifySuggestion.value = ''
    message.success('大纲已更新')
  } catch (e: any) {
    message.error(e?.message || 'AI 修改大纲失败')
  } finally {
    aiModifying.value = false
  }
}

// ==================== 确认大纲 ====================
const confirming = ref(false)

// 校验：每章标题非空、至少 1 个非空要点
const validationError = computed(() => {
  if (!localOutline.value.length) return '大纲不能为空'
  for (let i = 0; i < localOutline.value.length; i++) {
    const s = localOutline.value[i]
    if (!s.title.trim()) return `第 ${i + 1} 章标题不能为空`
    const validPoints = s.points.filter((p) => p.trim())
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
  // 提交前统一重排 section 编号为 1..n（拖拽/增删后编号可能乱序）
  const normalized = localOutline.value.map((s, i) => ({
    section: i + 1,
    title: s.title.trim(),
    points: s.points.map((p) => p.trim()).filter((p) => p),
  }))
  localOutline.value = normalized
  syncUp()
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
      item-key="section"
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
              item-key="idx"
              handle=".point-handle"
              :animation="200"
              class="points-list"
              @change="onDragChange"
            >
              <template #item="{ element: point, index: pIdx }">
                <div class="point-row">
                  <span class="point-handle" title="拖拽调整要点顺序"><HolderOutlined /></span>
                  <span class="point-dot">•</span>
                  <a-input
                    v-model:value="element.points[pIdx]"
                    class="point-input"
                    placeholder="请输入要点"
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
    <div class="ai-assistant">
      <div class="ai-head">
        <RobotOutlined />
        <span>AI 助手修改</span>
      </div>
      <a-textarea
        v-model:value="modifySuggestion"
        class="ai-input"
        placeholder="用自然语言描述你想怎么改，如：把第三章拆成两章并加入实战案例；增加一个总结章节；语言更轻松一些"
        :auto-size="{ minRows: 2, maxRows: 4 }"
        :maxlength="500"
      />
      <div class="ai-action">
        <a-button
          type="primary"
          :loading="aiModifying"
          :disabled="!modifySuggestion.trim()"
          @click="aiModify"
        >
          <RobotOutlined v-if="!aiModifying" />
          AI 修改大纲
        </a-button>
        <span class="ai-tip">可多次修改，每次基于当前大纲调整</span>
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
