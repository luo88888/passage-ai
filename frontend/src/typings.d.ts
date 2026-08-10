// 由 openapi 快照（frontend/openapi.json）生成的 API 类型声明
// 注意：本文件为手动维护 + 脚本生成混合；重新生成请执行 npm run openapi2ts 并核对
declare namespace API {
  // ==================== 通用响应包装 ====================
  type BaseResponse<T> = { code: number; data: T; message?: string }
  type PageResult<T> = { records: T[]; total: number }

  type AdminFeedbackVO = {
  id?: number;
  userId?: number;
  type?: string;
  content?: string;
  contact?: string | null;
  imageUrls?: string[] | null;
  status?: string;
  replyContent?: string | null;
  replyUserId?: number | null;
  replyTime?: string | null;
  createTime?: string;
  updateTime?: string | null;
  userAccount?: string | null;
  userName?: string | null;
}

  type AdminMessageSendRequest = {
  targetType?: string;
  userIds?: number[] | null;
  type?: string;
  title?: string;
  content?: string | null;
  link?: string | null;
}

  type AdminPointsAdjustRequest = {
  userId?: number;
  amount?: number;
  description?: string;
}

  type AdminPointsTransactionsRequest = {
  current?: number;
  pageSize?: number;
  sortField?: string | null;
  sortOrder?: string | null;
  type?: string | null;
  startTime?: string | null;
  endTime?: string | null;
  minAmount?: number | null;
  maxAmount?: number | null;
  userId?: number;
}

  type AdminUsageQueryRequest = {
  current?: number;
  pageSize?: number;
  sortField?: string | null;
  sortOrder?: string | null;
  userId?: number | null;
  category?: string | null;
  model?: string | null;
  startTime?: string | null;
  endTime?: string | null;
}

  type AgentExecutionStatsVO = {
  taskId?: string;
  userId?: number | null;
  model?: string | null;
  totalDurationMs?: number;
  agentCount?: number;
  agentDurations?: { [key: string]: number };
  overallStatus?: string;
  logs?: AgentLogVO[];
}

  type AgentLogVO = {
  id?: number;
  taskId?: string;
  userId?: number | null;
  model?: string | null;
  agentName?: string;
  startTime?: string;
  endTime?: string | null;
  durationMs?: number | null;
  status?: string;
  errorMessage?: string | null;
  prompt?: string | null;
  inputData?: string | null;
  outputData?: string | null;
  createTime?: string;
  updateTime?: string;
}

  type ArticleAiModifyOutlineRequest = {
  taskId?: string;
  modifySuggestion?: string;
}

  type ArticleConfirmOutlineRequest = {
  taskId?: string;
  outline?: OutlineSection[];
}

  type ArticleConfirmTitleRequest = {
  taskId?: string;
  selectedMainTitle?: string;
  selectedSubTitle?: string;
  userDescription?: string | null;
}

  type ArticleCreateRequest = {
  topic?: string;
  style?: string | null;
  genre?: string | null;
  languageStyle?: string | null;
  wordCount?: number | null;
  enabledImageMethods?: string[] | null;
}

  type ArticleQueryRequest = {
  current?: number;
  pageSize?: number;
  sortField?: string | null;
  sortOrder?: string | null;
  id?: number | null;
  taskId?: string | null;
  userId?: number | null;
  topic?: string | null;
  status?: string | null;
  statuses?: string[] | null;
}

  type ArticleVO = {
  id?: number;
  taskId?: string;
  userId?: number;
  topic?: string;
  userDescription?: string | null;
  style?: string | null;
  genre?: string | null;
  languageStyle?: string | null;
  wordCount?: number | null;
  mainTitle?: string | null;
  subTitle?: string | null;
  titleOptions?: TitleOption[] | null;
  outline?: any[] | null;
  content?: string | null;
  fullContent?: string | null;
  researchData?: ResearchDataVO | null;
  coverImage?: string | null;
  images?: any[] | null;
  status?: string;
  phase?: string | null;
  errorMessage?: string | null;
  createTime?: string;
  completedTime?: string | null;
  updateTime?: string;
}

  type CreationOptionsVO = {
  genres?: OptionItem[];
  languageStyles?: OptionItem[];
  imageMethods?: OptionItem[];
}

  type DeleteRequest = {
  id?: number;
}

  type FeedbackReplyRequest = {
  id?: number;
  replyContent?: string | null;
  status?: string;
}

  type FeedbackStatusRequest = {
  id?: number;
  status?: string;
}

  type FeedbackSubmitRequest = {
  type?: string;
  content?: string;
  contact?: string | null;
  imageUrls?: string[] | null;
}

  type FeedbackVO = {
  id?: number;
  userId?: number;
  type?: string;
  content?: string;
  contact?: string | null;
  imageUrls?: string[] | null;
  status?: string;
  replyContent?: string | null;
  replyUserId?: number | null;
  replyTime?: string | null;
  createTime?: string;
  updateTime?: string | null;
}

  type HTTPValidationError = {
  detail?: ValidationError[];
}

  type LoginUserVO = {
  id?: number;
  userAccount?: string;
  userName?: string | null;
  userAvatar?: string | null;
  userProfile?: string | null;
  userRole?: string;
  quota?: number | null;
  points?: number | null;
  pointsVersion?: number | null;
  activeTaskCount?: number | null;
  vipTime?: string | null;
  createTime?: string;
  updateTime?: string;
}

  type MessageDeleteRequest = {
  ids?: number[];
}

  type MessageReadRequest = {
  ids?: number[] | null;
  all?: boolean;
}

  type MessageUnreadCountVO = {
  count?: number;
}

  type MessageVO = {
  id?: number;
  userId?: number;
  type?: string;
  title?: string;
  content?: string | null;
  link?: string | null;
  relatedId?: number | null;
  isRead?: boolean;
  readTime?: string | null;
  createTime?: string;
}

  type ModelPricingSaveRequest = {
  category?: string;
  provider?: string;
  model?: string;
  agentName?: string | null;
  inputPricePer1k?: number;
  outputPricePer1k?: number;
  pricePerImage?: number;
  enabled?: boolean;
}

  type ModelPricingUpdateRequest = {
  id?: number;
  category?: string;
  provider?: string;
  model?: string;
  agentName?: string | null;
  inputPricePer1k?: number;
  outputPricePer1k?: number;
  pricePerImage?: number;
  enabled?: boolean;
}

  type ModelPricingVO = {
  id?: number;
  category?: string;
  provider?: string;
  model?: string;
  agentName?: string | null;
  inputPricePer1k?: number;
  outputPricePer1k?: number;
  pricePerImage?: number;
  enabled?: boolean;
}

  type ModelUsageStatsVO = {
  category?: string;
  provider?: string;
  model?: string;
  callCount?: number;
  inputTokens?: number;
  outputTokens?: number;
  imageCount?: number;
  costPoints?: number;
}

  type OptionItem = {
  value?: string;
  label?: string;
  description?: string | null;
  vipOnly?: boolean;
}

  type OutlineSection = {
  section?: number;
  title?: string;
  points?: string[];
  wordCount?: number | null;
}

  type PaymentRecordVO = {
  id?: number;
  userId?: number;
  stripeSessionId?: string | null;
  stripePaymentIntentId?: string | null;
  amount?: number;
  currency?: string;
  status?: string;
  productType?: string;
  description?: string | null;
  refundTime?: string | null;
  refundReason?: string | null;
  createTime?: string;
  updateTime?: string;
}

  type PointsBalanceVO = {
  balance?: number;
  totalEarned?: number;
  totalConsumed?: number;
  checkedInToday?: boolean;
}

  type PointsCheckinVO = {
  checkedIn?: boolean;
  gained?: number;
  balance?: number;
}

  type PointsOverviewVO = {
  userCount?: number;
  totalEarned?: number;
  totalConsumed?: number;
  totalBalance?: number;
  usageRecordCount?: number;
  totalCostPoints?: number;
  todayCheckinCount?: number;
  todayCheckinPoints?: number;
}

  type PointsTransactionQueryRequest = {
  current?: number;
  pageSize?: number;
  sortField?: string | null;
  sortOrder?: string | null;
  type?: string | null;
  startTime?: string | null;
  endTime?: string | null;
  minAmount?: number | null;
  maxAmount?: number | null;
}

  type ResearchArticleVO = {
  title?: string;
  url?: string;
  summary?: string;
  publishTime?: string | null;
  source?: string | null;
  author?: string | null;
  tags?: string[];
}

  type ResearchDataVO = {
  requirement?: string | null;
  searchQueriesUsed?: string[];
  articles?: ResearchArticleVO[];
}

  type StatisticsVO = {
  todayCount?: number;
  weekCount?: number;
  monthCount?: number;
  totalCount?: number;
  successRate?: number;
  avgDurationMs?: number;
  activeUserCount?: number;
  totalUserCount?: number;
  vipUserCount?: number;
  quotaUsed?: number;
  totalQuota?: number;
}

  type TitleOption = {
  mainTitle?: string;
  subTitle?: string;
}

  type UserAddRequest = {
  userAccount?: string;
  userPassword?: string;
  userName?: string | null;
  userAvatar?: string | null;
  userProfile?: string | null;
  userRole?: string;
}

  type UserChangePasswordRequest = {
  oldPassword?: string;
  newPassword?: string;
  checkPassword?: string;
}

  type UserLoginRequest = {
  userAccount?: string;
  userPassword?: string;
}

  type UserProfileUpdateRequest = {
  userName?: string | null;
  userAvatar?: string | null;
  userProfile?: string | null;
}

  type UserProfileVO = {
  id?: number;
  userAccount?: string;
  userName?: string | null;
  userAvatar?: string | null;
  userProfile?: string | null;
  userRole?: string;
  quota?: number | null;
  points?: number | null;
  activeTaskCount?: number | null;
  vipTime?: string | null;
  createTime?: string;
  articleCount?: number;
}

  type UserQueryRequest = {
  current?: number;
  pageSize?: number;
  sortField?: string | null;
  sortOrder?: string | null;
  id?: number | null;
  userAccount?: string | null;
  userName?: string | null;
  userProfile?: string | null;
  userRole?: string | null;
}

  type UserRegisterRequest = {
  userAccount?: string;
  userPassword?: string;
  checkPassword?: string;
}

  type UserUpdateRequest = {
  id?: number;
  userName?: string | null;
  userAvatar?: string | null;
  userProfile?: string | null;
  userRole?: string | null;
}

  type UserVO = {
  id?: number;
  userAccount?: string;
  userName?: string | null;
  userAvatar?: string | null;
  userProfile?: string | null;
  userRole?: string;
  quota?: number | null;
  points?: number | null;
  vipTime?: string | null;
  createTime?: string;
}

  type ValidationError = {
  loc?: string | number[];
  msg?: string;
  type?: string;
}

  type VipPlanVO = {
  productType?: string;
  price?: number;
  currency?: string;
  title?: string;
  description?: string;
  privileges?: string[];
}

  // ==================== BaseResponse 具体别名 ====================
  type BaseResponseString = BaseResponse<string>
  type BaseResponseLong = BaseResponse<number>
  type BaseResponseBoolean = BaseResponse<boolean>
  type BaseResponseVoid = BaseResponse<null>
  type BaseResponseArticleVO = BaseResponse<ArticleVO>
  type BaseResponseUser = BaseResponse<UserVO>
  type BaseResponseUserVO = BaseResponse<UserVO>
  type BaseResponseLoginUserVO = BaseResponse<LoginUserVO>
  type BaseResponseUserProfileVO = BaseResponse<UserProfileVO>
  type BaseResponseUserListPageVO = BaseResponse<PageResult<UserVO>>
  type BaseResponsePageUserVO = BaseResponse<PageResult<UserVO>>
  type BaseResponsePageArticleVO = BaseResponse<PageResult<ArticleVO>>
  type BaseResponseFeedbackVO = BaseResponse<FeedbackVO>
  type BaseResponseFeedbackPageVO = BaseResponse<PageResult<FeedbackVO>>
  type BaseResponseAdminFeedbackVO = BaseResponse<AdminFeedbackVO>
  type BaseResponseAdminFeedbackPageVO = BaseResponse<PageResult<AdminFeedbackVO>>
  type BaseResponseMessageVO = BaseResponse<MessageVO>
  type BaseResponseMessagePageVO = BaseResponse<PageResult<MessageVO>>
  type BaseResponseMessageUnreadCountVO = BaseResponse<MessageUnreadCountVO>
  type BaseResponseAdminMessagePageVO = BaseResponse<PageResult<MessageVO>>
  type BaseResponsePointsBalanceVO = BaseResponse<PointsBalanceVO>
  type BaseResponsePointsCheckinVO = BaseResponse<PointsCheckinVO>
  type BaseResponsePointsOverviewVO = BaseResponse<PointsOverviewVO>
  type BaseResponsePointsTransactionPageVO = BaseResponse<PageResult<PointsTransactionVO>>
  type BaseResponseStatisticsVO = BaseResponse<StatisticsVO>
  type BaseResponseListModelPricingVO = BaseResponse<ModelPricingVO[]>
  type BaseResponseListModelUsageStatsVO = BaseResponse<ModelUsageStatsVO[]>
  type BaseResponseAdminUsagePageVO = BaseResponse<PageResult<ModelUsageRecordVO>>
  type SseEmitter = unknown

  // ==================== 请求 Params 类型 ====================
  // 统一带 SESSION cookie 参数 + 索引签名，兼容各 GET 接口
  type getArticleParams = {
    taskId?: string;
    SESSION?: string | null
    [key: string]: any
  }

  type getProgressParams = {
    taskId?: string;
    after?: number;
    SESSION?: string | null
    [key: string]: any
  }

  type getUserByIdParams = {
    id?: number;
    SESSION?: string | null
    [key: string]: any
  }

  type getUserVOByIdParams = {
    id?: number;
    SESSION?: string | null
    [key: string]: any
  }

  type getPointsUsageStatsParams = {
    startTime?: string | null;
    endTime?: string | null;
    SESSION?: string | null
    [key: string]: any
  }

  type pageMyFeedbackParams = {
    current?: number;
    pageSize?: number;
    type?: string | null;
    status?: string | null;
    SESSION?: string | null
    [key: string]: any
  }

  type adminPageFeedbackParams = {
    current?: number;
    pageSize?: number;
    keyword?: string | null;
    type?: string | null;
    status?: string | null;
    startTime?: string | null;
    endTime?: string | null;
    SESSION?: string | null
    [key: string]: any
  }

  type pageMessageParams = {
    current?: number;
    pageSize?: number;
    type?: string | null;
    SESSION?: string | null
    [key: string]: any
  }

  type adminPageMessageParams = {
    current?: number;
    pageSize?: number;
    type?: string | null;
    keyword?: string | null;
    SESSION?: string | null
    [key: string]: any
  }
  // ==================== 后端未在 OpenAPI 暴露的类型（列表接口返回 BaseResponse[dict]，手动补充） ====================
  type PointsTransactionVO = {
  id?: number;
  userId?: number;
  taskId?: string | null;
  type?: string;
  amount?: number;
  balanceAfter?: number;
  description?: string | null;
  createTime?: string;
}

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
}

}
