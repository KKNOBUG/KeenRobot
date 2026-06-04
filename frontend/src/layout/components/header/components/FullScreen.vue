<script setup>
import { useFullscreen } from '@vueuse/core'
import { useAppStore } from '@/store'
import { Icon } from '@iconify/vue'

const appStore = useAppStore()
const { isFullscreen, toggle } = useFullscreen()
</script>

<template>
  <n-icon v-if="appStore.fullScreen" mr-20 size="18" style="cursor: pointer" @click="toggle">
    <Icon :icon="isFullscreen ? 'mdi:fullscreen-exit' : 'mdi:fullscreen'" />
  </n-icon>
</template>

<style scoped>
.n-icon {
  margin-right: 20px;
}
</style>
