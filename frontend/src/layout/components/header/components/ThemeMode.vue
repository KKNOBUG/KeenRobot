<script setup>
import { useAppStore } from '@/store'
import { useDark, useToggle } from '@vueuse/core'
import { Icon } from '@iconify/vue'

const appStore = useAppStore()
const isDark = useDark()
const toggleDark = () => {
  appStore.toggleDark()
  useToggle(isDark)()
}
</script>

<template>
  <n-icon mr-20 style="cursor: pointer" size="18" @click="toggleDark">
    <Icon v-if="isDark" icon="mdi:moon-waning-crescent" />
    <Icon v-else icon="mdi:white-balance-sunny" />
  </n-icon>
</template>

<style scoped>
.n-icon {
  margin-right: 20px;
}
</style>
