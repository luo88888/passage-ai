// @ts-ignore
/* eslint-disable */
import request from '@/request'

/** 获取系统统计数据（仅管理员） GET /statistics/overview */
export async function getStatisticsOverview(options?: { [key: string]: any }) {
  return request<API.BaseResponseStatisticsVO>('/statistics/overview', {
    method: 'GET',
    ...(options || {}),
  })
}