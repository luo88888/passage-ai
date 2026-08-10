import axios, { type AxiosError, type AxiosRequestConfig } from 'axios'
import { message } from 'ant-design-vue'

// 创建 Axios 实例
const myAxios = axios.create({
  // 生产默认同源 /api（由 Nginx 反代到后端）；跨域部署时用 VITE_API_BASE_URL 覆盖
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 60000,
  withCredentials: true,  // 必须！携带 Cookie
})

// 业务错误码：未登录
const NOT_LOGIN_CODE = 40100

// 公开接口：未登录也放行（不跳转登录页、不提示），如登录/注册/获取登录态/创作选项/会员套餐等
const PUBLIC_API_PATTERNS = [
  '/user/get/login',
  '/user/login',
  '/user/register',
  '/article/options',
  '/payment/plans',
]

// 请求选项扩展：skipAuthRedirect 供个别接口显式豁免「未登录跳转」
interface RequestOptions extends AxiosRequestConfig {
  skipAuthRedirect?: boolean
}

// ---------- 全局 message 去重：同文案短时间（默认 3s）内不重复弹 ----------
let lastToastText = ''
let lastToastAt = 0
function toastOnce(text: string, type: 'warning' | 'error' = 'warning', interval = 3000) {
  const now = Date.now()
  if (text === lastToastText && now - lastToastAt < interval) return
  lastToastText = text
  lastToastAt = now
  if (type === 'error') {
    message.error(text)
  } else {
    message.warning(text)
  }
}

/** 判断请求 URL 是否属于公开接口 */
function isPublicApi(url?: string): boolean {
  if (!url) return false
  return PUBLIC_API_PATTERNS.some((p) => url.includes(p))
}

// HTTP 状态码 → 中文文案（避免 "Network Error" / "timeout of 60000ms exceeded" 等英文直出）
const HTTP_ERROR_MESSAGE: Record<number, string> = {
  400: '请求参数错误',
  401: '未登录或登录已过期',
  403: '没有权限执行该操作',
  404: '请求的资源不存在',
  405: '请求方法不被允许',
  409: '请求冲突，请稍后重试',
  422: '请求参数校验失败',
  429: '请求过于频繁，请稍后再试',
  500: '服务器开小差了，请稍后重试',
  502: '网关错误，请稍后重试',
  503: '服务暂不可用，请稍后重试',
  504: '网关超时，请稍后重试',
}

/**
 * 未登录统一处理：
 * 1. 清空 Pinia 中的旧登录态（避免服务端会话过期后内存残留脏 id）；
 * 2. SPA 内跳转登录页并携带当前地址作为 redirect（动态 import router 避免循环依赖）；
 * 3. 仅提示一次，不打断其他页面逻辑。
 */
async function handleUnauthorized(url?: string) {
  if (isPublicApi(url)) return
  try {
    const { useLoginUserStore } = await import('@/stores/loginUser')
    useLoginUserStore().setLoginUser({ userName: '未登录' })
  } catch {
    // Pinia 未就绪时忽略，跳转兜底逻辑继续
  }
  try {
    const { default: router } = await import('@/router')
    const current = router.currentRoute.value
    if (current.path !== '/user/login') {
      const redirect = encodeURIComponent(current.fullPath)
      router.replace(`/user/login?redirect=${redirect}`)
    }
  } catch {
    // 兜底：动态 import 失败时退回整页跳转
    const current = window.location.pathname + window.location.search
    if (!current.startsWith('/user/login')) {
      window.location.href = `/user/login?redirect=${encodeURIComponent(current)}`
    }
  }
  toastOnce('请先登录')
}

// 全局响应拦截器
myAxios.interceptors.response.use(
  function (response) {
    const { data, config } = response
    // 未登录：公开接口放行，其余走统一处理并抛错短路业务代码（避免页面重复弹错误 toast）
    if (data && data.code === NOT_LOGIN_CODE) {
      const opts = (config || {}) as RequestOptions
      if (!opts.skipAuthRedirect) {
        void handleUnauthorized(config?.url)
        return Promise.reject(new Error('未登录'))
      }
    }
    return response
  },
  function (error) {
    const err = error as AxiosError
    // 无 response：网络异常 / 超时
    if (!err.response) {
      err.message = '网络异常，请稍后重试'
      toastOnce(err.message, 'error')
      return Promise.reject(err)
    }
    // 有 response：按状态码映射中文，业务响应体 message 优先
    const status = err.response.status
    const bizMsg = (err.response.data as { message?: string })?.message
    err.message = bizMsg || HTTP_ERROR_MESSAGE[status] || `请求失败（HTTP ${status}）`
    toastOnce(err.message, 'error')
    return Promise.reject(err)
  },
)

export default myAxios
