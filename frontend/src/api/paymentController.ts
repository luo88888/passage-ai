// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** Activate Vip 直接开通永久会员（临时免支付：Stripe 停用期间，点击「立即开通」即开通） POST /payment/activate-vip */
export async function activateVip(options?: { [key: string]: any }) {
  return request<API.BaseResponseBool_>("/payment/activate-vip", {
    method: "POST",
    ...(options || {}),
  });
}

/** Create Vip Payment Session 创建 VIP 支付会话 POST /payment/create-vip-session */
export async function createVipSession(options?: { [key: string]: any }) {
  return request<API.BaseResponseStr_>("/payment/create-vip-session", {
    method: "POST",
    ...(options || {}),
  });
}

/** Get Vip Plans 获取会员套餐列表（价格 + 特权，公开接口，无需登录） GET /payment/plans */
export async function getVipPlans(options?: { [key: string]: any }) {
  return request<API.BaseResponseListVipPlanVO_>("/payment/plans", {
    method: "GET",
    ...(options || {}),
  });
}

/** Get Payment Records 获取当前用户支付记录 GET /payment/records */
export async function getPaymentRecords(options?: { [key: string]: any }) {
  return request<API.BaseResponseListPaymentRecordVO_>("/payment/records", {
    method: "GET",
    ...(options || {}),
  });
}

/** Refund 申请退款 POST /payment/refund */
export async function refundPayment(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.refundPaymentParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseBool_>("/payment/refund", {
    method: "POST",
    params: {
      ...params,
    },
    ...(options || {}),
  });
}

/** Stripe Webhook Stripe webhook 回调 POST /webhook/stripe */
export async function stripeWebhook(options?: { [key: string]: any }) {
  return request<any>("/webhook/stripe", {
    method: "POST",
    ...(options || {}),
  });
}
