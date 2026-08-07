import { useLoginUserStore } from '@/stores/loginUser'
import { message } from 'ant-design-vue'
import router from '@/router'
import { USER_ROLE_ADMIN } from '@/constants/user'

// 是否为首次获取登录用户
let firstFetchLoginUser = true

/**
 * 全局权限校验
 */
router.beforeEach(async (to, from, next) => {
  const loginUserStore = useLoginUserStore()
  let loginUser = loginUserStore.loginUser
  
  // 首次加载时，等后端返回用户信息后再校验权限
  if (firstFetchLoginUser) {
    try {
      await loginUserStore.fetchLoginUser()
      loginUser = loginUserStore.loginUser
    } catch (e) {
      // 后端不可用/网络错误时也要放行，避免整个页面卡在守卫里无法渲染
      console.error('获取登录用户信息失败:', e)
    } finally {
      firstFetchLoginUser = false
    }
  }
  
  const toUrl = to.fullPath
  // 积分中心/个人主页需要登录
  if (toUrl.startsWith('/points') || toUrl.startsWith('/user/profile') || toUrl.startsWith('/user/settings')) {
    if (!loginUser || !loginUser.id) {
      next(`/user/login?redirect=${to.fullPath}`)
      return
    }
  }
  // 管理员页面权限校验
  if (toUrl.startsWith('/admin')) {
    if (!loginUser || loginUser.userRole !== USER_ROLE_ADMIN) {
      message.error('没有权限')
      next(`/user/login?redirect=${to.fullPath}`)
      return
    }
  }
  next()
})
