<script setup>
import { computed, ref, watch } from 'vue'
import ChatProcessTrace from './chat/ChatProcessTrace.vue'
import SkillIntakePanel from './skill/SkillIntakePanel.vue'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps({
  role: String,
  content: String,
  messageId: { type: Number, default: null },
  conversationId: { type: String, default: null },
  skillIntake: { type: Object, default: null },
  skillCatalog: { type: Object, default: null },
  modelConfigId: { type: String, default: null },
  knowledgeBaseIds: { type: Array, default: () => [] },
  processTrace: {
    type: Array,
    default: () => [],
  },
  skillRunRef: {
    type: Object,
    default: null,
  },
  isStreaming: Boolean,
  promptTokens: Number,
  completionTokens: Number,
  reasoningTokens: Number,
  retrievalEmpty: Boolean,
  retrievalEmptyMessage: String,
  sources: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['intake-update', 'intake-lock-change', 'intake-started', 'intake-cancelled'])

const sourcesExpanded = ref(false)

const showSources = computed(() =>
  props.role === 'assistant' && Array.isArray(props.sources) && props.sources.length > 0,
)
const renderedHtml = ref('')

const intakePhase = computed(() => props.skillIntake?.phase || '')
const showIntakePanel = computed(() => Boolean(props.skillIntake) && props.role === 'assistant')
const showBubbleProcessTrace = computed(() => {
  if (!props.processTrace.length) return false
  if (showIntakePanel.value) {
    if (['running', 'async', 'done', 'failed'].includes(intakePhase.value)) return true
    if (['collecting', 'confirming'].includes(intakePhase.value)) return false
    return false
  }
  return true
})

const intakeReadonly = computed(() =>
  ['submitted', 'cancelled', 'stale'].includes(intakePhase.value),
)

const displayIntake = computed(() => {
  if (!props.skillIntake) return null
  const legacyPhases = ['running', 'async', 'done', 'failed']
  if (!legacyPhases.includes(props.skillIntake.phase)) return props.skillIntake
  const steps = props.skillCatalog?.[props.skillIntake.skill_id]?.input_schema?.wizard_steps
  return {
    ...props.skillIntake,
    phase: 'submitted',
    step_index: steps?.length ? steps.length - 1 : props.skillIntake.step_index,
  }
})

const linkedSkill = computed(() => {
  if (!props.skillIntake?.skill_id || !props.skillCatalog) return null
  return props.skillCatalog[props.skillIntake.skill_id] || null
})

watch(
    () => [props.content, props.isStreaming, props.role],
    ([content, streaming, role]) => {
      if (role !== 'assistant') {
        renderedHtml.value = ''
        return
      }
      if (!streaming && content) {
        renderedHtml.value = renderMarkdown(content)
      } else if (!streaming) {
        renderedHtml.value = ''
      }
    },
    { immediate: true },
)

function hasTokenUsage(promptTokens, completionTokens, reasoningTokens) {
  return (
      promptTokens != null
      || completionTokens != null
      || (reasoningTokens != null && reasoningTokens > 0)
  )
}

function canCopy() {
  return Boolean(props.content?.trim()) && !props.isStreaming && !showIntakePanel.value
}

function showAssistantContent() {
  if (showIntakePanel.value) {
    if (['running', 'async', 'done', 'failed'].includes(intakePhase.value)) {
      return Boolean(props.content?.trim())
    }
    return false
  }
  return props.content || !props.processTrace.length
}

function onIntakeUpdate(next) {
  emit('intake-update', next)
}

function onIntakeLockChange(locked) {
  emit('intake-lock-change', locked)
}

function onIntakeStarted(payload) {
  emit('intake-started', payload)
}

function onIntakeCancelled() {
  emit('intake-cancelled')
}

async function copyContent() {
  const text = props.content?.trim()
  if (!text) return

  try {
    await navigator.clipboard.writeText(text)
    window.$message?.success('已复制')
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    try {
      document.execCommand('copy')
      window.$message?.success('已复制')
    } catch {
      window.$message?.error('复制失败')
    } finally {
      document.body.removeChild(textarea)
    }
  }
}
</script>

<template>
  <div class="message" :class="role">
    <div class="avatar-col">
      <div v-if="role === 'assistant'" class="avatar avatar--assistant">
        <icon-custom-logo-new text-36 color-primary />
      </div>
    </div>
    <div class="bubble">
      <ChatProcessTrace
          v-if="role === 'assistant' && showBubbleProcessTrace"
          :steps="processTrace"
          :streaming="isStreaming"
      />
      <div
          v-if="role === 'assistant' && retrievalEmpty"
          class="retrieval-empty-banner"
      >
        {{ retrievalEmptyMessage || '未在知识库中找到相关内容' }}
      </div>
      <div v-if="showSources" class="rag-sources">
        <button type="button" class="rag-sources__toggle" @click="sourcesExpanded = !sourcesExpanded">
          参考来源（{{ sources.length }}）
          <span class="rag-sources__chevron">{{ sourcesExpanded ? '▾' : '▸' }}</span>
        </button>
        <ul v-show="sourcesExpanded" class="rag-sources__list">
          <li v-for="item in sources" :key="item.chunk_id || item.index" class="rag-sources__item">
            <span class="rag-sources__title">
              [{{ item.index }}] {{ item.filename || '未知文档' }}
              <template v-if="item.page_number"> · 第{{ item.page_number }}页</template>
              <template v-if="item.score != null"> · {{ item.score }}</template>
            </span>
            <p v-if="item.snippet" class="rag-sources__snippet">{{ item.snippet }}</p>
          </li>
        </ul>
      </div>
      <div
          v-if="role === 'assistant' && showAssistantContent()"
          class="markdown-body bubble-content"
          :class="{ 'bubble-content--intake-intro': showIntakePanel }"
      >
        <div
            v-if="isStreaming"
            class="assistant-plain-text"
        >{{ content }}<span v-if="content" class="cursor-blink" /></div>
        <div v-else v-html="renderedHtml" />
      </div>
      <SkillIntakePanel
          v-if="showIntakePanel"
          :intake="displayIntake"
          :message-id="messageId"
          :conversation-id="conversationId"
          :skill="linkedSkill"
          :model-config-id="modelConfigId"
          :knowledge-base-ids="knowledgeBaseIds"
          :readonly="intakeReadonly"
          class="skill-intake-embed"
          @update:intake="onIntakeUpdate"
          @lock-change="onIntakeLockChange"
          @started="onIntakeStarted"
          @cancelled="onIntakeCancelled"
      />
      <div v-else-if="role !== 'assistant'" class="text-content bubble-content">{{ content }}</div>
      <div
          v-if="role === 'assistant' && (canCopy() || hasTokenUsage(promptTokens, completionTokens, reasoningTokens) || skillRunRef?.links?.length)"
          class="message-actions"
      >
        <router-link
            v-for="(link, linkIdx) in skillRunRef?.links || []"
            :key="linkIdx"
            :to="link.path"
            class="action-badge action-badge--skill-run"
        >
          {{ link.label || '查看执行记录' }}
        </router-link>
        <button
            v-if="canCopy()"
            type="button"
            class="action-badge action-badge--copy"
            title="复制内容"
            @click="copyContent"
        >
          <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2" />
            <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
          </svg>
          复制
        </button>
        <span v-if="promptTokens != null" class="token-badge token-badge--prompt">
          <svg class="token-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M12 19V5M12 5l-6 6M12 5l6 6" />
          </svg>
          {{ promptTokens }}
        </span>
        <span v-if="completionTokens != null" class="token-badge token-badge--completion">
          <svg class="token-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M12 5v14M12 19l-6-6M12 19l6-6" />
          </svg>
          {{ completionTokens }}
        </span>
        <span v-if="reasoningTokens != null && reasoningTokens > 0" class="token-badge token-badge--reasoning">
          <svg class="token-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
          </svg>
          {{ reasoningTokens }}
        </span>
      </div>
    </div>
    <div class="avatar-col">
      <div v-if="role === 'user'" class="avatar avatar--user">
        <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
        >
          <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
          <circle cx="12" cy="7" r="4" />
        </svg>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message {
  display: grid;
  grid-template-columns: 36px 1fr 36px;
  gap: 12px;
  align-items: start;
  margin: 0 auto 16px;
  width: 90%;
}

.avatar-col {
  width: 36px;
  flex-shrink: 0;
}

.avatar {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar--assistant {
  background: none;
  border-radius: 0;
}

.avatar--user {
  border-radius: 30%;
  background: var(--chat-input-border);
}

.bubble {
  min-width: 0;
}

.bubble-content {
  box-sizing: border-box;
  min-height: 36px;
  padding: 8px 14px;
  word-break: break-word;
  font-size: 14px;
  border-radius: 12px;
}

.message.user .bubble-content {
  background-color: var(--chat-input-border);
  white-space: pre-wrap;
  line-height: 1.7;
  tab-size: 4;
}

.message.assistant .bubble-content {
  background: rgba(244, 81, 30, 0.1);
}

.bubble-content--intake-intro {
  margin-bottom: 10px;
}

.skill-intake-embed {
  width: 100%;
}

.assistant-plain-text {
  white-space: pre-wrap;
  line-height: 1.7;
  tab-size: 4;
}

.action-badge--skill-run {
  background: rgba(244, 81, 30, 0.12);
  color: var(--primary-color, #f4511e);
  text-decoration: none;
}

.action-badge--skill-run:hover {
  background: rgba(244, 81, 30, 0.2);
}

.message-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
  padding-left: 2px;
}

.action-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border: none;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  line-height: 16px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.action-badge--copy {
  background: rgba(0, 0, 0, 0.06);
  color: var(--chat-muted-text, #737373);
}

.action-badge--copy:hover {
  background: rgba(0, 0, 0, 0.1);
  color: var(--n-text-color, #333);
}

.action-icon {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
}

.token-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  line-height: 16px;
}

.token-icon {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
}

.token-badge--prompt {
  background: rgba(24, 144, 255, 0.12);
  color: #1890ff;
}

.token-badge--completion {
  background: rgba(82, 196, 26, 0.12);
  color: #52c41a;
}

.token-badge--reasoning {
  background: rgba(250, 140, 22, 0.12);
  color: #fa8c16;
}

.retrieval-empty-banner {
  margin-bottom: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(250, 140, 22, 0.12);
  color: #d46b08;
  font-size: 13px;
  line-height: 1.5;
}

.rag-sources {
  margin-bottom: 8px;
}

.rag-sources__toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: none;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.05);
  color: var(--chat-muted-text, #737373);
  font-size: 12px;
  cursor: pointer;
}

.rag-sources__toggle:hover {
  background: rgba(0, 0, 0, 0.08);
}

.rag-sources__list {
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}

.rag-sources__item {
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.03);
  font-size: 12px;
}

.rag-sources__item + .rag-sources__item {
  margin-top: 6px;
}

.rag-sources__title {
  font-weight: 600;
  color: var(--n-text-color, #333);
}

.rag-sources__snippet {
  margin: 4px 0 0;
  color: var(--chat-muted-text, #737373);
  line-height: 1.5;
}

.cursor-blink {
  display: inline-block;
  width: 7px;
  height: 14px;
  background: var(--primary-color, #f4511e);
  border-radius: 2px;
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}

:global(html.dark) .message.assistant .bubble-content {
  background: rgba(244, 81, 30, 0.12);
  color: #e2e8f0;
  border-color: rgba(244, 81, 30, 0.2);
}

:global(html.dark) .action-badge--copy {
  background: rgba(255, 255, 255, 0.08);
  color: #a3a3a3;
}

:global(html.dark) .action-badge--copy:hover {
  background: rgba(255, 255, 255, 0.14);
  color: #e2e8f0;
}

:global(html.dark) .action-badge--skill-run {
  background: rgba(244, 81, 30, 0.18);
}

:global(html.dark) .token-badge--prompt {
  background: rgba(24, 144, 255, 0.18);
}

:global(html.dark) .token-badge--completion {
  background: rgba(82, 196, 26, 0.18);
}

:global(html.dark) .token-badge--reasoning {
  background: rgba(250, 140, 22, 0.18);
}
</style>
