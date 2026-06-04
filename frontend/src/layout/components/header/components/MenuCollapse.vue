<script setup>
import { useAppStore } from '@/store'
import { Icon } from '@iconify/vue'

const appStore = useAppStore()
</script>

<template>
  <n-icon size="20" style="cursor: pointer" @click="appStore.switchCollapsed()">
    <Icon :icon="appStore.collapsed ? 'mdi:format-indent-increase' : 'mdi:format-indent-decrease'" />
  </n-icon>
</template>
