from datetime import datetime
import json
from typing import List, Optional, Tuple
import uuid

from databases import Database
from databases.interfaces import Record
from sqlalchemy import and_, func, select


from app.constants.user import UserConstant
from app.exceptions import BusinessException, ErrorCode, throw_if, throw_if_not
from app.config import settings
from app.services.points_service import PointsService
from app.models.article import Article
from app.models.enums import ArticleGenreEnum, ArticleLanguageStyleEnum, ArticlePhaseEnum, ArticleStatusEnum, ImageMethodEnum
from app.schemas.article import ArticleQueryRequest, ArticleState, ArticleVO, CreationOptionsVO, OptionItem, OutlineSection, ResearchDataVO, TitleOption
from app.schemas.user import LoginUserVO
from app.services.image_generator import parallel_image_generator
from app.utils.logger import logger


class ArticleService:
    """文章服务类，对外提供下述服务：
    1. 创建文章任务，返回 (task_id, final_image_methods)（task_id 写进数据库）
        - create_article_task -> Tuple[str, Optional[List[str]]]
        - create_article_task_with_slot_check -> Tuple[str, Optional[List[str]]]
    2. 获取创作页可选项：文章风格 + 配图方式
        - get_creation_options(self) -> CreationOptionsVO
    3. 更新文章状态
        - update_article_status
    4. 保存文章内容（根据传入的 state）
        - save_article_content
    5. 获取文章详情（ArticleVO）
        - get_article_detail -> ArticleVO
    6. 根据任务 ID 查询文章记录
        - get_by_task_id -> Optional[Record]
    7. 删除文章
        - delete_article
    8. 分页查询文章列表
        - list_article_by_page -> Tuple[List[ArticleVO], int]
    9. 更新文章阶段
        - update_phase
    10. 保存标题方案列表
        - save_title_options
    11. 确认标题并进入大纲阶段
        - confirm_title
    12. 确认大纲并进入正文阶段
        - confirm_outline
    13. 保存大纲内容（不推进阶段）
        - save_outline
    14. AI 修改大纲
        - ai_modify_outline
    """

    def __init__(self, db: Database):
        self.db = db
        self._default_non_vip_image_methods = [
            ImageMethodEnum.PEXELS.value,
            ImageMethodEnum.MERMAID.value,
            ImageMethodEnum.ICONIFY.value,
            ImageMethodEnum.EMOJI_PACK.value,
        ]
        self._vip_only_image_methods = {
            ImageMethodEnum.NANO_BANANA.value,
            ImageMethodEnum.ZHIPU.value,
            ImageMethodEnum.SVG_DIAGRAM.value,
        }

    @staticmethod
    def _get_enabled_image_methods():
        """返回当前已注册的配图方式"""
        return parallel_image_generator.get_enabled_methods()


    async def create_article_task(
            self,
            topic: str,
            login_user: LoginUserVO,
            style: Optional[str] = None,
            enabled_image_methods: Optional[List[str]] = None,
            genre: Optional[str] = None,
            language_style: Optional[str] = None,
            word_count: Optional[int] = None,
        ) -> Tuple[str, Optional[List[str]]]:
            """创建文章任务

            Returns:
                (task_id, final_image_methods)：task_id 为任务 ID；
                final_image_methods 为处理后的配图白名单（None=全部可用），
                供图启动 state 使用，保证 DB 与图两侧口径一致。
            """
            final_image_methods = self._process_image_methods(enabled_image_methods, login_user)
            self._validate_image_methods(final_image_methods, login_user)

            task_id = str(uuid.uuid4())
            now = datetime.now()
            query = """
                INSERT INTO article (
                    taskId, userId, topic, style, enabledImageMethods, status, phase, createTime,
                    genre, languageStyle, wordCount
                )
                VALUES (
                    :taskId, :userId, :topic, :style, :enabledImageMethods, :status, :phase, :createTime,
                    :genre, :languageStyle, :wordCount
                )
            """
            await self.db.execute(
                query=query,
                values={
                    "taskId": task_id,
                    "userId": login_user.id,
                    "topic": topic,
                    "style": style,
                    "enabledImageMethods": json.dumps(final_image_methods, ensure_ascii=False)
                    if final_image_methods
                    else None,
                    "status": ArticleStatusEnum.PENDING.value,
                    "phase": ArticlePhaseEnum.PENDING.value,
                    "createTime": now,
                    "genre": genre,
                    "languageStyle": language_style,
                    "wordCount": word_count,
                },
            )
            logger.info("文章任务创建成功, taskId=%s, userId=%s", task_id, login_user.id)
            return task_id, final_image_methods

    async def create_article_task_with_slot_check(
        self,
        topic: str,
        login_user: LoginUserVO,
        style: Optional[str] = None,
        enabled_image_methods: Optional[List[str]] = None,
        genre: Optional[str] = None,
        language_style: Optional[str] = None,
        word_count: Optional[int] = None,
    ) -> Tuple[str, Optional[List[str]]]:
        """在同一事务中完成并发名额占用（activeTaskCount+1）和任务创建（后付费闸门）。

        以「积分 + 并发名额」作为门槛：
          - 仅 admin 豁免（不计数、不限并发）；VIP 与普通用户同样按积分结算并受并发限制；
          - 创建不预扣、不估算，仅原子占用「进行中」任务名额；
          - 余额 >= 0 的快速失败在路由层 require_create_slot 完成，此处做权威原子校验。

        Returns:
            (task_id, final_image_methods)：同 create_article_task。
        """
        if self._is_admin(login_user):
            return await self.create_article_task(
                topic=topic,
                login_user=login_user,
                style=style,
                enabled_image_methods=enabled_image_methods,
                genre=genre,
                language_style=language_style,
                word_count=word_count,
            )

        async with self.db.transaction():
            acquired = await self.acquire_task_slot(login_user.id)
            throw_if_not(
                acquired,
                ErrorCode.OPERATION_ERROR,
                f"进行中创作任务数已达上限（最多 {settings.max_active_tasks} 个），请先完成或删除后再创建",
            )
            return await self.create_article_task(
                topic=topic,
                login_user=login_user,
                style=style,
                enabled_image_methods=enabled_image_methods,
                genre=genre,
                language_style=language_style,
                word_count=word_count,
            )

    async def acquire_task_slot(self, user_id: int) -> bool:
        """原子占用任务名额：activeTaskCount + 1（< max_active_tasks 才成功）。

        Args:
            user_id: 用户 ID。

        Returns:
            True=占用成功；False=已超并发上限（原子 UPDATE 校验，无竞态）。
        """
        result = await self.db.execute(
            query="""
                UPDATE user
                SET activeTaskCount = activeTaskCount + 1
                WHERE id = :userId AND isDelete = 0 AND activeTaskCount < :maxActiveTasks
            """,
            values={"userId": user_id, "maxActiveTasks": settings.max_active_tasks},
        )
        return result > 0

    async def release_task_slot(self, user_id: int) -> None:
        """幂等释放任务名额：activeTaskCount - 1（GREATEST 防负数）。

        Args:
            user_id: 用户 ID。
        """
        await self.db.execute(
            query="""
                UPDATE user
                SET activeTaskCount = GREATEST(activeTaskCount - 1, 0)
                WHERE id = :userId AND activeTaskCount > 0
            """,
            values={"userId": user_id},
        )

    async def release_task_slot_for_task(self, task_id: str) -> None:
        """按任务释放名额：从 article 回查 userId 后幂等释放（终态事务内调用）。

        Args:
            task_id: 任务 ID。
        """
        article = await self.get_by_task_id(task_id)
        if article and article["userId"]:
            await self.release_task_slot(int(article["userId"]))

    def get_creation_options(self) -> CreationOptionsVO:
        """获取创作页可选项：题材 / 语言风格 + 配图方式（仅已注册可用的方法）。

        题材/语言风格枚举（ArticleGenreEnum / ArticleLanguageStyleEnum）提供 label 与
        description 中文文案；旧文章风格（ArticleStyleEnum）已弃用，不再返回。
        配图方式直接取策略器 service_map 已注册集合，保证与实际可用能力始终一致。
        """
        genres = [
            OptionItem(value=g.value, label=g.label, description=g.description) # pyright: ignore[reportCallIssue]
            for g in ArticleGenreEnum
        ]
        language_styles = [
            OptionItem(value=s.value, label=s.label, description=s.description) # pyright: ignore[reportCallIssue]
            for s in ArticleLanguageStyleEnum
        ]
        image_methods = [
            OptionItem(
                value=m.value,
                label=m.label,
                description=m.description,
                vip_only=m.value in self._vip_only_image_methods, # pyright: ignore[reportCallIssue]
            )
            for m in self._get_enabled_image_methods()
        ]
        return CreationOptionsVO(
            genres=genres,
            languageStyles=language_styles,
            imageMethods=image_methods,
        )


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
        research_data = None
        if article_dict.get("researchData"):
            try:
                research_data = ResearchDataVO(**json.loads(article_dict["researchData"])).model_dump(by_alias=True)
            except Exception as e:
                # 坏 JSON/字段缺失：容忍为空，不阻塞详情返回
                logger.warning(f"采集数据解析失败：{str(e)}")
                research_data = None
        return ArticleVO(
            id=article_dict["id"],
            taskId=article_dict["taskId"],
            userId=article_dict["userId"],
            topic=article_dict["topic"],
            userDescription=article_dict.get("userDescription"),    # 后期新增
            style=article_dict.get("style"),                        # 已弃用，保留兼容
            genre=article_dict.get("genre"),                        # 新增：题材
            languageStyle=article_dict.get("languageStyle"),        # 新增：语言风格
            wordCount=article_dict.get("wordCount"),                # 新增：目标字数
            mainTitle=article_dict.get("mainTitle"),
            subTitle=article_dict.get("subTitle"),
            titleOptions=title_options,                             # 后期新增
            outline=outline,
            content=article_dict.get("content"),
            fullContent=article_dict.get("fullContent"),
            researchData=research_data, # type: ignore
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
        """删除文章（进行中任务删除时释放并发名额 + 结算已发生用量）"""
        query = select(Article).where(and_(Article.id == article_id, Article.is_delete == 0))
        article = await self.db.fetch_one(query)
        throw_if_not(article, ErrorCode.NOT_FOUND_ERROR, "文章不存在")
        assert article is not None
        self._check_article_permission(article, login_user)

        was_active = article["status"] in (
            ArticleStatusEnum.PENDING.value,
            ArticleStatusEnum.PROCESSING.value,
        )

        async with self.db.transaction():
            await self.db.execute(query="UPDATE article SET isDelete = 1 WHERE id = :id", values={"id": article_id})
            if was_active:
                # 与 isDelete 同一事务释放名额（终态一致性）
                await self.release_task_slot(int(article["userId"]))

        # 删除进行中任务：结算剩余未结算用量（best-effort，结算水位幂等）
        if was_active:
            # 函数体内 import，避免启动期/路由层循环导入
            from app.services.settlement_service import SettlementService
            from app.services.model_usage_service import usage_recorder
            try:
                await SettlementService(self.db).settle_current_segment(article["taskId"])
            except Exception:
                logger.exception("删除任务结算失败 articleId=%s", article_id)
            usage_recorder.drop(article["taskId"])

        logger.info("删除文章 articleId=%s, operatorId=%s", article_id, login_user.id)
        return True

    async def complete_task_and_release_slot(self, task_id: str, state: ArticleState) -> None:
        """任务成功终态：保存内容 + 标记完成 + 释放并发名额（同一事务）。

        Args:
            task_id: 任务 ID。
            state: 智能体 class 形态的完整文章状态（含正文/配图/全文）。
        """
        async with self.db.transaction():
            await self.save_article_content(task_id, state)
            await self.update_article_status(task_id, ArticleStatusEnum.COMPLETED)
            await self.release_task_slot_for_task(task_id)

    async def fail_task_and_release_slot(self, task_id: str, error_message: Optional[str]) -> None:
        """任务失败终态：标记 FAILED + 释放并发名额（同一事务）。

        Args:
            task_id: 任务 ID。
            error_message: 失败原因。
        """
        async with self.db.transaction():
            await self.update_article_status(task_id, ArticleStatusEnum.FAILED, error_message)
            await self.release_task_slot_for_task(task_id)

    async def assert_sufficient_points_for_resume(
        self,
        task_id: str,
        login_user: LoginUserVO,
    ) -> None:
        """续跑/修改前余额复查：balance + max_debt_points >= 0（admin 豁免）。

        用于 confirm-title / confirm-outline / ai-modify-outline 路由层拦截：
        透支护栏 -MAX_DEBT_POINTS，透支超限拒绝续跑/修改，欠费用户签到/充值还清后再创作。

        Args:
            task_id: 任务 ID。
            login_user: 当前登录用户。

        Raises:
            BusinessException: 文章不存在 / 无权限 / 透支超限（INSUFFICIENT_POINTS）。
        """
        article = await self.get_by_task_id(task_id)
        throw_if_not(article, ErrorCode.NOT_FOUND_ERROR, "文章不存在")
        self._check_article_permission(article, login_user)
        if self._is_admin(login_user):
            return
        points_service = PointsService(self.db)
        balance = await points_service.get_balance(login_user.id)
        throw_if(
            balance + settings.max_debt_points < 0,
            ErrorCode.INSUFFICIENT_POINTS,
            f"当前透支已达上限（最多可透支 {settings.max_debt_points} 积分），请先签到/充值后再继续",
        )

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
        if request.statuses:
            # 多状态筛选（如“进行中”过滤 PENDING + PROCESSING）
            conditions.append(Article.status.in_(request.statuses))
        elif request.status:
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

    async def save_research_data(self, task_id: str, research_data: dict):
        """保存信息采集结果（结构化 JSON，供创作页/详情页可视化回看）

        Args:
            task_id: 任务 ID。
            research_data: 结构化采集结果，含 requirement / searchQueriesUsed / articles。
        """
        await self.db.execute(
            query="UPDATE article SET researchData = :researchData WHERE taskId = :taskId",
            values={
                "taskId": task_id,
                "researchData": json.dumps(research_data, ensure_ascii=False),
            },
        )

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

    async def assert_can_ai_modify_outline(
        self,
        task_id: str,
        login_user: LoginUserVO,
    ) -> None:
        """AI 修改大纲前置校验：文章存在 / 归属 / 阶段为 OUTLINE_EDITING / 已有大纲 / VIP

        实际的 LLM 重写 + 持久化 + SSE 已移入 graph 节点 ai_modify_outline_node，
        路由层校验通过后 fire-and-forget 调 article_async_service.resume 续跑图。
        """
        article = await self.get_by_task_id(task_id)
        throw_if_not(article, ErrorCode.NOT_FOUND_ERROR, "文章不存在")
        self._check_article_permission(article, login_user)
        throw_if(
            article["phase"] != ArticlePhaseEnum.OUTLINE_EDITING.value, # type: ignore
            ErrorCode.OPERATION_ERROR,
            "当前阶段不允许 AI 修改大纲",
        )
        throw_if(not article["outline"], ErrorCode.OPERATION_ERROR, "当前文章尚未生成大纲") # type: ignore
        throw_if_not(
            self._is_vip_or_admin(login_user),
            ErrorCode.NO_AUTH_ERROR,
            "AI 修改大纲功能仅限 VIP 会员使用",
        )

    def _process_image_methods(
        self,
        enabled_image_methods: Optional[List[str]],
        login_user: LoginUserVO,
    ) -> Optional[List[str]]:
        """处理配图方式默认值"""
        if enabled_image_methods:
            return enabled_image_methods

        if self._is_vip_or_admin(login_user):
            return None

        return list(self._default_non_vip_image_methods)

    def _validate_image_methods(
        self,
        enabled_image_methods: Optional[List[str]],
        login_user: LoginUserVO,
    ):
        """校验普通用户高级配图权限
        
        Raises:
            BusinessException: 高级配图功能仅限 VIP 会员使用
        """
        if not enabled_image_methods or self._is_vip_or_admin(login_user):
            return

        for method in enabled_image_methods:
            if method in self._vip_only_image_methods:
                raise BusinessException(
                    ErrorCode.NO_AUTH_ERROR,
                    "高级配图功能（AI 生图、SVG 图表）仅限 VIP 会员使用",
                )

    def _is_admin(self, login_user: LoginUserVO) -> bool:
        """是否为管理员（M3 起仅 admin 豁免积分与并发限制，VIP 与普通用户同价）"""
        return login_user.user_role == UserConstant.ADMIN_ROLE

    def _is_vip_or_admin(self, login_user: LoginUserVO) -> bool:
        """是否为 VIP 或管理员（历史配图权限判断仍按 VIP/admin 放行）"""
        return login_user.user_role in {UserConstant.ADMIN_ROLE, UserConstant.VIP_ROLE}
