from datetime import datetime
import json
from typing import List, Optional, Tuple
import uuid
from databases import Database
from databases.interfaces import Record
from sqlalchemy import and_, func, select



from app.constants.user import UserConstant
from app.exceptions import BusinessException, ErrorCode, throw_if, throw_if_not
from app.models.article import Article
from app.models.enums import ArticlePhaseEnum, ArticleStatusEnum, ArticleStyleEnum
from app.schemas.article import ArticleQueryRequest, ArticleState, ArticleVO, CreationOptionsVO, OptionItem, OutlineSection, TitleOption
from app.schemas.user import LoginUserVO
from app.services.article_agent_service import ArticleAgentService
from app.services.image_service_strategy import image_service_strategy
from app.utils.logger import logger


class ArticleService:
    """文章服务类，提供下述服务：
    1. 创建文章任务，返回 task_id（写进数据库）
    2. 更新文章状态
    3. 保存文章内容（根据传入的 state）
    4. 获取文章详情（ArticleVO）
    5. 删除文章
    6. 分页查询，返回 (List[Article], total)
    """

    def __init__(self, db: Database):
        self.db = db

    async def create_article_task_with_quota_check(
        self,
        topic: str,
        login_user: LoginUserVO,
        style: Optional[str] = None,
        enabled_image_methods: Optional[List[str]] = None
    ) -> str:
        """创建文章任务（暂不检查配额）"""
        task_id = str(uuid.uuid4())
        
        query = """
            INSERT INTO article (taskId, userId, topic, style, status, createTime, enabledImageMethods)
            VALUES (:taskId, :userId, :topic, :style, :status, :createTime, :enabledImageMethods)
        """
        await self.db.execute(
            query=query,
            values={
                "taskId": task_id,
                "userId": login_user.id,
                "topic": topic,
                "style": style,
                "status": ArticleStatusEnum.PENDING.value,
                "createTime": datetime.now(),
                "enabledImageMethods": json.dumps(enabled_image_methods or [])
            }
        )

        logger.info("创建文章任务 taskId=%s, userId=%s, topic=%s", task_id, login_user.id, topic)
        return task_id

    def get_creation_options(self) -> CreationOptionsVO:
        """获取创作页可选项：文章风格（全量枚举）+ 配图方式（仅已注册可用的方法）。

        enums.ArticleStyleEnum / ImageMethodEnum 提供 label 与 description 中文文案，
        而非在此处硬编码；配图方式直接取策略器 service_map 已注册集合，
        保证与实际可用能力始终一致。
        """
        styles = [
            OptionItem(value=s.value, label=s.label, description=s.description)
            for s in ArticleStyleEnum
        ]
        image_methods = [
            OptionItem(value=m.value, label=m.label, description=m.description)
            for m in image_service_strategy.get_enabled_methods()
        ]
        return CreationOptionsVO(styles=styles, imageMethods=image_methods)


    async def update_article_status(
        self,
        task_id: str,
        status: ArticleStatusEnum,
        error_message: Optional[str] = None
    ):
        """更新文章状态"""
        if status == ArticleStatusEnum.COMPLETED:
            query = """UPDATE article SET status = :status, completedTime = :completedTime
                    WHERE taskId = :taskId"""
            await self.db.execute(query=query, values={
                "status": status.value, "completedTime": datetime.now(), "taskId": task_id
            })
        elif status == ArticleStatusEnum.FAILED:
            query = """UPDATE article SET status = :status, errorMessage = :errorMessage
                    WHERE taskId = :taskId"""
            await self.db.execute(query=query, values={
                "status": status.value, "errorMessage": error_message, "taskId": task_id
            })
        else:
            query = "UPDATE article SET status = :status WHERE taskId = :taskId"
            await self.db.execute(query=query, values={"status": status.value, "taskId": task_id})

        if status == ArticleStatusEnum.FAILED:
            logger.error("文章状态流转 taskId=%s -> %s, errorMessage=%s", task_id, status.value, error_message)
        else:
            logger.info("文章状态流转 taskId=%s -> %s", task_id, status.value)


    async def save_article_content(self, task_id: str, state: ArticleState):
        """保存文章内容"""
        # 从 images 列表中提取 position=1 的封面图 URL
        cover_image = None
        if state.images:
            cover = next((img for img in state.images if img.position == 1), None)
            if cover and cover.url:
                cover_image = cover.url
        
        query = """
            UPDATE article 
            SET mainTitle = :mainTitle, subTitle = :subTitle, outline = :outline,
                content = :content, fullContent = :fullContent,
                coverImage = :coverImage, images = :images
            WHERE taskId = :taskId
        """
        assert state.title is not None
        assert state.outline is not None
        assert state.images is not None
        await self.db.execute(query=query, values={
            "mainTitle": state.title.main_title,
            "subTitle": state.title.sub_title,
            "outline": json.dumps([s.model_dump() for s in state.outline.sections], ensure_ascii=False),
            "content": state.content,
            "fullContent": state.full_content,
            "coverImage": cover_image,
            "images": json.dumps([img.model_dump(by_alias=True) for img in state.images], ensure_ascii=False),
            "taskId": task_id
        })

        logger.info("文章内容已保存 taskId=%s, mainTitle=%s, imagesCount=%s",
                    task_id, state.title.main_title, len(state.images))


    async def get_article_detail(self, task_id: str, login_user: LoginUserVO) -> ArticleVO:
        """获取文章详情"""
        article = await self.get_by_task_id(task_id)
        throw_if_not(article, ErrorCode.NOT_FOUND_ERROR, "文章不存在")
        assert article is not None
        self._check_article_permission(article, login_user)
        return self._to_article_vo(article)


    def _check_article_permission(self, article, login_user: LoginUserVO) -> None:
        """检查文章访问权限"""
        if article["userId"] != login_user.id and login_user.user_role != UserConstant.ADMIN_ROLE:
            logger.warning("无权限访问文章 taskId=%s, ownerId=%s, operatorId=%s",
                           article.get("taskId"), article.get("userId"), login_user.id)
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限访问")


    async def get_by_task_id(self, task_id: str) -> Optional[Record]:
        """根据任务 ID 查询文章记录"""
        query = select(Article).where(and_(Article.task_id == task_id, Article.is_delete == 0))
        return await self.db.fetch_one(query)


    def _to_article_vo(self, article: Record) -> ArticleVO:
        """转换为 ArticleVO"""
        article_dict = dict(article)
        title_options = json.loads(article_dict["titleOptions"]) if article_dict.get("titleOptions") else None
        outline = json.loads(article_dict["outline"]) if article_dict.get("outline") else None
        images = json.loads(article_dict["images"]) if article_dict.get("images") else None
        return ArticleVO(
            id=article_dict["id"],
            taskId=article_dict["taskId"],
            userId=article_dict["userId"],
            topic=article_dict["topic"],
            userDescription=article_dict.get("userDescription"),    # 后期新增
            style=article_dict.get("style"),                        # 后期新增
            mainTitle=article_dict.get("mainTitle"),
            subTitle=article_dict.get("subTitle"),
            titleOptions=title_options,                             # 后期新增
            outline=outline,
            content=article_dict.get("content"),
            fullContent=article_dict.get("fullContent"),
            coverImage=article_dict.get("coverImage"),
            images=images,
            status=article_dict["status"],
            phase=article_dict.get("phase"),                        # 后期新增
            errorMessage=article_dict.get("errorMessage"),
            createTime=article_dict["createTime"].isoformat(),
            completedTime=article_dict["completedTime"].isoformat() if article_dict.get("completedTime") else None,
            updateTime=article_dict["updateTime"].isoformat(),
        )

    async def delete_article(self, article_id: int, login_user: LoginUserVO) -> bool:
        """删除文章"""
        query = select(Article).where(and_(Article.id == article_id, Article.is_delete == 0))
        article = await self.db.fetch_one(query)
        throw_if_not(article, ErrorCode.NOT_FOUND_ERROR, "文章不存在")
        self._check_article_permission(article, login_user)
        await self.db.execute(query="UPDATE article SET isDelete = 1 WHERE id = :id", values={"id": article_id})
        logger.info("删除文章 articleId=%s, operatorId=%s", article_id, login_user.id)
        return True

    async def list_article_by_page(
        self,
        request: ArticleQueryRequest,
        login_user: LoginUserVO,
    ) -> Tuple[List[ArticleVO], int]:
        """分页查询文章列表"""
        conditions = [Article.is_delete == 0]
        if login_user.user_role != "admin":
            conditions.append(Article.user_id == login_user.id)

        if request.id:
            conditions.append(Article.id == request.id)
        if request.task_id:
            conditions.append(Article.task_id == request.task_id)
        if request.user_id:
            conditions.append(Article.user_id == request.user_id)
        if request.topic:
            conditions.append(Article.topic.like(f"%{request.topic}%"))
        if request.status:
            conditions.append(Article.status == request.status)

        count_query = select(func.count(Article.id)).where(and_(*conditions))
        total = await self.db.fetch_val(count_query)

        query = (
            select(Article)
            .where(and_(*conditions))
            .order_by(Article.create_time.desc())
            .limit(request.page_size)
            .offset((request.current - 1) * request.page_size)
        )
        articles = await self.db.fetch_all(query)
        return [self._to_article_vo(article) for article in articles], total # type: ignore

    async def update_phase(self, task_id: str, phase: ArticlePhaseEnum) -> None:
        """更新文章阶段"""
        article = await self.get_by_task_id(task_id)
        if not article:
            logger.error("文章不存在 taskId=%s", task_id)
            return

        current_phase_value = article["phase"] or ArticlePhaseEnum.PENDING.value
        try:
            current_phase = ArticlePhaseEnum(current_phase_value)
        except ValueError as e:
            raise BusinessException(ErrorCode.OPERATION_ERROR, "当前阶段非法") from e
        if current_phase != phase and not current_phase.can_transition_to(phase):
            raise BusinessException(ErrorCode.OPERATION_ERROR, "非法阶段转换")

        await self.db.execute(query="UPDATE article SET phase = :phase WHERE taskId = :taskId", values={
            "phase": phase.value,
            "taskId": task_id,
        })

    async def save_title_options(self, task_id: str, title_options: List[TitleOption]):
        """保存标题方案列表"""
        await self.db.execute(
            query="UPDATE article SET titleOptions = :titleOptions WHERE taskId = :taskId",
            values={
                "taskId": task_id,
                "titleOptions": json.dumps(
                    [item.model_dump(by_alias=True) for item in title_options],
                    ensure_ascii=False,
                ),
            },
        )

    async def confirm_title(
        self,
        task_id: str,
        selected_main_title: str,
        selected_sub_title: str,
        user_description: Optional[str],
        login_user: LoginUserVO,
    ):
        """确认标题并进入大纲阶段"""
        article = await self.get_by_task_id(task_id)
        throw_if_not(article, ErrorCode.NOT_FOUND_ERROR, "文章不存在")
        self._check_article_permission(article, login_user)
        throw_if(
            article["phase"] != ArticlePhaseEnum.TITLE_SELECTING.value, # type: ignore
            ErrorCode.OPERATION_ERROR,
            "当前阶段不允许确认标题",
        )

        await self.db.execute(
            query="""
                UPDATE article
                SET mainTitle = :mainTitle,
                    subTitle = :subTitle,
                    userDescription = :userDescription,
                    phase = :phase
                WHERE taskId = :taskId
            """,
            values={
                "taskId": task_id,
                "mainTitle": selected_main_title,
                "subTitle": selected_sub_title,
                "userDescription": user_description,
                "phase": ArticlePhaseEnum.OUTLINE_GENERATING.value,
            },
        )

    async def confirm_outline(
        self,
        task_id: str,
        outline: List[OutlineSection],
        login_user: LoginUserVO,
    ):
        """确认大纲并进入正文阶段"""
        article = await self.get_by_task_id(task_id)
        throw_if_not(article, ErrorCode.NOT_FOUND_ERROR, "文章不存在")
        self._check_article_permission(article, login_user)
        throw_if(
            article["phase"] != ArticlePhaseEnum.OUTLINE_EDITING.value, # type: ignore
            ErrorCode.OPERATION_ERROR,
            "当前阶段不允许确认大纲",
        )

        await self.db.execute(
            query="""
                UPDATE article
                SET outline = :outline,
                    phase = :phase
                WHERE taskId = :taskId
            """,
            values={
                "taskId": task_id,
                "outline": json.dumps([item.model_dump() for item in outline], ensure_ascii=False),
                "phase": ArticlePhaseEnum.CONTENT_GENERATING.value,
            },
        )

    async def save_outline(self, task_id: str, outline: List[OutlineSection]):
        """保存大纲内容（不推进阶段）"""
        await self.db.execute(
            query="UPDATE article SET outline = :outline WHERE taskId = :taskId",
            values={
                "taskId": task_id,
                "outline": json.dumps([item.model_dump() for item in outline], ensure_ascii=False),
            },
        )

    async def ai_modify_outline(
        self,
        task_id: str,
        modify_suggestion: str,
        login_user: LoginUserVO,
    ) -> List[OutlineSection]:
        """AI 修改大纲"""
        article = await self.get_by_task_id(task_id)
        throw_if_not(article, ErrorCode.NOT_FOUND_ERROR, "文章不存在")
        self._check_article_permission(article, login_user)
        throw_if(
            article["phase"] != ArticlePhaseEnum.OUTLINE_EDITING.value, # type: ignore
            ErrorCode.OPERATION_ERROR,
            "当前阶段不允许 AI 修改大纲",
        )
        throw_if(not article["outline"], ErrorCode.OPERATION_ERROR, "当前文章尚未生成大纲") # type: ignore

        current_outline = [OutlineSection(**item) for item in json.loads(article["outline"])]   # type: ignore
        agent_service = ArticleAgentService()
        modified_outline = await agent_service.ai_modify_outline(
            main_title=article["mainTitle"],    # type: ignore
            sub_title=article["subTitle"],      # type: ignore
            current_outline=current_outline,
            modify_suggestion=modify_suggestion,
        )
        await self.db.execute(
            query="UPDATE article SET outline = :outline WHERE taskId = :taskId",
            values={
                "taskId": task_id,
                "outline": json.dumps(
                    [item.model_dump() for item in modified_outline],
                    ensure_ascii=False,
                ),
            },
        )
        return modified_outline
