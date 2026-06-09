import { getToken } from '@/utils'
import { useUserStore } from '@/store'
import { resolveResError } from './helpers'

export function reqResolve(config) {
  if (config.noNeedToken) return config
  const token = getToken()
  if (token) {
    config.headers.token = config.headers.token || token
  }
  return config
}

export function reqReject(error) {
  return Promise.reject(error)
}

export function resResolve(response) {
  const { data, status, statusText } = response

  if (!data) {
    const code = status
    const message = resolveResError(code, statusText || '响应数据为空')
    window.$message?.error(message, { keepAliveOnHover: true })
    return Promise.reject({ code, message, error: response })
  }

  const responseCode = String(data.code || '')
  const responseStatus = String(data.status || '')
  const isSuccess = responseCode === '000000' && responseStatus === 'success'

  if (!isSuccess) {
    const code = data.code ?? status
    const message = resolveResError(code, data.message ?? statusText ?? '请求失败')
    window.$message?.error(message, { keepAliveOnHover: true })
    return Promise.reject({ code, message, error: data || response })
  }

  return Promise.resolve(data)
}

export async function resReject(error) {
  if (!error || !error.response) {
    const message = resolveResError(error?.code, error.message)
    window.$message?.error(message)
    return Promise.reject({ code: error?.code, message, error })
  }

  const { data, status } = error.response
  const responseCode = data?.code
  if (responseCode === 401 || responseCode === '400401' || String(responseCode) === '401') {
    try {
      const userStore = useUserStore()
      await userStore.logout()
    } catch (err) {
      console.error('resReject logout error', err)
    }
  }

  const code = data?.code ?? status
  const message = resolveResError(code, data?.message ?? error.message ?? '请求失败')
  window.$message?.error(message, { keepAliveOnHover: true })
  return Promise.reject({ code, message, error: error.response?.data || error.response })
}
