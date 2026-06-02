<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchConversations, getMe } from './api/index.js'

const route = useRoute()
const router = useRouter()

const conversations = ref([])
const currentUser = ref(null)
const sidebarCollapsed = ref(false)
const isAdmin = ref(false)

async function loadConversations() {
  try {
    conversations.value = await fetchConversations()
    console.log('[App] 对话列表加载成功:', conversations.value.length, '个对话')
  } catch (err) {
    console.error('[App] 加载对话失败:', err)
  }
}

async function loadUser() {
  try {
    const user = await getMe()
    currentUser.value = user
    isAdmin.value = user.is_admin || false
    console.log('[App] 用户信息加载成功:', user.username, 'isAdmin:', isAdmin.value)
  } catch (err) {
    console.error('[App] 加载用户信息失败:', err)
    // 如果是401错误，token可能过期，需要重新登录
    if (err.message === '登录已过期' || err.message.includes('401')) {
      logout()
    }
  }
}

function onSelectConversation(id) {
  router.push(`/?conversation=${id}`)
}

function onNewChat() {
  router.push('/')
}

function onConversationCreated() {
  loadConversations()
}

function onConversationDeleted() {
  router.push('/')
  loadConversations()
}

function logout() {
  localStorage.removeItem('token')
  router.push('/login')
}

function goToKnowledgeBase() {
  router.push('/knowledge-base')
}

function goToChat() {
  router.push('/')
}

onMounted(() => {
  // 无论什么路由，只要需要认证就加载
  if (route.meta.requiresAuth) {
    console.log('[App] onMounted: 加载用户和对话列表')
    loadConversations()
    loadUser()
  }
})

// 监听路由变化，确保每次进入需要认证的页面都加载用户信息
watch(() => route.fullPath, (newPath, oldPath) => {
  if (route.meta.requiresAuth) {
    console.log('[App] route changed:', oldPath, '->', newPath)
    loadConversations()
    loadUser()
  }
})
</script>

<template>
  <div class="app-layout">
    <!-- 顶部导航栏 - 仅在需要认证的页面显示 -->
    <header v-if="route.meta.requiresAuth" class="top-navbar">
      <div class="nav-left">
        <div class="logo" @click="goToChat">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
          </svg>
          <span class="logo-text">RAG系统</span>
        </div>
      </div>

      <nav class="nav-center">
        <button class="nav-btn" :class="{ active: route.path === '/' }" @click="goToChat">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
          </svg>
          <span>对话</span>
        </button>
        <button v-if="isAdmin" class="nav-btn" :class="{ active: route.path === '/knowledge-base' }" @click="goToKnowledgeBase">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
          </svg>
          <span>知识库</span>
        </button>
      </nav>

      <div class="nav-right">
        <div v-if="currentUser" class="user-info">
          <span class="username">{{ currentUser.username }}</span>
        </div>
        <button class="logout-btn" @click="logout" title="退出登录">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>
          </svg>
          <span>退出</span>
        </button>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content" :class="{ 'with-navbar': route.meta.requiresAuth }">
      <router-view
        :conversations="conversations"
        @select-conversation="onSelectConversation"
        @new-chat="onNewChat"
        @conversation-created="onConversationCreated"
        @conversation-deleted="onConversationDeleted"
      />
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

/* 顶部导航栏 */
.top-navbar {
  height: 60px;
  background: var(--surface, #ffffff);
  border-bottom: 1px solid var(--border, #e5e7eb);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
}

.nav-left {
  display: flex;
  align-items: center;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--primary, #4f46e5);
  cursor: pointer;
}

.logo-text {
  font-weight: 600;
  font-size: 18px;
  color: var(--text, #1f2937);
}

.nav-center {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border: none;
  background: none;
  color: var(--text-secondary, #6b7280);
  font-size: 14px;
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.2s;
}

.nav-btn:hover {
  background: var(--bg, #f9fafb);
  color: var(--text, #1f2937);
}

.nav-btn.active {
  background: var(--primary-bg, #eef2ff);
  color: var(--primary, #4f46e5);
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-info {
  display: flex;
  align-items: center;
}

.username {
  font-weight: 500;
  font-size: 14px;
  color: var(--text, #1f2937);
}

.logout-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: none;
  background: none;
  color: var(--text-secondary, #6b7280);
  font-size: 14px;
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.2s;
}

.logout-btn:hover {
  background: #fef2f2;
  color: #dc2626;
}

/* 主内容区 */
.main-content {
  flex: 1;
  overflow: hidden;
}

.main-content.with-navbar {
  /* 有顶部导航栏时的样式 */
}
</style>
