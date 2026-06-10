<template>
  <AppPage :show-footer="showFooter" :inherit-background="inheritBackground">
    <header
        v-if="showHeader && ($slots.header || $slots.action)"
        mb-15
        min-h-45
        flex
        items-center
        px-15
        :class="$slots.header ? 'justify-between' : 'justify-end'"
    >
      <slot v-if="$slots.header" name="header" />
      <slot v-else name="action" />
    </header>

    <div flex-1 min-h-0 min-w-0 flex flex-col>
      <slot />
    </div>
  </AppPage>
</template>

<script setup>
defineProps({
  showFooter: { type: Boolean, default: false },
  showHeader: { type: Boolean, default: true },
  inheritBackground: { type: Boolean, default: false },
  title: { type: String, default: undefined },
})
</script>
