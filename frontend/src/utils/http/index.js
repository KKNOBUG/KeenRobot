import axios from 'axios'
import { resReject, resResolve, reqReject, reqResolve } from './interceptors.js'

export function createAxios(options = {}) {
  const service = axios.create({
    timeout: 60000,
    ...options,
  })
  service.interceptors.request.use(reqResolve, reqReject)
  service.interceptors.response.use(resResolve, resReject)
  return service
}

export const request = createAxios({
  baseURL: import.meta.env.VITE_BASE_API || '/api',
})
