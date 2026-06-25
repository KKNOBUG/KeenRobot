<script setup>
defineOptions({ name: 'Chat' })

import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NLayout, NLayoutContent, NLayoutSider, NSkeleton } from 'naive-ui'
import MessageBubble from '../../components/MessageBubble.vue'
import ChatFeaturePicker from '../../components/chat/ChatFeaturePicker.vue'
import ChatDeepThinkingToggle from '../../components/chat/ChatDeepThinkingToggle.vue'
import ChatModelSelector from '../../components/chat/ChatModelSelector.vue'
import ChatTurnNodes from '../../components/chat/ChatTurnNodes.vue'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api, { chatStream, skillRunStream } from '@/api'

const route = useRoute()
const router = useRouter()

const conversations = ref([])

const messages = ref([])
const inputText = ref('')
const isLoading = ref(false)
const isConversationLoading = ref(false)
const messagesContainer = ref(null)
const inputRef = ref(null)
const showScrollFab = ref(false)
const scrollFabToBottom = ref(true)
const activeTurnIndex = ref(0)
let currentConvId = null
let streamController = null
let skillRunStreamController = null
const skillRunPollTimers = new Map()
let loadConversationSeq = 0

function normalizeConversationId(id) {
  if (id == null || id === '') return null
  return String(Array.isArray(id) ? id[0] : id)
}

// 知识库和模型配置
const knowledgeBases = ref([])
const modelConfigs = ref([])
const selectedKBs = ref([])
const selectedSkills = ref([])
const selectedMcps = ref([])
const enableDeepThinking = ref(false)
const skillItems = ref([])
const mcpItems = ref([])
const selectedModelConfig = ref('')

const kbPickerItems = computed(() =>
    knowledgeBases.value.map((kb) => ({
      id: kb.id,
      label: kb.knowledge_name,
      tag: kb.document_count != null ? `${kb.document_count} 篇文档` : undefined,
    })),
)

const skillPickerItems = computed(() =>
    skillItems.value
        .filter((skill) => (skill.interaction_mode || 'chat') === 'chat')
        .map((skill) => ({
          id: skill.id,
          label: skill.name,
          tag: skill.skill_key || undefined,
        })),
)

const wizardSkillPickerItems = computed(() =>
    skillItems.value
        .filter((skill) => ['wizard', 'async_job'].includes(skill.interaction_mode || ''))
        .map((skill) => ({
          id: skill.id,
          label: skill.name,
          tag: skill.interaction_mode === 'async_job' ? '异步' : '向导',
        })),
)

const selectedWizardSkillTrigger = ref([])
const lastConversationSkillIds = ref([])
const skillIntakeLocked = ref(false)
const syncingWizardSkillSelection = ref(false)
const syncingConversationBindings = ref(false)
let persistBindingsTimer = null

const mcpPickerDisabled = computed(
    () => skillIntakeLocked.value || selectedWizardSkillTrigger.value.length > 0,
)

const mcpPickerItems = computed(() =>
    mcpItems.value.map((mcp) => ({
      id: mcp.id,
      label: mcp.name,
      tag: mcp.transport || undefined,
    })),
)

const modelPickerItems = computed(() =>
    modelConfigs.value.map((config) => ({
      id: config.id,
      label: config.llm_model_name,
      sublabel: config.config_name,
    })),
)

const selectedConfig = computed(() =>
    modelConfigs.value.find((c) => c.id === selectedModelConfig.value) || null,
)

const showDeepThinking = computed(() => selectedConfig.value?.model_thinking === true)

const showModelSelector = computed(() => modelConfigs.value.length > 0)

const skillCatalog = computed(() =>
    Object.fromEntries((skillItems.value || []).map((item) => [item.id, item])),
)

const composerDisabled = computed(
    () => isLoading.value || isConversationLoading.value || skillIntakeLocked.value,
)

const composerPlaceholder = computed(() =>
    skillIntakeLocked.value
        ? '请先完成上方 Skill 信息收集，完成后可继续对话'
        : '请输入您的问题... Enter发送消息 / Shift+Enter换行',
)

function findWizardIntakeForPicker(skillId = null) {
  for (let i = messages.value.length - 1; i >= 0; i -= 1) {
    const intake = messages.value[i].skill_intake
    if (!intake?.skill_id) continue
    if (skillId != null && String(intake.skill_id) !== String(skillId)) continue
    const phase = intake.phase || 'collecting'
    if (['collecting', 'confirming', 'submitted'].includes(phase)) {
      return messages.value[i]
    }
  }
  return null
}

function resolveWizardSkillIdFromSkillIds(skillIds = []) {
  let fallbackId = null
  for (const id of skillIds) {
    const meta = skillItems.value.find((s) => String(s.id) === String(id))
    if (!meta) {
      if (!fallbackId) fallbackId = id
      continue
    }
    const mode = (meta.interaction_mode || 'chat').toLowerCase()
    if (['wizard', 'async_job'].includes(mode)) {
      return meta.id
    }
  }
  return fallbackId
}

function findActiveCollectingIntake(skillId = null) {
  return messages.value.find((msg) => {
    const intake = msg.skill_intake
    if (!intake?.skill_id) return false
    if (skillId != null && String(intake.skill_id) !== String(skillId)) return false
    const phase = intake.phase || 'collecting'
    return ['collecting', 'confirming'].includes(phase)
  })
}

function resolveWizardSkillPickerId(skillId) {
  if (skillId == null) return null
  const match = skillItems.value.find((s) => String(s.id) === String(skillId))
  return match ? match.id : skillId
}

function setWizardSkillSelection(skillId) {
  const next = skillId != null ? [resolveWizardSkillPickerId(skillId)] : []
  const current = selectedWizardSkillTrigger.value
  if (
    current.length === next.length
    && (current.length === 0 || String(current[0]) === String(next[0]))
  ) {
    return
  }
  syncingWizardSkillSelection.value = true
  selectedWizardSkillTrigger.value = next
  nextTick(() => {
    syncingWizardSkillSelection.value = false
  })
}

function applyConversationBindings(detail) {
  if (detail.knowledge_base_ids != null) {
    selectedKBs.value = detail.knowledge_base_ids
  }
  if (detail.model_config_id) {
    selectedModelConfig.value = detail.model_config_id
  }
  if (detail.mcp_ids != null) {
    selectedMcps.value = detail.mcp_ids
  }
  enableDeepThinking.value = Boolean(detail.enable_thinking)
  const skillIds = detail.skill_ids || []
  lastConversationSkillIds.value = skillIds
  const chatSkillIds = []
  skillIds.forEach((id) => {
    const meta = skillItems.value.find((s) => String(s.id) === String(id))
    if (!meta) return
    const mode = (meta.interaction_mode || 'chat').toLowerCase()
    if (mode === 'chat') {
      chatSkillIds.push(meta.id)
    }
  })
  selectedSkills.value = chatSkillIds
  const wizardSkillId = resolveWizardSkillIdFromSkillIds(skillIds)
  if (wizardSkillId) {
    setWizardSkillSelection(wizardSkillId)
  }
}

function buildBindingPayload() {
  const wizardSkillIds = selectedWizardSkillTrigger.value
  return {
    knowledge_base_ids: [...selectedKBs.value],
    model_config_id: selectedModelConfig.value || null,
    skill_ids: wizardSkillIds.length ? [...wizardSkillIds] : [...selectedSkills.value],
    mcp_ids: [...selectedMcps.value],
    enable_thinking: showDeepThinking.value ? enableDeepThinking.value : false,
  }
}

function schedulePersistConversationBindings() {
  if (syncingConversationBindings.value) return
  if (!currentConvId) return
  clearTimeout(persistBindingsTimer)
  persistBindingsTimer = setTimeout(() => {
    persistConversationBindings()
  }, 300)
}

async function persistConversationBindings() {
  if (syncingConversationBindings.value) return
  if (!currentConvId) return

  try {
    const detail = await api.updateConversationBindings(currentConvId, buildBindingPayload())
    lastConversationSkillIds.value = detail.skill_ids || []
  } catch (err) {
    console.error('[Chat] 保存会话绑定失败:', err)
  }
}

function syncIntakeLockFromMessages() {
  skillIntakeLocked.value = messages.value.some(
      (msg) => msg.skill_intake && ['collecting', 'confirming'].includes(msg.skill_intake.phase || 'collecting'),
  )
  syncWizardSkillSelectionFromMessages()
}

function syncWizardSkillSelectionFromMessages() {
  const active = findWizardIntakeForPicker()
  if (active) {
    setWizardSkillSelection(active.skill_intake.skill_id)
    return
  }
  const cancelled = messages.value.some((msg) => {
    const phase = msg.skill_intake?.phase
    return phase === 'cancelled' || phase === 'stale'
  })
  if (cancelled) {
    setWizardSkillSelection(null)
    return
  }
  const wizardSkillId = resolveWizardSkillIdFromSkillIds(lastConversationSkillIds.value)
  if (wizardSkillId) {
    setWizardSkillSelection(wizardSkillId)
  }
}

function clearWizardSkillSelection() {
  setWizardSkillSelection(null)
}

function handleWizardSkillPickerUpdate(ids) {
  if (syncingWizardSkillSelection.value) {
    selectedWizardSkillTrigger.value = ids
    return
  }
  selectedWizardSkillTrigger.value = ids
  if (!ids.length) return
  const skillId = ids[0]
  if (findActiveCollectingIntake(skillId)) return

  const skill = skillItems.value.find((item) => String(item.id) === String(skillId))
  if (skill) {
    openSkillIntake(skill)
  }
}

watch(selectedSkills, (skills) => {
  if (skills.length && selectedMcps.value.length) {
    selectedMcps.value = []
  }
  schedulePersistConversationBindings()
})

watch(selectedMcps, (mcps) => {
  if (mcps.length && selectedSkills.value.length) {
    selectedSkills.value = []
  }
  schedulePersistConversationBindings()
})

watch(selectedKBs, () => {
  schedulePersistConversationBindings()
})

watch(enableDeepThinking, () => {
  schedulePersistConversationBindings()
})

async function ensureConversationForIntake() {
  // 仅当当前会话已加载且 ID 一致时复用；避免「新建对话」后仍绑定旧 conversationId
  if (
    conversationId.value
    && currentConvId
    && conversationId.value === currentConvId
  ) {
    return conversationId.value
  }
  const conv = await api.createConversation()
  const convId = conv.id
  currentConvId = convId
  conversationId.value = convId
  prependConversation(convId, conv.title || '新对话')
  await router.replace({ path: '/ai-manage/chat', query: { conversation: convId } })
  return convId
}

async function startSkillIntakeRequest(convId, skill, forceNew = false) {
  return api.startSkillIntake(convId, {
    skill_id: skill.id,
    model_config_id: selectedModelConfig.value || null,
    knowledge_base_ids: selectedKBs.value.length ? selectedKBs.value : null,
    enable_thinking: showDeepThinking.value ? enableDeepThinking.value : false,
    force_new: forceNew,
  })
}

async function openSkillIntake(skill) {
  let fullSkill = skill
  if (!fullSkill.input_schema?.wizard_steps?.length) {
    try {
      fullSkill = await api.fetchSkill(skill.id)
    } catch (err) {
      clearWizardSkillSelection()
      window.$message?.error(err?.message || '加载 Skill 配置失败')
      return
    }
  }
  if (!fullSkill.input_schema?.wizard_steps?.length) {
    window.$message?.warning('该 Skill 尚未配置向导步骤（input_schema.wizard_steps）')
    clearWizardSkillSelection()
    return
  }

  try {
    const convId = await ensureConversationForIntake()
    selectedMcps.value = []

    if (findActiveCollectingIntake(skill.id)) {
      setWizardSkillSelection(skill.id)
      nextTick(() => scrollToBottom())
      return
    }

    const otherDraft = await api.fetchActiveSkillDraft(convId)
    const draftSkillId = otherDraft?.skill_id
    if (otherDraft?.id && draftSkillId != null && String(draftSkillId) !== String(skill.id)) {
      window.$message?.warning('当前对话已有进行中的 Skill 收集，请先取消后再选择其他 Skill')
      clearWizardSkillSelection()
      return
    }

    const sameDraft = otherDraft?.id && String(draftSkillId) === String(skill.id)
    let intakeResult = null
    if (sameDraft) {
      await new Promise((resolve) => {
        window.$dialog?.warning({
          title: '未完成收集',
          content: `Skill「${skill.name}」有未完成的收集，是否继续？`,
          positiveText: '继续未完成',
          negativeText: '取消并新建',
          onPositiveClick: async () => {
            intakeResult = await startSkillIntakeRequest(convId, fullSkill, false)
            resolve()
          },
          onNegativeClick: async () => {
            intakeResult = await startSkillIntakeRequest(convId, fullSkill, true)
            resolve()
          },
        })
      })
    } else {
      intakeResult = await startSkillIntakeRequest(convId, fullSkill, false)
    }

    if (intakeResult?.title) {
      updateConversationTitle(convId, intakeResult.title)
    }

    await loadConversation(convId)
    syncIntakeLockFromMessages()
    setWizardSkillSelection(fullSkill.id)
    nextTick(() => scrollToBottom())
  } catch (err) {
    clearWizardSkillSelection()
    window.$message?.error(err?.message || '无法开始 Skill 收集')
  }
}

function mapMessageFromServer(m) {
  return {
    id: m.id,
    role: m.role,
    content: m.content,
    prompt_tokens: m.prompt_tokens,
    completion_tokens: m.completion_tokens,
    reasoning_tokens: m.reasoning_tokens,
    process_trace: m.process_trace || [],
    skill_run_ref: m.skill_run_ref || null,
    skill_intake: m.skill_intake || null,
  }
}

function applyUsageToMessage(msg, usage) {
  if (!msg || !usage) return
  if (usage.prompt_tokens != null) msg.prompt_tokens = usage.prompt_tokens
  if (usage.completion_tokens != null) msg.completion_tokens = usage.completion_tokens
  if (usage.reasoning_tokens != null) msg.reasoning_tokens = usage.reasoning_tokens
}

async function syncMessageFromServer(messageId) {
  if (!conversationId.value || messageId == null) return
  const localIdx = messages.value.findIndex((m) => m.id === messageId)
  if (localIdx < 0) return
  try {
    const detail = await api.fetchConversation(conversationId.value)
    const serverMsg = (detail.messages || []).find((m) => m.id === messageId)
    if (!serverMsg) return
    Object.assign(messages.value[localIdx], mapMessageFromServer(serverMsg))
  } catch (err) {
    console.error('[Chat] 同步消息失败:', err)
  }
}

async function syncLatestAssistantMessageFromServer(convId, fallbackIdx) {
  try {
    const detail = await api.fetchConversation(convId)
    const assistants = (detail.messages || []).filter((m) => m.role === 'assistant')
    const latest = assistants[assistants.length - 1]
    if (!latest) return
    let idx = messages.value.findIndex((m) => m.id === latest.id)
    if (idx < 0) idx = fallbackIdx
    if (idx < 0 || !messages.value[idx]) return
    Object.assign(messages.value[idx], mapMessageFromServer(latest))
  } catch (err) {
    console.error('[Chat] 同步助手消息失败:', err)
  }
}

async function ensureExecutionMessage(payload) {
  let execIndex = payload.executionMessageId
      ? messages.value.findIndex((m) => m.id === payload.executionMessageId)
      : findExecutionMessageIndex(payload.runId)
  if (execIndex >= 0) return execIndex

  if (payload.executionMessageId) {
    messages.value.push({
      id: payload.executionMessageId,
      role: 'assistant',
      content: payload.isAsync ? '异步任务已提交，正在后台执行…' : '任务执行中…',
      process_trace: [],
      skill_run_ref: { run_id: payload.runId },
      skill_intake: null,
    })
    return messages.value.length - 1
  }

  if (!conversationId.value) return -1
  try {
    const detail = await api.fetchConversation(conversationId.value)
    const exec = (detail.messages || []).find(
        (m) => m.skill_run_ref?.run_id === payload.runId && !m.skill_intake,
    )
    if (exec) {
      messages.value.push(mapMessageFromServer(exec))
      return messages.value.length - 1
    }
  } catch (err) {
    console.error('[Chat] 加载执行消息失败:', err)
  }
  return -1
}

function handleIntakeUpdate(messageIndex, intake) {
  if (!messages.value[messageIndex]) return
  messages.value[messageIndex].skill_intake = intake
  syncIntakeLockFromMessages()
}

function findExecutionMessageIndex(runId) {
  return messages.value.findIndex(
      (msg) => msg.skill_run_ref?.run_id === runId && !msg.skill_intake,
  )
}

function updateSkillProcessTrace(trace, step) {
  if (!step) return trace || []
  const next = [...(trace || [])]
  const idx = next.findIndex((item) => item.type === 'skill' && item.name === step.name)
  if (idx >= 0) next[idx] = step
  else next.push(step)
  return next
}

function attachSkillRunStream(runId, messageIndex) {
  if (skillRunStreamController) {
    skillRunStreamController.abort()
    skillRunStreamController = null
  }
  if (messageIndex < 0 || !messages.value[messageIndex]) return

  skillRunStreamController = skillRunStream(runId, {
    onProcess(data) {
      const msg = messages.value[messageIndex]
      if (!msg) return
      msg.process_trace = data?.process_trace
          ? data.process_trace
          : updateSkillProcessTrace(msg.process_trace, data?.step)
    },
    onToken(token) {
      const msg = messages.value[messageIndex]
      if (!msg) return
      if (msg.content === '任务执行中…') msg.content = ''
      msg.content = (msg.content || '') + token
    },
    onDone(data) {
      const msg = messages.value[messageIndex]
      if (!msg) return
      if (data.content) msg.content = data.content
      if (data.process_trace) msg.process_trace = data.process_trace
      applyUsageToMessage(msg, data.usage)
      msg.skill_run_ref = {
        ...(msg.skill_run_ref || {}),
        run_id: runId,
        links: [{ label: '查看执行记录', path: `/ai-manage/skill-runs?run=${runId}` }],
      }
      skillRunStreamController = null
      if (msg.id) {
        syncMessageFromServer(msg.id)
      }
      nextTick(() => scrollToBottom())
    },
    onError(err) {
      window.$message?.error(err?.message || 'Skill 执行失败')
      skillRunStreamController = null
    },
  })
}

function startSkillRunPolling(runId, messageIndex) {
  if (skillRunPollTimers.has(runId)) {
    clearInterval(skillRunPollTimers.get(runId))
  }
  const timer = setInterval(async () => {
    try {
      const run = await api.fetchSkillRun(runId)
      const msg = messages.value[messageIndex]
      if (!msg) return
      if (run.status === 'completed') {
        clearInterval(timer)
        skillRunPollTimers.delete(runId)
        msg.content = run.error_message || `Skill「${run.skill_name || '任务'}」已执行完成。`
        msg.skill_run_ref = {
          ...(msg.skill_run_ref || {}),
          run_id: runId,
          skill_name: run.skill_name,
          links: [{ label: '查看执行记录', path: `/ai-manage/skill-runs?run=${runId}` }],
        }
        if (msg.id) {
          await syncMessageFromServer(msg.id)
        }
        nextTick(() => scrollToBottom())
      } else if (run.status === 'failed' || run.status === 'cancelled') {
        clearInterval(timer)
        skillRunPollTimers.delete(runId)
        window.$message?.error(run.error_message || `任务${run.status}`)
      }
    } catch {
      // ignore transient errors
    }
  }, 2500)
  skillRunPollTimers.set(runId, timer)
}

async function handleIntakeStarted(intakeMessageIndex, payload) {
  syncIntakeLockFromMessages()
  const execIndex = await ensureExecutionMessage(payload)
  if (execIndex < 0) return

  if (payload.isAsync) {
    startSkillRunPolling(payload.runId, execIndex)
  } else {
    attachSkillRunStream(payload.runId, execIndex)
  }
  nextTick(() => scrollToBottom())
}

function handleIntakeLockChange(locked) {
  if (locked) {
    skillIntakeLocked.value = true
    return
  }
  syncIntakeLockFromMessages()
}

function handleIntakeCancelled() {
  clearWizardSkillSelection()
  syncIntakeLockFromMessages()
}

// 从URL获取对话ID
const conversationId = ref(normalizeConversationId(route.query.conversation))

async function loadConversations() {
  try {
    conversations.value = await api.fetchConversations()
  } catch (err) {
    console.error('[Chat] 加载对话列表失败:', err)
    conversations.value = []
  }
}

function buildConversationTitle(question) {
  if (!question) return '新对话'
  return question.slice(0, 20) + (question.length > 20 ? '...' : '')
}

function buildTurnLabel(content) {
  if (!content) return ''
  return content.slice(0, 20) + (content.length > 20 ? '...' : '')
}

function getOrCreateRunningStep(trace, type) {
  if (!trace) return null
  let step = trace.find((item) => item.type === type && item.status === 'running')
  if (!step) {
    step = { type, content: '', status: 'running' }
    trace.push(step)
  }
  return step
}

function finishRunningStep(trace, type) {
  if (!trace) return
  const step = trace.find((item) => item.type === type && item.status === 'running')
  if (step) {
    step.status = 'done'
  }
}

const userTurns = computed(() => {
  const turns = []
  messages.value.forEach((msg, messageIndex) => {
    if (msg.role === 'user') {
      turns.push({
        turnIndex: turns.length,
        messageIndex,
        label: buildTurnLabel(msg.content),
        fullContent: msg.content,
      })
    }
  })
  return turns
})

const showTurnNodes = computed(() =>
    !isConversationLoading.value && userTurns.value.length > 0,
)

const selectedKbLabel = computed(() => {
  if (selectedKBs.value.length === 0) return '未选择知识库'
  const names = knowledgeBases.value
      .filter((kb) => selectedKBs.value.includes(kb.id))
      .map((kb) => kb.knowledge_name)
  return names.length > 0 ? names.join('、') : '未选择知识库'
})

const messageTurnMap = computed(() => {
  const map = new Map()
  userTurns.value.forEach((turn) => {
    map.set(turn.messageIndex, turn.turnIndex)
  })
  return map
})

function userTurnIndexForMessage(messageIndex) {
  return messageTurnMap.value.get(messageIndex)
}

function prependConversation(id, title) {
  const existingIdx = conversations.value.findIndex((c) => c.id === id)
  if (existingIdx >= 0) {
    const [conv] = conversations.value.splice(existingIdx, 1)
    if (title) conv.title = title
    conversations.value.unshift(conv)
    return
  }
  conversations.value.unshift({ id, title: title || '新对话' })
}

function updateConversationTitle(id, title) {
  if (!id || !title) return
  const conv = conversations.value.find((c) => c.id === id)
  if (conv) {
    conv.title = title
    return
  }
  prependConversation(id, title)
}

function bumpConversationToTop(id) {
  const idx = conversations.value.findIndex((c) => c.id === id)
  if (idx > 0) {
    const [conv] = conversations.value.splice(idx, 1)
    conversations.value.unshift(conv)
  }
}

onMounted(async () => {
  await loadConversations()

  // 加载知识库和模型配置（默认模型自动选中，下拉框仅用于切换）
  try {
    const kbs = await api.fetchKnowledgeBases()
    knowledgeBases.value = kbs || []
    console.log('[Chat] 知识库加载完成:', kbs)
  } catch (err) {
    console.error('[Chat] 加载知识库失败:', err)
    knowledgeBases.value = []
  }

  try {
    const configs = await api.fetchModelConfigs()
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

  try {
    const skills = await api.fetchSkills()
    skillItems.value = skills || []
  } catch (err) {
    console.error('[Chat] 加载技能列表失败:', err)
    skillItems.value = []
  }

  try {
    const mcps = await api.fetchMcpServers()
    mcpItems.value = mcps || []
  } catch (err) {
    console.error('[Chat] 加载 MCP 列表失败:', err)
    mcpItems.value = []
  }

  if (inputRef.value) inputRef.value.focus()

  // 加载对话
  if (conversationId.value) {
    await switchToConversation(conversationId.value)
  }

  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.addEventListener('scroll', onMessagesScroll, { passive: true })
  }
  updateScrollFabState()
})

onUnmounted(() => {
  if (messagesContainer.value) {
    messagesContainer.value.removeEventListener('scroll', onMessagesScroll)
  }
  if (skillRunStreamController) {
    skillRunStreamController.abort()
    skillRunStreamController = null
  }
  skillRunPollTimers.forEach((timer) => clearInterval(timer))
  skillRunPollTimers.clear()
  clearTimeout(persistBindingsTimer)
})

watch(selectedModelConfig, () => {
  if (syncingConversationBindings.value) return
  if (!showDeepThinking.value) {
    enableDeepThinking.value = false
  }
  schedulePersistConversationBindings()
})

watch(messages, () => {
  nextTick(() => {
    updateScrollFabState()
    updateActiveTurn()
  })
})

async function switchToConversation(newId) {
  const targetId = normalizeConversationId(newId)

  if (streamController) {
    streamController.abort()
    streamController = null
  }
  if (skillRunStreamController) {
    skillRunStreamController.abort()
    skillRunStreamController = null
  }
  skillRunPollTimers.forEach((timer) => clearInterval(timer))
  skillRunPollTimers.clear()
  isLoading.value = false
  conversationId.value = targetId

  if (targetId) {
    await loadConversation(targetId)
  } else {
    currentConvId = null
    messages.value = []
    lastConversationSkillIds.value = []
    skillIntakeLocked.value = false
    clearWizardSkillSelection()
    selectedKBs.value = []
    selectedSkills.value = []
    selectedMcps.value = []
    enableDeepThinking.value = false
    activeTurnIndex.value = 0
    // 恢复默认模型配置
    if (modelConfigs.value.length > 0) {
      selectedModelConfig.value = modelConfigs.value.find(c => c.is_default)?.id || modelConfigs.value[0].id
      console.log('[Chat] 新建对话，使用默认模型配置:', selectedModelConfig.value)
    }
  }
  await nextTick()
  scrollToBottom()
  updateScrollFabState()
}

// 仅处理浏览器前进/后退、新建对话等外部 URL 变化
watch(() => route.query.conversation, async (newId, oldId) => {
  if (normalizeConversationId(newId) === normalizeConversationId(oldId)) return

  const targetId = normalizeConversationId(newId)
  if (targetId === normalizeConversationId(currentConvId)) return

  await switchToConversation(targetId)
})

async function loadConversation(id) {
  const targetId = normalizeConversationId(id)
  const seq = ++loadConversationSeq

  isConversationLoading.value = true
  messages.value = []

  try {
    const detail = await api.fetchConversation(targetId)
    if (seq !== loadConversationSeq) return

    currentConvId = targetId
    if (detail.title) {
      updateConversationTitle(targetId, detail.title)
    }
    messages.value = detail.messages.map(mapMessageFromServer)
    syncingConversationBindings.value = true
    applyConversationBindings(detail)
    syncIntakeLockFromMessages()
    syncingConversationBindings.value = false
  } catch (err) {
    if (seq !== loadConversationSeq) return
    console.error('[Chat] 加载对话失败:', err)
    messages.value = []
    window.$message?.error('加载对话失败')
  } finally {
    if (seq === loadConversationSeq) {
      isConversationLoading.value = false
    }
  }
}

async function selectConversation(id) {
  const targetId = normalizeConversationId(id)

  // 点击列表时直接加载，不依赖 router watch（避免 URL 已匹配或 currentConvId 误判导致跳过）
  await switchToConversation(targetId)

  if (normalizeConversationId(route.query.conversation) !== targetId) {
    await router.replace({ path: '/ai-manage/chat', query: { conversation: targetId } })
  }
}

async function startNewChat() {
  await switchToConversation(null)
  if (normalizeConversationId(route.query.conversation)) {
    await router.replace({ path: '/ai-manage/chat' })
  }
}

async function handleDeleteConversation(id) {
  if (!confirm('确定要删除这个对话吗？')) return
  try {
    await api.deleteConversation(id)
    await loadConversations()
    if (normalizeConversationId(currentConvId) === normalizeConversationId(id)) {
      await startNewChat()
    }
  } catch (err) {
    window.$message?.error('删除失败: ' + err.message)
  }
}

const SCROLL_EDGE_THRESHOLD = 48

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

function scrollToTop() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = 0
  }
}

function updateScrollFabState() {
  const el = messagesContainer.value
  if (!el || isConversationLoading.value || messages.value.length === 0) {
    showScrollFab.value = false
    return
  }

  const { scrollTop, scrollHeight, clientHeight } = el
  const maxScroll = scrollHeight - clientHeight
  if (maxScroll <= SCROLL_EDGE_THRESHOLD) {
    showScrollFab.value = false
    return
  }

  showScrollFab.value = true
  // 以可滚动区域中点为界：上半区显示「跳到底部」，下半区显示「返回顶部」
  scrollFabToBottom.value = scrollTop < maxScroll / 2
}

function updateActiveTurn() {
  const container = messagesContainer.value
  if (!container || userTurns.value.length === 0) {
    activeTurnIndex.value = 0
    return
  }

  const containerRect = container.getBoundingClientRect()
  const threshold = containerRect.top + 80
  const turnEls = container.querySelectorAll('[data-user-turn]')
  let nextActive = 0

  turnEls.forEach((el, idx) => {
    if (el.getBoundingClientRect().top <= threshold) {
      nextActive = idx
    }
  })

  activeTurnIndex.value = nextActive
}

function scrollToTurn(turnIndex) {
  const container = messagesContainer.value
  if (!container) return

  const el = container.querySelector(`[data-user-turn="${turnIndex}"]`)
  if (!el) return

  activeTurnIndex.value = turnIndex
  const containerRect = container.getBoundingClientRect()
  const elRect = el.getBoundingClientRect()
  const targetTop = container.scrollTop + (elRect.top - containerRect.top) - 16
  container.scrollTo({
    top: Math.max(0, targetTop),
    behavior: 'smooth',
  })
}

function onMessagesScroll() {
  updateScrollFabState()
  updateActiveTurn()
}

function handleScrollFabClick() {
  if (scrollFabToBottom.value) {
    scrollToBottom()
  } else {
    scrollToTop()
  }
  nextTick(updateScrollFabState)
}

function confirmSendWithoutKb() {
  return new Promise((resolve) => {
    if (!window.$dialog?.confirm) {
      resolve(false)
      return
    }
    window.$dialog.confirm({
      title: '未选择知识库',
      type: 'warning',
      content: '当前未选择任何知识库，回答将不引用文档内容，是否继续发送？',
      positiveText: '确认发送',
      negativeText: '取消',
      confirm() {
        resolve(true)
      },
      cancel() {
        resolve(false)
      },
    })
  })
}

async function sendMessage() {
  const question = inputText.value.trim()

  if (!question || isLoading.value || isConversationLoading.value) {
    return
  }

  if (selectedKBs.value.length === 0) {
    const confirmed = await confirmSendWithoutKb()
    if (!confirmed) {
      return
    }
  }

  inputText.value = ''
  messages.value.push({ role: 'user', content: question })
  messages.value.push({ role: 'assistant', content: '', process_trace: [] })
  isLoading.value = true

  await nextTick()
  scrollToBottom()

  const assistantIdx = messages.value.length - 1

  streamController = chatStream(
      question,
      currentConvId,
      selectedKBs.value,
      selectedModelConfig.value || null,
      showDeepThinking.value ? enableDeepThinking.value : false,
      selectedSkills.value,
      selectedMcps.value,
      {
        onMeta(data) {
          if (data.conversation_id && !currentConvId) {
            currentConvId = data.conversation_id
            conversationId.value = data.conversation_id
            // 更新URL，使刷新页面后能保持对话
            router.replace({ path: '/ai-manage/chat', query: { conversation: data.conversation_id } })
            const firstQuestion = messages.value.find((m) => m.role === 'user')?.content
            prependConversation(data.conversation_id, buildConversationTitle(firstQuestion))
          }
        },
        onReasoning(token) {
          const trace = messages.value[assistantIdx].process_trace
          const step = getOrCreateRunningStep(trace, 'reasoning')
          if (step) {
            step.content += token
          }
          nextTick(scrollToBottom)
        },
        onProcess(data) {
          if (data?.process_trace) {
            messages.value[assistantIdx].process_trace = data.process_trace
          } else if (data?.step) {
            const trace = messages.value[assistantIdx].process_trace
            const step = data.step
            const idx = trace.findIndex(
                (item) =>
                    item.type === 'mcp' &&
                    item.tool === step.tool &&
                    item.server === step.server
            )
            if (idx >= 0) {
              trace[idx] = step
            } else {
              trace.push(step)
            }
          }
          nextTick(scrollToBottom)
        },
        onToken(token) {
          finishRunningStep(messages.value[assistantIdx].process_trace, 'reasoning')
          messages.value[assistantIdx].content += token
          nextTick(scrollToBottom)
        },
        onDone(data) {
          if (data?.process_trace) {
            messages.value[assistantIdx].process_trace = data.process_trace
          } else {
            finishRunningStep(messages.value[assistantIdx].process_trace, 'reasoning')
          }
          if (data?.usage) {
            applyUsageToMessage(messages.value[assistantIdx], data.usage)
          }
          isLoading.value = false
          streamController = null
          if (currentConvId) {
            bumpConversationToTop(currentConvId)
            syncLatestAssistantMessageFromServer(currentConvId, assistantIdx)
          }
        },
        onError() {
          messages.value[assistantIdx].content += '\n\n[连接中断，请重试]'
          isLoading.value = false
          streamController = null
        },
      }
  )
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

</script>

<template>
  <NLayout has-sider wh-full class="chat-page-layout">
    <NLayoutSider
        bordered
        :width="260"
        :collapsed-width="0"
        show-trigger="arrow-circle"
        :native-scrollbar="false"
        content-style="display: flex; flex-direction: column; height: 100%; padding: 12px; box-sizing: border-box;"
    >
      <NButton secondary circle type="primary" block @click="startNewChat">
        <template #icon>
          <TheIcon icon="hugeicons:message-add-02" :size="16" />
        </template>
        新建对话
      </NButton>

      <div class="conversation-list cus-scroll-y">
        <div
            v-for="conv in conversations"
            :key="conv.id"
            class="conversation-item"
            :class="{ active: conversationId === conv.id }"
            @click="selectConversation(conv.id)"
        >
          <span class="conv-icon">
            <TheIcon
                icon="hugeicons:message-02"
                :size="14"
                :color="conversationId === conv.id ? 'var(--primary-color)' : undefined"
            />
          </span>
          <span class="conv-title">{{ conv.title || '新对话' }}</span>
          <button
              class="delete-btn"
              title="删除对话"
              @click.stop="handleDeleteConversation(conv.id)"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
        <div v-if="conversations.length === 0" class="empty-conversations">
          暂无历史对话
        </div>
      </div>

      <p class="conversation-count">共 {{ conversations.length }} 个对话</p>
    </NLayoutSider>

    <NLayoutContent
        class="chat-main-content"
        content-style="height: 100%; overflow: hidden; background-color: var(--chat-surface);"
    >
      <CommonPage :show-header="false" :show-footer="false" inherit-background>
        <div class="chat-panel">
          <div class="chat-thread">
            <div class="messages-wrapper">
              <div v-if="showTurnNodes" class="turn-nodes-rail">
                <ChatTurnNodes
                    :turns="userTurns"
                    :active-turn-index="activeTurnIndex"
                    :kb-label="selectedKbLabel"
                    @select="scrollToTurn"
                />
              </div>
              <div
                  ref="messagesContainer"
                  class="messages-area"
                  :class="{ 'is-empty': !isConversationLoading && messages.length === 0 }"
              >
                <div v-if="isConversationLoading" class="messages-skeleton">
                  <div class="message-skeleton user">
                    <div class="avatar-col" />
                    <NSkeleton class="skeleton-bubble" :sharp="false" height="40px" width="38%" />
                    <div class="avatar-col">
                      <NSkeleton circle width="36px" height="36px" />
                    </div>
                  </div>
                  <div class="message-skeleton assistant">
                    <div class="avatar-col">
                      <NSkeleton circle width="36px" height="36px" />
                    </div>
                    <div class="skeleton-bubble skeleton-bubble--wide">
                      <NSkeleton text :repeat="3" />
                    </div>
                    <div class="avatar-col" />
                  </div>
                  <div class="message-skeleton user">
                    <div class="avatar-col" />
                    <NSkeleton class="skeleton-bubble" :sharp="false" height="40px" width="32%" />
                    <div class="avatar-col">
                      <NSkeleton circle width="36px" height="36px" />
                    </div>
                  </div>
                  <div class="message-skeleton assistant">
                    <div class="avatar-col">
                      <NSkeleton circle width="36px" height="36px" />
                    </div>
                    <div class="skeleton-bubble skeleton-bubble--wide">
                      <NSkeleton text :repeat="2" />
                    </div>
                    <div class="avatar-col" />
                  </div>
                </div>

                <div v-else-if="messages.length === 0" class="welcome">
                  <div class="welcome-brand">
                    <icon-custom-logo-new text-36 color-primary flex-shrink-0 />
                    <p class="welcome-greeting">
                      我是
                      <span class="welcome-app-name">{{ $t('app_name') }}</span>
                      智能助手，很高兴见到你！
                    </p>
                  </div>
                </div>

                <template v-else>
                  <div
                      v-for="(msg, idx) in messages"
                      :key="idx"
                      :data-user-turn="msg.role === 'user' ? userTurnIndexForMessage(idx) : undefined"
                  >
                    <MessageBubble
                        :role="msg.role"
                        :content="msg.content"
                        :message-id="msg.id"
                        :conversation-id="conversationId"
                        :skill-intake="msg.skill_intake || null"
                        :skill-catalog="skillCatalog"
                        :model-config-id="selectedModelConfig"
                        :knowledge-base-ids="selectedKBs"
                        :process-trace="msg.process_trace || []"
                        :skill-run-ref="msg.skill_run_ref || null"
                        :is-streaming="isLoading && idx === messages.length - 1 && msg.role === 'assistant' && !msg.skill_intake"
                        :prompt-tokens="msg.prompt_tokens"
                        :completion-tokens="msg.completion_tokens"
                        :reasoning-tokens="msg.reasoning_tokens"
                        @intake-update="(intake) => handleIntakeUpdate(idx, intake)"
                        @intake-lock-change="handleIntakeLockChange"
                        @intake-started="(payload) => handleIntakeStarted(idx, payload)"
                        @intake-cancelled="() => handleIntakeCancelled()"
                    />
                  </div>
                </template>
              </div>
            </div>

            <div class="input-area">
              <button
                  v-show="showScrollFab"
                  type="button"
                  class="scroll-fab"
                  :title="scrollFabToBottom ? '跳到底部' : '返回顶部'"
                  @click="handleScrollFabClick"
              >
                <TheIcon
                    :icon="scrollFabToBottom ? 'material-symbols:keyboard-arrow-down' : 'material-symbols:keyboard-arrow-up'"
                    :size="18"
                    color="var(--primary-color)"
                />
              </button>
              <div class="input-grid">
                <div class="input-box">
                  <textarea
                      ref="inputRef"
                      v-model="inputText"
                      class="input-textarea"
                      :placeholder="composerPlaceholder"
                      rows="3"
                      :disabled="composerDisabled"
                      @keydown="handleKeydown"
                  />
                  <div class="input-box-actions">
                    <div class="input-box-actions-left">
                      <ChatFeaturePicker
                          v-model="selectedKBs"
                          icon="hugeicons:book-open-02"
                          title="选择知识库"
                          search-placeholder="搜索知识库..."
                          empty-text="暂无可用知识库"
                          no-match-text="未找到匹配的知识库"
                          :items="kbPickerItems"
                      />
                      <ChatFeaturePicker
                          v-model="selectedSkills"
                          single
                          icon="hugeicons:magic-wand-01"
                          title="选择 Skill"
                          search-placeholder="搜索 Skills..."
                          empty-text="暂无可用 chat 模式 Skill"
                          no-match-text="未找到匹配的 Skills"
                          :items="skillPickerItems"
                          allow-empty
                      />
                      <ChatFeaturePicker
                          :model-value="selectedWizardSkillTrigger"
                          single
                          close-on-select
                          icon="hugeicons:workflow-square-01"
                          title="Skill 任务"
                          search-placeholder="搜索向导 / 异步 Skill..."
                          empty-text="暂无 wizard / async Skill"
                          no-match-text="未找到匹配的 Skill 任务"
                          :items="wizardSkillPickerItems"
                          allow-empty
                          @update:model-value="handleWizardSkillPickerUpdate"
                      />
                      <ChatFeaturePicker
                          v-model="selectedMcps"
                          icon="hugeicons:wrench-01"
                          title="选择 MCP 服务"
                          search-placeholder="搜索 MCP 服务..."
                          empty-text="暂无可用 MCP 服务"
                          no-match-text="未找到匹配的 MCP 服务"
                          :items="mcpPickerItems"
                          :disabled="mcpPickerDisabled"
                          allow-empty
                      />
                      <ChatDeepThinkingToggle
                          v-if="showDeepThinking"
                          v-model="enableDeepThinking"
                      />
                    </div>
                    <div class="input-box-actions-right">
                      <ChatModelSelector
                          v-if="showModelSelector"
                          v-model="selectedModelConfig"
                          :items="modelPickerItems"
                          :disabled="composerDisabled"
                      />
                      <button
                          class="send-btn"
                          type="button"
                          :disabled="!inputText.trim() || composerDisabled"
                          @click="sendMessage()"
                      >
                        <TheIcon icon="material-symbols:send-rounded" :size="18" color="#fff" />
                      </button>
                    </div>
                  </div>
                </div>
                <p class="input-disclaimer">内容由 AI 生成，请仔细甄别 · KEENROBOT助手</p>
              </div>
            </div>
          </div>
        </div>
      </CommonPage>
    </NLayoutContent>
  </NLayout>
</template>

<style scoped>
.chat-page-layout {
  height: 100%;
  overflow: hidden;
}

.chat-page-layout :deep(section.cus-scroll-y) {
  overflow: hidden;
}

.conversation-list {
  flex: 1;
  margin-top: 12px;
  min-height: 0;
}

.conversation-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: color 0.2s;
  margin-bottom: 2px;
  color: var(--n-text-color);
  font-size: 12px;
}

.conv-icon {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  color: var(--n-text-color-3);
  transition: color 0.2s;
}

.conversation-item:hover:not(.active) {
  color: var(--n-text-color);
}

.conversation-item:hover:not(.active) .conv-icon {
  color: var(--n-text-color-2);
}

.conversation-item.active {
  background: transparent;
  color: var(--primary-color, #f4511e);
}

.conversation-item.active .conv-icon {
  color: var(--primary-color, #f4511e);
}

.conversation-item.active .conv-icon :deep(.n-icon),
.conversation-item.active .conv-icon :deep(svg) {
  color: var(--primary-color, #f4511e);
}

.conversation-item.active .conv-title {
  color: var(--primary-color, #f4511e);
}

.conv-icon :deep(.n-icon),
.conv-icon :deep(svg) {
  color: currentColor;
}

.conv-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  transition: color 0.2s;
}

.empty-conversations {
  text-align: center;
  padding: 40px 12px;
  color: var(--n-text-color-3, #999);
  font-size: 12px;
}

.conversation-count {
  flex-shrink: 0;
  margin: 8px 0 0;
  padding-top: 8px;
  text-align: center;
  font-size: 11px;
  color: var(--n-text-color-3, #999);
  border-top: 1px solid var(--n-border-color);
}

.delete-btn {
  opacity: 0;
  background: none;
  border: none;
  color: var(--n-text-color-3, #999);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;
}

.delete-btn svg {
  width: 14px;
  height: 14px;
}

.conversation-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  background: rgba(208, 48, 80, 0.1);
  color: var(--error-color, #d03050);
}

.chat-panel {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-thread {
  --avatar-size: 36px;
  --avatar-gap: 12px;
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0 24px;
}

.messages-wrapper {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  overflow: hidden;
}

.turn-nodes-rail {
  position: absolute;
  right: 8px;
  top: 50%;
  z-index: 3;
  transform: translateY(-50%);
  pointer-events: none;
}

.messages-area {
  flex: 1;
  min-height: 0;
  width: 100%;
  overflow-y: auto;
  /* 滚动条样式 */
  scrollbar-width: thin; /* 火狐：细滚动条 */
  scrollbar-color: #ccc transparent;
}

/* Chrome / Edge / Safari */
.messages-area::-webkit-scrollbar {
  width: 6px;
}
.messages-area::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 3px;
}
.messages-area::-webkit-scrollbar-track {
  background: transparent;
}

.messages-area.is-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding-top: 15vh;
  overflow: hidden;
}

.messages-skeleton {
  padding: 8px 0;
}

.message-skeleton {
  display: grid;
  grid-template-columns: var(--avatar-size, 36px) 1fr var(--avatar-size, 36px);
  gap: var(--avatar-gap, 12px);
  align-items: start;
  margin: 0 auto 16px;
  width: 90%;
}

.message-skeleton .avatar-col {
  width: 36px;
  flex-shrink: 0;
}

.skeleton-bubble {
  min-width: 0;
}

.skeleton-bubble--wide {
  width: 100%;
}

.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
  box-sizing: border-box;
}

.welcome-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 640px;
}

.welcome-greeting {
  font-size: 24px;
  font-weight: 500;
  line-height: 1.8;
  color: var(--n-text-color, #333);
}

.welcome-app-name {
  margin: 0 4px;
  font-weight: 700;
  color: var(--primary-color, #f4511e);
}

.input-area {
  position: relative;
  flex-shrink: 0;
  margin-top: auto;
  padding: 14px 0 1px;
}

.scroll-fab {
  position: absolute;
  left: 50%;
  top: -5px;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid var(--chat-input-border);
  border-radius: 50%;
  background-color: var(--chat-input-surface);
  box-shadow: var(--chat-input-shadow);
  cursor: pointer;
  transform: translate(-50%, -50%);
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
}

.scroll-fab:hover {
  border-color: var(--primary-color, #f4511e);
}

.scroll-fab:active {
  transform: translate(-50%, -50%) scale(0.96);
}

.input-grid {
  display: grid;
  grid-template-columns: var(--avatar-size) 0.99fr var(--avatar-size);
  gap: var(--avatar-gap);
  align-items: end;
  margin: 0 auto;
  width: 90%;
}

.input-box {
  grid-column: 2;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px 8px 16px;
  border: 1px solid var(--chat-input-border);
  border-radius: 12px;
  background-color: var(--chat-input-surface);
  box-shadow: var(--chat-input-shadow);
}

.input-box-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.input-box-actions-left {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.input-box-actions-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.input-textarea {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  resize: none;
  min-height: 24px;
  max-height: 120px;
  line-height: 24px;
  padding: 0;
  font-size: 14px;
  color: var(--n-text-color);
  box-sizing: border-box;
}

.input-textarea::placeholder {
  color: var(--chat-muted-text);
  font-size: 12px;
  opacity: 1;
}

.input-textarea:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: var(--primary-color, #f4511e);
  color: #fff;
  flex-shrink: 0;
  transition: background-color 0.2s, opacity 0.2s;
  cursor: pointer;
}

.send-btn :deep(.n-icon) {
  display: flex;
  align-items: center;
  justify-content: center;
}

.send-btn:hover:not(:disabled) {
  background: var(--primary-color-hover, #f76b3c);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.input-disclaimer {
  grid-column: 2;
  text-align: center;
  font-size: 10px;
  color: var(--chat-muted-text);
  line-height: 1;
}
</style>
