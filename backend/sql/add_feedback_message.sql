-- Active: 1783421777382@@127.0.0.1@3306@ai_passage_creator
-- 意见反馈 + 站内信功能数据层（M1）
-- 幂等：可重复执行（建表均 CREATE TABLE IF NOT EXISTS）
-- 相关计划：docs/local/意见反馈与站内信功能开发计划.md（v1.1）

USE ai_passage_creator;

-- ==================== 1. 意见反馈表 ====================
-- 说明：反馈类型已确认为四类（BUG/FEATURE/COMPLAINT/OTHER），与计划 §10 待确认问题一致；
--       imageUrls 为 JSON 数组（最多 5 张截图 URL）。
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

-- ==================== 2. 站内信表 ====================
-- 说明：senderId 为计划 DDL 的补充列，标记管理员主动发信（系统自动触发为空），
--       用于支撑管理端「已发列表」（M3）；其余字段与计划 §4.2 一致。
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
