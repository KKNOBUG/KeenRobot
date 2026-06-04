import { createPageLoadingGuard } from './page-loading-guard.js'
import { createPageTitleGuard } from './page-title-guard.js'
import { createAuthGuard } from './auth-guard.js'

export function setupRouterGuard(router) {
  createPageLoadingGuard(router)
  createAuthGuard(router)
  createPageTitleGuard(router)
}
