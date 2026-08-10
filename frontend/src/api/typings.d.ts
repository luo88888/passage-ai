declare namespace API {
  type AdminFeedbackVO = {
    /** Id */
    id: number;
    /** Userid */
    userId: number;
    /** Type */
    type: string;
    /** Content */
    content: string;
    /** Contact */
    contact?: string | null;
    /** Imageurls */
    imageUrls?: string[] | null;
    /** Status */
    status: string;
    /** Replycontent */
    replyContent?: string | null;
    /** Replyuserid */
    replyUserId?: number | null;
    /** Replytime */
    replyTime?: string | null;
    /** Createtime */
    createTime: string;
    /** Updatetime */
    updateTime?: string | null;
    /** Useraccount 提交用户账号 */
    userAccount?: string | null;
    /** Username 提交用户昵称 */
    userName?: string | null;
  };

  type adminGetFeedbackParams = {
    feedbackId: number;
  };

  type AdminMessageSendRequest = {
    /** Targettype 收件人类型：SINGLE/BATCH/ALL */
    targetType: string;
    /** Userids 目标用户ID列表（ALL 时忽略） */
    userIds?: number[] | null;
    /** Type 消息类型：SYSTEM/FEEDBACK/VIP/POINTS */
    type?: string;
    /** Title 标题 */
    title: string;
    /** Content 内容 */
    content?: string | null;
    /** Link 跳转链接（前端路由） */
    link?: string | null;
  };

  type adminPageFeedbackParams = {
    /** 当前页码 */
    current?: number;
    /** 每页大小 */
    pageSize?: number;
    /** 关键字（匹配用户账号/昵称/反馈内容） */
    keyword?: string | null;
    /** 反馈类型筛选 */
    type?: string | null;
    /** 处理状态筛选 */
    status?: string | null;
    /** 起始时间（含） */
    startTime?: string | null;
    /** 结束时间（含） */
    endTime?: string | null;
  };

  type adminPageMessageParams = {
    /** 当前页码 */
    current?: number;
    /** 每页大小 */
    pageSize?: number;
    /** 消息类型筛选 */
    type?: string | null;
    /** 关键字（匹配标题/内容） */
    keyword?: string | null;
  };

  type AdminPointsAdjustRequest = {
    /** Userid 目标用户 ID */
    userId: number;
    /** Amount 调整积分（正=赠送，负=扣减） */
    amount: number;
    /** Description 调整说明 */
    description: string;
  };

  type AdminPointsTransactionsRequest = {
    /** Current 当前页码 */
    current?: number;
    /** Pagesize 每页大小 */
    pageSize?: number;
    /** Sortfield 排序字段 */
    sortField?: string | null;
    /** Sortorder 排序顺序 */
    sortOrder?: string | null;
    /** Type 流水类型筛选 */
    type?: string | null;
    /** Starttime 起始时间（含） */
    startTime?: string | null;
    /** Endtime 结束时间（含） */
    endTime?: string | null;
    /** Minamount 最小变动积分 */
    minAmount?: number | null;
    /** Maxamount 最大变动积分 */
    maxAmount?: number | null;
    /** Userid 目标用户 ID */
    userId: number;
  };

  type AdminUsageQueryRequest = {
    /** Current 当前页码 */
    current?: number;
    /** Pagesize 每页大小 */
    pageSize?: number;
    /** Sortfield 排序字段 */
    sortField?: string | null;
    /** Sortorder 排序顺序 */
    sortOrder?: string | null;
    /** Userid 按用户筛选 */
    userId?: number | null;
    /** Category 类别：LLM / IMAGE */
    category?: string | null;
    /** Model 模型名 */
    model?: string | null;
    /** Starttime 起始时间（含） */
    startTime?: string | null;
    /** Endtime 结束时间（含） */
    endTime?: string | null;
  };

  type AgentExecutionStatsVO = {
    /** Taskid */
    taskId: string;
    /** Userid */
    userId?: number | null;
    /** Model 模型名 */
    model?: string | null;
    /** Totaldurationms */
    totalDurationMs: number;
    /** Agentcount */
    agentCount: number;
    /** Agentdurations */
    agentDurations?: Record<string, any>;
    /** Overallstatus */
    overallStatus: string;
    /** Logs */
    logs?: AgentLogVO[];
  };

  type AgentLogVO = {
    /** Id */
    id: number;
    /** Taskid */
    taskId: string;
    /** Userid */
    userId?: number | null;
    /** Model 模型名 */
    model?: string | null;
    /** Agentname */
    agentName: string;
    /** Starttime */
    startTime: string;
    /** Endtime */
    endTime?: string | null;
    /** Durationms */
    durationMs?: number | null;
    /** Status */
    status: string;
    /** Errormessage */
    errorMessage?: string | null;
    /** Prompt */
    prompt?: string | null;
    /** Inputdata */
    inputData?: string | null;
    /** Outputdata */
    outputData?: string | null;
    /** Createtime */
    createTime: string;
    /** Updatetime */
    updateTime: string;
  };

  type ArticleAiModifyOutlineRequest = {
    /** Taskid 任务 ID */
    taskId: string;
    /** Modifysuggestion 用户的修改建议 */
    modifySuggestion: string;
  };

  type ArticleConfirmOutlineRequest = {
    /** Taskid 任务 ID */
    taskId: string;
    /** Outline 用户选择的大纲 */
    outline: OutlineSection[];
  };

  type ArticleConfirmTitleRequest = {
    /** Taskid 任务 ID */
    taskId: string;
    /** Selectedmaintitle 用户选择的主标题 */
    selectedMainTitle: string;
    /** Selectedsubtitle 用户选择的副标题 */
    selectedSubTitle: string;
    /** Userdescription 用户语言描述 */
    userDescription?: string | null;
  };

  type ArticleCreateRequest = {
    /** Topic 选题 */
    topic: string;
    /** Style 文章风格（已弃用，保留兼容前端旧请求） */
    style?: string | null;
    /** Genre 题材：news/knowledge/product/tutorial/opinion/story */
    genre?: string | null;
    /** Languagestyle 语言风格：professional/accessible/humorous/literary/formal */
    languageStyle?: string | null;
    /** Wordcount 目标字数（<=10000，为空走默认 2000） */
    wordCount?: number | null;
    /** Enabledimagemethods 允许使用的配图方式列表（为空表示可以使用全部方式） */
    enabledImageMethods?: string[] | null;
  };

  type ArticleQueryRequest = {
    /** Current 当前页码 */
    current?: number;
    /** Pagesize 每页大小 */
    pageSize?: number;
    /** Sortfield 排序字段 */
    sortField?: string | null;
    /** Sortorder 排序顺序 */
    sortOrder?: string | null;
    /** Id 文章 ID */
    id?: number | null;
    /** Taskid 任务 ID */
    taskId?: string | null;
    /** Userid 用户 ID */
    userId?: number | null;
    /** Topic 选题 */
    topic?: string | null;
    /** Status 状态（单状态，与 statuses 二选一） */
    status?: string | null;
    /** Statuses 状态列表（多状态筛选，例如“进行中”=过滤 PENDING+PROCESSING，与 status 二选一） */
    statuses?: string[] | null;
  };

  type ArticleVO = {
    /** Id */
    id: number;
    /** Taskid */
    taskId: string;
    /** Userid */
    userId: number;
    /** Topic */
    topic: string;
    /** Userdescription */
    userDescription?: string | null;
    /** Style */
    style?: string | null;
    /** Genre */
    genre?: string | null;
    /** Languagestyle */
    languageStyle?: string | null;
    /** Wordcount */
    wordCount?: number | null;
    /** Maintitle */
    mainTitle?: string | null;
    /** Subtitle */
    subTitle?: string | null;
    /** Titleoptions */
    titleOptions?: TitleOption[] | null;
    /** Outline */
    outline?: any[] | null;
    /** Content */
    content?: string | null;
    /** Fullcontent */
    fullContent?: string | null;
    /** 信息采集结果（结构化） */
    researchData?: ResearchDataVO | null;
    /** Coverimage */
    coverImage?: string | null;
    /** Images */
    images?: any[] | null;
    /** Status */
    status: string;
    /** Phase */
    phase?: string | null;
    /** Errormessage */
    errorMessage?: string | null;
    /** Createtime */
    createTime: string;
    /** Completedtime */
    completedTime?: string | null;
    /** Updatetime */
    updateTime: string;
  };

  type BaseResponseAdminFeedbackVO_ = {
    /** Code 状态码 */
    code?: number;
    /** 响应数据 */
    data?: AdminFeedbackVO | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseAgentExecutionStatsVO_ = {
    /** Code 状态码 */
    code?: number;
    /** 响应数据 */
    data?: AgentExecutionStatsVO | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseArticleVO_ = {
    /** Code 状态码 */
    code?: number;
    /** 响应数据 */
    data?: ArticleVO | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseBool_ = {
    /** Code 状态码 */
    code?: number;
    /** Data 响应数据 */
    data?: boolean | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseCreationOptionsVO_ = {
    /** Code 状态码 */
    code?: number;
    /** 响应数据 */
    data?: CreationOptionsVO | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseDict_ = {
    /** Code 状态码 */
    code?: number;
    /** Data 响应数据 */
    data?: Record<string, any> | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseFeedbackVO_ = {
    /** Code 状态码 */
    code?: number;
    /** 响应数据 */
    data?: FeedbackVO | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseInt_ = {
    /** Code 状态码 */
    code?: number;
    /** Data 响应数据 */
    data?: number | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseListModelPricingVO_ = {
    /** Code 状态码 */
    code?: number;
    /** Data 响应数据 */
    data?: ModelPricingVO[] | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseListModelUsageStatsVO_ = {
    /** Code 状态码 */
    code?: number;
    /** Data 响应数据 */
    data?: ModelUsageStatsVO[] | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseListPaymentRecordVO_ = {
    /** Code 状态码 */
    code?: number;
    /** Data 响应数据 */
    data?: PaymentRecordVO[] | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseListVipPlanVO_ = {
    /** Code 状态码 */
    code?: number;
    /** Data 响应数据 */
    data?: VipPlanVO[] | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseLoginUserVO_ = {
    /** Code 状态码 */
    code?: number;
    /** 响应数据 */
    data?: LoginUserVO | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseMessageUnreadCountVO_ = {
    /** Code 状态码 */
    code?: number;
    /** 响应数据 */
    data?: MessageUnreadCountVO | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseMessageVO_ = {
    /** Code 状态码 */
    code?: number;
    /** 响应数据 */
    data?: MessageVO | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseNoneType_ = {
    /** Code 状态码 */
    code?: number;
    /** Data 响应数据 */
    data?: null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponsePointsBalanceVO_ = {
    /** Code 状态码 */
    code?: number;
    /** 响应数据 */
    data?: PointsBalanceVO | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponsePointsCheckinVO_ = {
    /** Code 状态码 */
    code?: number;
    /** 响应数据 */
    data?: PointsCheckinVO | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponsePointsOverviewVO_ = {
    /** Code 状态码 */
    code?: number;
    /** 响应数据 */
    data?: PointsOverviewVO | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseStatisticsVO_ = {
    /** Code 状态码 */
    code?: number;
    /** 响应数据 */
    data?: StatisticsVO | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseStr_ = {
    /** Code 状态码 */
    code?: number;
    /** Data 响应数据 */
    data?: string | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseUserProfileVO_ = {
    /** Code 状态码 */
    code?: number;
    /** 响应数据 */
    data?: UserProfileVO | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BaseResponseUserVO_ = {
    /** Code 状态码 */
    code?: number;
    /** 响应数据 */
    data?: UserVO | null;
    /** Message 响应消息 */
    message?: string;
  };

  type BodyUploadAvatarApiUserAvatarUploadPost = {
    /** File */
    file: string;
  };

  type BodyUploadFeedbackImageApiFeedbackUploadPost = {
    /** File */
    file: string;
  };

  type CreationOptionsVO = {
    /** Genres 题材可选项 */
    genres?: OptionItem[];
    /** Languagestyles 语言风格可选项 */
    languageStyles: OptionItem[];
    /** Imagemethods 配图方式可选项 */
    imageMethods: OptionItem[];
  };

  type DeleteRequest = {
    /** Id 要删除的 ID */
    id: number;
  };

  type FeedbackReplyRequest = {
    /** Id 反馈 ID */
    id: number;
    /** Replycontent 回复内容（前端驼峰 replyContent） */
    replyContent?: string | null;
    /** Status 处理状态（默认 RESOLVED） */
    status?: string;
  };

  type FeedbackStatusRequest = {
    /** Id 反馈 ID */
    id: number;
    /** Status 处理状态：PENDING/PROCESSING/RESOLVED */
    status: string;
  };

  type FeedbackSubmitRequest = {
    /** Type 反馈类型：BUG/FEATURE/COMPLAINT/OTHER */
    type: string;
    /** Content 反馈内容（1~2000字） */
    content: string;
    /** Contact 联系方式（电话或邮箱） */
    contact?: string | null;
    /** Imageurls 截图URL列表（最多5张） */
    imageUrls?: string[] | null;
  };

  type FeedbackVO = {
    /** Id */
    id: number;
    /** Userid */
    userId: number;
    /** Type */
    type: string;
    /** Content */
    content: string;
    /** Contact */
    contact?: string | null;
    /** Imageurls */
    imageUrls?: string[] | null;
    /** Status */
    status: string;
    /** Replycontent */
    replyContent?: string | null;
    /** Replyuserid */
    replyUserId?: number | null;
    /** Replytime */
    replyTime?: string | null;
    /** Createtime */
    createTime: string;
    /** Updatetime */
    updateTime?: string | null;
  };

  type getArticleParams = {
    taskId: string;
  };

  type getExecutionLogsParams = {
    taskId: string;
  };

  type getFeedbackParams = {
    feedbackId: number;
  };

  type getMessageDetailParams = {
    messageId: number;
  };

  type getPointsUsageStatsParams = {
    start_time?: string | null;
    end_time?: string | null;
  };

  type getProgressParams = {
    taskId: string;
    after?: number;
  };

  type getUserByIdParams = {
    id: number;
  };

  type HTTPValidationError = {
    /** Detail */
    detail?: ValidationError[];
  };

  type LoginUserVO = {
    /** Id */
    id: number;
    /** Useraccount */
    userAccount: string;
    /** Username */
    userName?: string | null;
    /** Useravatar */
    userAvatar?: string | null;
    /** Userprofile */
    userProfile?: string | null;
    /** Userrole */
    userRole: string;
    /** Quota 剩余配额 */
    quota?: number | null;
    /** Points 积分余额 */
    points?: number | null;
    /** Pointsversion 积分账户乐观锁版本（前端实时刷新余额用） */
    pointsVersion?: number | null;
    /** Activetaskcount 进行中创作任务数（含挂起，并发限制计数） */
    activeTaskCount?: number | null;
    /** Viptime 成为会员时间 */
    vipTime?: string | null;
    /** Createtime */
    createTime: string;
    /** Updatetime */
    updateTime: string;
  };

  type MessageDeleteRequest = {
    /** Ids 要删除的消息 ID 列表 */
    ids: number[];
  };

  type MessageReadRequest = {
    /** Ids 要标记已读的消息 ID 列表 */
    ids?: number[] | null;
    /** All 是否全部标记已读 */
    all?: boolean;
  };

  type MessageUnreadCountVO = {
    /** Count 未读消息数 */
    count?: number;
  };

  type MessageVO = {
    /** Id */
    id: number;
    /** Userid */
    userId: number;
    /** Type */
    type: string;
    /** Title */
    title: string;
    /** Content */
    content?: string | null;
    /** Link */
    link?: string | null;
    /** Relatedid */
    relatedId?: number | null;
    /** Isread */
    isRead: boolean;
    /** Readtime */
    readTime?: string | null;
    /** Createtime */
    createTime: string;
  };

  type ModelPricingSaveRequest = {
    /** Category 类别：LLM / IMAGE */
    category: string;
    /** Provider 提供商 */
    provider: string;
    /** Model 模型名（LLM 用 * 通配兜底） */
    model: string;
    /** Agentname 按 Agent 细分（空=不限） */
    agentName?: string | null;
    /** Inputpriceper1K 输入 token 单价（积分/1k token） */
    inputPricePer1k?: number;
    /** Outputpriceper1K 输出 token 单价（积分/1k token） */
    outputPricePer1k?: number;
    /** Priceperimage 每张图积分（IMAGE） */
    pricePerImage?: number;
    /** Enabled 是否启用 */
    enabled?: boolean;
  };

  type ModelPricingUpdateRequest = {
    /** Id 计价配置 ID */
    id: number;
    /** Category 类别：LLM / IMAGE */
    category: string;
    /** Provider 提供商 */
    provider: string;
    /** Model 模型名 */
    model: string;
    /** Agentname 按 Agent 细分（空=不限） */
    agentName?: string | null;
    /** Inputpriceper1K 输入 token 单价（积分/1k token） */
    inputPricePer1k?: number;
    /** Outputpriceper1K 输出 token 单价（积分/1k token） */
    outputPricePer1k?: number;
    /** Priceperimage 每张图积分（IMAGE） */
    pricePerImage?: number;
    /** Enabled 是否启用 */
    enabled?: boolean;
  };

  type ModelPricingVO = {
    /** Id */
    id: number;
    /** Category */
    category: string;
    /** Provider */
    provider: string;
    /** Model */
    model: string;
    /** Agentname */
    agentName?: string | null;
    /** Inputpriceper1K */
    inputPricePer1k?: number;
    /** Outputpriceper1K */
    outputPricePer1k?: number;
    /** Priceperimage */
    pricePerImage?: number;
    /** Enabled */
    enabled?: boolean;
  };

  type ModelUsageStatsVO = {
    /** Category */
    category: string;
    /** Provider */
    provider: string;
    /** Model */
    model: string;
    /** Callcount */
    callCount?: number;
    /** Inputtokens */
    inputTokens?: number;
    /** Outputtokens */
    outputTokens?: number;
    /** Imagecount */
    imageCount?: number;
    /** Costpoints */
    costPoints?: number;
  };

  type OptionItem = {
    /** Value */
    value: string;
    /** Label */
    label: string;
    /** Description */
    description?: string | null;
    /** Viponly 是否为会员专属（配图方式中高级项为 True） */
    vipOnly?: boolean;
  };

  type OutlineSection = {
    /** Section */
    section: number;
    /** Title */
    title: string;
    /** Points */
    points: string[];
    /** Wordcount 本章目标字数（由大纲生成/用户编辑，驱动正文逐章字数） */
    wordCount?: number | null;
  };

  type pageMessageParams = {
    /** 当前页码 */
    current?: number;
    /** 每页大小 */
    pageSize?: number;
    /** 消息类型筛选：SYSTEM/FEEDBACK/VIP/POINTS */
    type?: string | null;
  };

  type pageMyFeedbackParams = {
    /** 当前页码 */
    current?: number;
    /** 每页大小 */
    pageSize?: number;
    /** 反馈类型筛选：BUG/FEATURE/COMPLAINT/OTHER */
    type?: string | null;
    /** 处理状态筛选：PENDING/PROCESSING/RESOLVED */
    status?: string | null;
  };

  type PaymentRecordVO = {
    /** Id */
    id: number;
    /** Userid */
    userId: number;
    /** Stripesessionid */
    stripeSessionId?: string | null;
    /** Stripepaymentintentid */
    stripePaymentIntentId?: string | null;
    /** Amount */
    amount: number;
    /** Currency */
    currency: string;
    /** Status */
    status: string;
    /** Producttype */
    productType: string;
    /** Description */
    description?: string | null;
    /** Refundtime */
    refundTime?: string | null;
    /** Refundreason */
    refundReason?: string | null;
    /** Createtime */
    createTime: string;
    /** Updatetime */
    updateTime: string;
  };

  type PointsBalanceVO = {
    /** Balance 当前积分余额 */
    balance?: number;
    /** Totalearned 累计获得积分 */
    totalEarned?: number;
    /** Totalconsumed 累计消耗积分 */
    totalConsumed?: number;
    /** Checkedintoday 今日是否已签到 */
    checkedInToday?: boolean;
  };

  type PointsCheckinVO = {
    /** Checkedin 本次是否签到成功 */
    checkedIn?: boolean;
    /** Gained 本次赠送积分 */
    gained?: number;
    /** Balance 签到后积分余额 */
    balance?: number;
  };

  type PointsOverviewVO = {
    /** Usercount 积分账户数 */
    userCount?: number;
    /** Totalearned 累计发放积分 */
    totalEarned?: number;
    /** Totalconsumed 累计消耗积分 */
    totalConsumed?: number;
    /** Totalbalance 全体用户当前余额合计 */
    totalBalance?: number;
    /** Usagerecordcount 模型用量记录条数 */
    usageRecordCount?: number;
    /** Totalcostpoints 用量累计折算积分 */
    totalCostPoints?: number;
    /** Todaycheckincount 今日签到人数 */
    todayCheckinCount?: number;
    /** Todaycheckinpoints 今日签到发放积分合计 */
    todayCheckinPoints?: number;
  };

  type PointsTransactionQueryRequest = {
    /** Current 当前页码 */
    current?: number;
    /** Pagesize 每页大小 */
    pageSize?: number;
    /** Sortfield 排序字段 */
    sortField?: string | null;
    /** Sortorder 排序顺序 */
    sortOrder?: string | null;
    /** Type 流水类型筛选 */
    type?: string | null;
    /** Starttime 起始时间（含） */
    startTime?: string | null;
    /** Endtime 结束时间（含） */
    endTime?: string | null;
    /** Minamount 最小变动积分 */
    minAmount?: number | null;
    /** Maxamount 最大变动积分 */
    maxAmount?: number | null;
  };

  type refundPaymentParams = {
    reason?: string | null;
  };

  type ResearchArticleVO = {
    /** Title 文章标题 */
    title: string;
    /** Url 文章原始链接 */
    url: string;
    /** Summary 基于全文内容的摘要 */
    summary: string;
    /** Publishtime 发布时间 */
    publishTime?: string | null;
    /** Source 来源媒体 */
    source?: string | null;
    /** Author 作者/机构 */
    author?: string | null;
    /** Tags 标签 */
    tags?: string[];
  };

  type ResearchDataVO = {
    /** Requirement 原始信息需求 */
    requirement?: string | null;
    /** Searchqueriesused 实际使用的搜索词 */
    searchQueriesUsed?: string[];
    /** Articles 相关新闻条目 */
    articles?: ResearchArticleVO[];
  };

  type StatisticsVO = {
    /** Todaycount */
    todayCount: number;
    /** Weekcount */
    weekCount: number;
    /** Monthcount */
    monthCount: number;
    /** Totalcount */
    totalCount: number;
    /** Successrate */
    successRate: number;
    /** Avgdurationms */
    avgDurationMs: number;
    /** Activeusercount */
    activeUserCount: number;
    /** Totalusercount */
    totalUserCount: number;
    /** Vipusercount */
    vipUserCount: number;
    /** Quotaused */
    quotaUsed: number;
    /** Totalquota */
    totalQuota?: number;
  };

  type TitleOption = {
    /** Maintitle */
    mainTitle: string;
    /** Subtitle */
    subTitle: string;
  };

  type UserAddRequest = {
    /** Useraccount 账号 */
    userAccount: string;
    /** Userpassword 密码 */
    userPassword: string;
    /** Username 用户昵称 */
    userName?: string | null;
    /** Useravatar 用户头像 */
    userAvatar?: string | null;
    /** Userprofile 用户简介 */
    userProfile?: string | null;
    /** Userrole 用户角色 */
    userRole?: string;
  };

  type UserChangePasswordRequest = {
    /** Oldpassword 原密码 */
    oldPassword: string;
    /** Newpassword 新密码 */
    newPassword: string;
    /** Checkpassword 确认新密码 */
    checkPassword: string;
  };

  type UserLoginRequest = {
    /** Useraccount 账号 */
    userAccount: string;
    /** Userpassword 密码 */
    userPassword: string;
  };

  type UserProfileUpdateRequest = {
    /** Username 用户昵称 */
    userName?: string | null;
    /** Useravatar 用户头像 URL */
    userAvatar?: string | null;
    /** Userprofile 用户简介 */
    userProfile?: string | null;
  };

  type UserProfileVO = {
    /** Id */
    id: number;
    /** Useraccount */
    userAccount: string;
    /** Username */
    userName?: string | null;
    /** Useravatar */
    userAvatar?: string | null;
    /** Userprofile */
    userProfile?: string | null;
    /** Userrole */
    userRole: string;
    /** Quota 剩余配额（历史兼容，不再作为创作门槛） */
    quota?: number | null;
    /** Points 积分余额（权威 user_points） */
    points?: number | null;
    /** Activetaskcount 进行中创作任务数（含挂起） */
    activeTaskCount?: number | null;
    /** Viptime 成为会员时间 */
    vipTime?: string | null;
    /** Createtime 注册时间 */
    createTime: string;
    /** Articlecount 创作文章总数（未删除） */
    articleCount?: number;
  };

  type UserQueryRequest = {
    /** Current 当前页码 */
    current?: number;
    /** Pagesize 每页大小 */
    pageSize?: number;
    /** Sortfield 排序字段 */
    sortField?: string | null;
    /** Sortorder 排序顺序 */
    sortOrder?: string | null;
    /** Id 用户 ID */
    id?: number | null;
    /** Useraccount 账号 */
    userAccount?: string | null;
    /** Username 用户昵称 */
    userName?: string | null;
    /** Userprofile 用户简介 */
    userProfile?: string | null;
    /** Userrole 用户角色 */
    userRole?: string | null;
  };

  type UserRegisterRequest = {
    /** Useraccount 账号 */
    userAccount: string;
    /** Userpassword 密码 */
    userPassword: string;
    /** Checkpassword 确认密码 */
    checkPassword: string;
  };

  type UserUpdateRequest = {
    /** Id 用户 ID */
    id: number;
    /** Username 用户昵称 */
    userName?: string | null;
    /** Useravatar 用户头像 */
    userAvatar?: string | null;
    /** Userprofile 用户简介 */
    userProfile?: string | null;
    /** Userrole 用户角色 */
    userRole?: string | null;
  };

  type UserVO = {
    /** Id */
    id: number;
    /** Useraccount */
    userAccount: string;
    /** Username */
    userName?: string | null;
    /** Useravatar */
    userAvatar?: string | null;
    /** Userprofile */
    userProfile?: string | null;
    /** Userrole */
    userRole: string;
    /** Quota 剩余配额 */
    quota?: number | null;
    /** Points 积分余额 */
    points?: number | null;
    /** Viptime 成为会员时间 */
    vipTime?: string | null;
    /** Createtime */
    createTime: string;
  };

  type ValidationError = {
    /** Location */
    loc: (string | number)[];
    /** Message */
    msg: string;
    /** Error Type */
    type: string;
  };

  type VipPlanVO = {
    /** Producttype 产品类型枚举值，如 VIP_PERMANENT */
    productType: string;
    /** Price 价格（美元） */
    price: number;
    /** Currency 货币，如 usd */
    currency: string;
    /** Title 套餐名称 */
    title: string;
    /** Description 套餐简短描述 */
    description: string;
    /** Privileges 会员特权文案列表 */
    privileges: string[];
  };
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
