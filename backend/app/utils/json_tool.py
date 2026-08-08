"""JSON 解析工具：直接解析失败时用 json_repair 修复，并记录日志。

LLM 输出 / 工具返回的 JSON 偶尔会带少量格式问题（尾逗号、缺引号、转义错误、
夹杂解释文字等），直接 json.loads 会失败。本工具提供 ``loads_with_repair``：
先直接解析，失败后调用 json_repair 修复再解析；无论修复成功与否都会记录日志，
便于定位与统计模型输出质量问题。
"""

import json
from typing import Any

from app.utils.logger import logger

try:
    from json_repair import loads as _json_repair_loads
except ImportError:  # pragma: no cover - 依赖缺失时退化为仅直接解析
    _json_repair_loads = None


def loads_with_repair(text: str, name: str = "JSON") -> Any:
    """解析 JSON 字符串；直接解析失败时尝试 json_repair 修复后再解析。

    Args:
        text: 待解析的 JSON 文本（模型输出 / 工具返回内容等）。
        name: 数据来源名称，仅用于日志（如 "大纲" / "标题方案" / "文章摘要"）。

    Returns:
        解析得到的对象（dict / list / 基本类型）。

    Raises:
        json.JSONDecodeError: 直接解析失败，且 json_repair 不可用、修复后仍失败、
            或修复结果仅为裸字符串（无有效 JSON 结构，对调用方无意义）。
    """
    if not isinstance(text, str) or not text.strip():
        raise json.JSONDecodeError(
            "待解析内容为空或非字符串",
            text if isinstance(text, str) else "",
            0,
        )

    # 1) 直接解析（绝大多数正常输出走这里，无额外开销）
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2) 直接解析失败 -> json_repair 修复后再解析
    if _json_repair_loads is None:
        logger.error(
            "%s JSON 直接解析失败且 json_repair 不可用, content=%r",
            name, text[:500],
        )
        raise json.JSONDecodeError("json_repair 不可用，无法修复 JSON", text, 0)

    try:
        repaired = _json_repair_loads(text)
    except Exception as e:
        logger.error(
            "%s JSON 直接解析与 json_repair 修复均失败, error=%s, content=%r",
            name, str(e), text[:500],
        )
        raise json.JSONDecodeError(f"json_repair 修复失败: {e}", text, 0) from e

    # json_repair 对无 JSON 结构的文本会退化为裸字符串（如空串），
    # 对期望 dict/list 的调用方无意义，按修复失败处理并记录日志。
    if isinstance(repaired, str):
        logger.error(
            "%s JSON 直接解析失败，json_repair 未提取到有效 JSON 结构, content=%r",
            name, text[:500],
        )
        raise json.JSONDecodeError("json_repair 未提取到有效 JSON 结构", text, 0)

    logger.warning(
        "%s JSON 直接解析失败，json_repair 修复成功, content=%r",
        name, text[:500],
    )
    return repaired
