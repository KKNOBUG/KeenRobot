<script setup>
import { computed, ref, watch } from 'vue'
import {
  NButton,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NSelect,
  NSpace,
  NSwitch,
} from 'naive-ui'

import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'
import {
  KWARGS_PLACEHOLDER,
  applyPresetToForm,
  emptyForm,
  formToPayload,
  isExamplePreset,
  rowToForm,
  syncKwargField,
  validateKwargs,
} from '../taskUtils.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  mode: { type: String, default: 'edit' },
  record: { type: Object, default: null },
  presets: { type: Array, default: () => [] },
  schedulerOptions: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:show', 'saved'])

const formRef = ref(null)
const saving = ref(false)
const form = ref(emptyForm())

const title = computed(() => (props.mode === 'create' ? '新建任务' : '编辑任务'))

const presetOptions = computed(() =>
  props.presets.map((p) => ({
    label: `${p.task_name}（${p.task_type}）`,
    value: p.preset_key,
  })),
)

const showExampleFields = computed(() => isExamplePreset(form.value))

const formWriteNumber = computed({
  get: () => form.value.write_number,
  set: (val) => {
    form.value.write_number = val
    form.value = syncKwargField(form.value, 'write_number', val ?? 100)
  },
})

const formWriteMessage = computed({
  get: () => form.value.write_message,
  set: (val) => {
    form.value.write_message = val
    form.value = syncKwargField(form.value, 'write_message', val || '')
  },
})

watch(
  () => [props.show, props.record, props.mode],
  () => {
    if (!props.show) return
    form.value = props.mode === 'create' ? emptyForm() : rowToForm(props.record || {})
  },
  { immediate: true },
)

function close() {
  emit('update:show', false)
}

function handlePresetChange(presetKey) {
  const preset = props.presets.find((p) => p.preset_key === presetKey)
  if (!preset) return
  form.value = applyPresetToForm(form.value, preset)
}

async function handleSave() {
  await formRef.value?.validate?.()
  saving.value = true
  try {
    const payload = formToPayload(form.value, props.mode === 'edit')
    if (props.mode === 'create') {
      await api.createTask(payload)
      window.$message?.success('创建成功')
    } else {
      await api.updateTask(payload)
      window.$message?.success('保存成功')
    }
    emit('saved')
    close()
  } catch (err) {
    if (err?.message) window.$message?.error(err.message)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <NDrawer :show="show" :width="760" placement="right" @update:show="emit('update:show', $event)">
    <NDrawerContent :title="title" closable :native-scrollbar="false" body-content-style="padding: 0;">
      <div class="task-edit">
        <div class="task-edit__body cus-scroll">
          <NForm
            ref="formRef"
            label-placement="top"
            :model="form"
            require-mark-placement="right-hanging"
          >
            <!-- 基本配置 -->
            <section class="task-edit__section">
              <div class="task-edit__section-head task-edit__section-head--basic">
                <TheIcon icon="material-symbols:task-outline" :size="18" />
                <span>基本配置</span>
              </div>
              <div class="task-edit__section-body">
                <NFormItem v-if="mode === 'create'" label="任务模板" path="preset_key">
                  <NSelect
                      v-model:value="form.preset_key"
                      :options="presetOptions"
                      clearable
                      placeholder="选择模板快速填充"
                      @update:value="handlePresetChange"
                  />
                </NFormItem>

                <NFormItem
                    label="任务名称"
                    path="task_name"
                    :rule="{ required: true, message: '请输入任务名称', trigger: ['input', 'blur'] }"
                >
                  <NInput v-model:value="form.task_name" placeholder="任务显示名称" />
                </NFormItem>

                <div class="task-edit__row">
                  <NFormItem label="任务分类" path="task_type" class="task-edit__col">
                    <NInput v-model:value="form.task_type" placeholder="如 example、rag" />
                  </NFormItem>
                  <NFormItem
                      label="任务调度节点"
                      path="task_celery_node"
                      class="task-edit__col"
                      :rule="{ required: true, message: '请填写任务调度节点', trigger: ['input', 'blur'] }"
                  >
                    <NInput v-model:value="form.task_celery_node" placeholder="backend.celery_scheduler.tasks..." />
                  </NFormItem>
                </div>

                <NFormItem label="任务描述" path="task_desc">
                  <NInput
                      v-model:value="form.task_desc"
                      type="textarea"
                      :rows="2"
                      placeholder="可选"
                  />
                </NFormItem>
              </div>
            </section>

            <!-- 执行配置 -->
            <section class="task-edit__section">
              <div class="task-edit__section-head task-edit__section-head--execution">
                <TheIcon icon="material-symbols:play-circle-outline" :size="18" />
                <span>执行配置</span>
              </div>
              <div class="task-edit__section-body">
                <div v-if="showExampleFields" class="task-edit__row">
                  <NFormItem label="写入行数" path="write_number" class="task-edit__col">
                    <NInputNumber
                        v-model:value="formWriteNumber"
                        :min="1"
                        :max="100"
                        :step="10"
                        class="w-full"
                    />
                  </NFormItem>
                  <NFormItem label="写入内容" path="write_message" class="task-edit__col">
                    <NInput
                        v-model:value="formWriteMessage"
                        placeholder="测试文本：通过Celery异步执行函数..."
                    />
                  </NFormItem>
                </div>

                <NFormItem
                    label="执行参数 (JSON)"
                    path="task_kwargs_text"
                    :rule="{ validator: validateKwargs, trigger: ['input', 'blur'] }"
                >
                  <NInput
                      v-model:value="form.task_kwargs_text"
                      type="textarea"
                      :rows="6"
                      :placeholder="KWARGS_PLACEHOLDER"
                  />
                </NFormItem>
              </div>
            </section>

            <!-- 调度配置 -->
            <section class="task-edit__section">
              <div class="task-edit__section-head task-edit__section-head--schedule">
                <TheIcon icon="material-symbols:schedule-outline" :size="18" />
                <span>调度配置</span>
              </div>
              <div class="task-edit__section-body">
                <NFormItem label="任务调度模式" path="task_celery_scheduler">
                  <NSelect
                      v-model:value="form.task_celery_scheduler"
                      :options="schedulerOptions"
                      clearable
                      placeholder="不选则仅支持手动执行"
                  />
                </NFormItem>

                <NFormItem
                    v-if="form.task_celery_scheduler === 'interval'"
                    label="间隔 (秒)"
                    path="task_interval_expr"
                >
                  <NInputNumber
                      v-model:value="form.task_interval_expr"
                      :min="10"
                      :step="10"
                      class="w-full"
                  />
                </NFormItem>

                <NFormItem
                    v-if="form.task_celery_scheduler === 'cron'"
                    label="Cron 表达式"
                    path="task_crontabs_expr"
                >
                  <NInput v-model:value="form.task_crontabs_expr" placeholder="如 0 */2 * * *" />
                </NFormItem>

                <NFormItem
                    v-if="form.task_celery_scheduler === 'datetime'"
                    label="执行时间"
                    path="task_datetime_expr"
                >
                  <NInput v-model:value="form.task_datetime_expr" placeholder="YYYY-MM-DD HH:MM:SS" />
                </NFormItem>

                <div class="task-edit__switch-row">
                  <div class="task-edit__switch-info">
                    <TheIcon icon="material-symbols:power-settings-new" :size="18" color="#22c55e" />
                    <div>
                      <div class="task-edit__switch-title">启用调度</div>
                      <div class="task-edit__switch-desc">开启后按调度模式自动执行</div>
                    </div>
                  </div>
                  <NSwitch v-model:value="form.task_enabled" />
                </div>
              </div>
            </section>
          </NForm>
        </div>

        <div class="task-edit__footer">
          <NSpace justify="end">
            <NButton @click="close">取消</NButton>
            <NButton type="primary" :loading="saving" @click="handleSave">
              {{ mode === 'create' ? '创建' : '保存' }}
            </NButton>
          </NSpace>
        </div>
      </div>
    </NDrawerContent>
  </NDrawer>
</template>

<style scoped lang="scss">
.task-edit {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px);
}

.task-edit__body {
  flex: 1;
  min-height: 0;
  padding: 20px 24px;
  overflow-y: auto;
}

.task-edit__section {
  margin-bottom: 16px;
  background: #fff;
  border: 1px solid #eef0f4;
  border-radius: 12px;
  overflow: hidden;
}

.task-edit__section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 18px;
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
  border-bottom: 1px solid #f1f5f9;

  &--basic :deep(.n-icon) {
    color: #3b82f6;
  }

  &--execution :deep(.n-icon) {
    color: #f59e0b;
  }

  &--schedule :deep(.n-icon) {
    color: #22c55e;
  }
}

.task-edit__section-body {
  padding: 16px 18px 6px;
}

.task-edit__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.task-edit__col {
  min-width: 0;
}

.task-edit__switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  margin-bottom: 8px;
  background: #f8fafc;
  border: 1px solid #eef0f4;
  border-radius: 10px;
}

.task-edit__switch-info {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.task-edit__switch-title {
  font-size: 14px;
  font-weight: 500;
  color: #1f2937;
}

.task-edit__switch-desc {
  margin-top: 2px;
  font-size: 12px;
  color: #9ca3af;
}

.task-edit__footer {
  padding: 14px 24px;
  border-top: 1px solid #eef0f4;
  background: #fff;
}

.w-full {
  width: 100%;
}
</style>

<style scoped lang="scss">
html.dark .task-edit__section {
  background: #18181c;
  border-color: rgba(255, 255, 255, 0.1);
}

html.dark .task-edit__section-head {
  color: #e5e7eb;
  border-bottom-color: rgba(255, 255, 255, 0.08);
}

html.dark .task-edit__switch-row {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.08);
}

html.dark .task-edit__switch-title {
  color: #e5e7eb;
}

html.dark .task-edit__footer {
  border-top-color: rgba(255, 255, 255, 0.1);
  background: #18181c;
}
</style>
