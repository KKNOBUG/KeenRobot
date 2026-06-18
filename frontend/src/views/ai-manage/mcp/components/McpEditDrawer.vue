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
import { renderIcon } from '@/utils'
import {
  CATEGORY_OPTIONS,
  TRANSPORT_OPTIONS,
  emptyForm,
  formToPayload,
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

const title = computed(() => (props.mode === 'create' ? '新建 MCP 服务' : '编辑 MCP 服务'))
const isStdio = computed(() => form.value.transport === 'stdio')
const toolCountText = computed(() => `${(form.value.tools || []).length} 个工具`)

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

async function handleRefreshTools() {
  if (!form.value.id) {
    window.$message?.warning('请先保存服务后再刷新工具列表')
    return
  }
  refreshing.value = true
  try {
    const res = await api.refreshMcpTools(form.value.id)
    form.value.tools = res?.tools || []
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
  <NDrawer :show="show" :width="1080" placement="right" @update:show="emit('update:show', $event)">
    <NDrawerContent :title="title" closable :native-scrollbar="false" body-content-style="padding: 0;">
      <div class="mcp-edit">
        <div class="mcp-edit__main">
          <section class="mcp-edit__panel">
            <div class="mcp-edit__panel-title">基础配置</div>
            <NForm
              ref="formRef"
              label-placement="top"
              :model="form"
              require-mark-placement="right-hanging"
            >
              <NFormItem
                label="服务名称"
                path="name"
                :rule="{ required: true, message: '请输入服务名称', trigger: ['input', 'blur'] }"
              >
                <NInput v-model:value="form.name" placeholder="如：高德地图-MCP" />
              </NFormItem>

              <NFormItem label="连接类型" path="transport">
                <NSelect v-model:value="form.transport" :options="TRANSPORT_OPTIONS" />
              </NFormItem>

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

              <NFormItem label="图标" path="icon">
                <NInput v-model:value="form.icon" placeholder="支持 emoji 或单字，如 🎉" />
              </NFormItem>

              <NFormItem label="分类" path="category">
                <NSelect v-model:value="form.category" :options="CATEGORY_OPTIONS" />
              </NFormItem>

              <NFormItem label="描述" path="description">
                <NInput
                  v-model:value="form.description"
                  type="textarea"
                  :rows="3"
                  placeholder="MCP 服务用途描述（可选）"
                />
              </NFormItem>

              <NFormItem v-if="isStdio" label="STDIO 配置" path="config_text" :rule="{ validator: validateStdioConfig }">
                <NInput
                  v-model:value="form.config_text"
                  type="textarea"
                  :rows="6"
                  placeholder='{"command":"npx","args":["-y","@modelcontextprotocol/server-filesystem","/tmp"]}'
                />
              </NFormItem>

              <NFormItem label="状态" path="is_enabled">
                <div class="mcp-edit__switch">
                  <span>禁用</span>
                  <NSwitch v-model:value="form.is_enabled" />
                  <span>启用</span>
                </div>
              </NFormItem>
            </NForm>
          </section>

          <section class="mcp-edit__panel mcp-edit__panel--tools">
            <div class="mcp-edit__tools-head">
              <div>
                <div class="mcp-edit__panel-title">工具列表</div>
                <div class="mcp-edit__tools-sub">{{ toolCountText }}</div>
              </div>
              <NButton :loading="refreshing" @click="handleRefreshTools">
                <template #icon>
                  <component :is="renderIcon('material-symbols:refresh', { size: 16 })" />
                </template>
                刷新
              </NButton>
            </div>

            <NSpin :show="refreshing">
              <div v-if="form.tools?.length" class="mcp-edit__tool-list cus-scroll">
                <div v-for="tool in form.tools" :key="tool.name" class="mcp-edit__tool-item">
                  <div class="mcp-edit__tool-icon">M</div>
                  <div class="mcp-edit__tool-body">
                    <div class="mcp-edit__tool-top">
                      <span class="mcp-edit__tool-name">{{ tool.name }}</span>
                      <span class="mcp-edit__tool-params">{{ tool.param_count || 0 }} 个参数</span>
                    </div>
                    <div class="mcp-edit__tool-desc">{{ tool.description || '暂无描述' }}</div>
                  </div>
                  <span class="i-material-symbols:chevron-right text-18 mcp-edit__tool-arrow" />
                </div>
              </div>
              <div v-else class="mcp-edit__tool-empty">
                <div class="mcp-edit__tool-empty-title">暂无工具</div>
                <div class="mcp-edit__tool-empty-desc">
                  {{ form.id ? '点击右上角刷新，从远程 MCP 服务获取工具列表' : '保存服务后可刷新工具列表' }}
                </div>
              </div>
            </NSpin>
          </section>
        </div>

        <div class="mcp-edit__footer">
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
.mcp-edit {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px);
}

.mcp-edit__main {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(320px, 380px) minmax(0, 1fr);
  gap: 0;
}

.mcp-edit__panel {
  padding: 20px 24px;
  overflow: auto;
}

.mcp-edit__panel--tools {
  border-left: 1px solid #eef0f4;
  background: #fafbfc;
}

.mcp-edit__panel-title {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 16px;
}

.mcp-edit__switch {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #6b7280;
}

.mcp-edit__tools-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.mcp-edit__tools-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #9ca3af;
}

.mcp-edit__tool-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: calc(100vh - 220px);
  padding-right: 4px;
}

.mcp-edit__tool-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #eef0f4;
  border-radius: 12px;
}

.mcp-edit__tool-icon {
  flex: 0 0 36px;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: #eff6ff;
  color: #3b82f6;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}

.mcp-edit__tool-body {
  flex: 1;
  min-width: 0;
}

.mcp-edit__tool-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.mcp-edit__tool-name {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.mcp-edit__tool-params {
  padding: 2px 8px;
  border-radius: 999px;
  background: #eff6ff;
  color: #3b82f6;
  font-size: 12px;
}

.mcp-edit__tool-desc {
  font-size: 13px;
  line-height: 1.5;
  color: #6b7280;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.mcp-edit__tool-arrow {
  color: #cbd5e1;
}

.mcp-edit__tool-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 280px;
  color: #9ca3af;
  text-align: center;
}

.mcp-edit__tool-empty-title {
  font-size: 15px;
  font-weight: 600;
  color: #6b7280;
  margin-bottom: 8px;
}

.mcp-edit__tool-empty-desc {
  max-width: 280px;
  font-size: 13px;
  line-height: 1.6;
}

.mcp-edit__footer {
  padding: 14px 24px;
  border-top: 1px solid #eef0f4;
  background: #fff;
}
</style>
