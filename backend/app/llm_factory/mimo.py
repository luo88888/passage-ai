from typing import Any
from langchain_deepseek import ChatDeepSeek
from pydantic import BaseModel

from langchain_core.language_models import BaseChatModel

from app.llm_factory.token_usage_handler import TokenUsageCallbackHandler
from app.config import settings



def _get_api_key() -> str:
    key = settings.mimo_api_key
    if not key:
        raise ValueError("未配置 MIMO_API_KEY 环境变量")
    return key


def _get_base_url() -> str:
    return settings.mimo_base_url or "https://api.xiaomimimo.com/v1"


def create_chat_model(
        model_name: str,
        temperature: float = 0.0,
        thinking: bool = False,
        reasoning_effort: str = "high",    # high/max
        extra_body: dict[str, Any] = {},
    ) -> BaseChatModel:
    """创建 MiMo 聊天模型。

    MiMo 的 function_calling 与思考模式兼容（不同于 DeepSeek），可通过 enable_thinking 开启。

    Args:
        model_name: 模型名称
        temperature: 温度参数
        thinking: 是否启用思考模式
        reasoning_effort: 推理力度（仅在 enable_thinking=True 时生效）
        extra_body: 额外参数
    """
    if thinking:
        extra_body["thinking"] = {"type": "enabled"}
    else:
        extra_body["thinking"] = {"type": "disabled"}
    return ChatDeepSeek(
        name="ChatXiaomi",
        model=model_name,
        api_key=_get_api_key(), # type: ignore
        temperature=temperature,
        extra_body=extra_body,
        reasoning_effort=reasoning_effort,
        base_url=_get_base_url(),
        stream_usage=True,
        callbacks=[TokenUsageCallbackHandler("Xiaomi", model_name)],
    )


def create_structured_model(
        structured: type[BaseModel],
        model_name: str,
        temperature: float = 0.0,
        thinking: bool = False,
        reasoning_effort: str = "high",
        extra_body: dict[str, Any] = {},
    ):
    """创建 MiMo 结构化输出模型。

    MiMo 的 function_calling 与思考模式兼容（不同于 DeepSeek），可通过 enable_thinking 开启。

    Args:
        structured: Pydantic 模型类
        model_name: 模型名称
        temperature: 温度参数
        thinking: 是否启用思考模式
        reasoning_effort: 推理力度（仅在 enable_thinking=True 时生效）
        extra_body: 额外参数
    """
    return create_chat_model(
        model_name=model_name,
        temperature=temperature,
        thinking=thinking,
        reasoning_effort=reasoning_effort,
        extra_body=extra_body
    ).with_structured_output(structured)


def _test_model():
    """快速功能测试：覆盖普通模型/结构化输出 × 流式/非流式 × 同步/异步。"""
    import asyncio

    class UserInfo(BaseModel):
        name: str
        age: int

    # ==================== 同步非流式 ====================
    print("=" * 50)
    print("1. 普通模型 同步 invoke")
    model = create_chat_model("mimo-v2.5")
    print(model.invoke("你好，请简短回复").content)
    print()

    print("=" * 50)
    print("2. 结构化输出 同步 invoke")
    structured_model = create_structured_model(UserInfo, "mimo-v2.5-pro", thinking=True)
    print(structured_model.invoke("我叫小班班，今年22岁。"))
    print()

    # ==================== 同步流式 ====================
    print("=" * 50)
    print("3. 普通模型 同步 stream")
    model = create_chat_model("mimo-v2.5-pro", thinking=True)
    for chunk in model.stream("9.9和9.11哪个大？请简短回答"):
        if chunk.content:
            print(chunk.content, end="", flush=True)
    print()
    print()

    # ==================== 异步 ====================
    async def _async_tests():
        # 异步非流式
        print("=" * 50)
        print("4. 普通模型 异步 ainvoke")
        model = create_chat_model("mimo-v2.5")
        result = await model.ainvoke("你好，请简短回复")
        print(result.content)
        print()

        print("=" * 50)
        print("5. 结构化输出 异步 ainvoke")
        structured_model = create_structured_model(UserInfo, "mimo-v2.5-pro", thinking=True)
        result = await structured_model.ainvoke("我叫小班班，今年22岁。")
        print(result)
        print()

        # 异步流式
        print("=" * 50)
        print("6. 普通模型 异步 astream")
        model = create_chat_model("mimo-v2.5-pro", thinking=True)
        async for chunk in model.astream("9.9和9.11哪个大？请简短回答"):
            if chunk.content:
                print(chunk.content, end="", flush=True)
        print()
        print()

    asyncio.run(_async_tests())

    print("全部测试通过！")



if __name__ == "__main__":
    _test_model()
