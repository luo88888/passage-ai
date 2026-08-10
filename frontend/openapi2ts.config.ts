/**
 * 中文 tag → 生成文件名（同 controller 合并）。openapi2ts 默认按 tag 生成文件，
 * 这里把后端 13 个中文 tag 收敛到前端按业务域划分的 controller。
 */
const TAG_FILE_MAP = {
  文章管理: 'articleController',
  用户管理: 'userController',
  支付管理: 'paymentController',
  支付回调: 'paymentController',
  积分: 'pointsController',
  积分管理: 'pointsController',
  模型计价管理: 'pointsController',
  意见反馈: 'feedbackController',
  意见反馈管理: 'feedbackController',
  站内信: 'messageController',
  站内信管理: 'messageController',
  统计分析: 'statisticsController',
  健康检查: 'healthController',
}

/**
 * operationId 短名 → 函数名 override。FastAPI 的 operationId 为
 * `{snake}_api_{path}_{method}`，默认提取 `_api_` 前段并转 camelCase。
 * 部分接口的短名与现有调用方不一致，这里显式对齐（key 为 operationId 的短名前段）。
 */
const FUNCTION_OVERRIDES = {
  // 登录/注册/登出：operationId 短名是 login/register/logout，现有函数名带 user 前缀
  login: 'userLogin',
  register: 'userRegister',
  logout: 'userLogout',
  // 文章相关：get_execution_logs / get_creation_options 短名已是期望形式，仅作显式声明
  get_execution_logs: 'getExecutionLogs',
  get_creation_options: 'getCreationOptions',
  // 支付：create_vip_payment_session / refund 短名与现有函数名不一致
  create_vip_payment_session: 'createVipSession',
  refund: 'refundPayment',
  // 积分：短名与现有函数名不一致（现有带 Points/Admin 前缀）
  get_points_overview: 'getAdminPointsOverview',
  get_usage_stats: 'getPointsUsageStats',
  list_transactions: 'listPointsTransactions',
  list_user_transactions: 'listAdminPointsTransactions',
  list_usage: 'listAdminPointsUsage',
  adjust_user_points: 'adminAdjustPoints',
  // 站内信：mark_message_read / get_unread_count 短名与现有 readMessage / getMessageUnreadCount 不一致
  mark_message_read: 'readMessage',
  get_unread_count: 'getMessageUnreadCount',
  // 统计：get_statistics 短名现有为 getStatisticsOverview
  get_statistics: 'getStatisticsOverview',
  // 头像上传：upload_avatar 现有为 uploadUserAvatar
  upload_avatar: 'uploadUserAvatar',
}

/** snake_case → camelCase */
function toCamel(s) {
  return s.replace(/_([a-z])/g, (_, c) => c.toUpperCase())
}

/**
 * 从 operationId 提取短函数名：取 `_api_` 之前的部分（FastAPI 路径前缀即操作短名），
 * 再走 override / camelCase 转换。
 */
function shortFunctionName(operationId) {
  const short = operationId.split('_api_')[0] ?? operationId
  return FUNCTION_OVERRIDES[short] ?? toCamel(short)
}

export default {
  requestLibPath: "import request from '@/request'",
  schemaPath: '../../../../openapi.json',
  serversPath: './src',
  hook: {
    // 中文 tag → 生成文件名。openapi2ts 按 tag 生成文件，这里把后端 13 个中文 tag
    // 收敛到前端按业务域划分的 controller（同 tag 的操作归入同一文件）。
    customFileNames: (operationObject) => {
      const tag = operationObject.tags?.[0]
      const mapped = TAG_FILE_MAP[tag]
      return mapped ? [mapped] : undefined
    },
    // 类名用文件名（生成器 index.ts 引用）。文件名已是 articleController 形式，
    // 这里确保类名与文件名一致（openapi2ts 默认首字母大写文件名的类名不一致，此处显式对齐）。
    customClassName: (tagName) => tagName,
    customFunctionName: (data) => (data.operationId ? shortFunctionName(data.operationId) : 'request'),
    // 移除 SESSION cookie 参数 + 路径参数 snake_case → camelCase。
    // 后端 FastAPI 用 {task_id}，前端调用方统一用 {taskId}，在数据源统一转换可避免每个 controller 手改。
    afterOpenApiDataInited: (openAPIData) => {
      const paths = openAPIData.paths ?? {}
      const snakeToCamel = (s) => s.replace(/_([a-z])/g, (_, c) => c.toUpperCase())
      for (const [pathKey, pathItem] of Object.entries(paths)) {
        const newPathKey = pathKey.replace(/\{([^}]+)\}/g, (_, name) => `{${snakeToCamel(name)}}`)
        for (const method of ['get', 'post', 'put', 'delete']) {
          const op = pathItem?.[method]
          if (!op) continue
          // 移除 SESSION cookie 参数
          if (op.parameters) {
            op.parameters = op.parameters.filter((p) => !('name' in p && p.name === 'SESSION'))
            // 路径参数名 snake → camel（仅影响 path 参数；query 参数保留原样）
            for (const p of op.parameters) {
              if ('name' in p && p.in === 'path') {
                p.name = snakeToCamel(p.name)
              }
            }
          }
        }
        if (newPathKey !== pathKey) {
          delete paths[pathKey]
          paths[newPathKey] = pathItem
        }
      }
      return openAPIData
    },
  },
}
