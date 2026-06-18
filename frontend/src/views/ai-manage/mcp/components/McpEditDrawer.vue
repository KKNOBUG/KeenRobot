<script setup>
import { computed, ref, watch } from 'vue'
import {
  NButton,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NSpace,
  NSwitch,
  NSpin,
} from 'naive-ui'

import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'
import { renderIcon } from '@/utils'
import {
  CATEGORY_OPTIONS,
  TRANSPORT_OPTIONS,
  emptyForm,
  formToPayload,
  getIconStyle,
  getToolParams,
  hasToolParams,
  rowToForm,
} from '../mcpUtils.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  mode: { type: String, default: 'edit' },
  record: { type: Object, default: null },
})

const emit = defineEmits(['update:show', 'saved'])

const formRef = ref(null)
const saving = ref(false)
const refreshing = ref(false)
const form = ref(emptyForm())
const expandedTools = ref(new Set())

const title = computed(() => (props.mode === 'create' ? '新建 MCP 服务' : '编辑 MCP 服务'))
const isStdio = computed(() => form.value.transport === 'stdio')
const toolCountText = computed(() => `${(form.value.tools || []).length} 个工具`)

watch(
  () => [props.show, props.record, props.mode],
  () => {
    if (!props.show) {
      expandedTools.value = new Set()
      return
    }
    expandedTools.value = new Set()
    form.value = props.mode === 'create' ? emptyForm() : rowToForm(props.record || {})
  },
  { immediate: true },
)

function isToolExpanded(name) {
  return expandedTools.value.has(name)
}

function toggleTool(name) {
  const next = new Set(expandedTools.value)
  if (next.has(name)) {
    next.delete(name)
  } else {
    next.add(name)
  }
  expandedTools.value = next
}

function close() {
  emit('update:show', false)
}

function toolIconStyle(index) {
  return getIconStyle(form.value.name, index)
}

async function handleRefreshTools() {
  if (!form.value.id) {
    window.$message?.warning('请先保存服务后再刷新工具列表')
    return
  }
  refreshing.value = true
  try {
    const res = await api.refreshMcpTools(form.value.id)
    form.value.tools = res?.tools || []
    expandedTools.value = new Set()
    window.$message?.success(`已刷新 ${form.value.tools.length} 个工具`)
  } catch (err) {
    window.$message?.error(err?.message || '刷新工具列表失败')
  } finally {
    refreshing.value = false
  }
}

async function handleSave() {
  await formRef.value?.validate?.()
  saving.value = true
  try {
    const payload = formToPayload(form.value)
    if (props.mode === 'create') {
      const created = await api.createMcpServer(payload)
      window.$message?.success('创建成功')
      emit('saved', created)
      close()
      return
    }
    const updated = await api.updateMcpServer(form.value.id, payload)
    window.$message?.success('保存成功')
    emit('saved', updated)
    close()
  } catch (err) {
    if (err?.message) window.$message?.error(err.message)
  } finally {
    saving.value = false
  }
}

function validateStdioConfig(_rule, value) {
  if (!isStdio.value) return true
  if (!value?.trim()) return new Error('请输入 STDIO 连接配置')
  try {
    JSON.parse(value)
    return true
  } catch {
    return new Error('STDIO 配置须为合法 JSON')
  }
}
</script>

<template>
  <NDrawer :show="show" :width="800" placement="right" @update:show="emit('update:show', $event)">
    <NDrawerContent :title="title" closable :native-scrollbar="false" body-content-style="padding: 0;">
      <div class="mcp-edit">
        <div class="mcp-edit__body cus-scroll">
          <NForm
            ref="formRef"
            label-placement="top"
            :model="form"
            require-mark-placement="right-hanging"
          >
            <section class="mcp-edit__section">
              <div class="mcp-edit__section-head mcp-edit__section-head--basic">
                <TheIcon icon="material-symbols:hub-outline" :size="18" />
                <span>基本配置</span>
              </div>
              <div class="mcp-edit__section-body">
                <div class="mcp-edit__row">
                  <NFormItem label="服务图标" path="icon" class="mcp-edit__col">
                    <NInput v-model:value="form.icon" placeholder="支持 emoji 或单字，如 🎉" />
                  </NFormItem>
                  <NFormItem
                      label="服务名称"
                      path="name"
                      class="mcp-edit__col"
                      :rule="{ required: true, message: '请输入服务名称', trigger: ['input', 'blur'] }"
                  >
                    <NInput v-model:value="form.name" placeholder="如：高德地图-MCP" />
                  </NFormItem>
                </div>

                <div class="mcp-edit__row">
                  <NFormItem label="服务类型" path="transport" class="mcp-edit__col">
                    <NSelect v-model:value="form.transport" :options="TRANSPORT_OPTIONS" />
                  </NFormItem>
                  <NFormItem label="服务分类" path="category" class="mcp-edit__col">
                    <NSelect v-model:value="form.category" :options="CATEGORY_OPTIONS" />
                  </NFormItem>
                </div>

                <div class="mcp-edit__switch-row">
                  <div class="mcp-edit__switch-info">
                    <TheIcon icon="material-symbols:power-settings-new" :size="18" color="#22c55e" />
                    <div>
                      <div class="mcp-edit__switch-title">启用服务</div>
                      <div class="mcp-edit__switch-desc">禁用后聊天中不可选用</div>
                    </div>
                  </div>
                  <NSwitch v-model:value="form.is_enabled" />
                </div>
              </div>
            </section>

            <section class="mcp-edit__section">
              <div class="mcp-edit__section-head mcp-edit__section-head--connection">
                <TheIcon icon="material-symbols:link" :size="18" />
                <span>连接配置</span>
              </div>
              <div class="mcp-edit__section-body">
                <NFormItem
                    v-if="!isStdio"
                    label="服务地址"
                    path="service_url"
                    :rule="{ required: true, message: '请输入服务地址', trigger: ['input', 'blur'] }"
                >
                  <NInput
                      v-model:value="form.service_url"
                      placeholder="https://mcp.example.com/..."
                  />
                </NFormItem>

                <NFormItem
                    v-if="isStdio"
                    label="STDIO 配置"
                    path="config_text"
                    :rule="{ validator: validateStdioConfig }"
                >
                  <NInput
                      v-model:value="form.config_text"
                      type="textarea"
                      :rows="6"
                      placeholder='{"command":"npx","args":["-y","@modelcontextprotocol/server-filesystem","/tmp"]}'
                  />
                </NFormItem>
              </div>
            </section>

            <section class="mcp-edit__section">
              <div class="mcp-edit__section-head mcp-edit__section-head--other">
                <TheIcon icon="material-symbols:more-horiz" :size="18" />
                <span>其他配置</span>
              </div>
              <div class="mcp-edit__section-body">
                <NFormItem label="服务描述" path="description">
                  <NInput
                      v-model:value="form.description"
                      type="textarea"
                      :rows="4"
                      placeholder="MCP 服务用途描述（可选）"
                  />
                </NFormItem>
              </div>
            </section>
          </NForm>

          <section class="mcp-edit__section mcp-edit__section--tools">
            <div class="mcp-edit__tools-head">
              <div>
                <div class="mcp-edit__section-head mcp-edit__section-head--tools">
                  <TheIcon icon="material-symbols:build-outline" :size="18" />
                  <span>工具列表</span>
                </div>
                <div class="mcp-edit__tools-sub">{{ toolCountText }}</div>
              </div>
              <NButton secondary :loading="refreshing" :disabled="!form.id" @click="handleRefreshTools">
                <template #icon>
                  <component :is="renderIcon('material-symbols:refresh', { size: 16 })" />
                </template>
                刷新
              </NButton>
            </div>

            <NSpin :show="refreshing" class="mcp-edit__tools-spin">
              <div v-if="form.tools?.length" class="mcp-edit__tool-list">
                <div
                    v-for="(tool, index) in form.tools"
                    :key="tool.name"
                    class="mcp-edit__tool-item"
                    :class="{ 'is-expanded': isToolExpanded(tool.name) }"
                >
                  <button
                      type="button"
                      class="mcp-edit__tool-header"
                      @click="toggleTool(tool.name)"
                  >
                    <div
                        class="mcp-edit__tool-icon"
                        :style="{
                          background: toolIconStyle(index).bg,
                          color: toolIconStyle(index).color,
                        }"
                    >
                      {{ (tool.name || 'M').slice(0, 1).toUpperCase() }}
                    </div>
                    <div class="mcp-edit__tool-body">
                      <div class="mcp-edit__tool-top">
                        <span class="mcp-edit__tool-name">{{ tool.name }}</span>
                        <span class="mcp-edit__tool-params">{{ tool.param_count || 0 }} 个参数</span>
                      </div>
                      <div
                          class="mcp-edit__tool-desc"
                          :class="{ 'is-expanded': isToolExpanded(tool.name) }"
                      >
                        {{ tool.description || '暂无描述' }}
                      </div>
                    </div>
                    <TheIcon
                        :icon="isToolExpanded(tool.name)
                          ? 'material-symbols:keyboard-arrow-down'
                          : 'material-symbols:keyboard-arrow-right'"
                        :size="18"
                        class="mcp-edit__tool-arrow"
                    />
                  </button>

                  <div
                      v-if="isToolExpanded(tool.name)"
                      class="mcp-edit__tool-detail"
                  >
                    <template v-if="hasToolParams(tool)">
                      <div
                          v-for="param in getToolParams(tool)"
                          :key="param.name"
                          class="mcp-edit__param-row"
                      >
                        <div class="mcp-edit__param-head">
                          <span class="mcp-edit__param-name">{{ param.name }}</span>
                          <span class="mcp-edit__param-type">{{ param.type }}</span>
                          <span v-if="param.required" class="mcp-edit__param-required">必填</span>
                        </div>
                        <div v-if="param.description" class="mcp-edit__param-desc">
                          {{ param.description }}
                        </div>
                      </div>
                    </template>
                    <div v-else class="mcp-edit__param-empty">该工具无输入参数</div>
                  </div>
                </div>
              </div>
              <div v-else-if="form.id" class="mcp-edit__tool-empty">
                <div class="mcp-edit__tool-empty-title">暂无工具</div>
                <div class="mcp-edit__tool-empty-desc">点击右上角刷新，从远程 MCP 服务获取工具列表</div>
              </div>
              <div v-else class="mcp-edit__tool-empty">
                <TheIcon icon="material-symbols:build-circle-outline" :size="28" color="#9ca3af" />
                <div class="mcp-edit__tool-empty-title">工具列表</div>
                <div class="mcp-edit__tool-empty-desc">保存服务后可刷新工具列表</div>
              </div>
            </NSpin>
          </section>
        </div>

        <div class="mcp-edit__footer">
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
.mcp-edit {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px);
}

.mcp-edit__body {
  flex: 1;
  min-height: 0;
  padding: 20px 24px;
  overflow-y: auto;
}

.mcp-edit__section {
  margin-bottom: 16px;
  background: #fff;
  border: 1px solid #eef0f4;
  border-radius: 12px;
  overflow: hidden;
}

.mcp-edit__section-head {
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

  &--other :deep(.n-icon) {
    color: #6b7280;
  }

  &--tools :deep(.n-icon) {
    color: #f59e0b;
    border-bottom: none;
  }
}

.mcp-edit__section-body {
  padding: 16px 18px 6px;
}

.mcp-edit__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.mcp-edit__col {
  min-width: 0;
}

.mcp-edit__switch-row {
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

.mcp-edit__switch-info {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.mcp-edit__switch-title {
  font-size: 14px;
  font-weight: 500;
  color: #1f2937;
}

.mcp-edit__switch-desc {
  margin-top: 2px;
  font-size: 12px;
  color: #9ca3af;
}

.mcp-edit__section--tools {
  padding-bottom: 12px;
}

.mcp-edit__tools-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px 0;
}

.mcp-edit__tools-sub {
  margin-top: 4px;
  padding: 0 18px 12px;
  font-size: 12px;
  color: #9ca3af;
}

.mcp-edit__tools-spin {
  padding: 0 18px 6px;
}

.mcp-edit__tool-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 480px;
  overflow-y: auto;
  padding-right: 4px;
}

.mcp-edit__tool-item {
  flex-shrink: 0;
  background: #f8fafc;
  border: 1px solid #eef0f4;
  border-radius: 10px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;

  &:hover,
  &.is-expanded {
    border-color: #dbe0e8;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
  }
}

.mcp-edit__tool-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
}

.mcp-edit__tool-icon {
  flex: 0 0 36px;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  line-height: 1;
}

.mcp-edit__tool-body {
  flex: 1;
  min-width: 0;
}

.mcp-edit__tool-top {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 4px;
}

.mcp-edit__tool-name {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  word-break: break-word;
}

.mcp-edit__tool-params {
  padding: 2px 8px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #6b7280;
  font-size: 12px;
}

.mcp-edit__tool-desc {
  font-size: 13px;
  line-height: 1.5;
  color: #9ca3af;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;

  &.is-expanded {
    display: block;
    -webkit-line-clamp: unset;
    line-clamp: unset;
    overflow: visible;
    white-space: normal;
  }
}

.mcp-edit__tool-arrow {
  flex-shrink: 0;
  color: #cbd5e1;

  :deep(.n-icon) {
    color: inherit;
  }
}

.mcp-edit__tool-detail {
  margin: 0 14px 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #eef0f4;
}

.mcp-edit__param-row + .mcp-edit__param-row {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #eef0f4;
}

.mcp-edit__param-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 4px;
}

.mcp-edit__param-name {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.mcp-edit__param-type {
  padding: 1px 6px;
  border-radius: 4px;
  background: #f3f4f6;
  color: #6b7280;
  font-size: 11px;
}

.mcp-edit__param-required {
  padding: 1px 6px;
  border-radius: 4px;
  background: #fef2f2;
  color: #dc2626;
  font-size: 11px;
}

.mcp-edit__param-desc {
  font-size: 12px;
  line-height: 1.6;
  color: #9ca3af;
  word-break: break-word;
  white-space: normal;
}

.mcp-edit__param-empty {
  font-size: 12px;
  color: #9ca3af;
  padding: 4px 0;
}

.mcp-edit__tool-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 180px;
  padding: 24px 18px;
  color: #9ca3af;
  text-align: center;
}

.mcp-edit__tool-empty-title {
  font-size: 15px;
  font-weight: 600;
  color: #6b7280;
}

.mcp-edit__tool-empty-desc {
  max-width: 320px;
  font-size: 13px;
  line-height: 1.6;
}

.mcp-edit__footer {
  padding: 14px 24px;
  border-top: 1px solid #eef0f4;
  background: #fff;
}
</style>

<style scoped lang="scss">
html.dark .mcp-edit__section {
  background: #18181c;
  border-color: rgba(255, 255, 255, 0.1);
}

html.dark .mcp-edit__section-head {
  color: #e5e7eb;
  border-bottom-color: rgba(255, 255, 255, 0.08);
}

html.dark .mcp-edit__switch-row,
html.dark .mcp-edit__tool-item {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.08);
}

html.dark .mcp-edit__switch-title,
html.dark .mcp-edit__tool-name {
  color: #e5e7eb;
}

html.dark .mcp-edit__tool-detail {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.08);
}

html.dark .mcp-edit__param-row + .mcp-edit__param-row {
  border-top-color: rgba(255, 255, 255, 0.08);
}

html.dark .mcp-edit__param-name {
  color: #e5e7eb;
}

html.dark .mcp-edit__param-type {
  background: rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
}

html.dark .mcp-edit__param-required {
  background: rgba(220, 38, 38, 0.16);
  color: #fca5a5;
}

html.dark .mcp-edit__param-desc,
html.dark .mcp-edit__param-empty,
html.dark .mcp-edit__tools-sub {
  color: #9ca3af;
}

html.dark .mcp-edit__tool-params {
  background: rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
}

html.dark .mcp-edit__tool-desc {
  color: #9ca3af;
}

html.dark .mcp-edit__tool-arrow {
  color: #94a3b8;
}

html.dark .mcp-edit__tool-empty-title {
  color: #cbd5e1;
}

html.dark .mcp-edit__tool-item:hover,
html.dark .mcp-edit__tool-item.is-expanded {
  border-color: rgba(255, 255, 255, 0.16);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.24);
}

html.dark .mcp-edit__footer {
  border-top-color: rgba(255, 255, 255, 0.1);
  background: #18181c;
}
</style>
