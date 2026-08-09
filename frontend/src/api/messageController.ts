// @ts-ignore
/* eslint-disable */
import request from '@/request'

/** GET /message/page 站内信分页（未读优先 + createTime 倒序，type 可选筛选，仅本人） */
export async function pageMessage(
  params: API.pageMessageParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseMessagePageVO>('/message/page', {
    method: 'GET',
    params: {
      ...params,
    },
    ...(options || {}),
  })
}

/** GET /message/unread-count 未读站内信数（供头部铃铛角标轮询） */
/** GET /message/{messageId} 站内信详情（仅本人，归属校验） */
export async function getMessageDetail(
  messageId: number,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseMessageVO>(`/message/${messageId}`, {
    method: 'GET',
    ...(options || {}),
  })
}
export async function getMessageUnreadCount(options?: { [key: string]: any }) {
  return request<API.BaseResponseMessageUnreadCountVO>('/message/unread-count', {
    method: 'GET',
    ...(options || {}),
  })
}

/** POST /message/read 标记已读（{ids: []} 或 {all: true}，仅本人） */
export async function readMessage(
  body: API.MessageReadRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseLong>('/message/read', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** POST /message/delete 删除站内信（软删，仅本人） */
export async function deleteMessage(
  body: API.MessageDeleteRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseLong>('/message/delete', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** POST /admin/message/send 管理员发送站内信（targetType: SINGLE/BATCH/ALL + userIds[]，写时展开） */
export async function adminSendMessage(
  body: API.AdminMessageSendRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseLong>('/admin/message/send', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** GET /admin/message/page 管理端已发消息分页（senderId 非空 = 管理员主动发信） */
export async function adminPageMessage(
  params: API.adminPageMessageParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseAdminMessagePageVO>('/admin/message/page', {
    method: 'GET',
    params: {
      ...params,
    },
    ...(options || {}),
  })
}
