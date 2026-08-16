import asyncio
import hashlib

from databases import Database
from fastapi import APIRouter, Depends

from app.config import settings
from app.database import get_db
from app.deps import require_create_slot, require_login
from app.exceptions import ErrorCode, throw_if, throw_if_not
from app.redis import get_client
from app.schemas.article import ArticleAiModifyOutlineRequest, ArticleConfirmOutlineRequest, ArticleConfirmTitleRequest, ArticleCreateRequest, ArticleQueryRequest, ArticleVO, CreationOptionsVO
from app.schemas.common import BaseResponse, DeleteRequest
from app.schemas.statistic import AgentExecutionStatsVO
from app.schemas.user import LoginUserVO
from app.services.agent_log_service import AgentLogService
from app.graph.graph_runner import article_async_service
from app.services.article_service import ArticleService
from app.managers.sse_manager import sse_emitter_manager
from app.utils.logger import logger


router = APIRouter(prefix="/article", tags=["文章管理"])


@router.post("/create", response_model=BaseResponse[str])
async def create_article(
    request: ArticleCreateRequest,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_create_slot)
):
    """创建文章任务（后付费闸门：余额 >= 0 + 并发名额快速失败）"""
    throw_if(
        not request.topic or not request.topic.strip(),
        ErrorCode.PARAMS_ERROR,
        "选题不能为空"
    )

    fingerprint = hashlib.sha256(
        f"{request.topic.strip()}|{request.word_count or 2000}|{request.genre or ''}|{request.language_style or ''}|{sorted(request.enabled_image_methods or [])}".encode()
    ).hexdigest()
    dedup_key = f"dedup:article:{current_user.id}:{fingerprint}"
    redis = get_client()
    if not redis:
        logger.error("redis 为 None")
        throw_if(True, ErrorCode.SYSTEM_ERROR, "系统内部错误")
        
    assert redis is not None
    acquired = await redis.set(dedup_key, "1", nx=True, ex=settings.dedup_window_seconds)
    throw_if_not(
        acquired,
        ErrorCode.OPERATION_ERROR,
        f"请勿重复提交，{settings.dedup_window_seconds} 秒内已提交过相同参数的任务",
    )
    

    service = ArticleService(db)

    # 占用并发名额（activeTaskCount+1）+ 创建文章任务（在同一事务中，后付费闸门）
    # 第二个返回值 final_image_methods 为处理后的配图白名单（非 VIP 未勾选时仅含普通方式），
    # 必须传给图启动 state，否则图里 None=全部可用会绕过 VIP 配图权限校验。
    task_id, final_image_methods = await service.create_article_task_with_slot_check(
        request.topic,
        current_user,
        request.style,
        request.enabled_image_methods,
        request.genre,
        request.language_style,
        request.word_count,
    )

    # 异步执行阶段1：生成标题方案（LangGraph 编排，跑到 confirm_title 后 interrupt）
    # 字数兜底：用户未填走默认 2000；新闻题材由条件边走信息采集节点
    word_count = request.word_count if request.word_count else 2000
    # 先原子占坑再启动任务（create 路径由上方 Redis 去重键兜底重复提交，这里统一走三段式并发守卫）
    article_async_service.reserve_task(task_id, action="正在生成标题方案")
    try:
        task = asyncio.create_task(
            article_async_service.start(
                task_id,
                request.topic,
                request.genre,
                request.language_style,
                word_count,
                final_image_methods,
                request.style,
                user_id=current_user.id,
            )
        )
        article_async_service.attach_task(task_id, task)
    except BaseException:
        article_async_service.release_task(task_id)
        raise

    return BaseResponse.success(data=task_id, message="任务创建成功")


@router.post("/confirm-title", response_model=BaseResponse[None])
async def confirm_title(
    request: ArticleConfirmTitleRequest,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login)
):
    """确认标题并输入补充描述"""
    # 先原子占坑（任何 await / DB 副作用之前），重复 resume 零副作用拒绝
    article_async_service.reserve_task(request.task_id, action="正在生成大纲")
    try:
        service = ArticleService(db)
        # 续跑前余额复查：balance + max_debt_points >= 0（透支护栏，admin 豁免）
        await service.assert_sufficient_points_for_resume(request.task_id, current_user)
        await service.confirm_title(
            task_id=request.task_id,
            selected_main_title=request.selected_main_title,
            selected_sub_title=request.selected_sub_title,
            user_description=request.user_description,
            login_user=current_user,
        )
        # 用户已确认标题，续跑图：注入标题/描述 → 生成大纲
        task = asyncio.create_task(article_async_service.resume(
            request.task_id,
            {
                "title": {
                    "mainTitle": request.selected_main_title,
                    "subTitle": request.selected_sub_title,
                },
                "user_description": request.user_description,
            },
            user_id=current_user.id,
        ))
        article_async_service.attach_task(request.task_id, task)
    except BaseException:
        # 校验/写库失败回滚占坑，避免名额卡死后续 resume
        article_async_service.release_task(request.task_id)
        raise
    return BaseResponse.success(data=None)


@router.post("/confirm-outline", response_model=BaseResponse[None])
async def confirm_outline(
    request: ArticleConfirmOutlineRequest,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login)
):
    """确认大纲"""
    # 先原子占坑（任何 await / DB 副作用之前），重复 resume 零副作用拒绝
    article_async_service.reserve_task(request.task_id, action="正在生成正文")
    try:
        service = ArticleService(db)
        # 续跑前余额复查：balance + max_debt_points >= 0（透支护栏，admin 豁免）
        await service.assert_sufficient_points_for_resume(request.task_id, current_user)
        await service.confirm_outline(
            task_id=request.task_id,
            outline=request.outline,
            login_user=current_user,
        )
        # 用户已确认大纲，续跑图：注入编辑后大纲 → 生成正文/配图/全文
        # 同时显式清空 modify_suggestion，兜底防止此前 AI 修改残留导致条件边再次路由进修改节点
        task = asyncio.create_task(article_async_service.resume(
            request.task_id,
            {
                "outline": {"sections": [s.model_dump() for s in request.outline]},
                "modify_suggestion": None,
            },
            user_id=current_user.id,
        ))
        article_async_service.attach_task(request.task_id, task)
    except BaseException:
        # 校验/写库失败回滚占坑，避免名额卡死后续 resume
        article_async_service.release_task(request.task_id)
        raise
    return BaseResponse.success(data=None)


@router.post("/ai-modify-outline", response_model=BaseResponse[dict])
async def ai_modify_outline(
    request: ArticleAiModifyOutlineRequest,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login)
):
    """AI 修改大纲（fire-and-forget）

    路由层做前置校验（文章存在 / 归属 / 阶段为 OUTLINE_EDITING / 已有大纲 / VIP），
    通过后异步续跑图：注入 modify_suggestion → 条件边路由进 ai_modify_outline 节点，
    由节点跑 LLM + 落库 + 发 AI_MODIFY_OUTLINE_COMPLETE / FAILED SSE。
    路由只回 ack（taskId），大纲由 SSE 回填前端。
    """
    # 先原子占坑（任何 await / DB 副作用之前），重复 resume 零副作用拒绝
    article_async_service.reserve_task(request.task_id, action="AI 正在修改大纲")
    try:
        service = ArticleService(db)
        # 续跑前余额复查：AI 修改大纲每轮都要即时结算，透支超限拒绝修改
        await service.assert_sufficient_points_for_resume(request.task_id, current_user)
        await service.assert_can_ai_modify_outline(
            task_id=request.task_id,
            login_user=current_user,
        )
        task = asyncio.create_task(
            article_async_service.resume(
                request.task_id,
                {"modify_suggestion": request.modify_suggestion},
                user_id=current_user.id,
            )
        )
        article_async_service.attach_task(request.task_id, task)
    except BaseException:
        # 校验/写库失败回滚占坑，避免名额卡死后续 resume
        article_async_service.release_task(request.task_id)
        raise
    return BaseResponse.success(data={"taskId": request.task_id})



@router.get("/options", response_model=BaseResponse[CreationOptionsVO])
async def get_creation_options(
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login)
):
    """获取创作页可选项（题材 / 语言风格 / 配图方式），供前端动态渲染，避免硬编码"""
    service = ArticleService(db)
    data = service.get_creation_options()
    return BaseResponse.success(data=data)


@router.get("/progress/{task_id}")
async def get_progress(
    task_id: str,
    after: int = 0,  # 断点续传：只重放 seq > after 的历史消息（after=0 全量重放）
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login)
):
    """SSE 进度推送（支持 ?after= 断点续传：先重放历史，再续接实时流）"""
    throw_if(not task_id or not task_id.strip(), ErrorCode.PARAMS_ERROR, "任务ID不能为空")
    throw_if(after < 0, ErrorCode.PARAMS_ERROR, "after 不能为负数")

    # 校验权限（内部会检查任务是否存在以及用户是否有权限访问）
    service = ArticleService(db)
    await service.get_article_detail(task_id, current_user)

    # 创建 SSE Emitter 并返回 StreamingResponse
    return sse_emitter_manager.create_emitter(task_id, after_seq=after)


@router.post("/list", response_model=BaseResponse[dict])
async def list_article(
    request: ArticleQueryRequest,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login)
):
    """分页查询文章列表"""
    service = ArticleService(db)
    articles, total = await service.list_article_by_page(request, current_user)
    return BaseResponse.success(data={
        "records": articles, "total": total,
        "current": request.current, "size": request.page_size
    })


@router.post("/delete", response_model=BaseResponse[bool])
async def delete_article(
    request: DeleteRequest,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login)
):
    """删除文章"""
    throw_if(not request.id, ErrorCode.PARAMS_ERROR, "文章ID不能为空")
    service = ArticleService(db)
    result = await service.delete_article(request.id, current_user)
    return BaseResponse.success(data=result, message="删除成功")


@router.get("/{task_id}", response_model=BaseResponse[ArticleVO])
async def get_article(
    task_id: str,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login)
):
    """获取文章详情"""
    service = ArticleService(db)
    article_vo = await service.get_article_detail(task_id, current_user)
    return BaseResponse.success(data=article_vo)


@router.get("/execution-logs/{task_id}", response_model=BaseResponse[AgentExecutionStatsVO])
async def get_execution_logs(
    task_id: str,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login),
):
    """获取任务执行日志"""
    throw_if(not task_id or not task_id.strip(), ErrorCode.PARAMS_ERROR, "任务ID不能为空")

    # 校验权限（内部会检查任务是否存在以及用户是否有权限访问）
    service = ArticleService(db)
    await service.get_article_detail(task_id, current_user)
    
    service = AgentLogService(db)
    stats = await service.get_execution_stats(task_id)
    return BaseResponse.success(data=stats)
