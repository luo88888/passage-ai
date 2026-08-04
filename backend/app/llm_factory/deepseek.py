import os
from typing import Any
import dotenv
from pydantic import BaseModel

dotenv.load_dotenv(override=True)

from langchain_deepseek import ChatDeepSeek
from langchain_core.language_models import BaseChatModel
from app.llm_factory.token_usage_handler import TokenUsageCallbackHandler
from app.config import settings


def create_chat_model(
        model_name: str,
        temperature: float = 0.0,
        thinking: bool = False,
        reasoning_effort: str = "high",    # high/max
        extra_body: dict[str, Any] = {},
    ) -> BaseChatModel:
    if thinking:
        extra_body["thinking"] = {"type": "enabled"}
    else:
        extra_body["thinking"] = {"type": "disabled"}
    return ChatDeepSeek(
        model=model_name,
        api_key=settings.deepseek_api_key, # type: ignore
        temperature=temperature,
        extra_body=extra_body,
        reasoning_effort=reasoning_effort,
        stream_usage=True,
        callbacks=[TokenUsageCallbackHandler("DeepSeek", model_name)],
    )


def create_structured_model(
        structured: type[BaseModel],
        model_name: str,
        temperature: float = 0.0,
        thinking: bool = False,
        reasoning_effort: str = "high",
        extra_body: dict[str, Any] = {},
    ):
    """创建结构化输出模型。

    DeepSeek 思考模式不支持 function_calling 底层的 tool_choice，因此结构化输出
    需要显式禁用 thinking。
    """
    chat_model = ChatDeepSeek(
        model=model_name,
        api_key=settings.deepseek_api_key,  # type: ignore
        temperature=temperature,
        extra_body={"thinking": {"type": "disabled"}},
        stream_usage=True,
        callbacks=[TokenUsageCallbackHandler("DeepSeek", model_name)],
    )
    return chat_model.with_structured_output(structured, method="function_calling")


def _test_model():
    class UserInfo(BaseModel):
        name: str
        age: int
    model = create_chat_model("deepseek-v4-flash")
    print(model.invoke("你好"))

    structured_model = create_structured_model(UserInfo, "deepseek-v4-flash")
    user_text = "我叫小班班，今年22岁。"
    response = structured_model.invoke(user_text)
    print(response)


if __name__ == "__main__":
    _test_model()
