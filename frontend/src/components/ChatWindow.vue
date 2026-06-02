<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'
import { marked } from 'marked'
import MessageBubble from './MessageBubble.vue'
import { fetchConversation, chatStream } from '../api/index.js'

const props = defineProps({
  conversationId: String,
})
const emit = defineEmits(['created', 'update-title'])

const messages = ref([])
const inputText = ref('')
const isLoading = ref(false)
const messagesContainer = ref(null)
const inputRef = ref(null)
let currentConvId = null
let streamController = null

// 监听对话切换
watch(() => props.conversationId, async (newId) => {
  // 中止正在进行的流
  if (streamController) {
    streamController.abort()
    streamController = null
  }
  isLoading.value = false

  if (newId) {
    currentConvId = newId
    const detail = await fetchConversation(newId)
    messages.value = detail.messages.map(m => ({
      role: m.role,
      content: m.content,
    }))
  } else {
    currentConvId = null
    messages.value = []
  }
  await nextTick()
  scrollToBottom()
}, { immediate: true })

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

async function sendMessage(questionOverride = null) {
  console.log('[sendMessage] 被调用，参数:', questionOverride)
  const question = (questionOverride || inputText.value).trim()
  console.log('[sendMessage] 处理问题:', question)
  console.log('[sendMessage] isLoading:', isLoading.value)
  
  if (!question) {
    console.log('[sendMessage] 问题为空，返回')
    return
  }
  if (isLoading.value) {
    console.log('[sendMessage] 正在加载中，返回')
    return
  }

  inputText.value = ''
  console.log('[sendMessage] 添加用户消息...')
  messages.value.push({ role: 'user', content: question })

  // 添加一条空的助手消息用于流式填充
  messages.value.push({ role: 'assistant', content: '' })
  isLoading.value = true

  await nextTick()
  scrollToBottom()

  const assistantIdx = messages.value.length - 1

  streamController = chatStream(question, currentConvId, {
    onMeta(data) {
      if (data.conversation_id && !currentConvId) {
        currentConvId = data.conversation_id
        emit('created', data.conversation_id)
      }
    },
    onToken(token) {
      messages.value[assistantIdx].content += token
      nextTick(scrollToBottom)
    },
    onDone() {
      isLoading.value = false
      streamController = null
      emit('update-title')
    },
    onError(err) {
      console.error('Stream error:', err)
      messages.value[assistantIdx].content += '\n\n[连接中断，请重试]'
      isLoading.value = false
      streamController = null
    },
  })
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function handleQuickQuestion(question) {
  console.log('[ChatWindow] 快速问题被点击:', question)
  console.log('[ChatWindow] isLoading状态:', isLoading.value)
  console.log('[ChatWindow] currentConvId:', currentConvId)
  inputText.value = question
  console.log('[ChatWindow] 调用sendMessage...')
  sendMessage(question)
  console.log('[ChatWindow] sendMessage调用完成')
}

function renderMarkdown(text) {
  if (!text) return ''
  return marked.parse(text, { breaks: true })
}

onMounted(() => {
  if (inputRef.value) inputRef.value.focus()
})
</script>

<template>
  <main class="chat-main">
    <!-- 头部 -->
    <header class="chat-header">
      <div class="header-content">
        <svg class="header-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
        </svg>
        <h1>奥德员工手册智能问答</h1>
      </div>
    </header>

    <!-- 消息区域 -->
    <div class="messages-area" ref="messagesContainer">
      <!-- 空状态 -->
      <div v-if="messages.length === 0" class="welcome">
        <div class="welcome-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="1.5">
            <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
          </svg>
        </div>
        <h2>你好，有什么可以帮你的？</h2>
        <p>我是奥德集团员工手册智能助手，可以回答关于公司制度、福利政策、员工规范等问题。</p>
        <div class="quick-questions">
          <button v-for="q in [
            '公司的考勤制度是什么？',
            '员工的休假政策有哪些？',
            '试用期相关规定是什么？',
          ]" :key="q" class="quick-btn" @click="handleQuickQuestion(q)">
            {{ q }}
          </button>
        </div>
      </div>

      <!-- 消息列表 -->
      <template v-else>
        <MessageBubble
          v-for="(msg, idx) in messages"
          :key="idx"
          :role="msg.role"
          :content="msg.content"
          :html="msg.role === 'assistant' ? renderMarkdown(msg.content) : ''"
          :isStreaming="isLoading && idx === messages.length - 1 && msg.role === 'assistant'"
        />
      </template>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <div class="input-wrapper">
        <textarea
          ref="inputRef"
          v-model="inputText"
          @keydown="handleKeydown"
          placeholder="输入你的问题..."
          rows="1"
          :disabled="isLoading"
        />
        <button
          class="send-btn"
          @click="sendMessage"
          :disabled="!inputText.trim() || isLoading"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
          </svg>
        </button>
      </div>
      <div class="input-hint">按 Enter 发送，Shift + Enter 换行</div>
    </div>
  </main>
</template>

<style scoped>
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  background: var(--bg);
}

/* 头部 */
.chat-header {
  padding: 14px 24px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.header-content {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-icon {
  color: var(--primary);
  flex-shrink: 0;
}
.chat-header h1 {
  font-size: 17px;
  font-weight: 600;
  color: var(--text);
}

/* 消息区域 */
.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px 24px 16px;
}

/* 欢迎页 */
.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  height: 100%;
  padding: 40px 20px;
  gap: 12px;
}
.welcome-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--primary-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 8px;
}
.welcome h2 {
  font-size: 22px;
  font-weight: 600;
  color: var(--text);
}
.welcome p {
  color: var(--text-secondary);
  max-width: 420px;
  font-size: 14.5px;
  line-height: 1.6;
}
.quick-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-top: 20px;
}
.quick-btn {
  padding: 8px 16px;
  border: 1px solid var(--border);
  border-radius: 20px;
  font-size: 13.5px;
  color: var(--text-secondary);
  background: var(--surface);
  transition: all var(--transition);
}
.quick-btn:hover {
  border-color: var(--primary-light);
  color: var(--primary);
  background: var(--primary-bg);
  box-shadow: var(--shadow-sm);
}

/* 输入区域 */
.input-area {
  padding: 12px 24px 16px;
  background: var(--surface);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}
.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 12px;
  transition: border-color var(--transition), box-shadow var(--transition);
}
.input-wrapper:focus-within {
  border-color: var(--primary-light);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}
.input-wrapper textarea {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  resize: none;
  min-height: 24px;
  max-height: 120px;
  line-height: 1.5;
  color: var(--text);
}
.input-wrapper textarea::placeholder {
  color: var(--text-muted);
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--primary);
  color: white;
  flex-shrink: 0;
  transition: all var(--transition);
}
.send-btn:hover:not(:disabled) {
  background: var(--primary-light);
  box-shadow: var(--shadow);
}
.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.input-hint {
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 8px;
}
</style>
