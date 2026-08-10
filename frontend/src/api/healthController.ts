// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** Health Check 健康检查 GET /health */
export async function healthCheck(options?: { [key: string]: any }) {
  return request<API.BaseResponseStr_>("/health", {
    method: "GET",
    ...(options || {}),
  });
}
