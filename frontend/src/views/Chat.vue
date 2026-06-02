<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { marked } from 'marked'
import MessageBubble from '../components/MessageBubble.vue'
import {
  fetchConversation,
  chatStream,
  fetchKnowledgeBases,
  fetchModelConfigs,
  fetchConversations,
  deleteConversation,
  getMe
} from '../api/index.js'

const route = useRoute()
const router = useRouter()

const props = defineProps({
  conversations: Array,
})
const emit = defineEmits(['select-conversation', 'new-chat', 'conversation-created', 'conversation-deleted'])

const messages = ref([])
const inputText = ref('')
const isLoading = ref(false)
const messagesContainer = ref(null)
const inputRef = ref(null)
let currentConvId = null
let streamController = null

// 知识库和模型配置
const knowledgeBases = ref([])
const modelConfigs = ref([])
const selectedKBs = ref([])
const selectedModelConfig = ref('')

// 用户权限
const isAdmin = ref(false)

// 从URL获取对话ID
const conversationId = ref(route.query.conversation || null)

onMounted(async () => {
  // 加载用户信息
  try {
    const userResponse = await getMe()
    isAdmin.value = userResponse.is_admin || false
    console.log('[Chat] 当前用户权限:', isAdmin.value ? 'admin' : '普通用户')
  } catch (error) {
    console.error('[Chat] 获取用户信息失败:', error)
  }
  
  // 加载知识库和模型配置
  try {
    const kbs = await fetchKnowledgeBases()
    knowledgeBases.value = kbs || []
    console.log('[Chat] 知识库加载完成:', kbs)
    // 自动选择第一个知识库
    if (kbs && kbs.length > 0) {
      selectedKBs.value = [kbs[0].id]
      console.log('[Chat] 自动选择知识库:', kbs[0].id)
    }
  } catch (err) {
    console.error('[Chat] 加载知识库失败:', err)
    knowledgeBases.value = []
  }
  
  try {
    const configs = await fetchModelConfigs()
    modelConfigs.value = configs || []
    console.log('[Chat] 模型配置加载完成:', configs)
    if (modelConfigs.value.length > 0) {
      selectedModelConfig.value = modelConfigs.value.find(c => c.is_default)?.id || modelConfigs.value[0].id
      console.log('[Chat] 默认模型配置ID:', selectedModelConfig.value)
    }
  } catch (err) {
    console.error('[Chat] 加载模型配置失败:', err)
    modelConfigs.value = []
  }
  
  if (inputRef.value) inputRef.value.focus()
  
  // 加载对话
  if (conversationId.value) {
    await loadConversation(conversationId.value)
  }
})

// 监听URL变化
watch(() => route.query.conversation, async (newId) => {
  conversationId.value = newId
  if (streamController) {
    streamController.abort()
    streamController = null
  }
  isLoading.value = false

  if (newId) {
    await loadConversation(newId)
  } else {
    currentConvId = null
    messages.value = []
    // 新建对话时，恢复默认知识库选择
    if (knowledgeBases.value.length > 0) {
      selectedKBs.value = [knowledgeBases.value[0].id]
      console.log('[Chat] 新建对话，自动选择知识库:', knowledgeBases.value[0].id)
    } else {
      selectedKBs.value = []
    }
    // 恢复默认模型配置
    if (modelConfigs.value.length > 0) {
      selectedModelConfig.value = modelConfigs.value.find(c => c.is_default)?.id || modelConfigs.value[0].id
      console.log('[Chat] 新建对话，使用默认模型配置:', selectedModelConfig.value)
    }
  }
  await nextTick()
  scrollToBottom()
})

async function loadConversation(id) {
  currentConvId = id
  const detail = await fetchConversation(id)
  messages.value = detail.messages.map(m => ({
    role: m.role,
    content: m.content,
  }))
  // 恢复知识库和模型配置选择
  if (detail.kb_ids) {
    selectedKBs.value = detail.kb_ids
  }
  if (detail.model_config_id) {
    selectedModelConfig.value = detail.model_config_id
  }
}

function selectConversation(id) {
  emit('select-conversation', id)
}

function startNewChat() {
  emit('new-chat')
}

async function handleDeleteConversation(id) {
  if (!confirm('确定要删除这个对话吗？')) return
  try {
    await deleteConversation(id)
    emit('conversation-deleted')
  } catch (err) {
    alert('删除失败: ' + err.message)
  }
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

async function sendMessage(questionOverride = null) {
  // 确保 questionOverride 是字符串（防止传入事件对象）
  const overrideStr = typeof questionOverride === 'string' ? questionOverride : null
  const question = (overrideStr || inputText.value).trim()
  
  console.log('[Chat.sendMessage] 开始执行')
  console.log('[Chat.sendMessage] questionOverride:', questionOverride)
  console.log('[Chat.sendMessage] overrideStr:', overrideStr)
  console.log('[Chat.sendMessage] inputText.value:', inputText.value)
  console.log('[Chat.sendMessage] 最终 question:', question)
  console.log('[Chat.sendMessage] isLoading:', isLoading.value)
  
  if (!question || isLoading.value) {
    console.log('[Chat.sendMessage] 退出：question为空或isLoading为true')
    return
  }

  console.log('[Chat.sendMessage] 清空输入框')
  inputText.value = ''
  
  console.log('[Chat.sendMessage] 添加用户消息')
  messages.value.push({ role: 'user', content: question })
  messages.value.push({ role: 'assistant', content: '' })
  isLoading.value = true

  await nextTick()
  scrollToBottom()

  const assistantIdx = messages.value.length - 1

  console.log('[Chat.sendMessage] 调用 chatStream')
  console.log('[Chat.sendMessage] 参数 - question:', question)
  console.log('[Chat.sendMessage] 参数 - currentConvId:', currentConvId)
  console.log('[Chat.sendMessage] 参数 - selectedKBs:', selectedKBs.value)
  console.log('[Chat.sendMessage] 参数 - selectedModelConfig:', selectedModelConfig.value)

  streamController = chatStream(
    question,
    currentConvId,
    selectedKBs.value,
    selectedModelConfig.value,
    {
      onMeta(data) {
        console.log('[Chat.sendMessage] onMeta 回调:', data)
        if (data.conversation_id && !currentConvId) {
          currentConvId = data.conversation_id
          // 更新URL，使刷新页面后能保持对话
          router.replace(`/?conversation=${data.conversation_id}`)
          emit('conversation-created')
        }
      },
      onToken(token) {
        messages.value[assistantIdx].content += token
        nextTick(scrollToBottom)
      },
      onDone() {
        console.log('[Chat.sendMessage] onDone 回调')
        isLoading.value = false
        streamController = null
        emit('conversation-created')
      },
      onError(err) {
        console.error('[Chat.sendMessage] onError 回调:', err)
        messages.value[assistantIdx].content += '\n\n[连接中断，请重试]'
        isLoading.value = false
        streamController = null
      },
    }
  )
  
  console.log('[Chat.sendMessage] chatStream 调用完成')
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function renderMarkdown(text) {
  if (!text) return ''
  return marked.parse(text, { breaks: true })
}

function handleQuickQuestion(question) {
  console.log('[Chat] 快速问题被点击:', question)
  console.log('[Chat] 问题类型:', typeof question)
  console.log('[Chat] 当前 isLoading:', isLoading.value)
  console.log('[Chat] 当前 currentConvId:', currentConvId)
  console.log('[Chat] 当前 selectedKBs:', selectedKBs.value)
  console.log('[Chat] 当前 selectedModelConfig:', selectedModelConfig.value)
  
  // 确保 question 是字符串
  if (typeof question !== 'string') {
    console.error('[Chat] 错误：question 不是字符串', question)
    return
  }
  
  // 检查知识库是否已选择
  if (!selectedKBs.value || selectedKBs.value.length === 0) {
    console.warn('[Chat] 警告：未选择知识库，将使用默认检索')
    // 如果有可用知识库，自动选择第一个
    if (knowledgeBases.value.length > 0) {
      selectedKBs.value = [knowledgeBases.value[0].id]
      console.log('[Chat] 自动选择知识库:', selectedKBs.value[0])
    } else {
      console.error('[Chat] 错误：没有可用的知识库')
      alert('请先创建或选择知识库')
      return
    }
  }
  
  // 检查模型配置
  if (!selectedModelConfig.value) {
    console.warn('[Chat] 警告：未选择模型配置，使用默认')
    if (modelConfigs.value.length > 0) {
      selectedModelConfig.value = modelConfigs.value.find(c => c.is_default)?.id || modelConfigs.value[0].id
      console.log('[Chat] 使用默认模型配置:', selectedModelConfig.value)
    }
  }
  
  // 直接调用 sendMessage，传入问题字符串
  sendMessage(question)
}
</script>

<template>
  <div class="chat-layout">
    <!-- 对话列表面板 -->
    <aside class="conversation-panel">
      <button class="new-chat-btn" @click="startNewChat">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 4v16m8-8H4"/>
        </svg>
        新建对话
      </button>
      
      <div class="conversation-list">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="conversation-item"
          :class="{ active: conversationId === conv.id }"
          @click="selectConversation(conv.id)"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
          </svg>
          <span class="conv-title">{{ conv.title || '新对话' }}</span>
          <button 
            class="delete-btn" 
            @click.stop="handleDeleteConversation(conv.id)"
            title="删除对话"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
            </svg>
          </button>
        </div>
        <div v-if="conversations.length === 0" class="empty-conversations">
          暂无历史对话
        </div>
      </div>
    </aside>

    <main class="chat-main">
      <!-- 配置栏 - 仅 admin 可见 -->
      <div v-if="isAdmin" class="config-bar">
      <div class="config-item">
        <label>知识库:</label>
        <select v-model="selectedKBs" multiple class="kb-select">
          <option v-for="kb in knowledgeBases" :key="kb.id" :value="kb.id">
            {{ kb.name }}
          </option>
        </select>
      </div>
      <div class="config-item">
        <label>模型配置:</label>
        <select v-model="selectedModelConfig">
          <option v-for="config in modelConfigs" :key="config.id" :value="config.id">
            {{ config.name }} ({{ config.model_name }})
          </option>
        </select>
      </div>
    </div>
    
    <!-- 普通用户提示 -->
    <div v-else class="config-bar config-bar-readonly">
      <div class="config-info">
        <span class="config-label">当前知识库:</span>
        <span class="config-value">{{ knowledgeBases.length > 0 ? knowledgeBases.map(kb => kb.name).join(', ') : '无' }}</span>
      </div>
      <div class="config-info">
        <span class="config-label">当前模型:</span>
        <span class="config-value">{{ modelConfigs.find(c => c.id === selectedModelConfig)?.name || '默认模型' }}</span>
      </div>
    </div>

    <!-- 头部 -->
    <header class="chat-header">
      <div class="header-content">
        <svg class="header-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
        </svg>
        <h1>企业知识库智能问答</h1>
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
        <p>我是企业知识库智能助手，可以回答关于公司制度、技术文档、产品信息等问题。</p>
        <div class="quick-questions">
          <button
            v-for="q in [
              '公司的考勤制度是什么？',
              '产品的核心功能有哪些？',
              '技术栈使用什么框架？',
            ]"
            :key="q"
            class="quick-btn"
            @click="handleQuickQuestion(q)"
          >
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
  </div>
</template>

<style scoped>
.chat-layout {
  display: flex;
  height: 100%;
  overflow: hidden;
}

/* 对话列表面板 */
.conversation-panel {
  width: 260px;
  background: var(--surface, #ffffff);
  border-right: 1px solid var(--border, #e5e7eb);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin: 16px;
  padding: 10px 16px;
  background: var(--primary, #4f46e5);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.new-chat-btn:hover {
  background: var(--primary-light, #6366f1);
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 8px;
}

.conversation-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  margin-bottom: 4px;
}

.conversation-item:hover {
  background: var(--bg, #f9fafb);
}

.conversation-item.active {
  background: var(--primary-bg, #eef2ff);
  color: var(--primary, #4f46e5);
}

.conv-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}

.delete-btn {
  opacity: 0;
  background: none;
  border: none;
  color: var(--text-secondary, #6b7280);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;
}

.conversation-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  background: #fef2f2;
  color: #dc2626;
}

.empty-conversations {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-secondary, #6b7280);
  font-size: 14px;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  background: var(--bg);
}

.config-bar {
  display: flex;
  gap: 16px;
  padding: 12px 24px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}

.config-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.config-item label {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}

/* 只读配置栏样式 */
.config-bar-readonly {
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border-bottom: 2px solid #bae6fd;
}

.config-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  background: white;
  border-radius: 6px;
  border: 1px solid #bae6fd;
}

.config-label {
  font-size: 13px;
  color: #0369a1;
  font-weight: 500;
}

.config-value {
  font-size: 13px;
  color: #0c4a6e;
  font-weight: 600;
}

.config-item select {
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  background: var(--bg);
  color: var(--text);
}

.kb-select {
  min-width: 150px;
  height: 32px;
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
  cursor: pointer;
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
  border: none;
  cursor: pointer;
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
