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
  NSlider,
  NSpace,
  NSwitch,
} from 'naive-ui'

import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'
import {
  PROVIDER_OPTIONS,
  MAX_TOKEN_OPTIONS,
  emptyForm,
  formToPayload,
  rowToForm,
  snapMaxTokens,
} from '../modelUtils.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  mode: { type: String, default: 'edit' },
  record: { type: Object, default: null },
})

const emit = defineEmits(['update:show', 'saved'])

const formRef = ref(null)
const saving = ref(false)
const form = ref(emptyForm())

const title = computed(() => (props.mode === 'create' ? '新建模型配置' : '编辑模型配置'))

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

async function handleSave() {
  await formRef.value?.validate?.()
  saving.value = true
  try {
    form.value.max_tokens = snapMaxTokens(form.value.max_tokens)
    const payload = formToPayload(form.value, props.mode === 'edit')
    if (props.mode === 'create') {
      await api.createModelConfig(payload)
      window.$message?.success('创建成功')
    } else {
      await api.updateModelConfig(form.value.id, payload)
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

function getMaxTokensIndex(value) {
  const idx = MAX_TOKEN_OPTIONS.indexOf(value)
  return idx >= 0 ? idx : MAX_TOKEN_OPTIONS.indexOf(4096)
}

function updateMaxTokensIndex(index) {
  form.value.max_tokens = MAX_TOKEN_OPTIONS[index] ?? 4096
}

function updateMaxTokensValue(value) {
  form.value.max_tokens = snapMaxTokens(value)
}

function formatMaxTokensTooltip(index) {
  return String(MAX_TOKEN_OPTIONS[index] ?? '')
}
</script>

<template>
  <NDrawer :show="show" :width="760" placement="right" @update:show="emit('update:show', $event)">
    <NDrawerContent :title="title" closable :native-scrollbar="false" body-content-style="padding: 0;">
      <div class="model-edit">
        <div class="model-edit__body cus-scroll">
          <NForm
            ref="formRef"
            label-placement="top"
            :model="form"
            require-mark-placement="right-hanging"
          >
            <!-- 基本配置 -->
            <section class="model-edit__section">
              <div class="model-edit__section-head model-edit__section-head--basic">
                <TheIcon icon="material-symbols:smart-toy-outline" :size="18" />
                <span>基本配置</span>
              </div>
              <div class="model-edit__section-body">
                <NFormItem
                    label="模型名称"
                    path="config_name"
                    :rule="{ required: true, message: '请输入模型名称', trigger: ['input', 'blur'] }"
                >
                  <NInput v-model:value="form.config_name" placeholder="如：客服-DeepSeek" />
                </NFormItem>

                <div class="model-edit__row">
                  <NFormItem label="模型供应商" path="model_provider" class="model-edit__col">
                    <NSelect v-model:value="form.model_provider" :options="PROVIDER_OPTIONS" />
                  </NFormItem>
                  <NFormItem
                      label="模型标识"
                      path="llm_model_name"
                      class="model-edit__col"
                      :rule="{ required: true, message: '请输入模型标识', trigger: ['input', 'blur'] }"
                  >
                    <NInput v-model:value="form.llm_model_name" placeholder="如：deepseek-chat" />
                  </NFormItem>
                </div>

                <div class="model-edit__capabilities">
                  <div class="model-edit__capability-item">
                    <div class="model-edit__capability-info">
                      <TheIcon icon="hugeicons:brain-02" :size="18" color="#7c3aed" />
                      <div>
                        <div class="model-edit__capability-title">支持思考模式</div>
                        <div class="model-edit__capability-desc">展示深度思考开关</div>
                      </div>
                    </div>
                    <NSwitch v-model:value="form.model_thinking" />
                  </div>
                  <div class="model-edit__capability-item">
                    <div class="model-edit__capability-info">
                      <TheIcon icon="material-symbols:star-outline" :size="18" color="#f59e0b" />
                      <div>
                        <div class="model-edit__capability-title">默认模型</div>
                        <div class="model-edit__capability-desc">聊天优先使用</div>
                      </div>
                    </div>
                    <NSwitch v-model:value="form.is_default" />
                  </div>
                </div>
              </div>
            </section>

            <!-- 连接配置 -->
            <section class="model-edit__section">
              <div class="model-edit__section-head model-edit__section-head--connection">
                <TheIcon icon="material-symbols:link" :size="18" />
                <span>连接配置</span>
              </div>
              <div class="model-edit__section-body">
                <NFormItem label="API 地址" path="llm_base_url">
                  <NInput
                      v-model:value="form.llm_base_url"
                      placeholder="留空使用 .env 中的 LLM_BASE_URL"
                  />
                </NFormItem>
                <NFormItem label="API Key" path="llm_api_key">
                  <NInput
                      v-model:value="form.llm_api_key"
                      type="password"
                      show-password-on="click"
                      :placeholder="form.has_llm_api_key ? '留空则不修改已保存的 Key' : '留空使用 .env 中的 LLM_API_KEY'"
                  />
                </NFormItem>
              </div>
            </section>

            <!-- 参数配置 -->
            <section class="model-edit__section">
              <div class="model-edit__section-head model-edit__section-head--params">
                <TheIcon icon="material-symbols:tune" :size="18" />
                <span>参数配置</span>
              </div>
              <div class="model-edit__section-body">
                <NFormItem path="temperature" :show-label="false" class="model-edit__slider-form-item">
                  <div class="model-edit__slider-row">
                    <span class="model-edit__slider-label">创意温度控制(Temperature)</span>
                    <span class="model-edit__slider-hint">精确</span>
                    <NSlider v-model:value="form.temperature" :min="0" :max="1" :step="0.1" class="model-edit__slider" />
                    <span class="model-edit__slider-hint">多样</span>
                    <NInputNumber
                        v-model:value="form.temperature"
                        :min="0"
                        :max="1"
                        :step="0.1"
                        class="model-edit__slider-input"
                    />
                  </div>
                </NFormItem>

                <NFormItem path="top_p" :show-label="false" class="model-edit__slider-form-item">
                  <div class="model-edit__slider-row">
                    <span class="model-edit__slider-label">核采样概率数(TOP-P)</span>
                    <NSlider v-model:value="form.top_p" :min="0" :max="1" :step="0.05" class="model-edit__slider" />
                    <NInputNumber
                        v-model:value="form.top_p"
                        :min="0"
                        :max="1"
                        :step="0.05"
                        class="model-edit__slider-input"
                    />
                  </div>
                </NFormItem>

                <NFormItem path="top_k" :show-label="false" class="model-edit__slider-form-item">
                  <div class="model-edit__slider-row">
                    <span class="model-edit__slider-label">固定候选词数(TOP-K)</span>
                    <NSlider v-model:value="form.top_k" :min="0" :max="100" :step="1" class="model-edit__slider" />
                    <NInputNumber
                        v-model:value="form.top_k"
                        :min="0"
                        :max="100"
                        :step="1"
                        :precision="0"
                        class="model-edit__slider-input"
                    />
                  </div>
                </NFormItem>

                <NFormItem path="max_tokens" :show-label="false" class="model-edit__slider-form-item">
                  <div class="model-edit__slider-row">
                    <span class="model-edit__slider-label">单次最大输出(Tokens)</span>
                    <NSlider
                        :value="getMaxTokensIndex(form.max_tokens)"
                        :min="0"
                        :max="MAX_TOKEN_OPTIONS.length - 1"
                        :step="1"
                        :format-tooltip="formatMaxTokensTooltip"
                        class="model-edit__slider"
                        @update:value="updateMaxTokensIndex"
                    />
                    <NInputNumber
                        :value="form.max_tokens"
                        :min="MAX_TOKEN_OPTIONS[0]"
                        :max="MAX_TOKEN_OPTIONS[MAX_TOKEN_OPTIONS.length - 1]"
                        :step="1"
                        :precision="0"
                        class="model-edit__slider-input"
                        @update:value="updateMaxTokensValue"
                    />
                  </div>
                </NFormItem>

                <NFormItem path="max_history_rounds" :show-label="false" class="model-edit__slider-form-item">
                  <div class="model-edit__slider-row">
                    <span class="model-edit__slider-label">历史对话轮数(History-Rounds)</span>
                    <NSlider v-model:value="form.max_history_rounds" :min="0" :max="20" :step="1" class="model-edit__slider" />
                    <NInputNumber
                        v-model:value="form.max_history_rounds"
                        :min="0"
                        :max="20"
                        :step="1"
                        :precision="0"
                        class="model-edit__slider-input"
                    />
                  </div>
                </NFormItem>

                <NFormItem path="score_threshold" :show-label="false" class="model-edit__slider-form-item">
                  <div class="model-edit__slider-row">
                    <span class="model-edit__slider-label">相似过滤阈值(Score-Threshold)</span>
                    <NSlider v-model:value="form.score_threshold" :min="0" :max="1" :step="0.05" class="model-edit__slider" />
                    <NInputNumber
                        v-model:value="form.score_threshold"
                        :min="0"
                        :max="1"
                        :step="0.05"
                        class="model-edit__slider-input"
                    />
                  </div>
                </NFormItem>
              </div>
            </section>

            <!-- 其他配置 -->
            <section class="model-edit__section">
              <div class="model-edit__section-head model-edit__section-head--other">
                <TheIcon icon="material-symbols:more-horiz" :size="18" />
                <span>其他配置</span>
              </div>
              <div class="model-edit__section-body">
                <NFormItem label="描述" path="config_desc">
                  <NInput
                      v-model:value="form.config_desc"
                      type="textarea"
                      :rows="3"
                      placeholder="模型用途备注（可选）"
                  />
                </NFormItem>

                <NFormItem label="系统提示词" path="system_prompt">
                  <NInput
                      v-model:value="form.system_prompt"
                      type="textarea"
                      :rows="4"
                      placeholder="留空使用全局默认；可包含 {context} 占位符注入检索内容"
                  />
                </NFormItem>
              </div>
            </section>
          </NForm>
        </div>

        <div class="model-edit__footer">
          <NSpace justify="end">
            <NButton @click="close">取消</NButton>
            <NButton type="primary" :loading="saving" @click="handleSave">保存</NButton>
          </NSpace>
        </div>
      </div>
    </NDrawerContent>
  </NDrawer>
</template>

<style scoped lang="scss">
.model-edit {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px);
}

.model-edit__body {
  flex: 1;
  min-height: 0;
  padding: 20px 24px;
  overflow-y: auto;
}

.model-edit__section {
  margin-bottom: 16px;
  background: #fff;
  border: 1px solid #eef0f4;
  border-radius: 12px;
  overflow: hidden;
}

.model-edit__section-head {
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

  &--connection :deep(.n-icon) {
    color: #22c55e;
  }

  &--params :deep(.n-icon) {
    color: #f59e0b;
  }

  &--other :deep(.n-icon) {
    color: #6b7280;
  }
}

.model-edit__section-body {
  padding: 16px 18px 6px;
}

.model-edit__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.model-edit__col {
  min-width: 0;
}

.model-edit__capabilities {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 8px;
}

.model-edit__capability-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 14px;
  background: #f8fafc;
  border: 1px solid #eef0f4;
  border-radius: 10px;
  min-width: 0;
}

.model-edit__capability-info {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.model-edit__capability-title {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
}

.model-edit__capability-desc {
  margin-top: 2px;
  font-size: 11px;
  color: #9ca3af;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.model-edit__slider-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.model-edit__slider-form-item {
  margin-bottom: 14px;

  :deep(.n-form-item-blank) {
    min-width: 0;
  }
}

.model-edit__slider-label {
  width: 220px;
  flex-shrink: 0;
  font-size: 14px;
  line-height: 1;
  color: var(--n-label-text-color);
  text-align: left;
  white-space: nowrap;
}

.model-edit__slider {
  flex: 1;
  min-width: 0;
}

.model-edit__slider-input {
  width: 112px;
  flex-shrink: 0;
}

.model-edit__slider-hint {
  flex-shrink: 0;
  font-size: 12px;
  color: #9ca3af;
  white-space: nowrap;
}

.model-edit__footer {
  padding: 14px 24px;
  border-top: 1px solid #eef0f4;
  background: #fff;
}

.w-full {
  width: 100%;
}
</style>

<style scoped lang="scss">
html.dark .model-edit__section {
  background: #18181c;
  border-color: rgba(255, 255, 255, 0.1);
}

html.dark .model-edit__section-head {
  color: #e5e7eb;
  border-bottom-color: rgba(255, 255, 255, 0.08);
}

html.dark .model-edit__capability-item {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.08);
}

html.dark .model-edit__capability-title {
  color: #e5e7eb;
}

html.dark .model-edit__footer {
  border-top-color: rgba(255, 255, 255, 0.1);
  background: #18181c;
}
</style>
