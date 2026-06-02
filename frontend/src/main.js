console.log('=== main.js 开始执行 ===')

import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'

console.log('=== 模块导入成功 ===')

try {
    const app = createApp(App)
    app.use(router)
    app.mount('#app')
    console.log('=== Vue 挂载成功 ===')
} catch (e) {
    console.error('=== Vue 挂载失败 ===', e)
}
