"""
文章智能体编排服务
职责：基础设施初始化 + 对外 API 门面
具体的 Agent 逻辑已迁移至 app/agent/agents/ 目录下的各个智能体类
"""
from contextlib import contextmanager
from datetime import datetime
import json
from typing import Callable, List, Optional

from openai import AsyncOpenAI

from app.agent.orchestrator import ArticleAgentOrchestrator
from app.config import settings
from app.database import database
from app.schemas.article import (
    ArticleState,
    OutlineSection,
)
from app.constants.prompt import PromptConstant
from app.services.agent_log_service import AgentLogService
from app.agent.image_generator import parallel_image_generator
from app.utils.logger import logger


class ArticleAgentService:
    """文章智能体编排服务

    职责：
    1. 创建和持有基础设施（LLM 客户端、图片策略、日志服务等）
    2. 创建编排器并注入依赖
    3. 提供 execute_phase1/2/3 对外接口（thin wrapper）
    4. 提供 ai_modify_outline 独立辅助方法
    """

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.dashscope_api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.model = settings.dashscope_model

        # 复用图片生成模块单例（服务实例与 httpx/AsyncOpenAI 客户端全程共享，
        # 避免每个请求重复构造 ParallelImageGenerator + 5 个图片服务）。
        self.agent_log_service = AgentLogService(database)
        self.parallel_image_generator = parallel_image_generator

        # 创建编排器，注入所有共享依赖
        self.orchestrator = ArticleAgentOrchestrator(
            client=self.client,
            model=self.model,
            agent_log_service=self.agent_log_service,
            parallel_image_generator=self.parallel_image_generator,
        )

    # ==================== 阶段入口（thin wrappers） ====================

    async def execute_phase1_generate_titles(
        self,
        state: ArticleState,
        stream_handler: Callable[[str], None],
    ):
        """阶段1：生成标题方案"""
        try:
            await self.orchestrator.execute_phase1(state, stream_handler)
        except Exception as e:
            logger.error("阶段1失败, taskId=%s, error=%s", state.task_id, e)
            raise RuntimeError(f"标题方案生成失败: {str(e)}")

    async def execute_phase2_generate_outline(
        self,
        state: ArticleState,
        stream_handler: Callable[[str], None],
    ):
        """阶段2：生成大纲"""
        try:
            await self.orchestrator.execute_phase2(state, stream_handler)
        except Exception as e:
            logger.error("阶段2失败, taskId=%s, error=%s", state.task_id, e)
            raise RuntimeError(f"大纲生成失败: {str(e)}")

    async def execute_phase3_generate_content(
        self,
        state: ArticleState,
        stream_handler: Callable[[str], None],
    ):
        """阶段3：生成正文、配图和合并内容"""
        try:
            await self.orchestrator.execute_phase3(state, stream_handler)
        except Exception as e:
            logger.error("阶段3失败, taskId=%s, error=%s", state.task_id, e)
            raise RuntimeError(f"正文生成失败: {str(e)}")

    # ==================== AI 修改大纲（独立辅助方法） ====================

    async def ai_modify_outline(
        self,
        main_title: str,
        sub_title: str,
        current_outline: List[OutlineSection],
        modify_suggestion: str,
        task_id: Optional[str],
    ) -> List[OutlineSection]:
        """AI 修改大纲（独立于编排流水线）"""
        current_outline_json = json.dumps(
            [item.model_dump() for item in current_outline],
            ensure_ascii=False,
        )
        prompt = (
            PromptConstant.AI_MODIFY_OUTLINE_PROMPT
            .replace("{mainTitle}", main_title)
            .replace("{subTitle}", sub_title)
            .replace("{currentOutline}", current_outline_json)
            .replace("{modifySuggestion}", modify_suggestion)
        )

        with self._agent_log_context_sync(
            task_id=task_id or "unknown",
            agent_name="ai_modify_outline",
            prompt=prompt,
            input_data={
                "mainTitle": main_title,
                "subTitle": sub_title,
                "currentSectionsCount": len(current_outline),
            },
        ) as log_data:
            content = await self._call_llm(prompt)
            outline_data = self._parse_json_response(content, "修改后的大纲")
            sections = [
                OutlineSection(**section) for section in outline_data["sections"]
            ]
            log_data["outputData"] = self._safe_json_dumps(
                {"sectionsCount": len(sections)}
            )
            return sections

    # ==================== 精简的私有辅助方法（仅用于 ai_modify_outline） ====================

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM（非流式）"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content  # type: ignore
        except Exception as e:
            logger.error(
                "LLM 调用失败(非流式) model=%s, error=%s",
                self.model,
                str(e),
                exc_info=True,
            )
            raise

    @contextmanager
    def _agent_log_context_sync(
        self,
        task_id: Optional[str],
        agent_name: str,
        prompt: Optional[str] = None,
        input_data: Optional[dict] = None,
    ):
        """同步智能体日志上下文"""
        start_time = datetime.now()
        log_data = {
            "taskId": task_id or "unknown",
            "agentName": agent_name,
            "startTime": start_time,
            "status": "RUNNING",
            "prompt": prompt,
            "inputData": self._safe_json_dumps(input_data),
            "outputData": None,
            "errorMessage": None,
        }
        try:
            yield log_data
            log_data["status"] = "SUCCESS"
        except Exception as exc:
            log_data["status"] = "FAILED"
            log_data["errorMessage"] = str(exc)
            raise
        finally:
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            log_data["endTime"] = end_time
            log_data["durationMs"] = duration_ms
            self.agent_log_service.save_log_async(log_data)

    @staticmethod
    def _parse_json_response(content: str, name: str) -> dict:
        """解析 JSON 响应"""
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(
                "%s解析失败, content=%s, error=%s", name, content, str(e)
            )
            raise RuntimeError(f"{name}解析失败")

    @staticmethod
    def _safe_json_dumps(value: Optional[dict]) -> Optional[str]:
        """安全序列化 JSON"""
        if value is None:
            return None
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return None
