-- ============================================================
-- AI 文章创作平台 · 数据库全量建表脚本（一键初始化）
-- ------------------------------------------------------------
-- 用途：全新环境初始化（一次性从零建库建表）
-- 幂等性：可重复执行（CREATE ... IF NOT EXISTS）
-- 已合并历史增量脚本：create_table.sql / create_article_table.sql /
--   add_vip_payment.sql / add_phase_fields.sql / add_genre_fields.sql /
--   add_points_system.sql / add_feedback_message.sql 的全部最终结构
-- 数据库：MySQL 8.0+，utf8mb4 / utf8mb4_unicode_ci
-- ============================================================

CREATE DATABASE IF NOT EXISTS ai_passage_creator CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ai_passage_creator;

-- ============================================================
-- 1. 用户表
-- ============================================================
CREATE TABLE IF NOT EXISTS user
(
    id              bigint auto_increment comment 'id' primary key,
    userAccount     varchar(256)                        not null comment '账号',
    userPassword    varchar(512)                        not null comment '密码',
    userName        varchar(256)                        null comment '用户昵称',
    userAvatar      varchar(1024)                       null comment '用户头像',
    userProfile     varchar(512)                        null comment '用户简介',
    userRole        varchar(256) default 'user'         not null comment '用户角色：user/admin',
    quota           int          default 5              not null comment '剩余配额',
    points          int          default 0              not null comment '积分余额（冗余展示，权威以 user_points 为准）',
    activeTaskCount int          default 0              not null comment '进行中创作任务数（含挂起，并发限制计数，MySQL 权威原子计数）',
    vipTime         datetime                            null comment '成为会员时间',
    editTime        datetime     default CURRENT_TIMESTAMP not null comment '编辑时间',
    createTime      datetime     default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime      datetime     default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete        tinyint      default 0              not null comment '是否删除',
    UNIQUE KEY uk_userAccount (userAccount),
    INDEX idx_userName (userName)
) comment '用户' collate = utf8mb4_unicode_ci;

-- ============================================================
-- 2. 文章表
-- ============================================================
CREATE TABLE IF NOT EXISTS article
(
    id                  bigint auto_increment comment 'id' primary key,
    taskId              varchar(64)                     not null comment '任务ID（UUID）',
    userId              bigint                          not null comment '用户ID',
    topic               varchar(500)                    not null comment '选题',
    userDescription     text                            null comment '用户补充描述',
    enabledImageMethods json                            null comment '允许的配图方式列表（JSON格式）',
    mainTitle           varchar(200)                    null comment '主标题',
    subTitle            varchar(300)                    null comment '副标题',
    titleOptions        json                            null comment '标题方案列表（3-5个方案）',
    outline             json                            null comment '大纲（JSON格式）',
    content             text                            null comment '正文（Markdown格式）',
    fullContent         text                            null comment '完整图文（Markdown格式，含配图）',
    coverImage          varchar(512)                    null comment '封面图 URL',
    images              json                            null comment '配图列表（JSON数组）',
    style               varchar(20)                     null comment '文章风格：tech/emotional/educational/humorous（已弃用，保留兼容存量数据）',
    genre               varchar(20)                     null comment '题材：news/knowledge/product/tutorial/opinion/story',
    languageStyle       varchar(20)                     null comment '语言风格：professional/accessible/humorous/literary/formal',
    wordCount           int                             null comment '目标字数（<=10000）',
    status              varchar(20) default 'PENDING'   not null comment '状态：PENDING/PROCESSING/COMPLETED/FAILED',
    phase               varchar(40) default 'PENDING'   not null comment '阶段：PENDING/TITLE_GENERATING/TITLE_SELECTING/OUTLINE_GENERATING/OUTLINE_EDITING/CONTENT_GENERATING',
    errorMessage        text                            null comment '错误信息',
    createTime          datetime    default CURRENT_TIMESTAMP not null comment '创建时间',
    completedTime       datetime                        null comment '完成时间',
    updateTime          datetime    default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete            tinyint     default 0           not null comment '是否删除',
    UNIQUE KEY uk_taskId (taskId),
    INDEX idx_userId (userId),
    INDEX idx_status (status),
    INDEX idx_createTime (createTime),
    INDEX idx_userId_status (userId, status)
) comment '文章表' collate = utf8mb4_unicode_ci;

-- ============================================================
-- 3. 智能体执行日志表
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_log
(
    id           bigint auto_increment comment 'id' primary key,
    taskId       varchar(64)                     not null comment '任务ID',
    userId       bigint                          null comment '用户ID',
    agentName    varchar(64)                     not null comment '智能体名称',
    model        varchar(64)                     null comment '模型名',
    startTime    datetime                        not null comment '开始时间',
    endTime      datetime                        null comment '结束时间',
    durationMs   int                             null comment '耗时（毫秒）',
    status       varchar(20)                     not null comment '状态：RUNNING/SUCCESS/FAILED',
    errorMessage text                            null comment '错误信息',
    prompt       text                            null comment '使用的Prompt',
    inputData    json                            null comment '输入数据（JSON格式）',
    outputData   json                            null comment '输出数据（JSON格式）',
    createTime   datetime    default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime   datetime    default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete     tinyint     default 0           not null comment '是否删除',
    INDEX idx_taskId (taskId),
    INDEX idx_agentName (agentName),
    INDEX idx_status (status),
    INDEX idx_createTime (createTime)
) comment '智能体执行日志表' collate = utf8mb4_unicode_ci;

-- ============================================================
-- 4. 支付记录表
-- ============================================================
CREATE TABLE IF NOT EXISTS payment_record
(
    id                     bigint auto_increment primary key comment '主键',
    userId                 bigint          not null comment '用户ID',
    stripeSessionId        varchar(128)    null comment 'Stripe Checkout Session ID，关联支付会话',
    stripePaymentIntentId  varchar(128)    null comment 'Stripe 支付意向ID，退款时用到',
    amount                 decimal(10, 2)  not null comment '金额（美元）',
    currency               varchar(8)      default 'usd' comment '货币',
    status                 varchar(32)     not null comment '状态：PENDING/SUCCEEDED/FAILED/REFUNDED',
    productType            varchar(32)     not null comment '产品类型：VIP_PERMANENT',
    description            varchar(256)    null comment '描述',
    refundTime             datetime        null comment '退款时间',
    refundReason           varchar(512)    null comment '退款原因',
    createTime             datetime        default CURRENT_TIMESTAMP comment '创建时间',
    updateTime             datetime        default CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP comment '更新时间',
    INDEX idx_userId (userId),
    INDEX idx_stripeSessionId (stripeSessionId),
    INDEX idx_status (status),
    INDEX idx_createTime (createTime)
) comment '支付记录表' collate = utf8mb4_unicode_ci;

-- ============================================================
-- 5. 用户积分账户表（每个用户一条，balance 权威，version 乐观锁）
-- ============================================================
CREATE TABLE IF NOT EXISTS user_points
(
    id            bigint auto_increment primary key comment '主键',
    userId        bigint      not null comment '用户ID',
    balance       int         not null default 0 comment '当前积分余额',
    totalEarned   int         not null default 0 comment '累计获得积分',
    totalConsumed int         not null default 0 comment '累计消耗积分',
    version       int         not null default 0 comment '乐观锁版本号',
    createTime    datetime    default CURRENT_TIMESTAMP comment '创建时间',
    updateTime    datetime    default CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP comment '更新时间',
    UNIQUE KEY uk_userId (userId)
) comment '用户积分账户' collate = utf8mb4_unicode_ci;

-- ============================================================
-- 6. 积分流水表（正=获得，负=消耗）
-- ============================================================
CREATE TABLE IF NOT EXISTS points_transaction
(
    id           bigint auto_increment primary key comment '主键',
    userId       bigint      not null comment '用户ID',
    taskId       varchar(64) null comment '关联任务ID',
    type         varchar(32) not null comment '类型：REGISTER/SIGN_IN/RECHARGE/USAGE_RESERVE/USAGE_SETTLE/USAGE_REFUND/ADMIN_ADJUST',
    amount       int         not null comment '变动积分（正=获得，负=消耗）',
    balanceAfter int         not null comment '变动后余额',
    description  varchar(255) null comment '描述',
    createTime   datetime    default CURRENT_TIMESTAMP comment '创建时间',
    INDEX idx_userId_time (userId, createTime),
    INDEX idx_taskId (taskId)
) comment '积分流水' collate = utf8mb4_unicode_ci;

-- ============================================================
-- 7. 模型用量记录表（各模型使用情况统计核心表）
-- ============================================================
CREATE TABLE IF NOT EXISTS model_usage_record
(
    id           bigint auto_increment primary key comment '主键',
    userId       bigint      not null comment '用户ID',
    taskId       varchar(64) null comment '任务ID',
    category     varchar(16) not null comment '类别：LLM / IMAGE',
    provider     varchar(32) not null comment '提供商：Xiaomi/DeepSeek/Zhipu/NanoBanana',
    model        varchar(64) not null comment '模型名',
    agentName    varchar(50) null comment '智能体名称',
    callCount    int         not null default 1 comment '调用次数',
    inputTokens  int         null comment '输入token（LLM）',
    outputTokens int         null comment '输出token（LLM）',
    imageCount   int         null comment '生成图片张数（IMAGE）',
    costPoints   int         not null default 0 comment '本记录消耗积分',
    status       varchar(16) not null default 'SUCCESS' comment 'SUCCESS/FAILED',
    startTime    datetime    not null comment '开始时间',
    endTime      datetime    null comment '结束时间',
    createTime   datetime    default CURRENT_TIMESTAMP comment '创建时间',
    INDEX idx_userId_model (userId, model, createTime),
    INDEX idx_taskId (taskId)
) comment '模型用量记录' collate = utf8mb4_unicode_ci;

-- ============================================================
-- 8. 模型计价表（agentName 空串=不限，model 为 * 通配兜底）
-- ============================================================
CREATE TABLE IF NOT EXISTS model_pricing
(
    id               bigint auto_increment primary key comment '主键',
    category         varchar(16)    not null comment '类别：LLM / IMAGE',
    provider         varchar(32)    not null comment '提供商',
    model            varchar(64)    not null comment '模型名（LLM用通配符 * 兜底）',
    agentName        varchar(50)    not null default '' comment '按Agent细分（空=不限）',
    inputPricePer1k  decimal(10, 4) not null default 0 comment '输入token单价（积分/1k token，LLM，允许小数）',
    outputPricePer1k decimal(10, 4) not null default 0 comment '输出token单价（积分/1k token，LLM，允许小数）',
    pricePerImage    decimal(10, 2) not null default 0 comment '每张图积分（IMAGE）',
    enabled          tinyint        not null default 1 comment '是否启用',
    updateTime       datetime       default CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP comment '更新时间',
    UNIQUE KEY uk_model (category, provider, model, agentName)
) comment '模型计价' collate = utf8mb4_unicode_ci;

-- ============================================================
-- 9. 意见反馈表（M1：意见反馈与站内信）
-- ============================================================
CREATE TABLE IF NOT EXISTS feedback
(
    id           BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    userId       BIGINT       NOT NULL COMMENT '提交用户ID',
    type         VARCHAR(32)  NOT NULL DEFAULT 'OTHER' COMMENT '类型：BUG/FEATURE/COMPLAINT/OTHER',
    content      TEXT         NOT NULL COMMENT '反馈内容',
    contact      VARCHAR(128) NULL COMMENT '联系方式（电话/邮箱）',
    imageUrls    json NULL COMMENT '截图URL列表（JSON数组，最多5张）',
    status       VARCHAR(32)  NOT NULL DEFAULT 'PENDING' COMMENT '状态：PENDING/PROCESSING/RESOLVED',
    replyContent TEXT         NULL COMMENT '管理员回复内容',
    replyUserId  BIGINT       NULL COMMENT '回复管理员ID',
    replyTime    DATETIME     NULL COMMENT '回复时间',
    createTime   DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updateTime   DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    isDelete     TINYINT      DEFAULT 0 NOT NULL COMMENT '是否删除',
    INDEX idx_userId (userId, createTime),
    INDEX idx_status (status, createTime)
) COMMENT '意见反馈' COLLATE = utf8mb4_unicode_ci;

-- ============================================================
-- 10. 站内信表（M1：意见反馈与站内信）
-- ============================================================
CREATE TABLE IF NOT EXISTS message
(
    id         BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    userId     BIGINT       NOT NULL COMMENT '收件用户ID（全体广播写时展开为每用户一行）',
    type       VARCHAR(32)  NOT NULL DEFAULT 'SYSTEM' COMMENT '类型：SYSTEM/FEEDBACK/VIP/POINTS',
    title      VARCHAR(200) NOT NULL COMMENT '标题',
    content    TEXT         NULL COMMENT '内容',
    link       VARCHAR(512) NULL COMMENT '跳转链接（前端路由）',
    relatedId  BIGINT       NULL COMMENT '关联业务ID（如反馈ID）',
    senderId   BIGINT       NULL COMMENT '发送者用户ID（管理员主动发信为管理员ID；系统自动触发为空）',
    isRead     TINYINT      DEFAULT 0 NOT NULL COMMENT '是否已读',
    readTime   DATETIME     NULL COMMENT '阅读时间',
    createTime DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    isDelete   TINYINT      DEFAULT 0 NOT NULL COMMENT '是否删除',
    INDEX idx_userId (userId, isRead, createTime),
    INDEX idx_userId_time (userId, createTime)
) COMMENT '站内信' COLLATE = utf8mb4_unicode_ci;
