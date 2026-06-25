<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NCheckbox,
  NInput,
  NSelect,
  NSpace,
  NSpin,
  NStep,
  NSteps,
  NTag,
  NUpload,
} from 'naive-ui'

import api from '@/api'
import { getModeLabel } from '@/views/ai-manage/skills/skillUtils.js'

const props = defineProps({
  intake: { type: Object, required: true },
  messageId: { type: Number, required: true },
  conversationId: { type: String, required: true },
  skill: { type: Object, default: null },
  modelConfigId: { type: String, default: null },
  knowledgeBaseIds: { type: Array, default: () => [] },
  readonly: { type: Boolean, default: false },
})

const emit = defineEmits(['update:intake', 'started', 'cancelled', 'lock-change'])

const skillDetail = ref(props.skill)
const loadingSkill = ref(false)
const submitting = ref(false)
const formValues = ref({})
const fileMap = ref({})
const dirFileMap = ref({})
const missingFields = ref([])

const phase = computed(() => props.intake?.phase || 'collecting')
const stepIndex = computed(() => props.intake?.step_index ?? 0)
const wizardSteps = computed(() => skillDetail.value?.input_schema?.wizard_steps || [])
const isAsync = computed(() => (props.intake?.interaction_mode || '') === 'async_job')
const isLocked = computed(() => ['collecting', 'confirming'].includes(phase.value))

const currentStep = computed(() => wizardSteps.value[stepIndex.value] || null)
const isConfirmStep = computed(() => currentStep.value?.type === 'confirm')
const showStepForm = computed(() => ['collecting', 'confirming'].includes(phase.value))
const showRetrospective = computed(() =>
  wizardSteps.value.length > 0
  && ['submitted', 'cancelled'].includes(phase.value),
)
const retrospectiveStepCurrent = computed(() => {
  const total = wizardSteps.value.length
  if (!total) return 0
  if (phase.value === 'submitted') return total
  return Math.min(stepIndex.value + 1, total)
})

const phaseStatusMeta = computed(() => {
  const map = {
    collecting: { label: '收集中', type: 'info' },
    confirming: { label: '待确认', type: 'warning' },
    submitted: { label: '已提交', type: 'success' },
    cancelled: { label: '已取消', type: 'default' },
    stale: { label: '已失效', type: 'warning' },
  }
  return map[phase.value] || { label: '收集中', type: 'info' }
})

watch(isLocked, (locked) => emit('lock-change', locked), { immediate: true })

watch(
  () => props.skill,
  (value) => {
    if (value) skillDetail.value = value
  },
  { immediate: true },
)

watch(
  () => props.intake,
  (value) => {
    if (!value) return
    formValues.value = { ...(value.form_values || {}) }
    missingFields.value = value.missing_fields || []
    if (value.file_labels) {
      Object.entries(value.file_labels).forEach(([key, label]) => {
        if (label && !fileMap.value[key]) {
          fileMap.value[key] = { name: label, persisted: true }
        }
      })
    }
  },
  { immediate: true, deep: true },
)

onMounted(async () => {
  await ensureSkillLoaded()
  if (phase.value === 'collecting' || phase.value === 'confirming') {
    await verifyDraftRun()
  }
})

async function ensureSkillLoaded() {
  if (skillDetail.value?.input_schema?.wizard_steps?.length) return
  if (!props.intake?.skill_id) return
  loadingSkill.value = true
  try {
    skillDetail.value = await api.fetchSkill(props.intake.skill_id)
    initFormDefaults()
  } catch (err) {
    window.$message?.error(err?.message || '加载 Skill 配置失败')
  } finally {
    loadingSkill.value = false
  }
}

function initFormDefaults() {
  wizardSteps.value.forEach((step) => {
    if (formValues.value[step.key] != null && formValues.value[step.key] !== '') return
    if (step.type === 'confirm') formValues.value[step.key] = false
    else if (step.type === 'text' || step.type === 'choice') formValues.value[step.key] = ''
  })
}

async function verifyDraftRun() {
  try {
    await api.fetchSkillRun(props.intake.run_id)
  } catch {
    await persistIntake({ phase: 'stale' })
  }
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
        return `${label}: ${f?.name || props.intake?.file_labels?.[step.key] || '未选择'}`
      }
      if (step.type === 'dir') {
        const files = dirFileMap.value[step.key] || []
        const dirLabel = props.intake?.file_labels?.[step.key]
        return `${label}: ${dirLabel || (files.length ? `${files.length} 个文件` : '未选择')}`
      }
      if (step.type === 'confirm') {
        return `${label}: ${formValues.value[step.key] ? '已确认' : '未确认'}`
      }
      return `${label}: ${formValues.value[step.key] || '-'}`
    })
    .join('\n')
}

function buildFileLabels() {
  const labels = {}
  wizardSteps.value.forEach((step) => {
    if (step.type === 'file') {
      const f = fileMap.value[step.key]
      if (f?.name) labels[step.key] = f.name
    }
    if (step.type === 'dir') {
      const files = dirFileMap.value[step.key] || []
      if (files.length) labels[step.key] = `${files.length} 个文件`
    }
  })
  return labels
}

async function persistIntake(patch, extra = {}) {
  const next = {
    ...props.intake,
    ...patch,
    form_values: { ...formValues.value },
    file_labels: buildFileLabels(),
  }
  emit('update:intake', next)
  if (!props.messageId || !props.conversationId) return next
  try {
    const updated = await api.updateSkillIntakeMessage(
      props.conversationId,
      props.messageId,
      {
        ...patch,
        form_values: next.form_values,
        file_labels: next.file_labels,
        ...extra,
      },
    )
    if (updated?.skill_intake) emit('update:intake', updated.skill_intake)
    return updated?.skill_intake || next
  } catch (err) {
    console.error('[SkillIntake] persist failed', err)
    return next
  }
}

async function uploadCurrentFiles(runId) {
  for (const step of wizardSteps.value) {
    if (step.type === 'file') {
      const file = fileMap.value[step.key]
      if (file && !file.persisted) {
        await api.uploadSkillRunFile(runId, step.key, file)
        fileMap.value[step.key] = { name: file.name, persisted: true }
      }
    }
    if (step.type === 'dir') {
      const files = dirFileMap.value[step.key] || []
      for (const file of files) {
        await api.uploadSkillRunFile(runId, step.key, file)
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
    await api.saveSkillRunInputs(runId, textFields)
  }
}

async function goNext() {
  if (props.readonly || submitting.value) return
  const step = currentStep.value
  if (!step) return

  if (step.type === 'confirm') {
    if (!formValues.value[step.key]) {
      window.$message?.warning('请先确认摘要')
      return
    }
    await submitAndStart()
    return
  }

  const nextIndex = Math.min(stepIndex.value + 1, wizardSteps.value.length - 1)
  const nextStep = wizardSteps.value[nextIndex]
  const nextPhase = nextStep?.type === 'confirm' ? 'confirming' : 'collecting'
  await persistIntake({ step_index: nextIndex, phase: nextPhase })
}

async function goPrev() {
  if (props.readonly || submitting.value || stepIndex.value <= 0) return
  const prevIndex = stepIndex.value - 1
  await persistIntake({ step_index: prevIndex, phase: 'collecting' })
}

async function submitAndStart() {
  if (submitting.value) return
  submitting.value = true
  missingFields.value = []
  const runId = props.intake.run_id

  try {
    await uploadCurrentFiles(runId)
    const validation = await api.validateSkillRun(runId)
    if (!validation.valid) {
      missingFields.value = validation.missing_fields || []
      await persistIntake({ missing_fields: missingFields.value })
      window.$message?.warning('输入未通过校验，请补全必填项')
      submitting.value = false
      return
    }

    const startResult = await api.startSkillRun(runId)
    const confirmStepIndex = Math.max(wizardSteps.value.length - 1, 0)
    await persistIntake({
      phase: 'submitted',
      step_index: confirmStepIndex,
      missing_fields: [],
    })
    emit('started', {
      runId,
      isAsync: isAsync.value,
      executionMessageId: startResult?.execution_message_id ?? null,
    })
  } catch (err) {
    window.$message?.error(err?.message || '启动失败')
  } finally {
    submitting.value = false
  }
}

async function handleCancel() {
  if (props.readonly) return
  try {
    if (props.intake.run_id) {
      await api.cancelSkillRun(props.intake.run_id)
    }
    await persistIntake({ phase: 'cancelled' })
    emit('cancelled')
  } catch (err) {
    window.$message?.error(err?.message || '取消失败')
  }
}
</script>

<template>
  <div class="skill-intake-panel">
    <div class="skill-intake-panel__head">
      <div class="skill-intake-panel__title">
        Skill 收集 · {{ intake.skill_name || skillDetail?.name }}
      </div>
      <NSpace :size="6">
        <NTag size="small" :type="phaseStatusMeta.type" :bordered="false">
          {{ phaseStatusMeta.label }}
        </NTag>
        <NTag size="small" :bordered="false">
          {{ getModeLabel(intake.interaction_mode) }}
        </NTag>
      </NSpace>
    </div>

    <NAlert v-if="phase === 'stale'" type="warning" :bordered="false">
      收集记录已失效（可能已被清理），请重新选择 Skill 开始。
    </NAlert>

    <NSpin v-else :show="loadingSkill || submitting">
      <template v-if="showStepForm">
        <NSteps
            v-if="wizardSteps.length"
            :current="stepIndex + 1"
            size="small"
            class="skill-intake-panel__steps"
        >
          <NStep v-for="step in wizardSteps" :key="step.key" :title="step.label || step.key" />
        </NSteps>

        <NAlert
          v-if="skillDetail?.description"
          type="info"
          :bordered="false"
          class="skill-intake-panel__tip"
        >
          {{ skillDetail.description }}
        </NAlert>

        <NAlert
          v-if="missingFields.length"
          type="warning"
          :bordered="false"
          title="校验未通过"
        >
          <ul class="skill-intake-panel__missing">
            <li v-for="item in missingFields" :key="item.key">
              {{ item.label || item.key }}：{{ item.reason }}
            </li>
          </ul>
        </NAlert>

        <div v-if="currentStep" class="skill-intake-panel__body">
          <div class="skill-intake-panel__field">
            <div class="skill-intake-panel__label">
              {{ currentStep.label || currentStep.key }}
              <span v-if="currentStep.required !== false" class="required">*</span>
            </div>

            <NUpload
              v-if="currentStep.type === 'file'"
              :max="1"
              :default-upload="false"
              :disabled="readonly"
              @change="(opts) => onFileChange(currentStep, opts)"
            >
              <NButton size="tiny">{{ fileMap[currentStep.key]?.name || '选择文件' }}</NButton>
            </NUpload>

            <NUpload
              v-else-if="currentStep.type === 'dir'"
              multiple
              :default-upload="false"
              :disabled="readonly"
              @change="(opts) => onDirChange(currentStep, opts)"
            >
              <NButton size="tiny">选择目录内文件（可多选）</NButton>
            </NUpload>

            <NInput
              v-else-if="currentStep.type === 'text'"
              v-model:value="formValues[currentStep.key]"
              :disabled="readonly"
              :placeholder="currentStep.label || currentStep.key"
            />

            <NSelect
              v-else-if="currentStep.type === 'choice' && currentStep.options?.length"
              v-model:value="formValues[currentStep.key]"
              :disabled="readonly"
              :options="currentStep.options.map((o) => ({ label: o, value: o }))"
              placeholder="请选择"
            />

            <NInput
              v-else-if="currentStep.type === 'choice'"
              v-model:value="formValues[currentStep.key]"
              :disabled="readonly"
              placeholder="请输入或选择项"
            />

            <div v-else-if="currentStep.type === 'confirm'" class="skill-intake-panel__confirm">
              <pre class="skill-intake-panel__summary">{{ buildSummaryText() }}</pre>
              <NCheckbox
                :checked="!!formValues[currentStep.key]"
                :disabled="readonly"
                @update:checked="(value) => { formValues[currentStep.key] = value }"
              >
                {{ currentStep.label || '确认以上信息并开始执行' }}
              </NCheckbox>
            </div>
          </div>

          <NSpace v-if="!readonly" justify="space-between" class="skill-intake-panel__actions">
            <NButton size="tiny" type="warning" @click="handleCancel">取消任务</NButton>
            <NSpace>
              <NButton v-if="stepIndex > 0" size="tiny" @click="goPrev">上一步</NButton>
              <NButton size="tiny" :type="isConfirmStep ? 'primary' : 'info'" @click="goNext">
                {{ isConfirmStep ? (isAsync ? '确认并提交异步任务' : '确认并开始') : '下一步' }}
              </NButton>
            </NSpace>
          </NSpace>
        </div>
      </template>

      <template v-else-if="showRetrospective">
        <NSteps
            :current="retrospectiveStepCurrent"
            size="small"
            class="skill-intake-panel__steps"
        >
          <NStep v-for="step in wizardSteps" :key="step.key" :title="step.label || step.key" />
        </NSteps>

        <div class="skill-intake-panel__retrospective">
          <div class="skill-intake-panel__section-title">已收集信息</div>
          <pre class="skill-intake-panel__summary">{{ buildSummaryText() }}</pre>
        </div>

        <NAlert v-if="phase === 'cancelled'" type="default" :bordered="false">
          已取消收集，未开始执行。
        </NAlert>
      </template>
    </NSpin>
  </div>
</template>

<style scoped lang="scss">
.skill-intake-panel {
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 12px;
  padding: 14px 16px;
  background: var(--card-color, #fafafa);
}

.skill-intake-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}

.skill-intake-panel__title {
  font-weight: 600;
  font-size: 14px;
}

.skill-intake-panel__steps {
  margin-bottom: 12px;
}

.skill-intake-panel__tip {
  margin-bottom: 12px;
}

.skill-intake-panel__field {
  margin-bottom: 12px;
}

.skill-intake-panel__label {
  margin-bottom: 8px;
  font-size: 13px;

  .required {
    color: #ef4444;
    margin-left: 2px;
  }
}

.skill-intake-panel__confirm {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.skill-intake-panel__summary {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.03);
  white-space: pre-wrap;
  font-size: 12px;
  line-height: 1.5;
}

.skill-intake-panel__retrospective,
.skill-intake-panel__execution {
  margin-bottom: 12px;
}

.skill-intake-panel__section-title {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--n-text-color-2, #666);
}

.skill-intake-panel__execution {
  padding-top: 4px;
  border-top: 1px dashed var(--border-color, #e5e7eb);
}

.skill-intake-panel__actions {
  margin-top: 8px;
}

.skill-intake-panel__stream-text {
  margin-top: 10px;
  white-space: pre-wrap;
  line-height: 1.6;
  font-size: 14px;
}

.skill-intake-panel__missing {
  margin: 0;
  padding-left: 18px;
}
</style>
