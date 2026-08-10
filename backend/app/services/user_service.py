"""用户服务"""

from typing import Optional, List, Tuple, Any
from sqlalchemy import select, func, and_, or_
from databases import Database

from app.models.user import User
from app.schemas.user import (
    UserRegisterRequest,
    UserLoginRequest,
    UserAddRequest,
    UserUpdateRequest,
    UserQueryRequest,
    UserVO,
    UserProfileVO,
    LoginUserVO,
    UserProfileUpdateRequest,
    UserChangePasswordRequest,
)
from app.constants.points import PointsConstant
from app.constants.user import UserConstant
from app.exceptions import ErrorCode, throw_if, throw_if_not, BusinessException
from app.services.points_service import PointsService
from app.utils.password import encrypt_password, verify_password
from app.utils.logger import logger


class UserService:
    """用户服务"""
    
    def __init__(self, db: Database):
        self.db = db
    
    async def register(self, request: UserRegisterRequest) -> int:
        """用户注册"""
        # 校验参数
        throw_if(
            len(request.user_account) < 4,
            ErrorCode.PARAMS_ERROR,
            "账号长度不能小于 4 位"
        )
        throw_if(
            len(request.user_password) < 8,
            ErrorCode.PARAMS_ERROR,
            "密码长度不能小于 8 位"
        )
        throw_if(
            request.user_password != request.check_password,
            ErrorCode.PARAMS_ERROR,
            "两次输入的密码不一致"
        )
        
        # 检查账号是否已存在
        query = select(func.count(User.id)).where(
            and_(User.user_account == request.user_account, User.is_delete == 0)
        )
        count = await self.db.fetch_val(query)
        throw_if(count > 0, ErrorCode.USER_ALREADY_EXIST, "账号已存在")
        
        # 加密密码
        encrypted_password = encrypt_password(request.user_password)
        
        # 插入用户 + 初始化积分账户（同一事务：注册赠送 100 积分）
        async with self.db.transaction():
            query = """
                INSERT INTO user (userAccount, userPassword, userName, userRole, quota)
                VALUES (:userAccount, :userPassword, :userName, :userRole, :quota)
            """
            user_id = await self.db.execute(
                query=query,
                values={
                    "userAccount": request.user_account,
                    "userPassword": encrypted_password,
                    "userName": f"用户{request.user_account}",
                    "userRole": UserConstant.DEFAULT_ROLE,
                    "quota": UserConstant.DEFAULT_QUOTA,
                }
            )
            await PointsService(self.db).grant_points(
                user_id=user_id,
                amount=PointsConstant.DEFAULT_POINTS,
                tx_type=PointsConstant.TX_REGISTER,
                description="注册赠送积分",
            )

        logger.info("用户注册成功 userAccount=%s, userId=%s", request.user_account, user_id)
        return user_id
    
    async def login(self, request: UserLoginRequest) -> LoginUserVO:
        """用户登录"""
        # 校验参数
        throw_if(
            len(request.user_account) < 4,
            ErrorCode.PARAMS_ERROR,
            "账号长度不能小于 4 位"
        )
        throw_if(
            len(request.user_password) < 8,
            ErrorCode.PARAMS_ERROR,
            "密码长度不能小于 8 位"
        )
        
        # 查询用户
        query = select(User).where(
            and_(User.user_account == request.user_account, User.is_delete == 0)
        )
        user = await self.db.fetch_one(query)
        # 账号不存在与密码错误统一对外提示，防止用户枚举；internal_code 保留内部区分（账号级锁定过滤用）
        throw_if_not(
            user,
            ErrorCode.PASSWORD_ERROR,
            "账号或密码错误",
            internal_code=ErrorCode.USER_NOT_EXIST,
        )
        assert user is not None  # type narrow: throw_if_not 保证了 user 不为 None
        
        # 验证密码（bcrypt(sha256(password))）
        password_match = verify_password(request.user_password, user["userPassword"])
        if not password_match:
            logger.warning("登录密码错误 userAccount=%s", request.user_account)
        throw_if(
            not password_match,
            ErrorCode.PASSWORD_ERROR,
            "账号或密码错误"
        )

        user_dict = dict(user)

        # 返回登录用户信息
        logger.info("用户登录成功 userAccount=%s, userId=%s", user_dict["userAccount"], user_dict["id"])
        return await self._to_login_vo(user_dict)
    
    async def _get_points_version(self, user_id: int) -> Optional[int]:
        """查询用户积分账户乐观锁版本（登录/当前用户接口带回，前端实时刷新余额用）。

        Args:
            user_id: 用户 ID。

        Returns:
            user_points.version；无账户（未初始化）返回 None。
        """
        try:
            row = await self.db.fetch_one(
                query="SELECT version FROM user_points WHERE userId = :userId",
                values={"userId": user_id},
            )
            return int(row["version"]) if row else None
        except Exception:
            logger.exception("积分版本查询失败 userId=%s", user_id)
            return None

    async def _to_login_vo(self, user_dict: dict) -> LoginUserVO:
        """将 user 行字典转为 LoginUserVO（含积分账户乐观锁版本）。

        Args:
            user_dict: 查询到的 user 行（dict 形态）。

        Returns:
            LoginUserVO 实例。
        """
        return LoginUserVO(
            id=user_dict["id"],
            userAccount=user_dict["userAccount"],
            userName=user_dict["userName"],
            userAvatar=user_dict["userAvatar"],
            userProfile=user_dict["userProfile"],
            userRole=user_dict["userRole"],
            quota=user_dict.get("quota"),
            points=user_dict.get("points"),
            pointsVersion=await self._get_points_version(user_dict["id"]),
            activeTaskCount=user_dict.get("activeTaskCount"),
            vipTime=user_dict["vipTime"].isoformat() if user_dict.get("vipTime") else None,
            createTime=user_dict["createTime"].isoformat(),
            updateTime=user_dict["updateTime"].isoformat()
        )

    async def get_login_user(self, user_id: int) -> Optional[LoginUserVO]:
        """按用户 ID 查询最新登录态（供开通会员等场景同步刷新 Redis Session 使用）。

        Args:
            user_id: 用户 ID。

        Returns:
            最新 LoginUserVO；用户不存在返回 None。
        """
        query = select(User).where(and_(User.id == user_id, User.is_delete == 0))
        user = await self.db.fetch_one(query)
        if not user:
            return None
        return await self._to_login_vo(dict(user))

    async def update_profile(
        self, user_id: int, request: UserProfileUpdateRequest
    ) -> Optional[LoginUserVO]:
        """更新当前用户个人资料（昵称/头像/简介）。

        Args:
            user_id: 当前登录用户 ID。
            request: 待更新内容（user_name / user_avatar / user_profile，至少一项非空）。

        Returns:
            更新后的 LoginUserVO；用户不存在返回 None。

        Raises:
            BusinessException: 没有可更新的字段 / 昵称为空。
        """
        # 检查用户是否存在
        query = select(User).where(and_(User.id == user_id, User.is_delete == 0))
        user = await self.db.fetch_one(query)
        if not user:
            return None

        # 至少提供一项要更新的字段
        has_update = any([
            request.user_name is not None,
            request.user_avatar is not None,
            request.user_profile is not None,
        ])
        throw_if(not has_update, ErrorCode.PARAMS_ERROR, "没有需要更新的字段")

        # 昵称不能为空字符串
        if request.user_name is not None:
            throw_if(not request.user_name.strip(), ErrorCode.PARAMS_ERROR, "昵称不能为空")

        # 构建动态更新字段
        update_fields = []
        values: dict[str, Any] = {"id": user_id}
        if request.user_name is not None:
            update_fields.append("userName = :userName")
            values["userName"] = request.user_name.strip()
        if request.user_avatar is not None:
            update_fields.append("userAvatar = :userAvatar")
            values["userAvatar"] = request.user_avatar
        if request.user_profile is not None:
            update_fields.append("userProfile = :userProfile")
            values["userProfile"] = request.user_profile

        query = f"UPDATE user SET {', '.join(update_fields)} WHERE id = :id"
        await self.db.execute(query=query, values=values)

        # 重新查询并返回最新用户信息（供前端同步刷新登录态）
        query = select(User).where(and_(User.id == user_id, User.is_delete == 0))
        user = await self.db.fetch_one(query)
        if not user:
            return None

        logger.info("用户更新个人资料 userId=%s, fields=%s", user_id, update_fields)
        return await self._to_login_vo(dict(user))

    async def change_password(self, user_id: int, request: UserChangePasswordRequest) -> bool:
        """修改密码（校验原密码后更新）。

        Args:
            user_id: 当前登录用户 ID。
            request: 原密码 + 新密码 + 确认密码。

        Returns:
            修改成功返回 True。

        Raises:
            BusinessException: 用户不存在 / 原密码错误 / 两次新密码不一致 /
                新密码长度不足 / 新密码与原密码相同。
        """
        query = select(User).where(and_(User.id == user_id, User.is_delete == 0))
        user = await self.db.fetch_one(query)
        throw_if_not(user, ErrorCode.USER_NOT_EXIST, "用户不存在")
        assert user is not None  # type narrow: throw_if_not 保证了 user 不为 None

        # 校验原密码
        old_match = verify_password(request.old_password, user["userPassword"])
        throw_if(not old_match, ErrorCode.PASSWORD_ERROR, "原密码错误")

        # 校验新密码
        throw_if(
            request.new_password != request.check_password,
            ErrorCode.PARAMS_ERROR,
            "两次输入的新密码不一致",
        )
        throw_if(
            len(request.new_password) < 8,
            ErrorCode.PARAMS_ERROR,
            "新密码长度不能小于 8 位",
        )
        throw_if(
            request.new_password == request.old_password,
            ErrorCode.PARAMS_ERROR,
            "新密码不能与原密码相同",
        )

        new_encrypted = encrypt_password(request.new_password)
        await self.db.execute(
            query="UPDATE user SET userPassword = :userPassword WHERE id = :id",
            values={"userPassword": new_encrypted, "id": user_id},
        )
        logger.info("用户修改密码成功 userId=%s", user_id)
        return True

    async def get_by_id(self, user_id: int) -> Optional[UserVO]:
        """根据 ID 获取用户"""
        query = select(User).where(and_(User.id == user_id, User.is_delete == 0))
        user = await self.db.fetch_one(query)
        
        if not user:
            return None

        user_dict = dict(user)
        
        return UserVO(
            id=user_dict["id"],
            userAccount=user_dict["userAccount"],
            userName=user_dict["userName"],
            userAvatar=user_dict["userAvatar"],
            userProfile=user_dict["userProfile"],
            userRole=user_dict["userRole"],
            quota=user_dict.get("quota"),
            points=user_dict.get("points"),
            vipTime=user_dict["vipTime"].isoformat() if user_dict.get("vipTime") else None,
            createTime=user_dict["createTime"].isoformat()
        )
    
    async def get_profile(self, user_id: int) -> Optional[UserProfileVO]:
        """获取用户主页信息（基本信息 + 积分/配额 + 创作统计）。

        Args:
            user_id: 用户 ID。

        Returns:
            UserProfileVO；用户不存在返回 None。
        """
        query = select(User).where(and_(User.id == user_id, User.is_delete == 0))
        user = await self.db.fetch_one(query)
        if not user:
            return None

        user_dict = dict(user)

        # 创作文章总数（未删除）
        article_count = await self.db.fetch_val(
            query="SELECT COUNT(*) FROM article WHERE userId = :userId AND isDelete = 0",
            values={"userId": user_id},
        )

        # 积分余额（权威以 user_points 为准，缺失回退 user.points 冗余字段）
        points = user_dict.get("points")
        try:
            points_row = await self.db.fetch_one(
                query="SELECT balance FROM user_points WHERE userId = :userId",
                values={"userId": user_id},
            )
            if points_row:
                points = int(points_row["balance"])
        except Exception:
            logger.exception("用户积分查询失败 userId=%s", user_id)

        return UserProfileVO(
            id=user_dict["id"],
            userAccount=user_dict["userAccount"],
            userName=user_dict["userName"],
            userAvatar=user_dict["userAvatar"],
            userProfile=user_dict["userProfile"],
            userRole=user_dict["userRole"],
            quota=user_dict.get("quota"),
            points=points,
            activeTaskCount=user_dict.get("activeTaskCount"),
            vipTime=user_dict["vipTime"].isoformat() if user_dict.get("vipTime") else None,
            createTime=user_dict["createTime"].isoformat(),
            articleCount=article_count or 0,
        )

    async def list_by_page(self, request: UserQueryRequest) -> Tuple[List[UserVO], int]:
        """分页查询用户列表"""
        # 构建查询条件
        conditions = [User.is_delete == 0]
        
        if request.id:
            conditions.append(User.id == request.id)
        if request.user_account:
            conditions.append(User.user_account.like(f"%{request.user_account}%"))
        if request.user_name:
            conditions.append(User.user_name.like(f"%{request.user_name}%"))
        if request.user_profile:
            conditions.append(User.user_profile.like(f"%{request.user_profile}%"))
        if request.user_role:
            conditions.append(User.user_role == request.user_role)
        
        # 查询总数
        count_query = select(func.count(User.id)).where(and_(*conditions))
        total = await self.db.fetch_val(count_query)
        
        # 分页查询
        query = select(User).where(and_(*conditions))
        
        # 排序
        if request.sort_field:
            order_column = getattr(User, request.sort_field, None)
            if order_column is not None:
                if request.sort_order == "ascend":
                    query = query.order_by(order_column.asc())
                else:
                    query = query.order_by(order_column.desc())
        else:
            query = query.order_by(User.create_time.desc())
        
        # 分页
        offset = (request.current - 1) * request.page_size
        query = query.limit(request.page_size).offset(offset)
        
        users = await self.db.fetch_all(query)
        
        user_list = []
        for user in users:
            user_dict = dict(user)
            user_list.append(
                UserVO(
                    id=user_dict["id"],
                    userAccount=user_dict["userAccount"],
                    userName=user_dict["userName"],
                    userAvatar=user_dict["userAvatar"],
                    userProfile=user_dict["userProfile"],
                    userRole=user_dict["userRole"],
                    quota=user_dict.get("quota"),
                    points=user_dict.get("points"),
                    vipTime=user_dict["vipTime"].isoformat() if user_dict.get("vipTime") else None,
                    createTime=user_dict["createTime"].isoformat()
                )
            )
        
        return user_list, total
    
    async def add_user(self, request: UserAddRequest) -> int:
        """添加用户（管理员）"""
        # 校验账号是否已存在
        query = select(func.count(User.id)).where(
            and_(User.user_account == request.user_account, User.is_delete == 0)
        )
        count = await self.db.fetch_val(query)
        throw_if(count > 0, ErrorCode.USER_ALREADY_EXIST, "账号已存在")
        
        # 加密密码
        encrypted_password = encrypt_password(request.user_password)
        
        # 插入用户 + 初始化积分账户（同一事务：管理员新增默认赠送积分）
        async with self.db.transaction():
            query = """
                INSERT INTO user (userAccount, userPassword, userName, userAvatar, userProfile, userRole, quota)
                VALUES (:userAccount, :userPassword, :userName, :userAvatar, :userProfile, :userRole, :quota)
            """
            user_id = await self.db.execute(
                query=query,
                values={
                    "userAccount": request.user_account,
                    "userPassword": encrypted_password,
                    "userName": request.user_name or f"用户{request.user_account}",
                    "userAvatar": request.user_avatar,
                    "userProfile": request.user_profile,
                    "userRole": request.user_role,
                    "quota": UserConstant.DEFAULT_QUOTA,
                }
            )
            await PointsService(self.db).grant_points(
                user_id=user_id,
                amount=PointsConstant.DEFAULT_POINTS,
                tx_type=PointsConstant.TX_ADMIN_ADJUST,
                description="管理员新增用户赠送积分",
            )

        logger.info("管理员新增用户 userAccount=%s, userId=%s, userRole=%s", request.user_account, user_id, request.user_role)
        return user_id
    
    async def update_user(self, request: UserUpdateRequest) -> bool:
        """更新用户（管理员）"""
        # 检查用户是否存在
        query = select(func.count(User.id)).where(and_(User.id == request.id, User.is_delete == 0))
        count = await self.db.fetch_val(query)
        throw_if(count == 0, ErrorCode.NOT_FOUND_ERROR, "用户不存在")
        
        # 构建更新字段
        update_fields = []
        values: dict[str, Any] = {"id": request.id}
        
        if request.user_name is not None:
            update_fields.append("userName = :userName")
            values["userName"] = request.user_name
        
        if request.user_avatar is not None:
            update_fields.append("userAvatar = :userAvatar")
            values["userAvatar"] = request.user_avatar
        
        if request.user_profile is not None:
            update_fields.append("userProfile = :userProfile")
            values["userProfile"] = request.user_profile
        
        if request.user_role is not None:
            update_fields.append("userRole = :userRole")
            values["userRole"] = request.user_role
        
        throw_if(len(update_fields) == 0, ErrorCode.PARAMS_ERROR, "没有需要更新的字段")
        
        # 执行更新
        query = f"UPDATE user SET {', '.join(update_fields)} WHERE id = :id"
        await self.db.execute(query=query, values=values)

        logger.info("管理员更新用户 userId=%s, fields=%s", request.id, update_fields)
        return True
    
    async def delete_user(self, user_id: int) -> bool:
        """删除用户（逻辑删除）"""
        # 检查用户是否存在
        query = select(func.count(User.id)).where(and_(User.id == user_id, User.is_delete == 0))
        count = await self.db.fetch_val(query)
        throw_if(count == 0, ErrorCode.NOT_FOUND_ERROR, "用户不存在")
        
        # 逻辑删除
        query = "UPDATE user SET isDelete = 1 WHERE id = :id"
        await self.db.execute(query=query, values={"id": user_id})

        logger.info("管理员删除用户 userId=%s", user_id)
        return True
