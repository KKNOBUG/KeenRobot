<script setup>
import { computed, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NSpace,
  NSwitch,
} from 'naive-ui'

import api from '@/api'
import { renderIcon } from '@/utils'
import {
  formToPayload,
  INTERACTION_MODE_OPTIONS,
  parseJsonText,
  rowToForm,
} from '../skillUtils.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  record: { type: Object, default: null },
})

const emit = defineEmits(['update:show', 'saved', 'preview'])

const formRef = ref(null)
const saving = ref(false)
const form = ref(rowToForm())
const mcpOptions = ref([])
const mcpLoading = ref(false)

const needsSchema = computed(() => {
  const mode = form.value.interaction_mode
  return mode === 'wizard' || mode === 'async_job'
})

async function loadMcpOptions() {
  mcpLoading.value = true
  try {
    const list = await api.fetchMcpServers('', true)
    mcpOptions.value = (list || [])
      .filter((item) => item.is_enabled !== false)
      .map((item) => ({
        label: item.name,
        value: item.id,
      }))
  } catch {
    mcpOptions.value = []
  } finally {
    mcpLoading.value = false
  }
}

watch(
  () => [props.show, props.record],
  () => {
    if (!props.show) return
    form.value = rowToForm(props.record || {})
    loadMcpOptions()
  },
  { immediate: true },
)

function close() {
  emit('update:show', false)
}

function validateJson(_rule, value) {
  if (!needsSchema.value && !(value || '').trim()) return true
  try {
    parseJsonText(value, 'input_schema')
    return true
  } catch (err) {
    return new Error(err.message)
  }
}

function validateExecutionJson(_rule, value) {
  if (!(value || '').trim()) return true
  try {
    parseJsonText(value, 'execution')
    return true
  } catch (err) {
    return new Error(err.message)
  }
}

async function handleSave() {
  await formRef.value?.validate?.()
  saving.value = true
  try {
    const payload = formToPayload(form.value)
    await api.updateSkill(form.value.id, payload)
    window.$message?.success('保存成功')
    emit('saved')
    close()
  } catch (err) {
    window.$message?.error(err?.message || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <NDrawer :show="show" :width="640" @update:show="emit('update:show', $event)">
    <NDrawerContent closable title="编辑集成配置">
      <NAlert type="info" :bordered="false" class="skill-edit__tip">
        名称与描述由磁盘 Skill 同步维护；此处仅配置平台接入方式（模式、Wizard、内嵌 MCP、启用状态）。
      </NAlert>

      <NForm
        ref="formRef"
        label-placement="left"
        label-align="left"
        :label-width="108"
        :model="form"
        class="skill-edit__form"
      >
        <NFormItem label="Skill Key">
          <NInput :value="form.skill_key" disabled placeholder="同步后自动填充" />
        </NFormItem>
        <NFormItem label="技能名称">
          <NInput :value="form.name" disabled />
        </NFormItem>
        <NFormItem label="描述">
          <NInput :value="form.description" type="textarea" :rows="2" disabled />
        </NFormItem>
        <NFormItem label="磁盘版本">
          <NInput :value="form.skill_version" disabled placeholder="同步后自动更新" />
        </NFormItem>
        <NFormItem
          label="交互模式"
          path="interaction_mode"
          :rule="{ required: true, message: '请选择交互模式', trigger: 'change' }"
        >
          <NSelect
            v-model:value="form.interaction_mode"
            :options="INTERACTION_MODE_OPTIONS"
            placeholder="选择交互模式"
          />
        </NFormItem>
        <NFormItem label="是否启用" path="is_enabled">
          <NSwitch v-model:value="form.is_enabled" />
        </NFormItem>
        <NFormItem label="内嵌 MCP">
          <NSelect
            v-model:value="form.execution_mcp_ids"
            :options="mcpOptions"
            :loading="mcpLoading"
            multiple
            clearable
            filterable
            placeholder="可选：执行时附加 MCP 工具（与聊天页 MCP 选择互斥）"
          />
        </NFormItem>
        <NFormItem
          v-if="needsSchema"
          label="input_schema"
          path="input_schema_text"
          :rule="{ validator: validateJson, trigger: ['input', 'blur'] }"
        >
          <NInput
            v-model:value="form.input_schema_text"
            type="textarea"
            :rows="12"
            placeholder='{"wizard_steps":[...],"layout":{...}}'
          />
        </NFormItem>
        <NFormItem
          v-else
          label="input_schema"
          path="input_schema_text"
          :rule="{ validator: validateJson, trigger: ['input', 'blur'] }"
        >
          <NInput
            v-model:value="form.input_schema_text"
            type="textarea"
            :rows="6"
            placeholder="chat 模式可选；wizard/async_job 启用时必填"
          />
        </NFormItem>
        <NFormItem
          label="execution"
          path="execution_text"
          :rule="{ validator: validateExecutionJson, trigger: ['input', 'blur'] }"
        >
          <NInput
            v-model:value="form.execution_text"
            type="textarea"
            :rows="4"
            placeholder='{"prefer_async": false, "estimated_duration": "medium"}'
          />
        </NFormItem>
      </NForm>

      <template #footer>
        <NSpace justify="space-between" style="width: 100%">
          <NButton quaternary @click="emit('preview', record)">
            <template #icon>
              <component :is="renderIcon('material-symbols:visibility-outline', { size: 18 })" />
            </template>
            预览 SKILL.md
          </NButton>
          <NSpace>
            <NButton @click="close">取消</NButton>
            <NButton type="primary" :loading="saving" @click="handleSave">保存</NButton>
          </NSpace>
        </NSpace>
      </template>
    </NDrawerContent>
  </NDrawer>
</template>

<style scoped lang="scss">
.skill-edit__tip {
  margin-bottom: 16px;
}

.skill-edit__form {
  margin-top: 4px;
}
</style>
