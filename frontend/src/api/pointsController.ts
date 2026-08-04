// @ts-ignore
/* eslint-disable */
import request from '@/request'

/** GET /points/balance 当前积分余额（含今日签到状态） */
export async function getPointsBalance(options?: { [key: string]: any }) {
  return request<API.BaseResponsePointsBalanceVO>('/points/balance', {
    method: 'GET',
    ...(options || {}),
  })
}

/** POST /points/checkin 每日签到 */
export async function checkin(options?: { [key: string]: any }) {
  return request<API.BaseResponsePointsCheckinVO>('/points/checkin', {
    method: 'POST',
    ...(options || {}),
  })
}

/** POST /points/transactions 积分明细分页 */
export async function listPointsTransactions(
  body: API.PointsTransactionQueryRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponsePointsTransactionPageVO>('/points/transactions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** GET /points/usage/stats 各模型用量统计 */
export async function getPointsUsageStats(
  params: API.getPointsUsageStatsParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseListModelUsageStatsVO>('/points/usage/stats', {
    method: 'GET',
    params: {
      ...params,
    },
    ...(options || {}),
  })
}

/** POST /admin/points/transactions 指定用户积分流水（管理员） */
export async function listAdminPointsTransactions(
  body: API.AdminPointsTransactionsRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponsePointsTransactionPageVO>('/admin/points/transactions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** GET /admin/points/overview 全局积分/用量看板（管理员） */
export async function getAdminPointsOverview(options?: { [key: string]: any }) {
  return request<API.BaseResponsePointsOverviewVO>('/admin/points/overview', {
    method: 'GET',
    ...(options || {}),
  })
}

/** POST /admin/points/adjust 手工调整用户积分（管理员） */
export async function adminAdjustPoints(
  body: API.AdminPointsAdjustRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseLong>('/admin/points/adjust', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** POST /admin/points/usage 分页查询模型用量（管理员） */
export async function listAdminPointsUsage(
  body: API.AdminUsageQueryRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseAdminUsagePageVO>('/admin/points/usage', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** GET /admin/model-pricing 模型计价配置列表（管理员） */
export async function listModelPricing(options?: { [key: string]: any }) {
  return request<API.BaseResponseListModelPricingVO>('/admin/model-pricing', {
    method: 'GET',
    ...(options || {}),
  })
}

/** POST /admin/model-pricing 新增模型计价配置（管理员） */
export async function createModelPricing(
  body: API.ModelPricingSaveRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseLong>('/admin/model-pricing', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** PUT /admin/model-pricing 更新模型计价配置（管理员） */
export async function updateModelPricing(
  body: API.ModelPricingUpdateRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseBoolean>('/admin/model-pricing', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}