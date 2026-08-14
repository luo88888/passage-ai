"""站内信相关常量。

存放已确认的站内信类型与收件人类型常量，供服务层/路由层引用，避免魔法字符串散落各处。
"""


class MessageConstant:
    """站内信常量。

    Attributes:
        TYPE_SYSTEM: 系统通知/公告。
        TYPE_FEEDBACK: 反馈回复。
        TYPE_VIP: 会员开通。
        TYPE_POINTS: 积分变动。
        TYPES: 全部消息类型列表。
        TYPE_LABELS: 类型 → 中文展示名。
        TARGET_SINGLE: 单用户发送。
        TARGET_BATCH: 批量发送。
        TARGET_ALL: 全体广播（写时展开为每用户一行）。
        TARGETS: 全部收件人类型列表。
        MAX_TITLE_LENGTH: 标题最大长度（对应 DDL title VARCHAR(200)）。
        MAX_CONTENT_LENGTH: 内容最大长度（请求层约束，DB 为 TEXT）。
        MAX_LINK_LENGTH: 跳转链接最大长度（对应 DDL link VARCHAR(512)）。
    """

    # 消息类型
    TYPE_SYSTEM = "SYSTEM"      # 系统通知/公告
    TYPE_FEEDBACK = "FEEDBACK"  # 反馈回复
    TYPE_VIP = "VIP"            # 会员开通
    TYPE_POINTS = "POINTS"      # 积分变动
    TYPES = [TYPE_SYSTEM, TYPE_FEEDBACK, TYPE_VIP, TYPE_POINTS]
    TYPE_LABELS = {
        TYPE_SYSTEM: "系统通知",
        TYPE_FEEDBACK: "反馈回复",
        TYPE_VIP: "会员开通",
        TYPE_POINTS: "积分变动",
    }

    # 收件人类型（管理端发送）
    TARGET_SINGLE = "SINGLE"    # 单用户
    TARGET_BATCH = "BATCH"      # 批量用户
    TARGET_ALL = "ALL"          # 全体用户（写时展开）
    TARGETS = [TARGET_SINGLE, TARGET_BATCH, TARGET_ALL]

    MAX_TITLE_LENGTH = 200
    MAX_CONTENT_LENGTH = 5000
    MAX_LINK_LENGTH = 512
