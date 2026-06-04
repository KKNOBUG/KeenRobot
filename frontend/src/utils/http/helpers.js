import { useUserStore } from '@/store'

export function parseErrorDetail(detail) {
  if (!detail) return null
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message || String(item)).join('; ')
  }
  return String(detail)
}

export function resolveResError(code, message) {
  if (message) return message

  switch (Number(code)) {
    case 400:
      return '请求参数错误'
    case 401:
      return '登录已过期'
    case 403:
      return '没有权限'
    case 404:
      return '资源或接口不存在'
    case 500:
      return '服务器异常'
    default:
      return '请求失败'
  }
}

export function addBaseParams(params) {
  if (!params.userId) {
    params.userId = useUserStore().userId
  }
}
