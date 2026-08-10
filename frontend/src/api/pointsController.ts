// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** List Model Pricing 查询全部模型计价配置（仅管理员） GET /admin/model-pricing */
export async function listModelPricing(options?: { [key: string]: any }) {
  return request<API.BaseResponseListModelPricingVO_>("/admin/model-pricing", {
    method: "GET",
    ...(options || {}),
  });
}

/** Update Model Pricing 更新模型计价配置（按 id，仅管理员） PUT /admin/model-pricing */
export async function updateModelPricing(
  body: API.ModelPricingUpdateRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseBool_>("/admin/model-pricing", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Create Model Pricing 新增模型计价配置（仅管理员） POST /admin/model-pricing */
export async function createModelPricing(
  body: API.ModelPricingSaveRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseInt_>("/admin/model-pricing", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Adjust User Points 手工调整用户积分（正=赠送，负=扣减，记 ADMIN_ADJUST 流水） POST /admin/points/adjust */
export async function adminAdjustPoints(
  body: API.AdminPointsAdjustRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseInt_>("/admin/points/adjust", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Get Points Overview 全局积分/用量看板（仅管理员） GET /admin/points/overview */
export async function getAdminPointsOverview(options?: { [key: string]: any }) {
  return request<API.BaseResponsePointsOverviewVO_>("/admin/points/overview", {
    method: "GET",
    ...(options || {}),
  });
}

/** List User Transactions 分页查询指定用户的积分流水（仅管理员，用于积分管理查看流水） POST /admin/points/transactions */
export async function listAdminPointsTransactions(
  body: API.AdminPointsTransactionsRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseDict_>("/admin/points/transactions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** List Usage 分页查询模型用量记录（按用户/类别/模型/时间筛选，仅管理员） POST /admin/points/usage */
export async function listAdminPointsUsage(
  body: API.AdminUsageQueryRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseDict_>("/admin/points/usage", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Get Points Balance 查询当前积分余额（余额 + 累计获得/消耗 + 今日签到状态） GET /points/balance */
export async function getPointsBalance(options?: { [key: string]: any }) {
  return request<API.BaseResponsePointsBalanceVO_>("/points/balance", {
    method: "GET",
    ...(options || {}),
  });
}

/** Checkin 每日签到（Redis SETNX 防重复，赠送 10 积分，记 SIGN_IN 流水） POST /points/checkin */
export async function checkin(options?: { [key: string]: any }) {
  return request<API.BaseResponsePointsCheckinVO_>("/points/checkin", {
    method: "POST",
    ...(options || {}),
  });
}

/** List Transactions 分页查询积分明细（type/时间/金额筛选） POST /points/transactions */
export async function listPointsTransactions(
  body: API.PointsTransactionQueryRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseDict_>("/points/transactions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Get Usage Stats 查询当前用户各模型用量统计（按 model 聚合次数/token/积分，可按时间范围筛选） GET /points/usage/stats */
export async function getPointsUsageStats(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getPointsUsageStatsParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseListModelUsageStatsVO_>(
    "/points/usage/stats",
    {
      method: "GET",
      params: {
        ...params,
      },
      ...(options || {}),
    }
  );
}
