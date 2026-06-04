<script setup>
import { Icon } from '@iconify/vue'

function handleLinkClick() {
  window.open('https://github.com/KKNOBUG/Krun', '_blank')
}
</script>

<template>
  <n-icon mr-20 size="18" style="cursor: pointer" @click="handleLinkClick">
    <Icon icon="mdi:github" />
  </n-icon>
</template>

<style scoped>
.n-icon {
  margin-right: 20px;
}
</style>
