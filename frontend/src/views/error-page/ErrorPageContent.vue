<script setup>
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import AppPage from '@/components/page/AppPage.vue'
import AppIcon from '@/components/icon/AppIcon.vue'

defineProps({
  icon: { type: String, required: true },
  code: { type: String, required: true },
  message: { type: String, default: '' },
})

const { t } = useI18n()
const router = useRouter()

function goHome() {
  router.replace('/workbench')
}
</script>

<template>
  <AppPage>
    <div class="error-page">
      <!-- SVG 引用见 props.icon，清单见 src/assets/svg/README.md -->
      <AppIcon :name="icon" size="280" />
      <h1 class="error-code">{{ code }}</h1>
      <p v-if="message" class="error-message">{{ message }}</p>
      <n-button type="primary" @click="goHome">{{ t('views.errors.text_back_to_home') }}</n-button>
    </div>
  </AppPage>
</template>

<style scoped>
.error-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 40px;
}

.error-code {
  font-size: 48px;
  font-weight: 600;
  margin: 16px 0 8px;
}

.error-message {
  font-size: 13px;
  color: var(--text-color-3, #999);
  margin-bottom: 24px;
}
</style>
