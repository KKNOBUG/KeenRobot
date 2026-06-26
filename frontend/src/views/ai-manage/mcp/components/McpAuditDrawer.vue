<script setup>
import { ref, watch } from 'vue'
import { NButton, NDataTable, NDrawer, NDrawerContent, NInput, NSelect, NSpin } from 'naive-ui'

import api from '@/api'

const props = defineProps({
  show: { type: Boolean, default: false },
  defaultMcpServerId: { type: String, default: '' },
})

const emit = defineEmits(['update:show'])

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const mcpServerId = ref('')
const toolName = ref('')
const status = ref(null)

const statusOptions = [
  { label: '全部状态', value: null },
  { label: '成功', value: 'done' },
  { label: '失败', value: 'error' },
  { label: '已取消', value: 'cancelled' },
]

const columns = [
  { title: '时间', key: 'created_time', width: 170, ellipsis: { tooltip: true } },
  { title: '服务', key: 'server_name', width: 120, ellipsis: { tooltip: true } },
  { title: '工具', key: 'tool_name', width: 140, ellipsis: { tooltip: true } },
  { title: '类型', key: 'event_type', width: 90 },
  { title: '状态', key: 'status', width: 80 },
  { title: '耗时(ms)', key: 'duration_ms', width: 90 },
  { title: '结果/错误', key: 'result_preview', ellipsis: { tooltip: true } },
]

async function loadLogs() {
  loading.value = true
  try {
    const data = await api.searchMcpAuditLogs({
      page: page.value,
      page_size: pageSize.value,
      mcp_server_id: mcpServerId.value || undefined,
      tool_name: toolName.value || undefined,
      status: status.value || undefined,
    })
    rows.value = data?.items || data || []
    total.value = data?.total ?? rows.value.length
  } catch (err) {
    window.$message?.error(err?.message || '加载审计记录失败')
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function close() {
  emit('update:show', false)
}

watch(
  () => props.show,
  (visible) => {
    if (!visible) return
    mcpServerId.value = props.defaultMcpServerId || ''
    page.value = 1
    loadLogs()
  },
)
</script>

<template>
  <NDrawer :show="show" width="920" @update:show="(v) => emit('update:show', v)">
    <NDrawerContent title="MCP 调用审计" closable @close="close">
      <div class="mcp-audit-toolbar">
        <NInput v-model:value="mcpServerId" clearable placeholder="MCP 服务 ID" style="width: 200px" />
        <NInput v-model:value="toolName" clearable placeholder="工具名" style="width: 160px" />
        <NSelect v-model:value="status" :options="statusOptions" style="width: 120px" />
        <NButton type="primary" @click="loadLogs">查询</NButton>
      </div>
      <NSpin :show="loading">
        <NDataTable
            :columns="columns"
            :data="rows"
            :pagination="{ page, pageSize, itemCount: total, onUpdatePage: (p) => { page = p; loadLogs() } }"
            size="small"
            :scroll-x="900"
        />
      </NSpin>
    </NDrawerContent>
  </NDrawer>
</template>

<style scoped>
.mcp-audit-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
</style>
