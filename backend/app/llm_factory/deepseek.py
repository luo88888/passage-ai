# -*- coding: utf-8 -*-
"""DeepSeek 模型工厂封装。

包含:
- create_chat_model:          普通对话模型（支持思考模式）
- create_structured_model:    结构化输出模型（与思考模式兼容）
"""

import json
import re
from typing import Any, AsyncIterator, Iterator

import dotenv
from pydantic import BaseModel

dotenv.load_dotenv(override=True)

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompt_values import PromptValue
from langchain_core.runnables import Runnable
from langchain_deepseek import ChatDeepSeek

from app.config import settings
from app.llm_factory.token_usage_handler import TokenUsageCallbackHandler
from app.utils.json_tool import loads_with_repair


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------
def _build_extra_body(
    thinking: bool,
    reasoning_effort: str | None = None,
    extra_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造 DeepSeek 的 extra_body，统一管理 thinking / reasoning_effort。

    DeepSeek V4 的 thinking 是对象形式 ``{"type": "enabled" | "disabled"}``，
    且 reasoning_effort 需要与 thinking 一起放入 extra_body 才会生效。
    """
    body = dict(extra_body or {})
    body["thinking"] = {"type": "enabled" if thinking else "disabled"}
    if thinking and reasoning_effort:
        body.setdefault("reasoning_effort", reasoning_effort)
    return body


def _extract_json(text: str) -> Any:
    """从模型输出中稳健地提取 JSON。

    依次尝试:
    1. 直接 json.loads（输出本身就是纯 JSON）
    2. 剥离 markdown 代码围栏后 json.loads
    3. 截取第一个 ``{`` 到最后一个 ``}``（兼容前后夹杂解释文字）
    4. json_repair 修复后再解析（兜底，直接解析与修复结果均记录日志）
    """
    if not text or not text.strip():
        raise ValueError("模型输出为空，无法提取 JSON")

    def _loads(candidate: str) -> Any:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    candidate = text.strip()
    parsed = _loads(candidate)
    if parsed is not None:
        return parsed

    fence = re.search(r"```(?:json)?\s*(.*?)```", candidate, re.DOTALL | re.IGNORECASE)
    if fence:
        parsed = _loads(fence.group(1).strip())
        if parsed is not None:
            return parsed

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        parsed = _loads(candidate[start : end + 1])
        if parsed is not None:
            return parsed

    # 4. json_repair 修复后再解析（兜底；修复成功/失败均由 loads_with_repair 记录日志）
    try:
        return loads_with_repair(candidate, name="模型输出")
    except json.JSONDecodeError as e:
        raise ValueError(f"无法从模型输出中提取有效 JSON: {text[:200]!r}") from e


def _attach_meta(parsed: BaseModel, raw: AIMessage) -> None:
    """把思考内容/原始响应挂到解析结果上（不污染 model_dump 字段）。"""
    try:
        object.__setattr__(
            parsed,
            "_reasoning_content",
            (raw.additional_kwargs or {}).get("reasoning_content"),
        )
        object.__setattr__(parsed, "_raw_response", raw)
    except Exception:  # pragma: no cover - 仅防御性兜底
        pass


# ---------------------------------------------------------------------------
# 结构化输出模型（思考模式兼容）
# ---------------------------------------------------------------------------
class DeepSeekStructuredModel(Runnable):
    """兼容 DeepSeek 思考模式的结构化输出 Runnable。

    返回对象与原生 ``with_structured_output()`` 保持一致：
    - ``method="function_calling"``: 走原生 tool 强制调用（最严格，但思考模式下
      DeepSeek API 会拒绝强制 tool_choice）；
    - ``method="prompt_json"``:     提示词内嵌 JSON Schema + pydantic 校验，
      与思考模式兼容（DeepSeek 思考模式默认开启时会自动走该路径）。

    用法:
        model = create_structured_model(UserInfo, "deepseek-v4-flash", thinking=True)
        user = model.invoke("我叫小班班，今年 22 岁。")   # -> UserInfo 实例
        print(user._reasoning_content)                    # 思考内容（可选）
    """

    name = None

    def __init__(
        self,
        llm: BaseChatModel,
        structured: type[BaseModel],
        *,
        method: str = "prompt_json",
        include_raw: bool = False,
    ) -> None:
        if method not in ("prompt_json", "function_calling", "json_mode"):
            raise ValueError(
                f"不支持的 method: {method!r}，"
                "可选: 'prompt_json' / 'function_calling' / 'json_mode'"
            )
        self.llm = llm
        self.structured = structured
        self.method = method
        self.include_raw = include_raw
        if method != "prompt_json":
            self._native = llm.with_structured_output(
                structured, method=method, include_raw=include_raw
            )

    # -- 内部辅助 -----------------------------------------------------------
    def _system_prompt(self) -> str:
        schema = json.dumps(
            self.structured.model_json_schema(), ensure_ascii=False, indent=2
        )
        return (
            "你必须严格输出一个 JSON 对象，其结构必须完全符合下面的 JSON Schema。\n"
            "不要输出 markdown 代码围栏、解释性文字或任何 JSON 之外的文本。\n"
            "你可以先思考（reasoning），但最终回答只能包含符合 schema 的 JSON 对象。\n"
            "\n"
            f"JSON Schema:\n{schema}"
        )

    def _build_messages(self, input: Any) -> list[BaseMessage]:
        if isinstance(input, PromptValue):
            msgs = input.to_messages()
        elif isinstance(input, str):
            msgs = [HumanMessage(content=input)]
        elif isinstance(input, BaseMessage):
            msgs = [input]
        elif isinstance(input, list):
            msgs = list(input)
        else:
            raise TypeError(
                f"不支持的输入类型: {type(input)!r}，"
                "应为 str / BaseMessage / list[BaseMessage] / PromptValue"
            )
        return [SystemMessage(content=self._system_prompt()), *msgs]

    def _parse(self, raw: AIMessage) -> BaseModel:
        content = raw.content
        # 理论上已是 str
        if isinstance(content, list):
            text = "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        else:
            text = str(content)
        parsed = self.structured.model_validate(_extract_json(text))
        _attach_meta(parsed, raw)
        return parsed

    def _wrap_result(self, raw: AIMessage) -> Any:
        try:
            parsed = self._parse(raw)
            parsing_error = None
        except Exception as exc:  # 与 with_structured_output(include_raw=True) 一致
            parsed = None
            parsing_error = exc
        if self.include_raw:
            return {"raw": raw, "parsed": parsed, "parsing_error": parsing_error}
        if parsing_error is not None:
            raise parsing_error
        return parsed

    # -- Runnable 接口 ------------------------------------------------------
    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        """返回 structured 的 pydantic 实例（或 include_raw 时的 dict）。"""
        if self.method != "prompt_json":
            return self._native.invoke(input, config=config, **kwargs)
        raw = self.llm.invoke(self._build_messages(input), config=config, **kwargs)
        return self._wrap_result(raw)

    async def ainvoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        if self.method != "prompt_json":
            return await self._native.ainvoke(input, config=config, **kwargs)
        raw = await self.llm.ainvoke(self._build_messages(input), config=config, **kwargs)
        return self._wrap_result(raw)

    def stream(self, input: Any, config: Any = None, **kwargs: Any) -> Iterator[Any]:
        """流式输出: 累积完整响应后产出最终的 pydantic 实例。"""
        yield self.invoke(input, config=config, **kwargs)

    async def astream(
        self, input: Any, config: Any = None, **kwargs: Any
    ) -> AsyncIterator[Any]:
        yield await self.ainvoke(input, config=config, **kwargs)


# ---------------------------------------------------------------------------
# 公开工厂函数
# ---------------------------------------------------------------------------
def create_chat_model(
    model_name: str,
    temperature: float = 0.0,
    thinking: bool = False,
    reasoning_effort: str = "high",    # low/high/max
    extra_body: dict[str, Any] | None = None,
    **llm_kwargs: Any,
) -> BaseChatModel:
    """创建 DeepSeek 对话模型。

    Args:
        model_name: 模型名称（如 deepseek-v4-flash / deepseek-v4-pro）
        temperature: 温度参数
        thinking: 是否启用思考模式
        reasoning_effort: 推理力度（low/high/max），仅 thinking=True 时生效
        extra_body: 额外请求体参数
        **llm_kwargs: 透传给 ChatDeepSeek 的其他参数（timeout/max_retries 等）
    """
    return ChatDeepSeek(
        model=model_name,
        api_key=settings.deepseek_api_key,  # type: ignore
        temperature=temperature,
        extra_body=_build_extra_body(thinking, reasoning_effort, extra_body),
        stream_usage=True,
        callbacks=[TokenUsageCallbackHandler("DeepSeek", model_name)],
        **llm_kwargs,
    )


def create_structured_model(
    structured: type[BaseModel],
    model_name: str,
    temperature: float = 0.0,
    thinking: bool = False,
    reasoning_effort: str = "high",
    extra_body: dict[str, Any] | None = None,
    method: str = "auto",     # auto / prompt_json / function_calling / json_mode
    include_raw: bool = False,
    **llm_kwargs: Any,
) -> DeepSeekStructuredModel:
    """创建与 DeepSeek 思考模式兼容的结构化输出模型。

    DeepSeek 思考模式（thinking）下 API 会拒绝强制 tool_choice
    （``Thinking mode does not support this tool_choice``），因此原生
    ``with_structured_output(method="function_calling")`` 无法在思考模式下使用。

    重新设计后:
    - ``thinking=False``: method 自动走原生 ``function_calling``，由 API 强制
      schema，约束最严格；
    - ``thinking=True``:  method 自动切换为 ``prompt_json`` —— 提示词内嵌
      JSON Schema，保留思考模式，并用 pydantic 校验输出，保证结构化结果可靠；
    - 解析结果上附带 ``_reasoning_content``（思考内容）与 ``_raw_response``。

    Args:
        structured: pydantic 模型类
        model_name: 模型名称
        temperature: 温度参数
        thinking: 是否启用思考模式
        reasoning_effort: 推理力度（low/high/max），仅 thinking=True 时生效
        extra_body: 额外请求体参数
        method: 结构化输出方式
            - "auto": thinking=False -> function_calling; thinking=True -> prompt_json
            - "prompt_json": 提示词 JSON + pydantic 解析（思考模式兼容，推荐）
            - "function_calling": 原生 tool 强制调用（思考模式会报错）
            - "json_mode": 原生 json_object 模式（不注入 schema，可靠性低）
        include_raw: 为 True 时返回 {"raw", "parsed", "parsing_error"} 字典
        **llm_kwargs: 透传给 ChatDeepSeek 的其他参数（timeout/max_retries 等）

    Returns:
        DeepSeekStructuredModel：与 with_structured_output 用法一致的 Runnable
    """
    if method == "auto":
        method = "function_calling" if not thinking else "prompt_json"
    if method == "function_calling" and thinking:
        raise ValueError(
            "DeepSeek 思考模式不支持强制 tool_choice 的 function_calling 结构化输出"
            "（API 返回 'Thinking mode does not support this tool_choice'）。"
            "请使用 method='prompt_json'（保留思考）或关闭 thinking。"
        )

    llm = ChatDeepSeek(
        model=model_name,
        api_key=settings.deepseek_api_key,  # type: ignore
        temperature=temperature,
        extra_body=_build_extra_body(thinking, reasoning_effort, extra_body),
        stream_usage=True,
        callbacks=[TokenUsageCallbackHandler("DeepSeek", model_name)],
        **llm_kwargs,
    )
    return DeepSeekStructuredModel(
        llm=llm,
        structured=structured,
        method=method,
        include_raw=include_raw,
    )


def _test_model():
    class UserInfo(BaseModel):
        name: str
        age: int

    model = create_chat_model("deepseek-v4-flash", thinking=True)
    print(model.invoke("你好，简单打个招呼"))

    for thinking in (False, True):
        structured_model = create_structured_model(
            UserInfo, "deepseek-v4-flash", thinking=thinking
        )
        user_text = "我叫小班班，今年22岁。"
        response = structured_model.invoke(user_text)
        print(f"[thinking={thinking}] {response!r}")
        print("reasoning:", bool(getattr(response, "_reasoning_content", None)))


if __name__ == "__main__":
    _test_model()
