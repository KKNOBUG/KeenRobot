export * from './storage/index.js'
export * from './common/index.js'
export * from './http/index.js'
export * from './auth/index.js'
export * from './permissionKey.js'

export { setupMessage, setupDialog } from './common/naiveTools.js'

export function debounce(fn, delay = 200) {
  let timer
  return function (...args) {
    clearTimeout(timer)
    timer = setTimeout(() => fn.apply(this, args), delay)
  }
}
