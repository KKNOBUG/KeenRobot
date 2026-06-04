<template>
  <router-view v-slot="{ Component, route }">
    <KeepAlive :include="keepAliveComponentNames">
      <component
        :is="Component"
        v-if="appStore.reloadFlag"
        :key="appStore.aliveKeys[route.name] || route.fullPath"
      />
    </KeepAlive>
  </router-view>
</template>

<script setup>
import { useAppStore } from '@/store'
import { router } from '@/router'

const appStore = useAppStore()

function collectKeepAliveNames(routes, result = []) {
  for (const r of routes) {
    if (r.meta?.keepAlive) {
      const name = r.meta.componentName || r.name
      if (name && !result.includes(name)) result.push(name)
    }
    if (r.children?.length) collectKeepAliveNames(r.children, result)
  }
  return result
}

const keepAliveComponentNames = computed(() => collectKeepAliveNames(router.getRoutes()))
</script>
