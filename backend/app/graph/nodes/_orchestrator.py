"""图节点共享的智能体编排器单例

现有智能体（app/agent/agents/）实例由 ArticleAgentOrchestrator 持有。
原 article_async_service 每个 phase 都 new 一个 ArticleAgentService（含新 OpenAI 客户端 + 新编排器），
既浪费连接又导致状态分散。此处改为图节点共享一个编排器单例。

get_orchestrator() 首次调用时惰性构造（import 也放在函数体内，避免与 services 层形成循环导入）：
  - 复用 app.agent.image_generator.parallel_image_generator（图片服务单例）
  - 建 AsyncOpenAI(DashScope) + AgentLogService
  - 构造 ArticleAgentOrchestrator 持有 6 个 agent
"""
from __future__ import annotations

from app.agent.orchestrator import ArticleAgentOrchestrator
from app.config import settings
from openai import AsyncOpenAI

# database / parallel_image_generator 延迟到 get_orchestrator() 内 import，
# 避免模块导入时触发 app.services.__init__ → article_async_service → graph 的循环。

_orchestrator: ArticleAgentOrchestrator | None = None


def get_orchestrator() -> ArticleAgentOrchestrator:
    """惰性获取共享编排器单例（持有 6 个 agent 实例）

    运行期才构造；AgentLogService / parallel_image_generator / database 的 import 延迟到此处，
    避免模块导入时触发 app.services.__init__ → article_async_service → graph 的循环。
    """
    global _orchestrator
    if _orchestrator is None:
        from app.services.agent_log_service import AgentLogService
        from app.database import database
        from app.agent.image_generator import parallel_image_generator

        client = AsyncOpenAI(
            api_key=settings.dashscope_api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        agent_log_service = AgentLogService(database)
        _orchestrator = ArticleAgentOrchestrator(
            client=client,
            model=settings.dashscope_model,
            agent_log_service=agent_log_service,
            parallel_image_generator=parallel_image_generator,
        )
    return _orchestrator