/**
 * 文章创作进度 SSE 订阅工具
 *
 * 后端端点：GET /api/article/progress/{taskId}，需登录（携带 SESSION cookie）。
 * 消息帧格式：`data: {json}\n\n`，json 含 type 字段，枚举见 SseMessageType。
 *
 * 注意：浏览器原生 EventSource 支持 withCredentials 跨域携带 cookie，
 * 后端 CORS 已 allow_credentials=true 且允许 localhost:5173 / 127.0.0.1:5173。
 */

/** SSE 消息类型（与后端 SseMessageTypeEnum 对齐） */
export type SseMessageType =
  | 'AGENT1_COMPLETE'
  | 'TITLE_GENERATED' // 阶段1结束：标题候选已就绪，等待用户选择（不关流）
  | 'AGENT2_STREAMING'
  | 'AGENT2_COMPLETE'
  | 'OUTLINE_GENERATED' // 阶段2结束：大纲已就绪，等待用户编辑（不关流）
  | 'AGENT3_STREAMING'
  | 'AGENT3_COMPLETE'
  | 'AGENT4_COMPLETE'
  | 'IMAGE_COMPLETE'
  | 'AGENT5_COMPLETE'
  | 'MERGE_COMPLETE'
  | 'ALL_COMPLETE'
  | 'AI_MODIFY_OUTLINE_COMPLETE' // AI 修改大纲完成（不关流）
  | 'AI_MODIFY_OUTLINE_FAILED' // AI 修改大纲失败（不关流）
  | 'RESEARCH_COMPLETE' // 信息采集完成（新闻题材，不关流）
  | 'ERROR'

/** 标题候选（AGENT1_COMPLETE / TITLE_GENERATED 携带） */
export interface TitleOption {
  mainTitle: string
  subTitle: string
}

/** 大纲章节（AGENT2_COMPLETE / OUTLINE_GENERATED 携带，后端 OutlineSection.model_dump() 无 alias，字段为 snake_case） */
export interface OutlineSection {
  section: number
  title: string
  points: string[]
  // 本章目标字数：后端落库/SSE 下发为 snake_case word_count（无 alias 的 model_dump()）
  // —— 前端提交确认大纲时可回传 wordCount(camel)，Pydantic 经 populate_by_name 兼容双键。
  word_count?: number
  wordCount?: number
}

/** 配图结果（IMAGE_COMPLETE 的 content 经 JSON.parse / AGENT5_COMPLETE 携带，camelCase） */
export interface ImageResult {
  position: number
  url: string
  method: string
  keywords: string
  sectionTitle: string
  description: string
  placeholderId?: string
}

/** 单条信息采集结果（新闻/文章摘要，对应后端 NewsArticleSummary 的 camelCase 形态） */
export interface ResearchArticle {
  title: string
  url: string
  summary: string
  publishTime?: string | null
  source?: string | null
  author?: string | null
  tags?: string[]
}

/** 信息采集结果（对应后端 article.researchData JSON 列 / RESEARCH_COMPLETE SSE 载荷） */
export interface ResearchData {
  requirement?: string
  searchQueriesUsed?: string[]
  articles?: ResearchArticle[]
}

/** SSE 消息载荷（按 type 不同携带不同字段） */
export interface SseMessage {
  type: SseMessageType
  // AGENT1_COMPLETE / TITLE_GENERATED：标题候选列表
  titleOptions?: TitleOption[]
  // AGENT2_STREAMING / AGENT3_STREAMING 增量内容；IMAGE_COMPLETE 为 ImageResult 的 JSON 字符串
  content?: string
  // AGENT2_COMPLETE / OUTLINE_GENERATED / AI_MODIFY_OUTLINE_COMPLETE：大纲章节（snake_case）
  outline?: OutlineSection[]
  // AGENT4_COMPLETE
  imageRequirements?: Array<{ position: number; type: string; sectionTitle: string; keywords: string }>
  // AGENT5_COMPLETE：全量配图（camelCase）
  images?: ImageResult[]
  // MERGE_COMPLETE
  fullContent?: string
  // ALL_COMPLETE
  taskId?: string
  // ERROR / AI_MODIFY_OUTLINE_FAILED
  message?: string
  // RESEARCH_COMPLETE：信息采集完成（新闻题材），携带采集到的相关新闻条数
  count?: number
  // RESEARCH_COMPLETE：实际使用的搜索词列表
  searchQueriesUsed?: string[]
  // RESEARCH_COMPLETE：采集到的新闻条目（结构化）
  articles?: ResearchArticle[]
}

export interface SseHandlers {
  /** 收到一条消息（已 JSON.parse） */
  onMessage: (data: SseMessage) => void
  /** 连接异常 */
  onError?: (err: Event) => void
  /** 收到 ALL_COMPLETE 或 ERROR（流已关闭）后回调 */
  onComplete?: () => void
}

// 与 request.ts 的 baseURL 保持一致：默认同源 /api，跨域部署时用 VITE_API_BASE_URL 覆盖
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

/** SSE 订阅句柄 */
export interface SseSubscription {
  close: () => void
  /** 最近一条 SSE 事件的序号（SSE 帧 `id: <seq>`），断线重连时作为 `after` 续传 */
  getLastSeq: () => number
}

export interface SubscribeOptions {
  /** 订阅起点：只重放 seq > after 的历史消息；after=0 全量重放；缺省 0 */
  after?: number
}

/**
 * 订阅文章生成进度 SSE 流。
 * - 支持 `?after=` 断点续传：先重放历史事件，再续接实时流（阶段三：创作进度准确恢复）；
 * - 每条消息记录 SSE 帧 `id: <seq>` 为 lastSeq，断线重连时以 `after=getLastSeq()` 续传，
 *   避免重复追加已收到的流式片段。
 * 返回带 close() / getLastSeq() 的句柄，调用方在组件卸载时应调用 close() 释放连接。
 */
export function subscribeArticleProgress(
  taskId: string,
  handlers: SseHandlers,
  options?: SubscribeOptions,
): SseSubscription {
  const after = options?.after ?? 0
  const url = `${API_BASE}/article/progress/${taskId}?after=${after}`
  const es = new EventSource(url, { withCredentials: true })

  let closed = false
  let lastSeq = 0

  const close = () => {
    if (closed) return
    closed = true
    es.close()
  }

  es.onmessage = (ev: MessageEvent) => {
    // 记录最近事件序号（SSE 帧 id: <seq>），供断线重连 after=lastSeq 续传
    if (ev.lastEventId) {
      const n = Number.parseInt(ev.lastEventId, 10)
      if (!Number.isNaN(n) && n > lastSeq) lastSeq = n
    }
    // 后端心跳或空数据跳过
    if (!ev.data) return
    let data: SseMessage
    try {
      data = JSON.parse(ev.data)
    } catch (e) {
      console.warn('SSE 消息解析失败:', ev.data, e)
      return
    }
    handlers.onMessage(data)
    // 收到终态消息：主动关闭流
    if (data.type === 'ALL_COMPLETE' || data.type === 'ERROR') {
      handlers.onComplete?.()
      close()
    }
  }

  es.onerror = (err: Event) => {
    // 若尚未收到终态就断开，通知上层；浏览器默认会重连，这里主动关闭避免无限重连
    if (!closed) {
      handlers.onError?.(err)
      close()
    }
  }

  return {
    close,
    getLastSeq: () => lastSeq,
  }
}