import { createI18n } from 'vue-i18n'
import { lStorage } from '@/utils'
import messages from './messages/index.js'

const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: lStorage.get('locale') || 'cn',
  fallbackLocale: 'cn',
  messages,
})

export default i18n
