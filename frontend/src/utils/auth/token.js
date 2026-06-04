import { lStorage } from '@/utils'

const TOKEN_CODE = 'access_token'

export function getToken() {
  return lStorage.get(TOKEN_CODE) || localStorage.getItem('token')
}

export function setToken(token) {
  lStorage.set(TOKEN_CODE, token)
  localStorage.removeItem('token')
}

export function removeToken() {
  lStorage.remove(TOKEN_CODE)
  localStorage.removeItem('token')
}
