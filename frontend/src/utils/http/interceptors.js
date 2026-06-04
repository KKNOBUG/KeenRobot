import { getToken } from '@/utils'
import { useUserStore } from '@/store'
import { parseErrorDetail, resolveResError } from './helpers'

export function reqResolve(config) {
  if (config.noNeedToken) return config
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
}

export function reqReject(error) {
  return Promise.reject(error)
}

export function resResolve(response) {
  return Promise.resolve(response.data)
}

export async function resReject(error) {
  if (!error || !error.response) {
    const message = resolveResError(error?.code, error.message)
    window.$message?.error(message)
    return Promise.reject({ code: error?.code, message, error })
  }

  const { data, status, config } = error.response
  const message = parseErrorDetail(data?.detail) || resolveResError(status, error.message)

  if (status === 401 && !config?.noNeedToken) {
    try {
      const userStore = useUserStore()
      await userStore.logout()
    } catch (err) {
      console.error('resReject logout error', err)
    }
    return Promise.reject({ code: status, message, error: data || error.response })
  }

  window.$message?.error(message, { keepAliveOnHover: true })
  return Promise.reject({ code: status, message, error: data || error.response })
}
