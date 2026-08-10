<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
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
  CheckOutlined,
  CrownOutlined,
  WalletOutlined,
  WarningOutlined,
} from '@ant-design/icons-vue'

import { useLoginUserStore } from '@/stores/loginUser'
import { isAdmin, isVip } from '@/utils/permission'
import {
  createArticle,
  getArticle,
  confirmTitle,
  confirmOutline,
  aiModifyOutline,
  getCreationOptions,
  type CreationOptionItem,
} from '@/api/articleController'
import { subscribeArticleProgress, type SseMessage, type OutlineSection, type TitleOption, type ResearchData } from '@/utils/sse'
import { getPointsBalance, checkin as pointsCheckin } from '@/api/pointsController.ts'
import { renderMarkdown } from '@/utils/markdown'
import { exportMarkdown, exportHtml } from '@/utils/export'
import OutlineEditor from '@/components/article/OutlineEditor.vue'
import ResearchPanel from '@/components/article/ResearchPanel.vue'

const route = useRoute()
const router = useRouter()
const loginUserStore = useLoginUserStore()

// ==================== 状态 ====================
// 多阶段状态机（对应后端 ArticlePhaseEnum + status）：
//   input       选题输入
//   titleSelect 阶段1完成，展示标题候选供用户选择
//   outlineEdit 阶段2完成，展示大纲编辑器
//   generating  阶段3进行中，流式预览正文/配图
//   done        全部完成
type Stage = 'input' | 'titleSelect' | 'outlineEdit' | 'generating' | 'done'
const stage = ref<Stage>('input')
const topic = ref('')
const taskId = ref('')
const creating = ref(false)
const completed = ref(false)
const errorMsg = ref('')
// 信息采集结果（数据采集可视化）：RESEARCH_COMPLETE 到达后回填；新闻题材且未完成时 loading
const researchData = ref<ResearchData | null>(null)
const researchLoading = ref(false)

// 题材 / 语言风格 / 配图方式 可选项（由后端 /article/options 动态返回，不在前端硬编码）
// 题材 / 语言风格均为单选：'default' 表示"默认"项（前端写死，后端不返回，提交时映射为 null）。
const genreOptions = ref<CreationOptionItem[]>([])
const languageStyleOptions = ref<CreationOptionItem[]>([])
const imageMethodOptions = ref<CreationOptionItem[]>([])
const selectedGenre = ref<string>('default')
const selectedLanguageStyle = ref<string>('default')
const selectedImageMethods = ref<string[]>([])
// 目标字数：默认 2000，范围 200~10000，为空走后端默认
const DEFAULT_WORD_COUNT = 2000
const targetWordCount = ref<number>(DEFAULT_WORD_COUNT)

// 标题候选阶段数据
const titleOptions = ref<TitleOption[]>([])
// selectedTitleIdx：选中的候选索引，或 'custom' 表示自定义标题
const selectedTitleIdx = ref<number | 'custom'>(0)
const customMainTitle = ref('')
const customSubTitle = ref('')
const userDescription = ref('') // 补充描述：随确认标题提交，影响大纲生成侧重点
const confirmingTitle = ref(false)

// 大纲编辑阶段数据（与 OutlineEditor v-model 双向同步）
const outline = ref<OutlineSection[]>([])
const confirmingOutline = ref(false)
const outlineEditorRef = ref<InstanceType<typeof OutlineEditor> | null>(null)
// AI 修改大纲：fire-and-forget + SSE 回填，loading 与清空信号由本页托管下放给子组件
const aiModifying = ref(false)
const aiClearInputSignal = ref(0)

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
const outlineRaw = ref('') // AGENT2_STREAMING 增量拼接（大纲生成中的流式预览）
const contentRaw = ref('') // AGENT3_STREAMING 增量拼接
const imageUrls = ref<string[]>([]) // IMAGE_COMPLETE 增量（解析 ImageResult JSON 取 url）
const images = ref<Array<{ position: number; url: string; description: string }>>([]) // AGENT5_COMPLETE 全量
const fullContent = ref('') // MERGE_COMPLETE

// SSE 句柄
let sseHandle: { close: () => void; getLastSeq: () => number } | null = null
// 本会话已收到的最近 SSE 事件序号（断线重连时 after=lastSeq 续传，避免重复追加）
let lastSseSeq = 0
// 订阅起点：不重放历史、仅接实时流（用于页面上已有当前状态、仅需续接新事件的场景）
const NO_REPLAY_AFTER = Number.MAX_SAFE_INTEGER
// 是否处于「详情页 → 去创作页观察进度」的恢复态（顶部展示恢复提示条）
const isRecovering = ref(false)
// SSE 断线重连：指数退避（1s/2s/4s/8s/16s/30s 封顶），最多 5 次后停止并给出手动重连入口（P1-5）
const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_BACKOFF = [1000, 2000, 4000, 8000, 16000, 30000]
let reconnectAttempt = 0
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
const sseInterrupted = ref(false) // 重连耗尽：展示「点击重连」按钮

// ==================== 计算属性 ====================
const canSubmit = computed(() => !!topic.value.trim() && !creating.value)

const wordCount = computed(() => {
  const text = fullContent.value || contentRaw.value
  return text.replace(/\s+/g, '').length
})

const imageCount = computed(() => (images.value.length ? images.value.length : imageUrls.value.length))

// 管理员标识
const isAdminUser = computed(() => isAdmin(loginUserStore.loginUser))

// 会员标识（VIP 或管理员均享受会员权益，后端 _is_vip_or_admin 同口径）
const isVipUser = computed(() => isVip(loginUserStore.loginUser))

// 判断某配图方式是否对该用户锁定：vipOnly 且非会员时为不可选
const isImageMethodLocked = (item: CreationOptionItem) => !!item.vipOnly && !isVipUser.value

// ==================== 积分卡（M5） ====================
// 积分余额（/points/balance；后端创建闸门：balance >= 0，admin 豁免）
const pointsBalance = ref<number | null>(null)
const pointsLoading = ref(false)

// 进行中任务数（登录用户信息已带）
const activeTaskCount = computed(() => loginUserStore.loginUser.activeTaskCount ?? 0)

// 是否为新闻题材（触发信息采集，消耗更大）
const isNewsGenre = computed(() => selectedGenre.value === 'news')

// 预标题阶段：尚未产出标题/大纲/正文/配图（「生成中」视图空态细分用）
const isPreTitlePhase = computed(
  () => stage.value === 'generating' && !titleResult.value && !outlineRaw.value && !contentRaw.value && !imageCount.value
)

// 「生成中」空态文案：预标题阶段细分「标题生成中」与新闻题材「采集中」
const emptyStreamingTip = computed(() => {
  if (isNewsGenre.value && researchLoading.value) return '正在采集新闻资讯并生成标题方案…'
  if (isPreTitlePhase.value) return 'AI 正在生成标题方案…'
  return 'AI 正在构思中…'
})

// 本单预计消耗：新闻题材固定 120 积分（含信息采集成本）；其余按目标字数粗略估算（约 6 积分/千字，含标题/大纲/正文输入+输出），实际以后端用量结算为准
const estimateCost = computed(() => {
  if (isNewsGenre.value) return 120
  const wc = targetWordCount.value || DEFAULT_WORD_COUNT
  return Math.max(1, Math.ceil((wc * 6) / 1000))
})

// 是否欠费（admin 豁免）
const isDebt = computed(() => {
  if (isAdminUser.value) return false
  return (pointsBalance.value ?? 0) < 0
})

// 是否允许创建（后端口径 balance >= 0；admin 豁免）
const hasPoints = computed(() => isAdminUser.value || (pointsBalance.value ?? 0) >= 0)

// 拉取积分余额
const fetchPointsBalance = async () => {
  if (!loginUserStore.loginUser.id) return
  pointsLoading.value = true
  try {
    const res = await getPointsBalance()
    if (res.data.code === 0 && res.data.data) {
      pointsBalance.value = res.data.data.balance ?? 0
    }
  } catch (e) {
    // 未登录/网络异常静默处理
  } finally {
    pointsLoading.value = false
  }
}

// 积分不足/欠费引导签到弹窗
const showPointsGuide = (debt: number) => {
  Modal.confirm({
    title: '积分不足',
    content: `当前欠费 ${debt} 积分，请先签到（每日 +10 积分）还清欠款后再创作。`,
    okText: '立即签到',
    cancelText: '稍后再说',
    onOk: async () => {
      try {
        const res = await pointsCheckin()
        if (res.data.code === 0 && res.data.data) {
          message.success(`签到成功，+${res.data.data.gained} 积分`)
          await fetchPointsBalance()
          await loginUserStore.fetchLoginUser()
        } else {
          message.error(res.data.message || '签到失败')
        }
      } catch (e: any) {
        message.error(e?.message || '签到失败')
      }
    },
  })
}

// 文章正文 markdown HTML（流式期间节流渲染：约每 100ms 刷新一次 + 尾缘兜底，
// 避免每帧对整篇 markdown 全量 marked.parse + DOMPurify 造成主线程卡顿，同时保证流式输出连续可见，P1-6）
const contentHtml = ref('')
const outlineHtml = ref('')
let renderTimer: ReturnType<typeof setTimeout> | null = null
let lastRenderAt = 0
const RENDER_THROTTLE_MS = 100
function renderStreamingMarkdown() {
  contentHtml.value = renderMarkdown(contentRaw.value)
  outlineHtml.value = renderMarkdown(outlineRaw.value)
}
watch([contentRaw, outlineRaw], () => {
  const now = Date.now()
  const elapsed = now - lastRenderAt
  if (elapsed >= RENDER_THROTTLE_MS) {
    // 距上次渲染已超过节流窗口：立即渲染（流式过程中约每 100ms 刷新一次，正文保持打字机式输出）
    lastRenderAt = now
    renderStreamingMarkdown()
    return
  }
  // 窗口内到达的帧：合并，仅调度一次尾缘渲染（捕捉停止前最后一段增量）
  if (renderTimer) return
  renderTimer = setTimeout(() => {
    renderTimer = null
    lastRenderAt = Date.now()
    renderStreamingMarkdown()
  }, RENDER_THROTTLE_MS - elapsed)
})

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
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  reconnectAttempt = 0
  sseInterrupted.value = false
  stage.value = 'input'
  taskId.value = ''
  completed.value = false
  errorMsg.value = ''
  currentStep.value = 0
  titleResult.value = null
  titleOptions.value = []
  selectedTitleIdx.value = 0
  customMainTitle.value = ''
  customSubTitle.value = ''
  userDescription.value = ''
  confirmingTitle.value = false
  outline.value = []
  confirmingOutline.value = false
  outlineRaw.value = ''
  contentRaw.value = ''
  imageUrls.value = []
  images.value = []
  fullContent.value = ''
  researchData.value = null
  researchLoading.value = false
  lastSseSeq = 0
  isRecovering.value = false
  // 重置新输入控件（保留用户已选题材/语言风格/字数，便于连续创作同类型）
  // —— 这里不重置 selectedGenre/selectedLanguageStyle/wordCount，让用户改字段后点"再创作一篇"即可继续用
}

// 订阅 SSE（若尚未订阅）。跨阶段复用同一条连接，避免重复订阅。
// 断连后 sseHandle 会被置空并自动延迟重连一次，确保多阶段长连接在抖动后自愈。
// after: 订阅起点序号——0=全量重放（首次进入/新建任务）；lastSseSeq=断线续传；NO_REPLAY_AFTER=仅实时续接
const ensureSse = (after: number = 0) => {
  if (sseHandle || !taskId.value) return
  sseHandle = subscribeArticleProgress(
    taskId.value,
    {
      onMessage: (data) => {
        // 收到消息说明连接已恢复：重置重连计数与中断提示
        reconnectAttempt = 0
        sseInterrupted.value = false
        // 记录最近事件序号，供断线重连 after=lastSeq 续传
        const seq = sseHandle?.getLastSeq() ?? 0
        if (seq > lastSseSeq) lastSseSeq = seq
        handleSse(data)
        // 重连成功后若任务已终态（ALL_COMPLETE/ERROR 可能已错过），兜底拉取最终详情
        if (completed.value || stage.value === 'done') {
          fetchFinalDetail()
        }
      },
      onError: () => {
        // 连接断开：置空句柄以便可重连；未到终态时按指数退避自动重连（最多 5 次）
        sseHandle = null
        if (completed.value || stage.value === 'done') return
        if (reconnectAttempt >= MAX_RECONNECT_ATTEMPTS) {
          // 重连耗尽：停止自动重连，展示「点击重连」入口，避免后端故障时持续打请求
          sseInterrupted.value = true
          errorMsg.value = '生成进度连接中断，请点击下方按钮重连'
          return
        }
        const delay = RECONNECT_BACKOFF[reconnectAttempt] ?? RECONNECT_BACKOFF[RECONNECT_BACKOFF.length - 1]
        reconnectAttempt += 1
        errorMsg.value = `生成进度连接中断，${Math.round(delay / 1000)}s 后自动重连…`
        // 延迟重连：携带 after=lastSseSeq 续传，避免重复追加已收到的流式片段
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null
          ensureSse(lastSseSeq)
        }, delay)
      },
    },
    { after }
  )
}

// 手动重连（重试耗尽后的按钮入口）：重置计数后按 lastSseSeq 续传重新订阅
const manualReconnect = () => {
  reconnectAttempt = 0
  sseInterrupted.value = false
  errorMsg.value = ''
  ensureSse(lastSseSeq)
}

// SSE 事件分派（多阶段）
const handleSse = (data: SseMessage) => {
  errorMsg.value = ''
  switch (data.type) {
    case 'RESEARCH_COMPLETE':
      // 信息采集完成（新闻题材）：结构化结果回填采集面板，不影响阶段（标题随后仍点火）
      if (data.searchQueriesUsed?.length || data.articles?.length) {
        researchData.value = {
          searchQueriesUsed: data.searchQueriesUsed || [],
          articles: data.articles || [],
        }
      }
      researchLoading.value = false
      if (typeof data.count === 'number' && data.count > 0) {
        message.info(`信息采集完成，已收集 ${data.count} 条相关新闻`)
      }
      break
    case 'AGENT1_COMPLETE':
      // 兼容性兜底：部分实现可能仅发 AGENT1_COMPLETE，提前拿到候选
      if (data.titleOptions?.length) titleOptions.value = data.titleOptions
      currentStep.value = 1
      break
    case 'TITLE_GENERATED':
      // 阶段1结束：标题候选就绪，切到选标题 UI（不关流，等用户确认后继续 phase2）
      if (data.titleOptions?.length) titleOptions.value = data.titleOptions
      selectedTitleIdx.value = 0
      currentStep.value = 1
      stage.value = 'titleSelect'
      break
    case 'AGENT2_STREAMING':
      outlineRaw.value += data.content || ''
      break
    case 'AGENT2_COMPLETE':
      if (data.outline?.length) outline.value = data.outline
      currentStep.value = 2
      break
    case 'OUTLINE_GENERATED':
      // 阶段2结束：大纲就绪，切到编辑大纲 UI（不关流，等用户确认后继续 phase3）
      if (data.outline?.length) outline.value = data.outline
      outlineRaw.value = ''
      currentStep.value = 2
      stage.value = 'outlineEdit'
      break
    case 'AGENT3_STREAMING':
      contentRaw.value += data.content || ''
      stage.value = 'generating'
      break
    case 'AGENT3_COMPLETE':
      stage.value = 'generating'
      currentStep.value = 3
      break
    case 'AGENT4_COMPLETE':
      currentStep.value = 4
      break
    case 'IMAGE_COMPLETE':
      // content 是 ImageResult 的 JSON 字符串，解析取 url
      if (data.content) {
        try {
          const img = JSON.parse(data.content)
          if (img?.url && !imageUrls.value.includes(img.url)) {
            imageUrls.value.push(img.url)
          }
        } catch {
          // 兼容旧实现：content 直接是 URL
          if (!imageUrls.value.includes(data.content)) imageUrls.value.push(data.content)
        }
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
      stage.value = 'done'
      isRecovering.value = false
      fetchFinalDetail()
      break
    case 'AI_MODIFY_OUTLINE_COMPLETE':
      // AI 修改大纲成功：SSE 回填新大纲，关 loading + 清空输入提示
      if (data.outline?.length) outline.value = data.outline
      aiModifying.value = false
      aiClearInputSignal.value++
      message.success('大纲已更新')
      break
    case 'AI_MODIFY_OUTLINE_FAILED':
      // AI 修改大纲失败：关 loading，提示错误（文章不标 FAILED，可继续）
      aiModifying.value = false
      errorMsg.value = data.message || 'AI 修改大纲失败'
      message.error(errorMsg.value)
      break
    case 'ERROR':
      errorMsg.value = data.message || '生成失败，请稍后重试'
      message.error(errorMsg.value)
      // 积分相关错误（透支/欠费）→ 引导签到
      if (/(积分|欠费|透支)/.test(errorMsg.value)) {
        showPointsGuide(-(pointsBalance.value ?? 0))
      }
      isRecovering.value = false
      break
  }
}

// 完成后兜底拉取最终详情，确保 fullContent / images 等为落库后的最终态
const fetchFinalDetail = async () => {
  if (!taskId.value) return
  try {
    const res = await getArticle({ taskId: taskId.value } as any)
    const a = res.data?.data
    if (a) {
      if (!fullContent.value && a.fullContent) fullContent.value = a.fullContent
      if (a.content && !contentRaw.value) contentRaw.value = a.content
      if (a.outline && !outline.value.length) outline.value = a.outline as OutlineSection[]
      if (a.images && !images.value.length) {
        images.value = (a.images as any[]).map((i) => ({ position: i.position, url: i.url, description: i.description }))
      }
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
      genreOptions.value = data.genres || []
      languageStyleOptions.value = data.languageStyles || []
      imageMethodOptions.value = data.imageMethods || []
    }
  } catch (e) {
    // 兜底：接口失败则不展示选项，提交时走后端默认（genre=null、languageStyle=null、enabledImageMethods=null）
    console.warn('拉取创作选项失败:', e)
    genreOptions.value = []
    languageStyleOptions.value = []
    imageMethodOptions.value = []
  }
}

// 开始创作
const startGenerate = async () => {
  if (!topic.value.trim()) return
  if (!hasPoints.value) {
    showPointsGuide(-(pointsBalance.value ?? 0))
    return
  }
  resetAll()
  creating.value = true
  errorMsg.value = ''
  try {
    // 题材/语言风格: 'default' 映射为 null（走后端通用基调）；字数兜底到默认 2000；enabledImageMethods: 空数组映射为 null（全部可用）
    const genre = selectedGenre.value === 'default' ? null : selectedGenre.value
    const languageStyle = selectedLanguageStyle.value === 'default' ? null : selectedLanguageStyle.value
    const wc = targetWordCount.value ? targetWordCount.value : undefined
    // 过滤掉对当前用户锁定的会员专属配图方式，避免误提交后被后端拦截
    const allowedMethods = selectedImageMethods.value.filter(
      (m) => !imageMethodOptions.value.find((o) => o.value === m)?.vipOnly || isVipUser.value
    )
    const enabledImageMethods = allowedMethods.length > 0 ? allowedMethods : null
    const res = await createArticle({
      topic: topic.value.trim(),
      genre,
      languageStyle,
      wordCount: wc,
      enabledImageMethods,
    } as any)
    if (res.data.code !== 0 || !res.data.data) {
      // 创建失败：回退输入态并展示错误，避免出现「无任务可看的创作页」
      stage.value = 'input'
      errorMsg.value = res.data.message || '创建任务失败'
      message.error(errorMsg.value)
      if (/(积分|欠费|透支)/.test(errorMsg.value)) {
        showPointsGuide(-(pointsBalance.value ?? 0))
      }
      return
    }
    taskId.value = res.data.data
    // 点击「开始创作」立即进入三栏创作视图（时间轴第 1 步「生成标题」高亮），
    // 不再等待 TITLE_GENERATED；标题生成 / 信息采集在后台推进，SSE 接续到「选标题」
    stage.value = 'generating'
    currentStep.value = 0
    // 新闻题材：采集完成前展示「信息采集中…」占位（ResearchPanel loading）
    researchLoading.value = isNewsGenre.value
    ensureSse()
  } catch (e: any) {
    // 创建失败：回退输入态并展示错误
    stage.value = 'input'
    errorMsg.value = e?.message || '创建任务失败'
    message.error(errorMsg.value)
  } finally {
    creating.value = false
  }
}

// 确认标题：调 confirm-title，触发后端 phase2（生成大纲）
const confirmTitleSelection = async () => {
  // 确定选中的主/副标题
  let mainTitle = ''
  let subTitle = ''
  if (selectedTitleIdx.value === 'custom') {
    mainTitle = customMainTitle.value.trim()
    subTitle = customSubTitle.value.trim()
    if (!mainTitle) {
      message.warning('请输入自定义主标题')
      return
    }
  } else {
    const opt = titleOptions.value[selectedTitleIdx.value]
    if (!opt) {
      message.warning('请选择一个标题方案')
      return
    }
    mainTitle = opt.mainTitle
    subTitle = opt.subTitle
  }

  confirmingTitle.value = true
  errorMsg.value = ''
  try {
    const res = await confirmTitle({
      taskId: taskId.value,
      selectedMainTitle: mainTitle,
      selectedSubTitle: subTitle,
      userDescription: userDescription.value.trim() || undefined,
    } as any)
    if (res.data.code !== 0) {
      errorMsg.value = res.data.message || '确认标题失败'
      message.error(errorMsg.value)
      return
    }
    // 记录已选标题用于后续展示
    titleResult.value = { mainTitle, subTitle }
    // 切到大纲编辑阶段；phase2 异步开始，SSE 继续推 AGENT2_STREAMING / OUTLINE_GENERATED
    // 先进入 outlineEdit（展示"大纲生成中"占位），OUTLINE_GENERATED 到来后填充大纲
    outlineRaw.value = ''
    outline.value = []
    stage.value = 'outlineEdit'
    // 续接实时流：仅订阅新事件（本页已有当前状态，不重放历史，避免阶段回跳）
    ensureSse(lastSseSeq > 0 ? lastSseSeq : NO_REPLAY_AFTER)
  } catch (e: any) {
    errorMsg.value = e?.message || '确认标题失败'
    message.error(errorMsg.value)
  } finally {
    confirmingTitle.value = false
  }
}

// AI 修改大纲：fire-and-forget 注入 modify_suggestion，由 graph 节点跑 LLM + 落库 + SSE 回填
const onAiModify = async (modifySuggestion: string) => {
  if (aiModifying.value || !taskId.value) return
  aiModifying.value = true
  errorMsg.value = ''
  // 确保此时 SSE 仍连着（大纲编辑阶段不关流，但断点续作场景下可能未连）
  // 续接实时流：仅订阅新事件（本页已有当前状态，不重放历史，避免阶段回跳）
  ensureSse(lastSseSeq > 0 ? lastSseSeq : NO_REPLAY_AFTER)
  try {
    const res = await aiModifyOutline({
      taskId: taskId.value,
      modifySuggestion,
    } as any)
    if (res.data.code !== 0) {
      // 路由层校验失败（如非 VIP / 阶段不符）：直接关 loading 并提示
      aiModifying.value = false
      errorMsg.value = res.data.message || 'AI 修改大纲失败'
      message.error(errorMsg.value)
    }
    // 成功：应答只回 ack，大纲/成功提示由 SSE AI_MODIFY_OUTLINE_COMPLETE 回填
  } catch (e: any) {
    aiModifying.value = false
    errorMsg.value = e?.message || 'AI 修改大纲失败'
    message.error(errorMsg.value)
  }
}

// 大纲编辑器确认：调 confirm-outline，触发后端 phase3（生成正文+配图）
const onOutlineConfirm = async () => {
  confirmingOutline.value = true
  errorMsg.value = ''
  try {
    const res = await confirmOutline({
      taskId: taskId.value,
      outline: outline.value,
    } as any)
    if (res.data.code !== 0) {
      errorMsg.value = res.data.message || '确认大纲失败'
      message.error(errorMsg.value)
      // 通知子组件重置确认 loading
      outlineEditorRef.value?.resetConfirming()
      confirmingOutline.value = false
      return
    }
    // 切到正文生成阶段，重连 SSE 看 phase3 流式
    contentRaw.value = ''
    imageUrls.value = []
    images.value = []
    fullContent.value = ''
    currentStep.value = 2
    stage.value = 'generating'
    // 续接实时流：仅订阅新事件（本页已有当前状态，不重放历史，避免阶段回跳）
    ensureSse(lastSseSeq > 0 ? lastSseSeq : NO_REPLAY_AFTER)
  } catch (e: any) {
    errorMsg.value = e?.message || '确认大纲失败'
    message.error(errorMsg.value)
    outlineEditorRef.value?.resetConfirming()
  } finally {
    confirmingOutline.value = false
  }
}

// 断点续作：根据 taskId 拉取 ArticleVO，按 phase/status 恢复到对应阶段
// （仅「详情页 → 去创作页观察进度」的 /create?taskId= 场景触发；直接访问 /create 不自动恢复）
const resumeByTaskId = async (id: string) => {
  // 本会话新起点：清空流式累加器与序号，作为 SSE 全量重放还原中间态的干净基准
  lastSseSeq = 0
  outlineRaw.value = ''
  contentRaw.value = ''
  imageUrls.value = []
  images.value = []
  fullContent.value = ''
  try {
    const res = await getArticle({ taskId: id } as any)
    if (res.data.code !== 0 || !res.data?.data) {
      message.error(res.data?.message || '恢复任务失败')
      return
    }
    const a = res.data.data as any
    taskId.value = id
    errorMsg.value = a.errorMessage || ''
    // 采集结果回填（若已存在，详情接口已带 researchData）
    if (a.researchData) {
      researchData.value = a.researchData
      researchLoading.value = false
    }

    // 失败态：展示错误
    if (a.status === 'FAILED') {
      stage.value = 'generating'
      completed.value = false
      isRecovering.value = false
      return
    }

    // 完成态：直接展示结果
    if (a.status === 'COMPLETED') {
      if (a.mainTitle) titleResult.value = { mainTitle: a.mainTitle, subTitle: a.subTitle || '' }
      if (a.outline) outline.value = a.outline as OutlineSection[]
      if (a.content) contentRaw.value = a.content
      if (a.fullContent) fullContent.value = a.fullContent
      if (a.images) {
        images.value = (a.images as any[]).map((i) => ({ position: i.position, url: i.url, description: i.description }))
      }
      completed.value = true
      stage.value = 'done'
      isRecovering.value = false
      return
    }

    // 进行中：按 phase 定位阶段（恢复矩阵见 docs/用户体验优化实施计划.md §3.3）
    // 顶部展示「正在恢复创作进度」提示条；流式进行中阶段订阅 SSE 并全量重放（after=0）还原中间态
    isRecovering.value = true
    const phase = a.phase
    if (phase === 'PENDING') {
      // 任务已创建但图尚未推进（start 异步中）：生成中视图（预标题空态）+ 订阅 SSE，事件到达即展示
      stage.value = 'generating'
      currentStep.value = 0
      ensureSse(0)
    } else if (phase === 'TITLE_GENERATING') {
      // 标题还在生成：与「立即进入创作页」统一为生成中视图（预标题空态）+ 订阅 SSE
      stage.value = 'generating'
      currentStep.value = 0
      ensureSse(0)
    } else if (phase === 'TITLE_SELECTING') {
      // 标题候选已就绪，等待用户选择；不重连 SSE（后端已停）
      if (a.titleOptions) titleOptions.value = a.titleOptions
      selectedTitleIdx.value = 0
      stage.value = 'titleSelect'
    } else if (phase === 'OUTLINE_EDITING') {
      // 大纲已就绪，等待用户编辑；不重连 SSE
      if (a.outline) outline.value = a.outline as OutlineSection[]
      stage.value = 'outlineEdit'
    } else if (phase === 'OUTLINE_GENERATING') {
      // 大纲还在生成：展示已确认标题 + 「编辑大纲」占位 + 订阅 SSE（重放 AGENT2_STREAMING 还原流式大纲）
      if (a.mainTitle) titleResult.value = { mainTitle: a.mainTitle, subTitle: a.subTitle || '' }
      stage.value = 'outlineEdit'
      ensureSse(0)
    } else if (phase === 'CONTENT_GENERATING') {
      // 正文生成中：展示已确认大纲 + 生成中流式区 + 订阅 SSE（重放 AGENT3_STREAMING / IMAGE_COMPLETE 还原中间态）
      if (a.mainTitle) titleResult.value = { mainTitle: a.mainTitle, subTitle: a.subTitle || '' }
      if (a.outline) outline.value = a.outline as OutlineSection[]
      stage.value = 'generating'
      ensureSse(0)
    } else {
      // 未知/早期阶段，回退到输入态
      stage.value = 'input'
      isRecovering.value = false
    }
  } catch (e: any) {
    console.warn('恢复任务失败:', e)
    message.error('恢复任务失败')
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
  // 断点续作：优先处理 taskId（详情页"去创作页观察进度"会带 taskId 跳转）
  const qTaskId = route.query.taskId
  if (qTaskId && typeof qTaskId === 'string') {
    resumeByTaskId(qTaskId)
    fetchCreationOptions()
    return
  }
  // 支持 /create?topic= 预填（仅新建流程生效）
  const q = route.query.topic
  if (q && typeof q === 'string') {
    topic.value = q
  }
  // 拉取文章风格 / 配图方式可选项
  fetchCreationOptions()
  // 拉取积分余额（积分卡）
  fetchPointsBalance()
})

onBeforeUnmount(() => {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (renderTimer) {
    clearTimeout(renderTimer)
    renderTimer = null
  }
  sseHandle?.close()
  sseHandle = null
})
</script>

<template>
  <div id="createArticlePage">
    <!-- 恢复提示条：详情页「去创作页观察进度」进入且任务进行中时展示；放弃恢复回到干净输入态 -->
    <div v-if="isRecovering && !completed" class="recover-banner">
      <a-alert type="info" show-icon>
        <template #message>
          正在恢复创作进度 · 任务ID：<span class="recover-task-id">{{ taskId }}</span>
        </template>
        <template #action>
          <a-button size="small" type="primary" ghost @click="resetAll">放弃恢复</a-button>
        </template>
      </a-alert>
    </div>

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
          <!-- 题材：单选（含"默认"，默认项提交时映射为 null） -->
          <div v-if="genreOptions.length" class="option-group">
            <div class="option-head">
              <span class="option-title">题材</span>
              <span class="option-hint">（可选题材，单选，决定文章基调与结构；新闻题材将先采集相关资讯）</span>
            </div>
            <a-radio-group v-model:value="selectedGenre" class="option-options">
              <a-radio-button value="default">默认</a-radio-button>
              <a-radio-button
                v-for="item in genreOptions"
                :key="item.value"
                :value="item.value"
              >{{ item.label }}</a-radio-button>
            </a-radio-group>
            <!-- 新闻题材内联提醒（非弹窗）：先采集新闻资讯，消耗较大 -->
            <div v-if="isNewsGenre" class="genre-news-notice">
              <WarningOutlined />
              <span>新闻题材将自动采集相关新闻资讯，生成链路更长、消耗更大，本单预估消耗 <b>120</b> 积分。</span>
            </div>
          </div>

          <!-- 语言风格：单选（含"默认"，默认项提交时映射为 null） -->
          <div v-if="languageStyleOptions.length" class="option-group">
            <div class="option-head">
              <span class="option-title">语言风格</span>
              <span class="option-hint">（可选风格，单选，决定语言语气特质）</span>
            </div>
            <a-radio-group v-model:value="selectedLanguageStyle" class="option-options">
              <a-radio-button value="default">默认</a-radio-button>
              <a-radio-button
                v-for="item in languageStyleOptions"
                :key="item.value"
                :value="item.value"
              >{{ item.label }}</a-radio-button>
            </a-radio-group>
          </div>

          <!-- 目标字数：数字输入（默认 2000，范围 200~10000） -->
          <div class="option-group">
            <div class="option-head">
              <span class="option-title">目标字数</span>
              <span class="option-hint">（决定大纲各章节字数分配，上限 10000）</span>
            </div>
            <a-input-number
              v-model:value="targetWordCount"
              class="option-wordcount"
              :min="200"
              :max="10000"
              :step="100"
              :precision="0"
              placeholder="目标字数"
            />
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
                :disabled="isImageMethodLocked(item)"
                :class="['option-check', { 'option-check-locked': isImageMethodLocked(item) }]"
              >
                <span>{{ item.label }}</span>
                <span
                  v-if="item.vipOnly"
                  class="vip-only-mark"
                  :title="isVipUser ? '会员专属' : '开通会员解锁'"
                >
                  <CrownOutlined /> 会员
                </span>
              </a-checkbox>
            </a-checkbox-group>
            <!-- 非会员：底部开通会员入口 -->
            <div v-if="!isVipUser" class="option-unlock">
              <a-button type="link" size="small" @click="router.push('/vip')">
                <CrownOutlined /> 开通会员解锁全部配图方式
              </a-button>
            </div>
          </div>

          <a-button
            type="primary"
            size="large"
            block
            class="start-btn"
            :disabled="!canSubmit || isDebt"
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
        <!-- 积分卡（M5） -->
        <div class="quota-card points-card">
          <div class="panel-head">
            <WalletOutlined />
            <span>积分余额</span>
            <a-spin v-if="pointsLoading" :spinning="pointsLoading" size="small" class="points-loading" />
          </div>
          <div class="points-body">
            <div class="points-balance-row">
              <span class="points-num" :class="{ 'is-debt': isDebt }">{{ pointsBalance ?? '--' }}</span>
              <span class="points-unit">积分</span>
              <a-tag v-if="isAdminUser" color="gold" class="role-tag">管理员</a-tag>
            </div>
            <div class="points-estimate">
              本单预计消耗 <b>{{ estimateCost }}</b> 积分
              <div class="points-estimate-sub">
                <template v-if="isNewsGenre">新闻题材固定预估 120 积分（含信息采集），实际按用量结算</template>
                <template v-else>按 {{ targetWordCount || DEFAULT_WORD_COUNT }} 字估算，实际按用量结算</template>
              </div>
            </div>
            <div class="points-active">进行中任务 <b>{{ activeTaskCount }}</b> 个</div>
            <div v-if="isDebt" class="points-debt-warning">
              <WarningOutlined />
              <span>当前欠费 {{ -(pointsBalance ?? 0) }} 积分，请先签到还清后再创作</span>
              <a-button type="link" size="small" class="points-checkin-link" @click="showPointsGuide(-(pointsBalance ?? 0))">
                去签到
              </a-button>
            </div>
            <div
              v-else-if="!isAdminUser && (pointsBalance ?? 0) >= 0 && (pointsBalance ?? 0) < estimateCost"
              class="points-hint"
            >
              余额低于本单估算，将按实际用量结算（后付费，可小额透支）
            </div>
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

      <!-- 中栏：按阶段切换内容 -->
      <main class="main-panel">
        <!-- 阶段：选择标题 -->
        <div v-if="stage === 'titleSelect'" class="preview-card">
          <div class="stage-head">
            <h2 class="stage-title">选择标题</h2>
            <p class="stage-subtitle">AI 已生成多个标题方案，选择一个或自定义，确认后开始生成大纲</p>
          </div>
          <div v-if="errorMsg" class="error-banner">
            <a-alert :message="errorMsg" type="error" show-icon />
          </div>

          <!-- 信息采集面板（新闻题材） -->
          <ResearchPanel :research="researchData" :loading="researchLoading" />

          <!-- 标题候选列表 -->
          <div v-if="titleOptions.length" class="title-options">
            <div
              v-for="(opt, i) in titleOptions"
              :key="i"
              class="title-option-card"
              :class="{ selected: selectedTitleIdx === i }"
              @click="selectedTitleIdx = i"
            >
              <div class="title-option-radio">
                <CheckCircleFilled v-if="selectedTitleIdx === i" />
                <span v-else class="radio-empty"></span>
              </div>
              <div class="title-option-body">
                <div class="title-option-main">{{ opt.mainTitle }}</div>
                <div class="title-option-sub">{{ opt.subTitle }}</div>
              </div>
            </div>
            <!-- 自定义标题选项 -->
            <div
              class="title-option-card custom"
              :class="{ selected: selectedTitleIdx === 'custom' }"
              @click="selectedTitleIdx = 'custom'"
            >
              <div class="title-option-radio">
                <CheckCircleFilled v-if="selectedTitleIdx === 'custom'" />
                <span v-else class="radio-empty"></span>
              </div>
              <div class="title-option-body">
                <div class="title-option-main custom-label"><EditOutlined /> 自定义标题</div>
                <div v-if="selectedTitleIdx === 'custom'" class="custom-inputs" @click.stop>
                  <a-input
                    v-model:value="customMainTitle"
                    class="custom-input"
                    placeholder="请输入主标题"
                    :maxlength="100"
                  />
                  <a-input
                    v-model:value="customSubTitle"
                    class="custom-input"
                    placeholder="请输入副标题（可选）"
                    :maxlength="100"
                  />
                </div>
              </div>
            </div>
          </div>
          <div v-else class="empty-streaming">
            <a-spin tip="AI 正在生成标题方案…" />
          </div>

          <!-- 补充描述 -->
          <div class="desc-area">
            <div class="desc-head">
              <span class="desc-title">补充描述</span>
              <span class="desc-hint">（可选，告诉 AI 生成大纲时的侧重点）</span>
            </div>
            <a-textarea
              v-model:value="userDescription"
              class="desc-textarea"
              placeholder="例如：重点写实战案例、面向初级读者、多加入数据对比…"
              :auto-size="{ minRows: 2, maxRows: 4 }"
              :maxlength="300"
              show-count
            />
          </div>

          <!-- 确认按钮 -->
          <a-button
            type="primary"
            size="large"
            block
            class="stage-confirm-btn"
            :loading="confirmingTitle"
            :disabled="!titleOptions.length && selectedTitleIdx !== 'custom'"
            @click="confirmTitleSelection"
          >
            <CheckOutlined v-if="!confirmingTitle" />
            确认标题并生成大纲
          </a-button>
        </div>

        <!-- 阶段：编辑大纲 -->
        <div v-else-if="stage === 'outlineEdit'" class="preview-card">
          <div class="stage-head">
            <h2 class="stage-title">编辑大纲</h2>
            <p class="stage-subtitle">可拖拽排序、直接编辑，或用 AI 助手自然语言修改，确认后生成正文与配图</p>
          </div>
          <div v-if="errorMsg" class="error-banner">
            <a-alert :message="errorMsg" type="error" show-icon />
          </div>
          <!-- 大纲生成中占位；OUTLINE_GENERATED 到来后展示编辑器 -->
          <div v-if="!outline.length" class="empty-streaming empty-streaming--outline">
            <a-spin tip="AI 正在生成大纲…" />
            <div v-if="outlineRaw" class="markdown-body streaming outline-streaming" v-html="outlineHtml"></div>
          </div>
          <OutlineEditor
            v-else
            ref="outlineEditorRef"
            v-model:outline="outline"
            v-model:aiModifying="aiModifying"
            :task-id="taskId"
            :is-vip="isVipUser"
            :clear-input-signal="aiClearInputSignal"
            @ai-modify="onAiModify"
            @confirm="onOutlineConfirm"
          />
        </div>

        <!-- 阶段：生成中/完成（流式预览） -->
        <div v-else class="preview-card">
          <!-- 完成胶囊 -->
          <div v-if="completed" class="complete-badge">
            <CheckCircleFilled />
            <span>文章创作完成！</span>
          </div>
          <div v-if="errorMsg && !completed" class="error-banner">
            <a-alert :message="errorMsg" type="error" show-icon>
              <template v-if="sseInterrupted" #action>
                <a-button size="small" type="primary" ghost @click="manualReconnect">
                  <ReloadOutlined /> 点击重连
                </a-button>
              </template>
            </a-alert>
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
                <div class="outline-block-title">
                  {{ item.section }}. {{ item.title }}
                  <span v-if="item.word_count" class="outline-block-word">约 {{ item.word_count }} 字</span>
                </div>
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

          <!-- 空态：预标题阶段（标题/大纲/正文/配图均未产出） -->
          <div
            v-if="!titleResult && !outlineRaw && !contentRaw && !imageCount"
            class="empty-streaming"
            :class="{ 'empty-streaming--research': isNewsGenre }"
          >
            <a-spin :tip="emptyStreamingTip" />
            <!-- 新闻题材：信息采集占位/结果（标题生成前展示；RESEARCH_COMPLETE 到达后回填） -->
            <ResearchPanel v-if="isNewsGenre" :research="researchData" :loading="researchLoading" />
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
  grid-template-columns: 240px minmax(0, 1fr) 260px;
}
/* 生成/编辑阶段：左右栏吸附固定，不随中间大纲区域滚动 */
.generating-layout .side-panel {
  position: sticky;
  top: 88px; /* 64px 顶栏 + 24px 页面 padding */
  align-self: start;
}
/* 中栏宽度固定，不随长文本扩展（minmax(0,1fr) + min-width:0 抑制 grid 列被内容撑宽） */
.generating-layout .main-panel {
  min-width: 0;
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

/* 积分卡（M5） */
.points-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.points-balance-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex-wrap: wrap;
}
.points-num {
  font-size: 30px;
  font-weight: 800;
  color: var(--color-primary-dark);
  line-height: 1;
}
.points-num.is-debt {
  color: var(--color-error);
}
.points-unit {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.points-loading {
  margin-left: auto;
}
.points-estimate {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.points-estimate b {
  color: var(--color-primary-dark);
}
.points-estimate-sub {
  color: var(--color-text-muted);
  font-size: 12px;
  margin-top: 2px;
}
.points-active {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.points-active b {
  color: var(--color-text);
}
.points-debt-warning {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--color-error);
  background: rgba(239, 68, 68, 0.08);
  border-radius: var(--radius-md);
  padding: 8px 10px;
  flex-wrap: wrap;
}
.points-checkin-link {
  padding: 0 !important;
  height: auto !important;
  line-height: inherit !important;
}
.points-hint {
  font-size: 12px;
  color: var(--color-warning);
  background: rgba(234, 179, 8, 0.08);
  border-radius: var(--radius-md);
  padding: 6px 10px;
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

/* 新闻题材提醒（内联，非弹窗） */
.genre-news-notice {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 10px;
  padding: 8px 12px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-warning, #b45309);
  background: rgba(234, 179, 8, 0.08);
  border: 1px solid rgba(234, 179, 8, 0.25);
  border-radius: var(--radius-md);
}
.genre-news-notice .anticon {
  margin-top: 3px;
  flex-shrink: 0;
}
.genre-news-notice b {
  color: var(--color-primary-dark, #16a34a);
}
.option-wordcount {
  width: 200px;
  border-radius: var(--radius-md);
}
.option-check {
  margin-inline-start: 0 !important;
}

/* 会员专属配图：置灰 + 皇冠小标 */
.option-check-locked :deep(.ant-checkbox-inner) {
  background-color: #e5e7eb !important;
  border-color: #d1d5db !important;
}
.option-check-locked :deep(.ant-checkbox-wrapper) {
  color: var(--color-text-muted) !important;
}
.vip-only-mark {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-inline-start: 6px;
  font-size: 12px;
  line-height: 1;
  color: #f59e0b;
  vertical-align: middle;
}
.option-check-locked .vip-only-mark {
  opacity: 0.8;
}
.option-unlock {
  margin-top: 6px;
}
.option-unlock .ant-btn {
  padding-inline-start: 0;
  color: #f59e0b;
}
.option-unlock .ant-btn:hover {
  color: #d97706;
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
/* 恢复提示条（详情页 → 去创作页观察进度） */
.recover-banner {
  max-width: 1240px;
  margin: 0 auto 20px;
}
.recover-task-id {
  font-weight: 600;
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
.outline-block-word {
  margin-inline-start: 8px;
  font-size: 12px;
  font-weight: 400;
  color: var(--color-text-muted);
  background: var(--color-background-tertiary);
  padding: 1px 8px;
  border-radius: var(--radius-full);
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
/* 空态（新闻题材含信息采集面板时）：纵向排列，spinner 居中、面板占满宽度 */
.empty-streaming--research {
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-start;
  gap: 8px;
  padding: 16px 0;
}
.empty-streaming--research :deep(.ant-spin-nested-loading) {
  align-self: center;
}
/* 大纲生成中的流式预览：纵向排列，约束子项宽度并强制换行，避免长行撑破容器 */
.empty-streaming--outline {
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-start;
  gap: 16px;
  padding: 16px 0;
}
.outline-streaming {
  width: 100%;
  min-width: 0;
  /* 兜底换行：长单词/URL/代码不撑破容器，超出按字符断行 */
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: normal;
}
.outline-streaming :deep(pre) {
  white-space: pre-wrap;
  overflow-x: auto;
  max-width: 100%;
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

/* ===== 多阶段交互 UI ===== */
/* 阶段标题 */
.stage-head {
  margin-bottom: 20px;
}
.stage-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 6px;
}
.stage-subtitle {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
}

/* 标题候选 */
.title-options {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}
.title-option-card {
  display: flex;
  gap: 14px;
  padding: 16px 18px;
  background: var(--color-background-secondary);
  border: 2px solid var(--color-border-light);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.title-option-card:hover {
  border-color: var(--color-primary-light);
}
.title-option-card.selected {
  border-color: var(--color-primary);
  background: rgba(34, 197, 94, 0.06);
}
.title-option-radio {
  flex-shrink: 0;
  padding-top: 2px;
  font-size: 20px;
  color: var(--color-primary);
}
.radio-empty {
  display: inline-block;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid var(--color-border);
  background: var(--color-background);
}
.title-option-body {
  flex: 1;
  min-width: 0;
}
.title-option-main {
  font-size: 17px;
  font-weight: 600;
  color: var(--color-text);
  line-height: 1.4;
}
.title-option-sub {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}
.custom-label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-primary-dark);
}
.custom-inputs {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}
.custom-input {
  border-radius: var(--radius-md);
}

/* 补充描述 */
.desc-area {
  margin-bottom: 18px;
}
.desc-head {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: 8px;
}
.desc-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
}
.desc-hint {
  font-size: 12px;
  color: var(--color-text-muted);
}
.desc-textarea {
  border-radius: var(--radius-md);
}

/* 阶段确认按钮 */
.stage-confirm-btn {
  height: 46px !important;
  font-size: 16px !important;
  font-weight: 600 !important;
  border-radius: var(--radius-md) !important;
}

</style>
