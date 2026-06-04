<script setup>
/**
 * SVG 图标组件 — 统一从 src/assets/svg/ 加载
 * @param {string} name - SVG 文件名（不含 .svg），如 logo_new、front-page
 * @see src/assets/svg/README.md 查看全部 SVG 清单
 */
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 36 },
  color: { type: String, default: '' },
})

const svgModules = import.meta.glob('../../assets/svg/*.svg', {
  query: '?raw',
  import: 'default',
  eager: true,
})

const svgContent = computed(() => {
  const key = Object.keys(svgModules).find((k) => k.endsWith(`/${props.name}.svg`))
  return key ? svgModules[key] : ''
})

const iconStyle = computed(() => ({
  width: typeof props.size === 'number' ? `${props.size}px` : props.size,
  height: typeof props.size === 'number' ? `${props.size}px` : props.size,
  color: props.color || undefined,
}))
</script>

<template>
  <span class="app-icon" :style="iconStyle" v-html="svgContent" />
</template>

<style scoped>
.app-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--primary);
}

.app-icon :deep(svg) {
  width: 100%;
  height: 100%;
  display: block;
}
</style>
