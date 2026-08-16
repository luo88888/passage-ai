"""
AI 修改大纲智能体
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, List, Optional

from app.agent.base_agent import BaseAgent
from app.constants.prompt import PromptConstant
from app.schemas.article import OutlineResult, OutlineSection
from app.utils.logger import logger

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from app.services.agent_log_service import AgentLogService


class AiModifyOutlineAgent(BaseAgent):
    """AI 修改大纲智能体（根据用户建议重写大纲，产出结构化 OutlineResult）"""

    def __init__(
        self,
        model: BaseChatModel,
        agent_log_service: AgentLogService,
        structured_model: Optional[Any] = None,
    ):
        """初始化智能体

        Args:
            model: 已配置好的 LangChain BaseChatModel 实例（由 llm_factory 创建）
            agent_log_service: 日志服务
            structured_model: 结构化输出模型（OutlineResult schema），供
                _call_structured_model 使用
        """
        super().__init__(model, agent_log_service, structured_model)

    async def run(
        self,
        task_id: str,
        main_title: str,
        sub_title: str,
        current_sections: List[OutlineSection],
        modify_suggestion: str,
        target_word_count: int,
        language_style: Optional[str],
    ) -> List[OutlineSection]:
        """根据用户修改建议重写大纲，返回新的章节列表

        Args:
            task_id: 任务 ID
            main_title: 主标题
            sub_title: 副标题
            current_sections: 当前大纲章节
            modify_suggestion: 用户修改建议
            target_word_count: 目标总字数
            language_style: 语言风格（可选）

        Returns:
            修改后的章节列表
        """
        current_outline_json = json.dumps(
            [item.model_dump() for item in current_sections],
            ensure_ascii=False,
        )
        prompt = (
            PromptConstant.AI_MODIFY_OUTLINE_PROMPT
            .replace("{mainTitle}", main_title)
            .replace("{subTitle}", sub_title)
            .replace("{currentOutline}", current_outline_json)
            .replace("{modifySuggestion}", modify_suggestion)
            .replace("{targetWordCount}", str(target_word_count))
        )
        # 注入语言风格提示词（与大纲生成节点保持一致），使修改后大纲同样贴合语气取向
        prompt += self._get_language_style_prompt(language_style)

        async with self._agent_log_context(
            task_id=task_id or "unknown",
            agent_name="ai_modify_outline",
            prompt=prompt,
            input_data={
                "mainTitle": main_title,
                "subTitle": sub_title,
                "currentSectionsCount": len(current_sections),
            },
        ) as log_data:
            result: OutlineResult = await self._call_structured_model(
                prompt,
                agent_name="ai_modify_outline",
            )
            sections = result.sections
            log_data["outputData"] = self._safe_json_dumps(
                {"sectionsCount": len(sections)}
            )

        logger.info(
            "AI 修改大纲成功, taskId=%s, sections=%s", task_id, len(sections)
        )
        return sections
