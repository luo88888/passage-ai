"""积分相关常量。

存放已确认的积分规则数值与积分流水类型，供各服务层引用，避免魔法数字散落各处。
规则来源：docs/积分系统开发计划.md v1.3（100 积分 = 1 元；后付费段级结算 + 透支护栏 + 并发限制；
v1.2 的「预扣-结算」设计废弃，USAGE_RESERVE / USAGE_REFUND 流水类型仅作兼容保留不再使用）。
"""


class PointsConstant:
    """积分常量。

    Attributes:
        DEFAULT_POINTS: 注册赠送积分。
        SIGN_IN_POINTS: 每日签到赠送积分。
        QUOTA_TO_POINTS_RATE: 历史配额折算比例（1 quota = 100 积分）。
        TX_REGISTER: 注册赠送流水类型。
        TX_SIGN_IN: 每日签到流水类型。
        TX_RECHARGE: 充值流水类型（本期暂不实现）。
        TX_USAGE_SETTLE: 生成任务段级结算（后付费扣费）流水类型。
        TX_USAGE_RESERVE: 生成任务预扣流水类型（v1.2 遗留，已废弃不再使用）。
        TX_USAGE_REFUND: 失败退回流水类型（v1.2 遗留，已废弃不再使用）。
        TX_ADMIN_ADJUST: 管理员调整/历史折算流水类型。
    """

    DEFAULT_POINTS = 100        # 注册赠送积分
    SIGN_IN_POINTS = 10         # 每日签到赠送积分
    QUOTA_TO_POINTS_RATE = 100  # 历史配额折算比例（1 quota = 100 积分）

    # 积分流水类型
    TX_REGISTER = "REGISTER"            # 注册赠送
    TX_SIGN_IN = "SIGN_IN"              # 每日签到
    TX_RECHARGE = "RECHARGE"            # 充值（本期暂不实现）
    TX_USAGE_SETTLE = "USAGE_SETTLE"    # 生成任务段级结算（后付费扣费，v1.3 起使用）
    TX_USAGE_RESERVE = "USAGE_RESERVE"  # 生成任务预扣（v1.2 遗留，已废弃不再使用）
    TX_USAGE_REFUND = "USAGE_REFUND"    # 失败退回（v1.2 遗留，已废弃不再使用）
    TX_ADMIN_ADJUST = "ADMIN_ADJUST"    # 管理员调整/历史折算
