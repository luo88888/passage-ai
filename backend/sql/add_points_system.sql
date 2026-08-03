-- 用户积分系统数据层（M1）
-- 幂等：可重复执行；建表/加列/回填/清理均有防重保护
-- 相关计划：docs/积分系统开发计划.md（v1.2）

USE ai_passage_creator;

-- ==================== 1. 用户积分账户表 ====================
CREATE TABLE IF NOT EXISTS user_points (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    userId       BIGINT NOT NULL COMMENT '用户ID',
    balance      INT NOT NULL DEFAULT 0 COMMENT '当前积分余额',
    totalEarned  INT NOT NULL DEFAULT 0 COMMENT '累计获得积分',
    totalConsumed INT NOT NULL DEFAULT 0 COMMENT '累计消耗积分',
    version      INT NOT NULL DEFAULT 0 COMMENT '乐观锁版本号',
    createTime   DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updateTime   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_userId (userId)
) COMMENT='用户积分账户' COLLATE=utf8mb4_unicode_ci;

-- ==================== 2. 积分流水表（积分明细） ====================
CREATE TABLE IF NOT EXISTS points_transaction (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    userId        BIGINT NOT NULL COMMENT '用户ID',
    taskId        VARCHAR(64) NULL COMMENT '关联任务ID',
    type          VARCHAR(32) NOT NULL COMMENT '类型：REGISTER/SIGN_IN/RECHARGE/USAGE_RESERVE/USAGE_SETTLE/USAGE_REFUND/ADMIN_ADJUST',
    amount        INT NOT NULL COMMENT '变动积分（正=获得，负=消耗）',
    balanceAfter  INT NOT NULL COMMENT '变动后余额',
    description   VARCHAR(255) NULL COMMENT '描述',
    createTime    DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_userId_time (userId, createTime),
    INDEX idx_taskId (taskId)
) COMMENT='积分流水' COLLATE=utf8mb4_unicode_ci;

-- ==================== 3. 模型用量记录表（核心统计表） ====================
CREATE TABLE IF NOT EXISTS model_usage_record (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    userId        BIGINT NOT NULL COMMENT '用户ID',
    taskId        VARCHAR(64) NULL COMMENT '任务ID',
    category      VARCHAR(16) NOT NULL COMMENT '类别：LLM / IMAGE',
    provider      VARCHAR(32) NOT NULL COMMENT '提供商：Xiaomi/DeepSeek/Zhipu/NanoBanana',
    model         VARCHAR(64) NOT NULL COMMENT '模型名',
    agentName     VARCHAR(50) NULL COMMENT '智能体名称',
    callCount     INT NOT NULL DEFAULT 1 COMMENT '调用次数',
    inputTokens   INT NULL COMMENT '输入token（LLM）',
    outputTokens  INT NULL COMMENT '输出token（LLM）',
    imageCount    INT NULL COMMENT '生成图片张数（IMAGE）',
    costPoints    INT NOT NULL DEFAULT 0 COMMENT '本记录消耗积分',
    status        VARCHAR(16) NOT NULL DEFAULT 'SUCCESS' COMMENT 'SUCCESS/FAILED',
    startTime     DATETIME NOT NULL COMMENT '开始时间',
    endTime       DATETIME NULL COMMENT '结束时间',
    createTime    DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_userId_model (userId, model, createTime),
    INDEX idx_taskId (taskId)
) COMMENT='模型用量记录' COLLATE=utf8mb4_unicode_ci;

-- ==================== 4. 模型计价表 ====================
CREATE TABLE IF NOT EXISTS model_pricing (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    category        VARCHAR(16) NOT NULL COMMENT 'LLM / IMAGE',
    provider        VARCHAR(32) NOT NULL COMMENT '提供商',
    model           VARCHAR(64) NOT NULL COMMENT '模型名（LLM用通配符 * 兜底）',
    agentName       VARCHAR(50) NOT NULL DEFAULT '' COMMENT '按Agent细分（空=不限）',
    inputPricePer1k DECIMAL(10,4) NOT NULL DEFAULT 0 COMMENT '输入token单价（积分/1k token，LLM，允许小数）',
    outputPricePer1k DECIMAL(10,4) NOT NULL DEFAULT 0 COMMENT '输出token单价（积分/1k token，LLM，允许小数）',
    pricePerImage   DECIMAL(10,2) NOT NULL DEFAULT 0 COMMENT '每张图积分（IMAGE）',
    enabled         TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用',
    updateTime      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_model (category, provider, model, agentName)
) COMMENT='模型计价' COLLATE=utf8mb4_unicode_ci;

-- ==================== 5. 计价表历史清理（兼容早期 agentName=NULL 版本，幂等） ====================
-- 5.1 删除重复计价行（每组合保留最小 id）
DELETE mp FROM model_pricing mp
INNER JOIN (
    SELECT category, provider, model, agentName, MIN(id) AS keep_id
    FROM model_pricing
    GROUP BY category, provider, model, agentName
) k
ON mp.category = k.category AND mp.provider = k.provider AND mp.model = k.model
   AND (mp.agentName = k.agentName OR (mp.agentName IS NULL AND k.agentName IS NULL))
WHERE mp.id <> k.keep_id;

-- 5.2 NULL 归一为 ''（保证唯一键生效）
UPDATE model_pricing SET agentName = '' WHERE agentName IS NULL;

-- 5.3 兼容旧表结构：agentName 改为 NOT NULL DEFAULT ''（幂等）
SET @col_nullable = (SELECT IS_NULLABLE FROM information_schema.COLUMNS
                     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'model_pricing' AND COLUMN_NAME = 'agentName');
SET @ddl = IF(@col_nullable = 'YES',
    'ALTER TABLE model_pricing MODIFY agentName VARCHAR(50) NOT NULL DEFAULT '''' COMMENT ''按Agent细分（空=不限）''',
    'SELECT 1');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ==================== 6. 计价种子数据（已确认规则：100 积分 = 1 元；见计划 4.4） ====================
INSERT IGNORE INTO model_pricing (category, provider, model, agentName, inputPricePer1k, outputPricePer1k, pricePerImage, enabled) VALUES
('LLM', 'Xiaomi',      'mimo-v2.5-pro',          '', 1.0000, 2.0000, 0, 1),
('LLM', 'Xiaomi',      'mimo-v2.5',              '', 0.3000, 0.6000, 0, 1),
('LLM', 'DeepSeek',    'deepseek-v4-flash',      '', 0.3000, 0.6000, 0, 1),
('LLM', '*',           '*',                      '', 1.0000, 2.0000, 0, 1),
('IMAGE', 'Zhipu',     'cogview-3-flash',        '', 0, 0, 0, 1),
('IMAGE', 'NanoBanana','gemini-2.5-flash-image', '', 0, 0, 2.00, 1);

-- ==================== 7. user 表新增 points 冗余展示字段（幂等） ====================
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user' AND COLUMN_NAME = 'points');
SET @ddl = IF(@col_exists = 0,
    'ALTER TABLE user ADD COLUMN points INT NOT NULL DEFAULT 0 COMMENT ''积分余额（冗余展示，权威以 user_points 为准）'' AFTER quota',
    'SELECT 1');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ==================== 8. agent_log 表新增 userId / model 列（幂等） ====================
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agent_log' AND COLUMN_NAME = 'userId');
SET @ddl = IF(@col_exists = 0,
    'ALTER TABLE agent_log ADD COLUMN userId BIGINT NULL COMMENT ''用户ID'' AFTER taskId',
    'SELECT 1');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agent_log' AND COLUMN_NAME = 'model');
SET @ddl = IF(@col_exists = 0,
    'ALTER TABLE agent_log ADD COLUMN model VARCHAR(64) NULL COMMENT ''模型名'' AFTER agentName',
    'SELECT 1');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ==================== 9. 存量用户积分账户回填：1 quota = 100 积分（幂等：仅无账户的用户） ====================
INSERT IGNORE INTO user_points (userId, balance, totalEarned, totalConsumed, version, createTime, updateTime)
SELECT u.id, u.quota * 100, u.quota * 100, 0, 0, NOW(), NOW()
FROM user u
WHERE u.isDelete = 0;

-- ==================== 10. 存量折算流水（幂等：同类型同描述存在则跳过） ====================
INSERT INTO points_transaction (userId, taskId, type, amount, balanceAfter, description, createTime)
SELECT u.id, NULL, 'ADMIN_ADJUST', u.quota * 100, u.quota * 100, '历史配额折算（1 quota = 100 积分）', NOW()
FROM user u
WHERE u.isDelete = 0 AND u.quota > 0
  AND NOT EXISTS (
      SELECT 1 FROM points_transaction t
      WHERE t.userId = u.id AND t.type = 'ADMIN_ADJUST' AND t.description LIKE '历史配额折算%'
  );

-- ==================== 11. 同步 user.points 冗余字段 ====================
UPDATE user u
JOIN user_points up ON up.userId = u.id
SET u.points = up.balance
WHERE u.isDelete = 0;