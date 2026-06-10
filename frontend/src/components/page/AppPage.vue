<template>
  <transition name="fade-slide" mode="out-in" appear>
    <section
        class="cus-scroll-y wh-full flex-col p-15"
        :class="inheritBackground ? 'app-page-inherit' : 'bg-[#f5f6fb] dark:bg-hex-121212'"
    >
      <slot />
      <AppFooter v-if="showFooter" mt-15 />
      <n-back-top :bottom="20" />
    </section>
  </transition>
</template>

<script setup>
import AppFooter from '@/components/common/AppFooter.vue'

defineProps({
  showFooter: { type: Boolean, default: false },
  inheritBackground: { type: Boolean, default: false },
})
</script>

<style>
.app-page-inherit {
  background: transparent !important;
}
</style>
