/**
 * 文章状态文案与 Badge 颜色映射
 * 后端状态枚举：PENDING / PROCESSING / COMPLETED / FAILED
 */

export type ArticleStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'

interface StatusMeta {
  text: string
  /** Ant Design Badge / Tag 的 status 颜色 */
  color: string
  /** 用于自定义圆点的实际色值 */
  dot: string
}

export const STATUS_MAP: Record<ArticleStatus, StatusMeta> = {
  PENDING: { text: '等待中', color: 'default', dot: '#94A3B8' },
  PROCESSING: { text: '生成中', color: 'processing', dot: '#3B82F6' },
  COMPLETED: { text: '已完成', color: 'success', dot: '#22C55E' },
  FAILED: { text: '失败', color: 'error', dot: '#EF4444' },
}

/** 状态中文文案，未知状态原样返回 */
export function statusText(s?: string): string {
  return (s && STATUS_MAP[s as ArticleStatus]?.text) || s || '-'
}

/** Ant Design Badge/Tag 颜色 */
export function statusColor(s?: string): string {
  return (s && STATUS_MAP[s as ArticleStatus]?.color) || 'default'
}

/** 自定义圆点色值 */
export function statusDotColor(s?: string): string {
  return (s && STATUS_MAP[s as ArticleStatus]?.dot) || '#94A3B8'
}