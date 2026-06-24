<script setup>
import { computed, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NCheckbox,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NSpin,
  NTag,
  NUpload,
} from 'naive-ui'

import ChatProcessTrace from '@/components/chat/ChatProcessTrace.vue'
import api, { skillRunStream } from '@/api'
import { getModeLabel } from '@/views/ai-manage/skills/skillUtils.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  skill: { type: Object, default: null },
  conversationId: { type: String, default: null },
  modelConfigId: { type: String, default: null },
  knowledgeBaseIds: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:show', 'completed'])

const phase = ref('form')
const submitting = ref(false)
const runId = ref('')
const formValues = ref({})
const fileMap = ref({})
const dirFileMap = ref({})
const missingFields = ref([])
const runSummary = ref('')
const processTrace = ref([])
const streamController = ref(null)
const pollTimer = ref(null)

const wizardSteps = computed(() => props.skill?.input_schema?.wizard_steps || [])
const isAsync = computed(() => (props.skill?.interaction_mode || '') === 'async_job')
const title = computed(() => props.skill?.name ? `Skill 向导 · ${props.skill.name}` : 'Skill 向导')

watch(
  () => [props.show, props.skill?.id],
  () => {
    if (!props.show) {
      resetState()
      return
    }
    resetState()
    initFormDefaults()
  },
)

function resetState() {
  if (streamController.value) {
    streamController.value.abort()
    streamController.value = null
  }
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
  phase.value = 'form'
  submitting.value = false
  runId.value = ''
  formValues.value = {}
  fileMap.value = {}
  dirFileMap.value = {}
  missingFields.value = []
  runSummary.value = ''
  processTrace.value = []
}

function initFormDefaults() {
  wizardSteps.value.forEach((step) => {
    if (step.type === 'confirm') {
      formValues.value[step.key] = false
    } else if (step.type === 'text' || step.type === 'choice') {
      formValues.value[step.key] = ''
    }
  })
}

function close() {
  emit('update:show', false)
}

function stepAccept(step) {
  if (step.accept?.length) return step.accept.join(',')
  if (step.type === 'dir') return undefined
  return '.md,.txt,.json,.csv,.xlsx,.zip'
}

function onFileChange(step, options) {
  const file = options.file?.file
  if (!file) return
  fileMap.value[step.key] = file
}

function onDirChange(step, options) {
  const list = options.fileList || []
  dirFileMap.value[step.key] = list.map((item) => item.file).filter(Boolean)
}

function buildSummaryText() {
  return wizardSteps.value
    .map((step) => {
      const label = step.label || step.key
      if (step.type === 'file') {
        const f = fileMap.value[step.key]
        return `${label}: ${f?.name || '未选择'}`
      }
      if (step.type === 'dir') {
        const files = dirFileMap.value[step.key] || []
        return `${label}: ${files.length} 个文件`
      }
      if (step.type === 'confirm') {
        return `${label}: ${formValues.value[step.key] ? '已确认' : '未确认'}`
      }
      return `${label}: ${formValues.value[step.key] || '-'}`
    })
    .join('\n')
}

async function submitWizard() {
  if (!props.skill?.id || submitting.value) return
  submitting.value = true
  missingFields.value = []

  try {
    const run = await api.createSkillRun({
      skill_id: props.skill.id,
      conversation_id: props.conversationId || null,
      model_config_id: props.modelConfigId || null,
      knowledge_base_ids: props.knowledgeBaseIds?.length ? props.knowledgeBaseIds : null,
    })
    runId.value = run.id

    for (const step of wizardSteps.value) {
      if (step.type === 'file') {
        const file = fileMap.value[step.key]
        if (file) {
          await api.uploadSkillRunFile(run.id, step.key, file)
        }
      }
      if (step.type === 'dir') {
        const files = dirFileMap.value[step.key] || []
        for (const file of files) {
          await api.uploadSkillRunFile(run.id, step.key, file)
        }
      }
    }

    const textFields = {}
    wizardSteps.value.forEach((step) => {
      if (['text', 'choice', 'confirm'].includes(step.type)) {
        textFields[step.key] = formValues.value[step.key]
      }
    })
    if (Object.keys(textFields).length) {
      await api.saveSkillRunInputs(run.id, textFields)
    }

    const validation = await api.validateSkillRun(run.id)
    if (!validation.valid) {
      missingFields.value = validation.missing_fields || []
      window.$message?.warning('输入未通过校验，请补全必填项')
      submitting.value = false
      return
    }

    await api.startSkillRun(run.id)

    if (isAsync.value) {
      phase.value = 'async'
      startPolling(run.id)
      return
    }

    phase.value = 'running'
    streamController.value = skillRunStream(run.id, {
      onProcess(data) {
        if (data?.process_trace) {
          processTrace.value = data.process_trace
        } else if (data?.step) {
          const trace = [...processTrace.value]
          const idx = trace.findIndex(
            (item) => item.type === 'skill' && item.name === data.step.name,
          )
          if (idx >= 0) trace[idx] = data.step
          else trace.push(data.step)
          processTrace.value = trace
        }
      },
      onToken(token) {
        runSummary.value += token
      },
      onDone(data) {
        runSummary.value = data.content || runSummary.value
        if (data.process_trace) processTrace.value = data.process_trace
        finishCompleted(run.id)
      },
      onError(err) {
        window.$message?.error(err?.message || 'Skill 执行失败')
        submitting.value = false
        phase.value = 'form'
      },
    })
  } catch (err) {
    window.$message?.error(err?.message || '提交失败')
    submitting.value = false
  }
}

function startPolling(id) {
  pollTimer.value = setInterval(async () => {
    try {
      const run = await api.fetchSkillRun(id)
      if (run.status === 'completed') {
        clearInterval(pollTimer.value)
        pollTimer.value = null
        runSummary.value = run.error_message || '异步任务已完成，请在执行记录查看产物。'
        finishCompleted(id)
      } else if (run.status === 'failed' || run.status === 'cancelled') {
        clearInterval(pollTimer.value)
        pollTimer.value = null
        window.$message?.error(run.error_message || `任务${run.status}`)
        submitting.value = false
        phase.value = 'form'
      }
    } catch {
      // ignore transient poll errors
    }
  }, 2500)
}

async function finishCompleted(id) {
  submitting.value = false
  phase.value = 'done'
  let outputs = []
  try {
    outputs = await api.fetchSkillRunOutputs(id)
  } catch {
    outputs = []
  }
  emit('completed', {
    runId: id,
    skillId: props.skill.id,
    skillName: props.skill.name,
    summary: runSummary.value || 'Skill 任务已执行完成。',
    outputs,
  })
}
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    :title="title"
    class="skill-wizard-modal"
    style="width: 720px; max-width: 96vw"
    @update:show="emit('update:show', $event)"
  >
    <template #header-extra>
      <NTag v-if="skill" size="small" :bordered="false">
        {{ getModeLabel(skill.interaction_mode) }}
      </NTag>
    </template>

    <NSpin :show="submitting && phase === 'form'">
      <div v-if="phase === 'form'" class="skill-wizard__body">
        <NAlert v-if="skill?.description" type="info" :bordered="false" class="skill-wizard__tip">
          {{ skill.description }}
        </NAlert>
        <NAlert
          v-if="missingFields.length"
          type="warning"
          :bordered="false"
          class="skill-wizard__tip"
          title="校验未通过"
        >
          <ul class="skill-wizard__missing">
            <li v-for="item in missingFields" :key="item.key">
              {{ item.label || item.key }}：{{ item.reason }}
            </li>
          </ul>
        </NAlert>

        <div v-for="step in wizardSteps" :key="step.key" class="skill-wizard__field">
          <div class="skill-wizard__label">
            {{ step.label || step.key }}
            <span v-if="step.required !== false" class="required">*</span>
          </div>

          <NUpload
            v-if="step.type === 'file'"
            :max="1"
            :default-upload="false"
            @change="(opts) => onFileChange(step, opts)"
          >
            <NButton>{{ fileMap[step.key]?.name || '选择文件' }}</NButton>
          </NUpload>

          <NUpload
            v-else-if="step.type === 'dir'"
            multiple
            :default-upload="false"
            @change="(opts) => onDirChange(step, opts)"
          >
            <NButton>选择目录内文件（可多选）</NButton>
          </NUpload>

          <NInput
            v-else-if="step.type === 'text'"
            v-model:value="formValues[step.key]"
            :placeholder="step.label || step.key"
          />

          <NSelect
            v-else-if="step.type === 'choice' && step.options?.length"
            v-model:value="formValues[step.key]"
            :options="step.options.map((o) => ({ label: o, value: o }))"
            placeholder="请选择"
          />

          <NInput
            v-else-if="step.type === 'choice'"
            v-model:value="formValues[step.key]"
            placeholder="请输入或选择项"
          />

          <div v-else-if="step.type === 'confirm'" class="skill-wizard__confirm">
            <pre class="skill-wizard__summary">{{ buildSummaryText() }}</pre>
            <NCheckbox v-model:checked="formValues[step.key]">
              {{ step.label || '确认以上信息' }}
            </NCheckbox>
          </div>
        </div>
      </div>

      <div v-else-if="phase === 'running'" class="skill-wizard__body">
        <ChatProcessTrace :steps="processTrace" :streaming="true" />
        <div v-if="runSummary" class="skill-wizard__stream-text">{{ runSummary }}</div>
      </div>

      <div v-else-if="phase === 'async'" class="skill-wizard__body">
        <NAlert type="info" :bordered="false">
          任务已提交后台执行，请稍候；完成后将自动关闭向导，也可在「Skill 执行记录」查看详情。
        </NAlert>
      </div>

      <div v-else-if="phase === 'done'" class="skill-wizard__body">
        <NAlert type="success" :bordered="false">执行完成</NAlert>
        <div v-if="runSummary" class="skill-wizard__stream-text">{{ runSummary }}</div>
      </div>
    </NSpin>

    <template #footer>
      <NSpace justify="end">
        <NButton @click="close">{{ phase === 'done' ? '关闭' : '取消' }}</NButton>
        <NButton
          v-if="phase === 'form'"
          type="primary"
          :loading="submitting"
          @click="submitWizard"
        >
          {{ isAsync ? '提交异步任务' : '校验并执行' }}
        </NButton>
        <NButton v-if="phase === 'done'" type="primary" @click="close">完成</NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped lang="scss">
.skill-wizard__body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 60vh;
  overflow-y: auto;
}

.skill-wizard__tip {
  margin-bottom: 0;
}

.skill-wizard__field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skill-wizard__label {
  font-size: 13px;
  font-weight: 600;
  color: #374151;

  .required {
    color: #ef4444;
    margin-left: 2px;
  }
}

.skill-wizard__confirm {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.skill-wizard__summary {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f9fafb;
  border: 1px solid #eef0f4;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.skill-wizard__stream-text {
  margin-top: 12px;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.skill-wizard__missing {
  margin: 0;
  padding-left: 18px;
}
</style>

<style scoped lang="scss">
html.dark .skill-wizard__label {
  color: #e5e7eb;
}

html.dark .skill-wizard__summary {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.1);
}
</style>
