from datetime import datetime
import json
from typing import List, Optional, Tuple
import uuid
from databases import Database
from databases.interfaces import Record
from sqlalchemy import and_, func, select



from app.constants.user import UserConstant
from app.exceptions import BusinessException, ErrorCode, throw_if_not
from app.models.article import Article
from app.models.enums import ArticleStatusEnum
from app.schemas.article import ArticleQueryRequest, ArticleState, ArticleVO
from app.schemas.user import LoginUserVO
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
        login_user: LoginUserVO
    ) -> str:
        """创建文章任务（暂不检查配额）"""
        task_id = str(uuid.uuid4())
        
        query = """
            INSERT INTO article (taskId, userId, topic, status, createTime)
            VALUES (:taskId, :userId, :topic, :status, :createTime)
        """
        await self.db.execute(
            query=query,
            values={
                "taskId": task_id,
                "userId": login_user.id,
                "topic": topic,
                "status": ArticleStatusEnum.PENDING.value,
                "createTime": datetime.now()
            }
        )

        logger.info("创建文章任务 taskId=%s, userId=%s, topic=%s", task_id, login_user.id, topic)
        return task_id


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
        # HACK: 空字符串可能导致异常
        # title_options = json.loads(article_dict["titleOptions"]) if article_dict.get("titleOptions") else None
        title_options = None
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