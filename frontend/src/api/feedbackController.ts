// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** Admin Get Feedback 管理端反馈详情（含提交用户信息） GET /admin/feedback/${param0} */
export async function adminGetFeedback(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.adminGetFeedbackParams,
  options?: { [key: string]: any }
) {
  const { feedbackId: param0, ...queryParams } = params;
  return request<API.BaseResponseAdminFeedbackVO_>(
    `/admin/feedback/${param0}`,
    {
      method: "GET",
      params: { ...queryParams },
      ...(options || {}),
    }
  );
}

/** Admin Page Feedback 管理端全量分页（关键字/类型/状态/时间筛选，含提交用户信息） GET /admin/feedback/page */
export async function adminPageFeedback(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.adminPageFeedbackParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseDict_>("/admin/feedback/page", {
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

/** Admin Reply Feedback 管理员回复反馈（回复内容 + 状态，默认置 RESOLVED；联动发送 FEEDBACK 站内信） POST /admin/feedback/reply */
export async function adminReplyFeedback(
  body: API.FeedbackReplyRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseFeedbackVO_>("/admin/feedback/reply", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Admin Update Feedback Status 管理员仅改状态（不回复） POST /admin/feedback/status */
export async function adminUpdateFeedbackStatus(
  body: API.FeedbackStatusRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseFeedbackVO_>("/admin/feedback/status", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Get Feedback 反馈详情（仅本人，归属校验） GET /feedback/${param0} */
export async function getFeedback(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getFeedbackParams,
  options?: { [key: string]: any }
) {
  const { feedbackId: param0, ...queryParams } = params;
  return request<API.BaseResponseFeedbackVO_>(`/feedback/${param0}`, {
    method: "GET",
    params: { ...queryParams },
    ...(options || {}),
  });
}

/** Page My Feedback 我的反馈分页（type/status 筛选，仅本人） GET /feedback/page */
export async function pageMyFeedback(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.pageMyFeedbackParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseDict_>("/feedback/page", {
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

/** Submit Feedback 提交意见反馈（每日限流：每用户每天最多 feedback_daily_limit 条，超限返回 REQUEST_TOO_FREQUENT） POST /feedback/submit */
export async function submitFeedback(
  body: API.FeedbackSubmitRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseInt_>("/feedback/submit", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Upload Feedback Image 上传反馈截图（multipart/form-data，字段名 file）
 *
 * 仅支持 JPG / PNG / WebP / GIF，大小不超过 2MB，不接受 SVG（防存储型 XSS）；
 * 单张上传返回可访问 URL，同一反馈可多次调用（提交时最多 5 张，由提交接口兜底校验）。
 * 文件保存到本地 static/images/feedback/。 POST /feedback/upload */
export async function uploadFeedbackImage(file: File, options?: { [key: string]: any }) {
  const formData = new FormData()
  formData.append('file', file)
  return request<API.BaseResponseStr_>('/feedback/upload', {
    method: 'POST',
    data: formData,
    ...(options || {}),
  })
}
