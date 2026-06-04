<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppStore } from '@/store'
import { Icon } from '@iconify/vue'
import router from '@/router'

const store = useAppStore()
const { availableLocales, t } = useI18n()

const options = computed(() =>
  availableLocales.map((locale) => ({
    label: t('lang', 1, { locale }),
    key: locale,
  }))
)

function handleChangeLocale(value) {
  store.setLocale(value)
  router.go(0)
}
</script>

<template>
  <n-dropdown :options="options" @select="handleChangeLocale">
    <n-icon mr-20 size="18" style="cursor: pointer">
      <Icon icon="mdi:globe" />
    </n-icon>
  </n-dropdown>
</template>

<style scoped>
.n-icon {
  margin-right: 20px;
}
</style>
