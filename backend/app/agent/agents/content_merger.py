"""
图文合并智能体
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.agent.base_agent import _safe_json_dumps, agent_log_context_sync
from app.schemas.article import ArticleState
from app.utils.logger import logger

if TYPE_CHECKING:
    from app.services.agent_log_service import AgentLogService


class ContentMergerAgent:
    """图文合并智能体（同步，不调用 LLM）"""

    def __init__(self, agent_log_service: AgentLogService):
        self.agent_log_service = agent_log_service

    def run(self, state: ArticleState):
        """将配图占位符替换为 Markdown 图片语法，填充 state.full_content"""
        with agent_log_context_sync(
            self.agent_log_service,
            task_id=state.task_id,
            agent_name="agent6_merge_content",
            prompt="merge_images_into_content",
            input_data={"imagesCount": len(state.images or [])},
        ) as log_data:
            content = state.content
            images = state.images

            if not images:
                state.full_content = content
                log_data["outputData"] = _safe_json_dumps(
                    {"fullContentLength": len(content or "")}
                )
                return

            full_content = content

            for image in images:
                placeholder_id = image.placeholder_id
                if placeholder_id:
                    image_markdown = f"![{image.description}]({image.url})"
                    full_content = full_content.replace(  # type: ignore
                        placeholder_id, image_markdown
                    )

            state.full_content = full_content
            log_data["outputData"] = _safe_json_dumps(
                {"fullContentLength": len(full_content) if full_content else 0}
            )
            logger.info(
                "图文合并完成 taskId=%s, images=%s",
                state.task_id,
                len(images) if images else 0,
            )
