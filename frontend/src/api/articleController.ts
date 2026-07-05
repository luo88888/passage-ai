// @ts-ignore
/* eslint-disable */
import request from '@/request'

/** 获取文章详情 GET /article/${param0} */
export async function getArticle(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getArticleParams,
  options?: { [key: string]: any }
) {
  const { taskId: param0, ...queryParams } = params
  return request<API.BaseResponseArticleVO>(`/article/${param0}`, {
    method: 'GET',
    params: { ...queryParams },
    ...(options || {}),
  })
}

/** AI 修改大纲 POST /article/ai-modify-outline
 *  fire-and-forget:仅回 ack {taskId};新大纲由 SSE AI_MODIFY_OUTLINE_COMPLETE 回填前端。
 *  body: { taskId, modifySuggestion };响应:{ code, data:{taskId}, message }。
 */
export async function aiModifyOutline(
  body: API.ArticleAiModifyOutlineRequest,
  options?: { [key: string]: any }
) {
  return request<{ code: number; data: { taskId: string }; message?: string }>(
    '/article/ai-modify-outline',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      data: body,
      ...(options || {}),
    }
  )
}

/** 确认大纲 POST /article/confirm-outline */
export async function confirmOutline(
  body: API.ArticleConfirmOutlineRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseVoid>('/article/confirm-outline', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 确认标题并输入补充描述 POST /article/confirm-title */
export async function confirmTitle(
  body: API.ArticleConfirmTitleRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseVoid>('/article/confirm-title', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 创建文章任务 POST /article/create */
export async function createArticle(
  body: API.ArticleCreateRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseString>('/article/create', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 删除文章 POST /article/delete */
export async function deleteArticle(body: API.DeleteRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>('/article/delete', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 分页查询文章列表 POST /article/list */
export async function listArticle(body: API.ArticleQueryRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponsePageArticleVO>('/article/list', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

// NOTE: 以下 getCreationOptions 为手写补充——后端 OpenAPI 暴露在默认 /openapi.json，
// 而 openapi2ts.config.ts 指向的 /api/v3/api-docs 路径后端未提供，openapi2ts 无法直接生成。
// 类型 API.CreationOptionsVO / API.OptionItem 未生成，故这里内联最小类型。
export interface CreationOptionItem {
  value: string
  label: string
  description?: string
  vipOnly?: boolean
}
export interface CreationOptionsVO {
  styles: CreationOptionItem[]
  imageMethods: CreationOptionItem[]
}

/** 获取创作页可选项（文章风格 / 配图方式） GET /article/options */
export async function getCreationOptions(options?: { [key: string]: any }) {
  return request<{ code: number; data: CreationOptionsVO; message?: string }>('/article/options', {
    method: 'GET',
    ...(options || {}),
  })
}

/** 获取文章生成进度(SSE) GET /article/progress/${param0} */
export async function getProgress(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getProgressParams,
  options?: { [key: string]: any }
) {
  const { taskId: param0, ...queryParams } = params
  return request<API.SseEmitter>(`/article/progress/${param0}`, {
    method: 'GET',
    params: { ...queryParams },
    ...(options || {}),
  })
}

// NOTE: 以下 getExecutionLogs 为手写补充——同 getCreationOptions，后端 OpenAPI 路径与
// openapi2ts.config.ts 指向的 /api/v3/api-docs 不一致，故无法自动生成，类型内联最小定义。
// 后端对应：GET /article/execution-logs/{taskId}，返回 BaseResponse<AgentExecutionStatsVO>。

/** 单个智能体执行日志 */
export interface AgentLogVO {
  id: number
  taskId: string
  agentName: string
  startTime: string
  endTime?: string | null
  durationMs?: number | null
  status: 'RUNNING' | 'SUCCESS' | 'FAILED' | string
  errorMessage?: string | null
  prompt?: string | null
  inputData?: string | null
  outputData?: string | null
  createTime: string
  updateTime: string
}

/** 任务执行统计（含全部日志） */
export interface AgentExecutionStatsVO {
  taskId: string
  totalDurationMs: number
  agentCount: number
  agentDurations: Record<string, number>
  overallStatus: 'RUNNING' | 'SUCCESS' | 'FAILED' | 'NOT_FOUND' | string
  logs: AgentLogVO[]
}

/** 获取任务执行日志 GET /article/execution-logs/${param0} */
export async function getExecutionLogs(
  params: { taskId: string },
  options?: { [key: string]: any }
) {
  const { taskId: param0 } = params
  return request<{ code: number; data: AgentExecutionStatsVO; message?: string }>(
    `/article/execution-logs/${param0}`,
    {
      method: 'GET',
      ...(options || {}),
    }
  )
}
