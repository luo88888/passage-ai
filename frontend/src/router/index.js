import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '@/pages/HomePage.vue'
import UserLoginPage from '@/pages/user/UserLoginPage.vue'
import UserRegisterPage from '@/pages/user/UserRegisterPage.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: '主页',
      component: HomePage,
    },
    {
      path: '/user/login',
      name: '用户登录',
      component: UserLoginPage,
    },
    {
      path: '/user/register',
      name: '用户注册',
      component: UserRegisterPage,
    },

    {
      path: '/user/profile',
      name: '个人主页',
      component: () => import('@/pages/user/UserProfilePage.vue'),
    },
    {
      path: '/user/settings',
      name: '账号设置',
      component: () => import('@/pages/user/UserSettingsPage.vue'),
    },
    {
      path: '/admin/userManage',
      name: '用户管理',
      component: () => import('@/pages/admin/UserManagePage.vue'),
    },
    {
      path: '/admin/statistics',
      name: '数据分析',
      component: () => import('@/pages/admin/StatisticsPage.vue'),
    },

    {
      path: '/admin/points',
      name: '积分管理',
      component: () => import('@/pages/admin/PointsAdminPage.vue'),
    },
    {
      path: '/admin/model-pricing',
      name: '模型计价',
      component: () => import('@/pages/admin/ModelPricingPage.vue'),
    },
    {
      path: '/points',
      name: '积分中心',
      component: () => import('@/pages/points/PointsPage.vue'),
    },
    {
      path: '/create',
      name: '创作',
      component: () => import('@/pages/article/CreateArticlePage.vue'),
    },
    {
      path: '/article/list',
      name: '文章列表',
      component: () => import('@/pages/article/ArticleListPage.vue'),
    },
    {
      path: '/article/:taskId',
      name: '文章详情',
      component: () => import('@/pages/article/ArticleDetailPage.vue'),
    },
    {
      path: '/vip',
      name: '开通会员',
      component: () => import('@/pages/vip/VipPage.vue'),
    },
    {
      path: '/payment/success',
      name: '支付成功',
      component: () => import('@/pages/payment/PaymentResultPage.vue'),
    },
    {
      path: '/payment/cancel',
      name: '支付取消',
      component: () => import('@/pages/payment/PaymentResultPage.vue'),
    },
  ],
})

export default router
