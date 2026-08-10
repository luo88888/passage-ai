// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** Get Article 获取文章详情 GET /article/${param0} */
export async function getArticle(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getArticleParams,
  options?: { [key: string]: any }
) {
  const { taskId: param0, ...queryParams } = params;
  return request<API.BaseResponseArticleVO_>(`/article/${param0}`, {
    method: "GET",
    params: { ...queryParams },
    ...(options || {}),
  });
}

/** Ai Modify Outline AI 修改大纲（fire-and-forget）

路由层做前置校验（文章存在 / 归属 / 阶段为 OUTLINE_EDITING / 已有大纲 / VIP），
通过后异步续跑图：注入 modify_suggestion → 条件边路由进 ai_modify_outline 节点，
由节点跑 LLM + 落库 + 发 AI_MODIFY_OUTLINE_COMPLETE / FAILED SSE。
路由只回 ack（taskId），大纲由 SSE 回填前端。 POST /article/ai-modify-outline */
export async function aiModifyOutline(
  body: API.ArticleAiModifyOutlineRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseDict_>("/article/ai-modify-outline", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Confirm Outline 确认大纲 POST /article/confirm-outline */
export async function confirmOutline(
  body: API.ArticleConfirmOutlineRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseNoneType_>("/article/confirm-outline", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Confirm Title 确认标题并输入补充描述 POST /article/confirm-title */
export async function confirmTitle(
  body: API.ArticleConfirmTitleRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseNoneType_>("/article/confirm-title", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Create Article 创建文章任务（M3 后付费闸门：余额 >= 0 + 并发名额快速失败） POST /article/create */
export async function createArticle(
  body: API.ArticleCreateRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseStr_>("/article/create", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Delete Article 删除文章 POST /article/delete */
export async function deleteArticle(
  body: API.DeleteRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseBool_>("/article/delete", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Get Execution Logs 获取任务执行日志 GET /article/execution-logs/${param0} */
export async function getExecutionLogs(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getExecutionLogsParams,
  options?: { [key: string]: any }
) {
  const { taskId: param0, ...queryParams } = params;
  return request<API.BaseResponseAgentExecutionStatsVO_>(
    `/article/execution-logs/${param0}`,
    {
      method: "GET",
      params: { ...queryParams },
      ...(options || {}),
    }
  );
}

/** List Article 分页查询文章列表 POST /article/list */
export async function listArticle(
  body: API.ArticleQueryRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseDict_>("/article/list", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Get Creation Options 获取创作页可选项（题材 / 语言风格 / 配图方式），供前端动态渲染，避免硬编码 GET /article/options */
export async function getCreationOptions(options?: { [key: string]: any }) {
  return request<API.BaseResponseCreationOptionsVO_>("/article/options", {
    method: "GET",
    ...(options || {}),
  });
}

/** Get Progress SSE 进度推送（支持 ?after= 断点续传：先重放历史，再续接实时流） GET /article/progress/${param0} */
export async function getProgress(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getProgressParams,
  options?: { [key: string]: any }
) {
  const { taskId: param0, ...queryParams } = params;
  return request<any>(`/article/progress/${param0}`, {
    method: "GET",
    params: {
      ...queryParams,
    },
    ...(options || {}),
  });
}
