// @ts-ignore
/* eslint-disable */
// 手写支付控制器——后端 OpenAPI 未在 openapi2ts 配置所指向的 /api/v3/api-docs 暴露，
// 与 articleController.ts 中 getCreationOptions 同样为手写补充，类型内联最小集。
// 接口返回统一 BaseResponse：{ code: number; data; message?: string }，code===0 表示成功。
import request from '@/request'

/** 会员套餐视图 */
export interface VipPlanVO {
  productType: string
  price: number
  currency: string
  title: string
  description: string
  privileges: string[]
}

/** 支付记录视图 */
export interface PaymentRecordVO {
  id: number
  userId: number
  stripeSessionId?: string
  stripePaymentIntentId?: string
  amount: number
  currency: string
  status: string
  productType: string
  description?: string
  refundTime?: string
  refundReason?: string
  createTime: string
  updateTime: string
}

interface BaseResponse<T> {
  code: number
  data: T
  message?: string
}

/** 获取会员套餐列表（价格 + 特权，公开接口） GET /payment/plans */
export async function getVipPlans(options?: { [key: string]: any }) {
  return request<BaseResponse<VipPlanVO[]>>('/payment/plans', {
    method: 'GET',
    ...(options || {}),
  })
}

/** 创建 VIP 支付会话，返回 Stripe 支付页 URL POST /payment/create-vip-session */
export async function createVipSession(options?: { [key: string]: any }) {
  return request<BaseResponse<string>>('/payment/create-vip-session', {
    method: 'POST',
    ...(options || {}),
  })
}

/** 直接开通永久会员（临时免支付：Stripe 停用期间，点击即开通） POST /payment/activate-vip */
export async function activateVip(options?: { [key: string]: any }) {
  return request<BaseResponse<boolean>>('/payment/activate-vip', {
    method: 'POST',
    ...(options || {}),
  })
}

/** 获取当前用户支付记录 GET /payment/records */
export async function getPaymentRecords(options?: { [key: string]: any }) {
  return request<BaseResponse<PaymentRecordVO[]>>('/payment/records', {
    method: 'GET',
    ...(options || {}),
  })
}

/** 申请退款（仅 VIP 会员可调） POST /payment/refund?reason=... */
export async function refundPayment(reason?: string, options?: { [key: string]: any }) {
  return request<BaseResponse<boolean>>('/payment/refund', {
    method: 'POST',
    params: reason ? { reason } : {},
    ...(options || {}),
  })
}