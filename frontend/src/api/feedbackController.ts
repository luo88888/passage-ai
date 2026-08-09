// @ts-ignore
/* eslint-disable */
import request from '@/request'

/** POST /feedback/upload 上传反馈截图（单张，multipart/form-data，字段名 file；返回可访问 URL） */
export async function uploadFeedbackImage(
  file: File,
  options?: { [key: string]: any }
) {
  const formData = new FormData()
  formData.append('file', file)
  return request<API.BaseResponseString>('/feedback/upload', {
    method: 'POST',
    data: formData,
    ...(options || {}),
  })
}

/** POST /feedback/submit 提交意见反馈 */
export async function submitFeedback(
  body: API.FeedbackSubmitRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseLong>('/feedback/submit', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** GET /feedback/page 我的反馈分页（type/status 筛选，仅本人） */
export async function pageMyFeedback(
  params: API.pageMyFeedbackParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseFeedbackPageVO>('/feedback/page', {
    method: 'GET',
    params: {
      ...params,
    },
    ...(options || {}),
  })
}

/** GET /feedback/{feedbackId} 反馈详情（仅本人，归属校验） */
export async function getFeedback(
  feedbackId: number,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseFeedbackVO>(`/feedback/${feedbackId}`, {
    method: 'GET',
    ...(options || {}),
  })
}

/** GET /admin/feedback/page 管理端全量分页（关键字/类型/状态/时间筛选） */
export async function adminPageFeedback(
  params: API.adminPageFeedbackParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseAdminFeedbackPageVO>('/admin/feedback/page', {
    method: 'GET',
    params: {
      ...params,
    },
    ...(options || {}),
  })
}

/** GET /admin/feedback/{feedbackId} 管理端反馈详情（含提交用户信息） */
export async function adminGetFeedback(
  feedbackId: number,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseAdminFeedbackVO>(`/admin/feedback/${feedbackId}`, {
    method: 'GET',
    ...(options || {}),
  })
}

/** POST /admin/feedback/reply 管理员回复反馈（回复内容 + 状态，联动发送 FEEDBACK 站内信） */
export async function adminReplyFeedback(
  body: API.FeedbackReplyRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseFeedbackVO>('/admin/feedback/reply', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** POST /admin/feedback/status 管理员仅改状态（不回复） */
export async function adminUpdateFeedbackStatus(
  body: API.FeedbackStatusRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseFeedbackVO>('/admin/feedback/status', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}
