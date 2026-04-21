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
  | 'AGENT2_STREAMING'
  | 'AGENT2_COMPLETE'
  | 'AGENT3_STREAMING'
  | 'AGENT3_COMPLETE'
  | 'AGENT4_COMPLETE'
  | 'IMAGE_COMPLETE'
  | 'AGENT5_COMPLETE'
  | 'MERGE_COMPLETE'
  | 'ALL_COMPLETE'
  | 'ERROR'

/** SSE 消息载荷（按 type 不同携带不同字段） */
export interface SseMessage {
  type: SseMessageType
  // AGENT1_COMPLETE
  titleResult?: { mainTitle: string; subTitle: string }
  // AGENT2_STREAMING / AGENT3_STREAMING / IMAGE_COMPLETE 增量内容
  content?: string
  // AGENT2_COMPLETE
  outline?: Array<{ section: number; title: string; points: string[] }>
  // AGENT4_COMPLETE
  imageRequirements?: Array<{ position: number; type: string; sectionTitle: string; keywords: string }>
  // AGENT5_COMPLETE
  images?: Array<{ position: number; url: string; method: string; keywords: string; sectionTitle: string; description: string }>
  // MERGE_COMPLETE
  fullContent?: string
  // ALL_COMPLETE
  taskId?: string
  // ERROR
  message?: string
}

export interface SseHandlers {
  /** 收到一条消息（已 JSON.parse） */
  onMessage: (data: SseMessage) => void
  /** 连接异常 */
  onError?: (err: Event) => void
  /** 收到 ALL_COMPLETE 或 ERROR（流已关闭）后回调 */
  onComplete?: () => void
}

// 与 request.ts 的 baseURL 保持一致
const API_BASE = 'http://localhost:8567/api'

/**
 * 订阅文章生成进度 SSE 流。
 * 返回一个带 close() 的句柄，调用方在组件卸载时应调用 close() 释放连接。
 */
export function subscribeArticleProgress(
  taskId: string,
  handlers: SseHandlers,
): { close: () => void } {
  const url = `${API_BASE}/article/progress/${taskId}`
  const es = new EventSource(url, { withCredentials: true })

  let closed = false
  const close = () => {
    if (closed) return
    closed = true
    es.close()
  }

  es.onmessage = (ev: MessageEvent) => {
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

  return { close }
}