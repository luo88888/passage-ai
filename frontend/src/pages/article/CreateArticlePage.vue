<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  EditOutlined,
  ThunderboltFilled,
  CheckCircleFilled,
  LoadingOutlined,
  BulbOutlined,
  StarOutlined,
  SettingOutlined,
  CopyOutlined,
  EyeOutlined,
  ReloadOutlined,
  DownloadOutlined,
  FileTextOutlined,
  PictureOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'

import { useLoginUserStore } from '@/stores/loginUser'
import { isAdmin } from '@/utils/permission'
import {
  createArticle,
  getArticle,
  getCreationOptions,
  type CreationOptionItem,
} from '@/api/articleController'
import { subscribeArticleProgress, type SseMessage } from '@/utils/sse'
import { renderMarkdown } from '@/utils/markdown'
import { exportMarkdown, exportHtml } from '@/utils/export'

const route = useRoute()
const router = useRouter()
const loginUserStore = useLoginUserStore()

// ==================== 状态 ====================
// input 输入态 | generating 生成中（含完成）
const stage = ref<'input' | 'generating'>('input')
const topic = ref('')
const taskId = ref('')
const creating = ref(false)
const completed = ref(false)
const errorMsg = ref('')

// 文章风格 / 配图方式 可选项（由后端 /article/options 动态返回，不在前端硬编码）
// 文章风格为单选：'default' 表示"默认"项（前端写死，后端不返回，提交时映射为 style=null）。
const styleOptions = ref<CreationOptionItem[]>([])
const imageMethodOptions = ref<CreationOptionItem[]>([])
const selectedStyle = ref<string>('default')
const selectedImageMethods = ref<string[]>([])

// 时间轴当前步（0~6），每完成一个 *_COMPLETE 推进一步
const currentStep = ref(0)
interface StepMeta {
  title: string
  desc: string
  sseType: SseMessage['type']
  icon: any
}
const steps: StepMeta[] = [
  { title: '生成标题', desc: 'AI 分析选题，生成吸睛标题', sseType: 'AGENT1_COMPLETE', icon: EditOutlined },
  { title: '规划大纲', desc: '构建文章结构，理清脉络', sseType: 'AGENT2_COMPLETE', icon: FileTextOutlined },
  { title: '撰写正文', desc: 'AI 生成高质量文章内容', sseType: 'AGENT3_COMPLETE', icon: EditOutlined },
  { title: '分析配图', desc: '智能分析配图需求匹配位置', sseType: 'AGENT4_COMPLETE', icon: PictureOutlined },
  { title: '生成配图', desc: '自动生成高清无版权图片', sseType: 'AGENT5_COMPLETE', icon: PictureOutlined },
  { title: '图文合成', desc: '将配图嵌入正文，完美呈现', sseType: 'MERGE_COMPLETE', icon: ThunderboltOutlined },
]

// 流式累积内容
const titleResult = ref<{ mainTitle: string; subTitle: string } | null>(null)
const outlineRaw = ref('') // AGENT2_STREAMING 增量拼接
const outline = ref<Array<{ section: number; title: string; points: string[] }>>([])
const contentRaw = ref('') // AGENT3_STREAMING 增量拼接
const imageUrls = ref<string[]>([]) // IMAGE_COMPLETE 增量
const images = ref<Array<{ position: number; url: string; description: string }>>([]) // AGENT5_COMPLETE 全量
const fullContent = ref('') // MERGE_COMPLETE

// SSE 句柄
let sseHandle: { close: () => void } | null = null

// ==================== 计算属性 ====================
const canSubmit = computed(() => !!topic.value.trim() && !creating.value)

const wordCount = computed(() => {
  const text = fullContent.value || contentRaw.value
  return text.replace(/\s+/g, '').length
})

const imageCount = computed(() => (images.value.length ? images.value.length : imageUrls.value.length))

// 管理员标识
const isAdminUser = computed(() => isAdmin(loginUserStore.loginUser))

// 文章正文 markdown HTML
const contentHtml = computed(() => renderMarkdown(contentRaw.value))
const outlineHtml = computed(() => renderMarkdown(outlineRaw.value))

// 热门选题
const hotTopics = [
  '2026年AI如何改变职场',
  '程序员如何提升核心竞争力',
  '远程办公的利与弊',
  '副业刚需：普通人如何开启第一份收入',
  '高效学习的5个底层方法论',
  '为什么我们需要数字极简',
]

// 爆款技巧
const tips = [
  { title: '抓住痛点', desc: '直击用户最关心的问题' },
  { title: '制造反差', desc: '用颠覆认知的标题吸引点击' },
  { title: '结构清晰', desc: '小标题+要点，降低阅读门槛' },
]

// ==================== 方法 ====================
// 重置全部状态
const resetAll = () => {
  sseHandle?.close()
  sseHandle = null
  stage.value = 'input'
  taskId.value = ''
  completed.value = false
  errorMsg.value = ''
  currentStep.value = 0
  titleResult.value = null
  outlineRaw.value = ''
  outline.value = []
  contentRaw.value = ''
  imageUrls.value = []
  images.value = []
  fullContent.value = ''
}

// SSE 事件分派
const handleSse = (data: SseMessage) => {
  errorMsg.value = ''
  switch (data.type) {
    case 'AGENT1_COMPLETE':
      titleResult.value = data.titleResult || null
      currentStep.value = 1
      break
    case 'AGENT2_STREAMING':
      outlineRaw.value += data.content || ''
      break
    case 'AGENT2_COMPLETE':
      outline.value = data.outline || []
      currentStep.value = 2
      break
    case 'AGENT3_STREAMING':
      contentRaw.value += data.content || ''
      break
    case 'AGENT3_COMPLETE':
      currentStep.value = 3
      break
    case 'AGENT4_COMPLETE':
      currentStep.value = 4
      break
    case 'IMAGE_COMPLETE':
      if (data.content && !imageUrls.value.includes(data.content)) {
        imageUrls.value.push(data.content)
      }
      break
    case 'AGENT5_COMPLETE':
      if (data.images?.length) {
        images.value = data.images.map((i) => ({ position: i.position, url: i.url, description: i.description }))
      }
      currentStep.value = 5
      break
    case 'MERGE_COMPLETE':
      fullContent.value = data.fullContent || ''
      currentStep.value = 6
      break
    case 'ALL_COMPLETE':
      completed.value = true
      fetchFinalDetail()
      break
    case 'ERROR':
      errorMsg.value = data.message || '生成失败，请稍后重试'
      message.error(errorMsg.value)
      break
  }
}

// 完成后兜底拉取最终详情，确保 fullContent / images 等为落库后的最终态
const fetchFinalDetail = async () => {
  if (!taskId.value) return
  try {
    const res = await getArticle({ taskId: taskId.value })
    const a = res.data?.data
    if (a) {
      if (!fullContent.value && a.fullContent) fullContent.value = a.fullContent
      if (a.content && !contentRaw.value) contentRaw.value = a.content
      if (a.outline && !outline.value.length) outline.value = a.outline
      if (a.images && !images.value.length) images.value = a.images
      if (!titleResult.value && a.mainTitle) {
        titleResult.value = { mainTitle: a.mainTitle, subTitle: a.subTitle || '' }
      }
    }
  } catch (e) {
    // 兜底失败不影响已有 SSE 数据
    console.warn('拉取最终详情失败:', e)
  }
}

// 拉取创作页可选项（文章风格 / 配图方式）；失败不阻塞创作
const fetchCreationOptions = async () => {
  try {
    const res = await getCreationOptions()
    const data = res.data?.data
    if (res.data.code === 0 && data) {
      styleOptions.value = data.styles || []
      imageMethodOptions.value = data.imageMethods || []
    }
  } catch (e) {
    // 兜底：接口失败则不展示选项，提交时走后端默认（style=null、enabledImageMethods=null）
    console.warn('拉取创作选项失败:', e)
    styleOptions.value = []
    imageMethodOptions.value = []
  }
}

// 开始创作
const startGenerate = async () => {
  if (!topic.value.trim()) return
  resetAll()
  creating.value = true
  errorMsg.value = ''
  try {
    // style: 'default' 映射为 null（后端走通用爆款风格）；enabledImageMethods: 空数组映射为 null（全部可用）
    const style = selectedStyle.value === 'default' ? null : selectedStyle.value
    const enabledImageMethods =
      selectedImageMethods.value.length > 0 ? selectedImageMethods.value : null
    const res = await createArticle({
      topic: topic.value.trim(),
      style,
      enabledImageMethods,
    } as any)
    if (res.data.code !== 0 || !res.data.data) {
      errorMsg.value = res.data.message || '创建任务失败'
      message.error(errorMsg.value)
      return
    }
    taskId.value = res.data.data
    stage.value = 'generating'
    // 立即订阅 SSE（后端 fire-and-forget 可能已开跑，丢一两条早期事件可接受）
    sseHandle = subscribeArticleProgress(taskId.value, {
      onMessage: handleSse,
      onError: () => {
        // 连接异常且尚未完成：提示并保持在生成态，可重试
        if (!completed.value) {
          errorMsg.value = '生成进度连接中断，请稍后重试'
          message.warning(errorMsg.value)
        }
      },
    })
  } catch (e: any) {
    errorMsg.value = e?.message || '创建任务失败'
    message.error(errorMsg.value)
  } finally {
    creating.value = false
  }
}

// 选中热门选题
const pickTopic = (t: string) => {
  topic.value = t
}

// 复制全文
const copyContent = async () => {
  const text = fullContent.value || contentRaw.value
  if (!text) {
    message.warning('暂无可复制的内容')
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    message.success('已复制全文')
  } catch {
    message.error('复制失败，请手动选择复制')
  }
}

// 导出（完成态）
const doExportMd = () => {
  const name = titleResult.value?.mainTitle || topic.value
  const text = fullContent.value || contentRaw.value
  if (!text) {
    message.warning('暂无可导出的内容')
    return
  }
  exportMarkdown(name, text)
}
const doExportHtml = () => {
  const name = titleResult.value?.mainTitle || topic.value
  const text = fullContent.value || contentRaw.value
  if (!text) {
    message.warning('暂无可导出的内容')
    return
  }
  exportHtml(name, text)
}

// 查看详情
const goDetail = () => {
  if (taskId.value) router.push(`/article/${taskId.value}`)
}

// ==================== 生命周期 ====================
onMounted(() => {
  // 登录态兜底
  if (!loginUserStore.loginUser.id) {
    router.replace(`/user/login?redirect=${encodeURIComponent(route.fullPath)}`)
    return
  }
  // 支持 /create?topic= 预填
  const q = route.query.topic
  if (q && typeof q === 'string') {
    topic.value = q
  }
  // 拉取文章风格 / 配图方式可选项
  fetchCreationOptions()
})

onBeforeUnmount(() => {
  sseHandle?.close()
  sseHandle = null
})
</script>

<template>
  <div id="createArticlePage">
    <!-- 输入态：左右辅助栏隐藏，居中输入卡 -->
    <div v-if="stage === 'input'" class="layout input-layout">
      <!-- 左栏占位：输入态仅展示配额在右侧，左侧流程轴隐藏 -->
      <aside class="side-panel left-panel"></aside>

      <!-- 中栏：输入卡 -->
      <main class="main-panel">
        <div class="input-card">
          <div class="input-card-head">
            <h2 class="input-title">创作新文章</h2>
            <p class="input-subtitle">输入选题，AI 帮你生成爆款文章</p>
          </div>
          <a-textarea
            v-model:value="topic"
            class="topic-textarea"
            placeholder="请输入您想创作的文章选题，例如：2026年AI如何改变职场"
            :maxlength="500"
            show-count
            :auto-size="{ minRows: 6 }"
            @pressEnter="startGenerate"
          />
          <!-- 文章风格：单选（含"默认"，默认项提交时映射为 null） -->
          <div v-if="styleOptions.length" class="option-group">
            <div class="option-head">
              <span class="option-title">文章风格</span>
              <span class="option-hint">（可选风格，单选，默认走通用爆款风格）</span>
            </div>
            <a-radio-group v-model:value="selectedStyle" class="option-options">
              <a-radio-button value="default">默认</a-radio-button>
              <a-radio-button
                v-for="item in styleOptions"
                :key="item.value"
                :value="item.value"
              >{{ item.label }}</a-radio-button>
            </a-radio-group>
          </div>

          <!-- 配图方式：多选（不选则使用全部可用方式） -->
          <div v-if="imageMethodOptions.length" class="option-group">
            <div class="option-head">
              <span class="option-title">配图方式</span>
              <span class="option-hint">（可多选，不选则使用全部可用方式）</span>
            </div>
            <a-checkbox-group v-model:value="selectedImageMethods" class="option-options">
              <a-checkbox
                v-for="item in imageMethodOptions"
                :key="item.value"
                :value="item.value"
                class="option-check"
              >{{ item.label }}</a-checkbox>
            </a-checkbox-group>
          </div>

          <a-button
            type="primary"
            size="large"
            block
            class="start-btn"
            :disabled="!canSubmit"
            @click="startGenerate"
          >
            <ThunderboltFilled />
            开始创作
          </a-button>
          <p v-if="errorMsg" class="error-tip">{{ errorMsg }}</p>
        </div>
      </main>

      <!-- 右栏：配额 + 热门选题 + 爆款技巧 -->
      <aside class="side-panel right-panel">
        <!-- 创作配额 -->
        <div class="quota-card">
          <div class="panel-head">
            <SettingOutlined />
            <span>创作配额</span>
          </div>
          <div class="quota-body">
            <a-tag v-if="isAdminUser" color="gold" class="role-tag">管理员</a-tag>
            <span class="quota-text">暂不限制</span>
          </div>
        </div>

        <!-- 热门选题 -->
        <div class="panel-card">
          <div class="panel-head">
            <BulbOutlined />
            <span>热门选题</span>
          </div>
          <div class="topic-tags">
            <span
              v-for="t in hotTopics"
              :key="t"
              class="topic-tag"
              @click="pickTopic(t)"
            >{{ t }}</span>
          </div>
        </div>

        <!-- 爆款技巧 -->
        <div class="panel-card">
          <div class="panel-head">
            <StarOutlined />
            <span>爆款技巧</span>
          </div>
          <div class="tips-list">
            <div v-for="(tip, i) in tips" :key="i" class="tip-item">
              <div class="tip-no">{{ i + 1 }}</div>
              <div class="tip-content">
                <div class="tip-title">{{ tip.title }}</div>
                <div class="tip-desc">{{ tip.desc }}</div>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>

    <!-- 生成中/完成态：左中右三栏 -->
    <div v-else class="layout generating-layout">
      <!-- 左栏：创作流程时间轴 -->
      <aside class="side-panel left-panel">
        <div class="timeline-card">
          <div class="timeline-head">
            <h3>创作流程</h3>
            <p>智能协作可视化</p>
          </div>
          <div class="timeline">
            <div
              v-for="(step, idx) in steps"
              :key="step.title"
              class="timeline-item"
              :class="{
                done: idx < currentStep,
                active: idx === currentStep && !completed,
                'active-done': idx === currentStep && completed,
              }"
            >
              <div class="timeline-icon">
                <CheckCircleFilled v-if="idx < currentStep || (completed && idx <= currentStep)" />
                <LoadingOutlined v-else-if="idx === currentStep" />
                <span v-else class="step-no">{{ idx + 1 }}</span>
              </div>
              <div class="timeline-body">
                <div class="step-title">{{ step.title }}</div>
                <div class="step-desc">{{ step.desc }}</div>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <!-- 中栏：流式文章预览 -->
      <main class="main-panel">
        <div class="preview-card">
          <!-- 完成胶囊 -->
          <div v-if="completed" class="complete-badge">
            <CheckCircleFilled />
            <span>文章创作完成！</span>
          </div>
          <div v-if="errorMsg && !completed" class="error-banner">
            <a-alert :message="errorMsg" type="error" show-icon />
          </div>

          <!-- 标题区 -->
          <div v-if="titleResult" class="article-title-area">
            <h1 class="article-main-title">{{ titleResult.mainTitle }}</h1>
            <p class="article-sub-title">{{ titleResult.subTitle }}</p>
            <a-divider />
          </div>

          <!-- 大纲区 -->
          <section v-if="outlineRaw || outline.length" class="article-section">
            <h3 class="section-label">文章大纲</h3>
            <!-- 优先结构化大纲 -->
            <div v-if="outline.length" class="outline-struct">
              <div v-for="item in outline" :key="item.section" class="outline-block">
                <div class="outline-block-title">{{ item.section }}. {{ item.title }}</div>
                <ul class="outline-points">
                  <li v-for="(p, i) in item.points" :key="i">{{ p }}</li>
                </ul>
              </div>
            </div>
            <!-- 否则流式 markdown 预览 -->
            <div v-else class="markdown-body streaming" v-html="outlineHtml"></div>
          </section>

          <!-- 正文区 -->
          <section v-if="contentRaw" class="article-section">
            <h3 class="section-label">文章正文</h3>
            <div class="markdown-body streaming" v-html="contentHtml"></div>
          </section>

          <!-- 配图区 -->
          <section v-if="imageCount" class="article-section">
            <h3 class="section-label">配图预览</h3>
            <div class="image-gallery">
              <template v-if="images.length">
                <a-image
                  v-for="img in images"
                  :key="img.position"
                  :src="img.url"
                  class="gallery-img"
                  :preview="{ src: img.url }"
                />
              </template>
              <template v-else>
                <a-image
                  v-for="(url, i) in imageUrls"
                  :key="i"
                  :src="url"
                  class="gallery-img"
                  :preview="{ src: url }"
                />
              </template>
            </div>
          </section>

          <!-- 空态 -->
          <div v-if="!titleResult && !outlineRaw && !contentRaw && !imageCount" class="empty-streaming">
            <a-spin tip="AI 正在构思中…" />
          </div>
        </div>
      </main>

      <!-- 右栏：快捷操作 + 统计 -->
      <aside class="side-panel right-panel">
        <!-- 快捷操作 -->
        <div class="panel-card">
          <div class="panel-head">
            <ThunderboltFilled />
            <span>快捷操作</span>
          </div>
          <div class="quick-actions">
            <a-button class="action-btn" block @click="copyContent">
              <CopyOutlined /> 复制全文
            </a-button>
            <a-button class="action-btn" block :disabled="!taskId" @click="goDetail">
              <EyeOutlined /> 查看详情
            </a-button>
            <a-dropdown placement="bottomRight">
              <a-button type="primary" class="action-btn primary" block :disabled="!completed">
                <DownloadOutlined /> 导出文章
              </a-button>
              <template #overlay>
                <a-menu>
                  <a-menu-item @click="doExportMd">导出 Markdown</a-menu-item>
                  <a-menu-item @click="doExportHtml">导出 HTML</a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
            <a-button class="action-btn" block @click="resetAll">
              <ReloadOutlined /> 再创作一篇
            </a-button>
          </div>
        </div>

        <!-- 文章统计 -->
        <div class="panel-card">
          <div class="panel-head">
            <ThunderboltOutlined />
            <span>文章统计</span>
          </div>
          <div class="stats-grid">
            <div class="stat-card">
              <div class="stat-num">{{ wordCount }}</div>
              <div class="stat-label">字数</div>
            </div>
            <div class="stat-card">
              <div class="stat-num">{{ imageCount }}</div>
              <div class="stat-label">配图</div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
#createArticlePage {
  min-height: calc(100vh - 64px);
  background: var(--color-background-secondary);
  padding: 24px 20px 40px;
}

.layout {
  max-width: 1240px;
  margin: 0 auto;
  display: grid;
  gap: 20px;
  align-items: start;
}

/* 输入态：中栏居中，左右栏辅助 */
.input-layout {
  grid-template-columns: 0 1fr 300px;
}
.generating-layout {
  grid-template-columns: 240px 1fr 260px;
}

@media (max-width: 992px) {
  .input-layout {
    grid-template-columns: 1fr;
  }
  .input-layout .left-panel {
    display: none;
  }
  .generating-layout {
    grid-template-columns: 1fr;
  }
  .generating-layout .left-panel,
  .generating-layout .right-panel {
    display: none;
  }
}

/* 通用面板 */
.side-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-card,
.quota-card,
.timeline-card {
  background: var(--color-background);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 18px;
}

.panel-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 14px;
}
.panel-head .anticon {
  color: var(--color-primary);
}

/* 配额卡：绿底 */
.quota-card {
  background: rgba(34, 197, 94, 0.08);
  border-color: rgba(34, 197, 94, 0.2);
}
.quota-body {
  display: flex;
  align-items: center;
  gap: 10px;
}
.role-tag {
  margin: 0;
}
.quota-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-primary-dark);
}

/* 热门选题标签云 */
.topic-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.topic-tag {
  padding: 6px 12px;
  background: var(--color-background);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: 13px;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.topic-tag:hover {
  color: var(--color-primary-dark);
  border-color: var(--color-primary-light);
  background: rgba(34, 197, 94, 0.06);
}

/* 爆款技巧 */
.tips-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.tip-item {
  display: flex;
  gap: 10px;
  padding: 10px;
  background: var(--color-background-secondary);
  border-radius: var(--radius-md);
}
.tip-no {
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
.tip-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}
.tip-desc {
  font-size: 12px;
  color: var(--color-text-muted);
}

/* 中栏输入卡 */
.input-card {
  background: var(--color-background);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: 36px;
  box-shadow: var(--shadow-card);
}
.input-card-head {
  text-align: center;
  margin-bottom: 24px;
}
.input-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 8px;
}
.input-subtitle {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
}
.topic-textarea {
  border-radius: var(--radius-md);
  font-size: 15px;
  resize: none;
}
.start-btn {
  margin-top: 18px;
  height: 46px !important;
  font-size: 16px !important;
  font-weight: 600 !important;
  border-radius: var(--radius-md) !important;
}
.error-tip {
  margin: 12px 0 0;
  color: var(--color-error);
  font-size: 13px;
  text-align: center;
}

/* 文章风格 / 配图方式 选项 */
.option-group {
  margin-top: 20px;
}
.option-head {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: 10px;
}
.option-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
}
.option-hint {
  font-size: 12px;
  color: var(--color-text-muted);
}
.option-options {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.option-check {
  margin-inline-start: 0 !important;
}

/* 风格单选胶囊：选中态为绿色背景白字，贴合参考图 */
:deep(.ant-radio-button-wrapper) {
  border-radius: var(--radius-full) !important;
  border-color: var(--color-border) !important;
  color: var(--color-text-secondary) !important;
}
:deep(.ant-radio-button-wrapper:not(:first-child)) {
  /* 圆角胶囊视觉不连缀，去掉左侧直角叠加 */
  border-inline-start: 1px solid var(--color-border) !important;
}
:deep(.ant-radio-button-wrapper-checked) {
  background: var(--color-primary) !important;
  border-color: var(--color-primary) !important;
  color: #fff !important;
  box-shadow: none !important;
}
:deep(.ant-radio-button-wrapper-checked)::before {
  background: var(--color-primary) !important;
}
:deep(.ant-radio-button-wrapper:hover) {
  color: var(--color-primary-dark) !important;
  border-color: var(--color-primary-light) !important;
}
:deep(.ant-radio-button-wrapper-checked:hover) {
  color: #fff !important;
}

/* 时间轴 */
.timeline-head h3 {
  font-size: 16px;
  font-weight: 700;
  margin: 0;
}
.timeline-head p {
  font-size: 12px;
  color: var(--color-text-muted);
  margin: 2px 0 16px;
}
.timeline {
  display: flex;
  flex-direction: column;
}
.timeline-item {
  display: flex;
  gap: 12px;
  padding-bottom: 20px;
  position: relative;
}
.timeline-item:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 15px;
  top: 32px;
  bottom: 0;
  width: 2px;
  background: var(--color-border);
}
.timeline-item.done:not(:last-child)::before,
.timeline-item.active-done:not(:last-child)::before {
  background: var(--color-primary);
}
.timeline-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--color-background-tertiary);
  color: var(--color-text-muted);
  font-size: 16px;
  z-index: 1;
}
.timeline-item.done .timeline-icon,
.timeline-item.active-done .timeline-icon {
  background: var(--color-primary);
  color: #fff;
}
.timeline-item.active .timeline-icon {
  background: var(--color-primary);
  color: #fff;
}
.step-no {
  font-size: 14px;
  font-weight: 600;
}
.step-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 2px;
}
.timeline-item.active .step-title {
  color: var(--color-primary-dark);
}
.step-desc {
  font-size: 12px;
  color: var(--color-text-muted);
}

/* 预览卡 */
.preview-card {
  background: var(--color-background);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: 32px;
  min-height: 60vh;
}
.complete-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 18px;
  background: var(--color-primary);
  color: #fff;
  border-radius: var(--radius-full);
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 20px;
  box-shadow: var(--shadow-green);
}
.error-banner {
  margin-bottom: 16px;
}
.article-title-area {
  text-align: center;
  margin-bottom: 8px;
}
.article-main-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 8px;
}
.article-sub-title {
  font-size: 15px;
  color: var(--color-text-secondary);
  margin: 0;
}
.article-section {
  margin-top: 24px;
}
.section-label {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 12px;
  padding-left: 10px;
  border-left: 4px solid var(--color-primary);
}
/* 结构化大纲 */
.outline-struct {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.outline-block {
  background: var(--color-background-secondary);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: 14px 16px;
}
.outline-block-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 8px;
}
.outline-points {
  margin: 0;
  padding-left: 20px;
  color: var(--color-text-secondary);
  font-size: 14px;
  line-height: 1.8;
}
.outline-points li {
  margin-bottom: 4px;
}
/* markdown 正文 */
.markdown-body {
  color: var(--color-text);
  font-size: 15px;
  line-height: 1.9;
}
.markdown-body.streaming::after {
  content: '▍';
  color: var(--color-primary);
  animation: blink 1s steps(2) infinite;
}
@keyframes blink {
  to {
    opacity: 0;
  }
}
/* 配图 */
.image-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}
.gallery-img {
  width: 100%;
  height: 120px;
  object-fit: cover;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
}
.empty-streaming {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
}

/* 快捷操作 */
.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.action-btn {
  height: 38px !important;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: var(--radius-md) !important;
}
.action-btn.primary {
  background: var(--gradient-primary) !important;
  border: none !important;
  color: #fff !important;
  font-weight: 600 !important;
}

/* 统计 */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.stat-card {
  background: var(--color-background-secondary);
  border-radius: var(--radius-md);
  padding: 14px;
  text-align: center;
}
.stat-num {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-primary-dark);
}
.stat-label {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

/* markdown 正文深度样式 */
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 18px 0 10px;
  font-weight: 700;
}
.markdown-body :deep(p) {
  margin: 10px 0;
}
.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: var(--radius-md);
  margin: 12px 0;
}
.markdown-body :deep(pre) {
  background: var(--color-background-tertiary);
  padding: 12px 14px;
  border-radius: var(--radius-md);
  overflow: auto;
}
.markdown-body :deep(code) {
  background: var(--color-background-tertiary);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.9em;
}
.markdown-body :deep(blockquote) {
  border-left: 4px solid var(--color-primary);
  margin: 12px 0;
  padding: 6px 14px;
  color: var(--color-text-secondary);
  background: var(--color-background-secondary);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
}
</style>