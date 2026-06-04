import { defineStore } from 'pinia'
import { basicRoutes } from '@/router/routes/index.js'

export const usePermissionStore = defineStore('permission', {
  state() {
    return {
      accessRoutes: [],
      accessApis: [],
    }
  },
  getters: {
    routes() {
      return basicRoutes.concat(this.accessRoutes)
    },
    menus() {
      return this.routes.filter((route) => route.name && !route.isHidden)
    },
    apis() {
      return this.accessApis
    },
  },
  actions: {
    async generateRoutes() {
      return this.accessRoutes
    },
    async getAccessApis() {
      return this.accessApis
    },
    resetPermission() {
      this.$reset()
    },
  },
})
