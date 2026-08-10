// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** Admin Page Message 管理端已发消息分页（senderId 非空 = 管理员主动发信） GET /admin/message/page */
export async function adminPageMessage(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.adminPageMessageParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseDict_>("/admin/message/page", {
    method: "GET",
    params: {
      // current has a default value: 1
      current: "1",
      // pageSize has a default value: 10
      pageSize: "10",

      ...params,
    },
    ...(options || {}),
  });
}

/** Admin Send Message 管理员发送站内信（targetType: SINGLE/BATCH/ALL + userIds[]，写时展开） POST /admin/message/send */
export async function adminSendMessage(
  body: API.AdminMessageSendRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseInt_>("/admin/message/send", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Get Message Detail 站内信详情（仅本人，归属校验） GET /message/${param0} */
export async function getMessageDetail(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getMessageDetailParams,
  options?: { [key: string]: any }
) {
  const { messageId: param0, ...queryParams } = params;
  return request<API.BaseResponseMessageVO_>(`/message/${param0}`, {
    method: "GET",
    params: { ...queryParams },
    ...(options || {}),
  });
}

/** Delete Message 删除站内信（软删，仅本人） POST /message/delete */
export async function deleteMessage(
  body: API.MessageDeleteRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseInt_>("/message/delete", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Page Message 站内信分页（未读优先 + createTime 倒序，type 可选筛选，仅本人） GET /message/page */
export async function pageMessage(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.pageMessageParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseDict_>("/message/page", {
    method: "GET",
    params: {
      // current has a default value: 1
      current: "1",
      // pageSize has a default value: 10
      pageSize: "10",
      ...params,
    },
    ...(options || {}),
  });
}

/** Mark Message Read 标记已读（{ids: []} 或 {all: true}，仅本人） POST /message/read */
export async function readMessage(
  body: API.MessageReadRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseInt_>("/message/read", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Get Unread Count 未读站内信数（DB count 实时查询，供头部铃铛角标轮询） GET /message/unread-count */
export async function getMessageUnreadCount(options?: { [key: string]: any }) {
  return request<API.BaseResponseMessageUnreadCountVO_>(
    "/message/unread-count",
    {
      method: "GET",
      ...(options || {}),
    }
  );
}
