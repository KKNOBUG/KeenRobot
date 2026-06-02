<script setup>
const props = defineProps({
  role: String,
  content: String,
  html: String,
  isStreaming: Boolean,
})
</script>

<template>
  <div class="message" :class="role">
    <div class="avatar">
      <!-- 用户头像 -->
      <svg v-if="role === 'user'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/>
        <circle cx="12" cy="7" r="4"/>
      </svg>
      <!-- AI头像 -->
      <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2a4 4 0 014 4v1h2a2 2 0 012 2v2a2 2 0 01-1 1.73V18a2 2 0 01-2 2H7a2 2 0 01-2-2v-5.27A2 2 0 014 11V9a2 2 0 012-2h2V6a4 4 0 014-4z"/>
        <circle cx="9" cy="13" r="1"/>
        <circle cx="15" cy="13" r="1"/>
      </svg>
    </div>
    <div class="bubble">
      <div class="role-label">{{ role === 'user' ? '你' : '助手' }}</div>
      <div v-if="role === 'assistant'" class="markdown-body" v-html="html"></div>
      <div v-else class="text-content">{{ content }}</div>
      <span v-if="isStreaming" class="cursor-blink"></span>
    </div>
  </div>
</template>

<style scoped>
.message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  max-width: 800px;
  margin-left: auto;
  margin-right: auto;
}
.message.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.message.user .avatar {
  background: var(--user-bubble);
  color: white;
}
.message.assistant .avatar {
  background: var(--primary-bg);
  color: var(--primary);
}

.bubble {
  max-width: 75%;
  min-width: 0;
}
.role-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
  font-weight: 500;
}
.message.user .role-label {
  text-align: right;
}

.message.user .text-content {
  background: var(--user-bubble);
  color: var(--user-text);
  padding: 10px 16px;
  border-radius: 16px 16px 4px 16px;
  line-height: 1.6;
  word-break: break-word;
  font-size: 14.5px;
}

.message.assistant .bubble :deep(.markdown-body) {
  background: var(--assistant-bubble);
  color: var(--assistant-text);
  padding: 12px 16px;
  border-radius: 16px 16px 16px 4px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-light);
  font-size: 14.5px;
}

/* 流式光标闪烁 */
.cursor-blink {
  display: inline-block;
  width: 7px;
  height: 16px;
  background: var(--primary);
  border-radius: 2px;
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 1s step-end infinite;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
