"""意见反馈相关常量。

存放已确认的反馈类型与状态常量，供服务层/路由层引用，避免魔法字符串散落各处。
规则来源：docs/local/意见反馈与站内信功能开发计划.md（v1.1，已确认：反馈类型四类
BUG/FEATURE/COMPLAINT/OTHER，状态仅 PENDING/PROCESSING/RESOLVED 三段，截图最多 5 张）。
"""


class FeedbackConstant:
    """反馈常量。

    Attributes:
        TYPE_BUG: BUG 反馈。
        TYPE_FEATURE: 功能建议。
        TYPE_COMPLAINT: 投诉。
        TYPE_OTHER: 其他。
        TYPE_LABELS: 类型 → 中文展示名。
        STATUS_PENDING: 待处理。
        STATUS_PROCESSING: 处理中。
        STATUS_RESOLVED: 已解决。
        STATUS_LABELS: 状态 → 中文展示名。
        MAX_IMAGE_COUNT: 单条反馈截图上限。
        MAX_CONTENT_LENGTH: 反馈内容最大长度。
        MAX_CONTACT_LENGTH: 联系方式最大长度。
        LINK_PREFIX: 反馈详情前端路由前缀（站内信 link 用）。
    """

    # 反馈类型（四类，已确认）
    TYPE_BUG = "BUG"                # BUG
    TYPE_FEATURE = "FEATURE"        # 建议
    TYPE_COMPLAINT = "COMPLAINT"    # 投诉
    TYPE_OTHER = "OTHER"            # 其他
    TYPES = [TYPE_BUG, TYPE_FEATURE, TYPE_COMPLAINT, TYPE_OTHER]
    TYPE_LABELS = {
        TYPE_BUG: "BUG",
        TYPE_FEATURE: "建议",
        TYPE_COMPLAINT: "投诉",
        TYPE_OTHER: "其他",
    }

    # 反馈状态（三段，已确认）
    STATUS_PENDING = "PENDING"          # 待处理
    STATUS_PROCESSING = "PROCESSING"    # 处理中
    STATUS_RESOLVED = "RESOLVED"        # 已解决
    STATUSES = [STATUS_PENDING, STATUS_PROCESSING, STATUS_RESOLVED]
    STATUS_LABELS = {
        STATUS_PENDING: "待处理",
        STATUS_PROCESSING: "处理中",
        STATUS_RESOLVED: "已解决",
    }

    MAX_IMAGE_COUNT = 5          # 单条反馈截图最多 5 张
    MAX_CONTENT_LENGTH = 2000    # 反馈内容最长 2000 字
    MAX_CONTACT_LENGTH = 128     # 联系方式最长 128 字
    LINK_PREFIX = "/feedback?activeId="   # 反馈详情前端路由前缀（站内信 link 用）
