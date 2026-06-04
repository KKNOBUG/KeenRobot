<template>
  <div ref="wrapper" class="scroll-x-wrapper">
    <div ref="content" class="scroll-x-content">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { debounce } from '@/utils'

const wrapper = ref(null)
const content = ref(null)
const translateX = ref(0)

function handleScroll(x, width) {
  const wrapperWidth = wrapper.value?.offsetWidth
  const contentWidth = content.value?.offsetWidth
  if (!wrapperWidth || contentWidth <= wrapperWidth) return

  if (x < -translateX.value + 150) {
    translateX.value = -(x - 150)
  }
  if (x + width > -translateX.value + wrapperWidth) {
    translateX.value = wrapperWidth - (x + width)
  }
  content.value.style.transform = `translateX(${translateX.value}px)`
}

defineExpose({ handleScroll })

const onResize = debounce(() => {}, 200)
let observer

onMounted(() => {
  observer = new ResizeObserver(onResize)
  if (wrapper.value) observer.observe(wrapper.value)
})

onBeforeUnmount(() => {
  observer?.disconnect()
})
</script>

<style scoped>
.scroll-x-wrapper {
  overflow: hidden;
  width: 100%;
}

.scroll-x-content {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  padding: 0 10px;
  transition: transform 0.3s;
  min-height: 50px;
}
</style>
