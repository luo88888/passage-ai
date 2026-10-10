"""
自定义异常和错误码
"""

from enum import Enum
from typing import Any, Optional


class ErrorCode(Enum):
    """错误码枚举"""

    SUCCESS = (0, "ok")

    # 通用错误
    PARAMS_ERROR = (40000, "请求参数错误")
    NOT_LOGIN_ERROR = (40100, "未登录")
    NO_AUTH_ERROR = (40101, "无权限")
    NOT_FOUND_ERROR = (40400, "请求数据不存在")
    FORBIDDEN_ERROR = (40300, "禁止访问")
    REQUEST_TOO_FREQUENT = (42900, "请求过于频繁")
    SYSTEM_ERROR = (50000, "系统内部错误")
    OPERATION_ERROR = (50001, "操作失败")


    # 业务错误
    USER_NOT_EXIST = (40401, "用户不存在")
    USER_ALREADY_EXIST = (40402, "用户已存在")
    PASSWORD_ERROR = (40103, "密码错误")
    INSUFFICIENT_POINTS = (50002, "积分不足")


    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message


class LLMTransientError(Exception):
    """LLM 瞬时错误（超时、429、5xx、连接中断等），可重试。"""


class LLMOutputFormatError(Exception):
    """LLM 输出格式/校验错误，可重试（重试时把错误反馈拼回提示词）。

    Attributes:
        raw_output: 模型原始输出文本（可选，用于构造重试提示词的错误反馈）。
    """

    def __init__(self, message: str, raw_output: Optional[str] = None):
        self.raw_output = raw_output
        super().__init__(message)


class AgentMaxRetriesError(Exception):
    """智能体重试次数耗尽后的统一异常（向上抛给图节点做降级决策）。

    Attributes:
        attempts: 已尝试次数（含首次）。
        last_error: 最后一次失败原因（可选）。
    """

    def __init__(
        self,
        message: str,
        attempts: Optional[int] = None,
        last_error: Optional[Exception] = None,
    ):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(message)


class BusinessException(Exception):
    """业务异常"""
    
    def __init__(
        self,
        error_code: ErrorCode,
        message: Optional[str] = None,
        internal_code: Optional[ErrorCode] = None,
    ):
        self.error_code = error_code
        self.internal_code = internal_code
        self.message = message or error_code.message
        super().__init__(self.message)


def throw_if(
    condition: Any,
    error_code: ErrorCode,
    message: Optional[str] = None,
    internal_code: Optional[ErrorCode] = None,
):
    """条件为真时抛出异常"""
    if condition:
        raise BusinessException(error_code, message, internal_code)


def throw_if_not(
    condition: Any,
    error_code: ErrorCode,
    message: Optional[str] = None,
    internal_code: Optional[ErrorCode] = None,
):
    """条件为假时抛出异常"""
    if not condition:
        raise BusinessException(error_code, message, internal_code)
