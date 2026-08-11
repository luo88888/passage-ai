// ==================== 手工维护类型 ====================
// 后端未在 OpenAPI 暴露的类型（列表接口返回 BaseResponse[dict]，手动补充）。
// 注意：此文件必须放在 src/api/ 之外——openapi2ts 生成前会 rimraf 清空 src/api/**，
// 放 src/api/ 下会被覆盖删除；本文件与生成的 typings.d.ts 通过 namespace 合并。
declare namespace API {
  type PointsTransactionVO = {
    id?: number;
    userId?: number;
    taskId?: string | null;
    type?: string;
    amount?: number;
    balanceAfter?: number;
    description?: string | null;
    createTime?: string;
  };

  type ModelUsageRecordVO = {
    id?: number;
    userId?: number;
    taskId?: string | null;
    category?: string;
    provider?: string;
    model?: string;
    agentName?: string | null;
    callCount?: number;
    inputTokens?: number | null;
    outputTokens?: number | null;
    imageCount?: number | null;
    costPoints?: number;
    status?: string;
    startTime?: string;
    endTime?: string | null;
    createTime?: string;
  };
}
