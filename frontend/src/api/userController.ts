// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** Add User 添加用户（管理员） POST /user/add */
export async function addUser(
  body: API.UserAddRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseInt_>("/user/add", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Upload Avatar 上传用户头像（multipart/form-data，字段名 file）
 *
 * 仅支持 JPG / PNG / WebP / GIF，大小不超过 2MB；
 * 文件保存到本地 static/images/avatar/，返回可访问的图片 URL。 POST /user/avatar/upload */
export async function uploadUserAvatar(file: File, options?: { [key: string]: any }) {
  const formData = new FormData()
  formData.append('file', file)
  return request<{ code: number; data: string; message?: string }>('/user/avatar/upload', {
    method: 'POST',
    data: formData,
    ...(options || {}),
  })
}

/** Change Password 修改当前登录用户的密码

安全策略：修改成功后清除 Redis Session 与 Cookie，强制用户重新登录。 POST /user/change-password */
export async function changePassword(
  body: API.UserChangePasswordRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseBool_>("/user/change-password", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Delete User 删除用户（管理员） POST /user/delete */
export async function deleteUser(
  body: API.DeleteRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseBool_>("/user/delete", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Get User By Id 根据 ID 获取用户 GET /user/get */
export async function getUserById(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getUserByIdParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseUserVO_>("/user/get", {
    method: "GET",
    params: {
      ...params,
    },
    ...(options || {}),
  });
}

/** Get Login User 获取当前登录用户 GET /user/get/login */
export async function getLoginUser(options?: { [key: string]: any }) {
  return request<API.BaseResponseLoginUserVO_>("/user/get/login", {
    method: "GET",
    ...(options || {}),
  });
}

/** List Users By Page 分页查询用户列表（管理员） POST /user/list/page */
export async function listUsersByPage(
  body: API.UserQueryRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseDict_>("/user/list/page", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Login 用户登录（单账号失败超限后锁定 + IP 级失败限流，防密码爆破与撞库） POST /user/login */
export async function userLogin(
  body: API.UserLoginRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseLoginUserVO_>("/user/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Logout 用户登出（清除 Cookie 与 Redis 服务端会话） POST /user/logout */
export async function userLogout(options?: { [key: string]: any }) {
  return request<API.BaseResponseBool_>("/user/logout", {
    method: "POST",
    ...(options || {}),
  });
}

/** Get User Profile 获取当前登录用户的主页信息（个人详情页：基本信息 + 积分/配额 + 创作数量等统计） GET /user/profile */
export async function getUserProfile(options?: { [key: string]: any }) {
  return request<API.BaseResponseUserProfileVO_>("/user/profile", {
    method: "GET",
    ...(options || {}),
  });
}

/** Update User Profile 更新当前登录用户的个人资料（昵称/头像/简介）

更新成功后同步刷新 Redis Session 中的用户信息，
保证下次 GET /user/get/login 返回最新资料。 POST /user/profile/update */
export async function updateUserProfile(
  body: API.UserProfileUpdateRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseLoginUserVO_>("/user/profile/update", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Register 用户注册（同一 IP 在窗口内限次） POST /user/register */
export async function userRegister(
  body: API.UserRegisterRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseInt_>("/user/register", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** Update User 更新用户（管理员） POST /user/update */
export async function updateUser(
  body: API.UserUpdateRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseBool_>("/user/update", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}
