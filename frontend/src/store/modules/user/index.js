import { defineStore } from 'pinia'
import { resetRouter } from '@/router'
import { useTagsStore, usePermissionStore } from '@/store'
import { removeToken, toLogin } from '@/utils'
import api from '@/api'

export const useUserStore = defineStore('user', {
  state() {
    return {
      userInfo: {},
    }
  },
  getters: {
    userId() {
      return this.userInfo?.id
    },
    username() {
      return this.userInfo?.username || ''
    },
    email() {
      return this.userInfo?.email || ''
    },
    alias() {
      return this.userInfo?.username || ''
    },
    avatar() {
      const name = this.userInfo?.username || 'U'
      return `https://api.dicebear.com/7.x/initials/svg?seed=${encodeURIComponent(name)}&backgroundColor=F4511E`
    },
    isAdmin() {
      return this.userInfo?.is_admin || false
    },
    lastLogin() {
      return this.userInfo?.created_at || '-'
    },
  },
  actions: {
    async getUserInfo() {
      try {
        const data = await api.getUserInfo()
        this.userInfo = data || {}
        return data
      } catch (error) {
        return error
      }
    },
    async logout() {
      const { resetTags } = useTagsStore()
      const { resetPermission } = usePermissionStore()
      removeToken()
      resetTags()
      resetPermission()
      resetRouter()
      this.$reset()
      toLogin()
    },
    setUserInfo(userInfo = {}) {
      this.userInfo = { ...this.userInfo, ...userInfo }
    },
  },
})
