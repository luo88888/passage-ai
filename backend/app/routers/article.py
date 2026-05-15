import asyncio

from databases import Database
from fastapi import APIRouter, Depends

from app.database import get_db
from app.deps import require_login
from app.exceptions import ErrorCode, throw_if
from app.schemas.article import ArticleAiModifyOutlineRequest, ArticleConfirmOutlineRequest, ArticleConfirmTitleRequest, ArticleCreateRequest, ArticleQueryRequest, ArticleVO, CreationOptionsVO
from app.schemas.common import BaseResponse, DeleteRequest
from app.schemas.user import LoginUserVO
from app.services.article_async_service import article_async_service
from app.services.article_service import ArticleService
from app.managers.sse_manager import sse_emitter_manager


router = APIRouter(prefix="/article", tags=["文章管理"])


@router.post("/create", response_model=BaseResponse[str])
async def create_article(
    request: ArticleCreateRequest,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login)
):
    """创建文章任务"""
    throw_if(
        not request.topic or not request.topic.strip(),
        ErrorCode.PARAMS_ERROR,
        "选题不能为空"
    )
    
    service = ArticleService(db)
    
    # 检查并消耗配额 + 创建文章任务（在同一事务中）
    task_id = await service.create_article_task_with_quota_check(
        request.topic,
        current_user,
        request.style,
        request.enabled_image_methods
    )
    
    # 异步执行阶段1：生成标题方案
    # FIXME: 未保存引用的 Task 可能被 GC，phase1/2/3 各一处
    asyncio.create_task(
        article_async_service.execute_phase1(
            task_id,
            request.topic,
            request.style,
        )
    )
    
    return BaseResponse.success(data=task_id, message="任务创建成功")


@router.post("/confirm-title", response_model=BaseResponse[None])
async def confirm_title(
    request: ArticleConfirmTitleRequest,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login)
):
    """确认标题并输入补充描述"""
    service = ArticleService(db)
    await service.confirm_title(
        task_id=request.task_id,
        selected_main_title=request.selected_main_title,
        selected_sub_title=request.selected_sub_title,
        user_description=request.user_description,
        login_user=current_user,
    )
    asyncio.create_task(article_async_service.execute_phase2(request.task_id))
    return BaseResponse.success(data=None)


@router.post("/confirm-outline", response_model=BaseResponse[None])
async def confirm_outline(
    request: ArticleConfirmOutlineRequest,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login)
):
    """确认大纲"""
    service = ArticleService(db)
    await service.confirm_outline(
        task_id=request.task_id,
        outline=request.outline,
        login_user=current_user,
    )
    asyncio.create_task(article_async_service.execute_phase3(request.task_id))
    return BaseResponse.success(data=None)


@router.post("/ai-modify-outline", response_model=BaseResponse[list])
async def ai_modify_outline(
    request: ArticleAiModifyOutlineRequest,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login)
):
    """AI 修改大纲"""
    service = ArticleService(db)
    modified_outline = await service.ai_modify_outline(
        task_id=request.task_id,
        modify_suggestion=request.modify_suggestion,
        login_user=current_user,
    )
    return BaseResponse.success(data=[section.model_dump() for section in modified_outline])



@router.get("/options", response_model=BaseResponse[CreationOptionsVO])
async def get_creation_options(
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login)
):
    """获取创作页可选项（文章风格 / 配图方式），供前端动态渲染，避免硬编码"""
    service = ArticleService(db)
    data = service.get_creation_options()
    return BaseResponse.success(data=data)


@router.get("/progress/{task_id}")
async def get_progress(
    task_id: str,
    db: Database = Depends(get_db),
    current_user: LoginUserVO = Depends(require_login)
):
    """SSE 进度推送"""
    throw_if(not task_id or not task_id.strip(), ErrorCode.PARAMS_ERROR, "任务ID不能为空")
    
    # 校验权限（内部会检查任务是否存在以及用户是否有权限访问）
    service = ArticleService(db)
    await service.get_article_detail(task_id, current_user)
    
    # 创建 SSE Emitter 并返回 StreamingResponse
    return sse_emitter_manager.create_emitter(task_id)


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