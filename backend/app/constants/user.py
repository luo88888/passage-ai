"""用户相关常量"""

from enum import Enum


class UserRole(str, Enum):
    """合法用户角色（str-Enum：值即数据库 userRole 列值，可直接与字符串比较/绑定）"""

    USER = "user"
    ADMIN = "admin"
    VIP = "vip"


class UserConstant:
    """用户常量"""

    DEFAULT_ROLE = UserRole.USER.value
    ADMIN_ROLE = UserRole.ADMIN.value
    VIP_ROLE = UserRole.VIP.value
    DEFAULT_QUOTA = 5   # 默认配额
