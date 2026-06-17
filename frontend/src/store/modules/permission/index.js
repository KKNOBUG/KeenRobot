import { defineStore } from 'pinia'
import { shallowRef } from 'vue'
import { basicRoutes, vueModules } from '@/router/routes/index.js'
import Layout from '@/layout/index.vue'
import api from '@/api'
import { normalizeBackendApiPermissionKey } from '@/utils/permissionKey.js'

function buildRoutes(routes = []) {
  return routes.map((e) => {
    const route = {
      name: e.name,
      path: e.path,
      component: shallowRef(Layout),
      isHidden: e.is_hidden,
      redirect: e.redirect,
      meta: {
        title: e.name,
        icon: e.icon,
        order: e.order,
        keepAlive: e.keepalive,
      },
      children: [],
    }

    if (e.children?.length) {
      route.children = e.children.map((e_child) => ({
        name: e_child.name,
        path: e_child.path,
        component: vueModules[`/src/views${e_child.component}/index.vue`],
        isHidden: e_child.is_hidden,
        meta: {
          title: e_child.name,
          icon: e_child.icon,
          order: e_child.order,
          keepAlive: e_child.keepalive,
          componentName: e_child.name,
        },
      }))
    } else {
      route.children.push({
        name: `${e.name}Default`,
        path: '',
        component: vueModules[`/src/views${e.component}/index.vue`],
        isHidden: true,
        meta: {
          title: e.name,
          icon: e.icon,
          order: e.order,
          keepAlive: e.keepalive,
          componentName: e.name,
        },
      })
    }

    return route
  })
}

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
      const res = await api.getUserMenu()
      this.accessRoutes = buildRoutes(res.data)
      return this.accessRoutes
    },
    async getAccessApis() {
      const res = await api.getUserRouters()
      const raw = Array.isArray(res.data) ? res.data : []
      this.accessApis = raw.map(normalizeBackendApiPermissionKey)
      return this.accessApis
    },
    resetPermission() {
      this.$reset()
    },
  },
})
