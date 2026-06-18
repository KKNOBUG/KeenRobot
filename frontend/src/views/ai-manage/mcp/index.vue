<script setup>
import { computed, onMounted, ref } from 'vue'
import { NButton, NEmpty, NInput, NSpin } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import { renderIcon } from '@/utils'
import api from '@/api'

import McpCard from './components/McpCard.vue'
import McpEditDrawer from './components/McpEditDrawer.vue'

defineOptions({ name: 'McpManage' })

const loading = ref(false)
const keyword = ref('')
const mcpList = ref([])

const drawerVisible = ref(false)
const drawerMode = ref('edit')
const currentRecord = ref(null)

const filteredList = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return mcpList.value
  return mcpList.value.filter((item) => {
    const desc = item.description || ''
    const category = item.config?.category || ''
    return (
      item.name?.toLowerCase().includes(kw) ||
      desc.toLowerCase().includes(kw) ||
      category.toLowerCase().includes(kw)
    )
  })
})

async function loadList() {
  loading.value = true
  try {
    mcpList.value = (await api.fetchMcpServers('', true)) || []
  } catch (err) {
    window.$message?.error(err?.message || '加载 MCP 列表失败')
    mcpList.value = []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  drawerMode.value = 'create'
  currentRecord.value = null
  drawerVisible.value = true
}

function openEdit(item) {
  drawerMode.value = 'edit'
  currentRecord.value = item
  drawerVisible.value = true
}

async function handleDelete(item) {
  await window.$dialog?.confirm({
    title: '删除确认',
    type: 'warning',
    content: `确定删除 MCP 服务「${item.name}」吗？`,
    positiveText: '删除',
    negativeText: '取消',
    async onPositiveClick() {
      try {
        await api.deleteMcpServer(item.id)
        window.$message?.success('删除成功')
        await loadList()
      } catch (err) {
        window.$message?.error(err?.message || '删除失败')
      }
    },
  })
}

async function handleSaved() {
  await loadList()
}

onMounted(() => {
  loadList()
})
</script>

<template>
  <CommonPage :show-header="false" :show-footer="false">
    <div class="mcp-page">
      <div class="mcp-page__toolbar">
        <NInput
          v-model:value="keyword"
          clearable
          class="mcp-page__search"
          placeholder="搜索 MCP 服务名称、描述或分类"
        >
          <template #prefix>
            <span class="i-material-symbols:search text-18 text-gray-400" />
          </template>
        </NInput>
        <NButton type="primary" @click="openCreate">
          <template #icon>
            <component :is="renderIcon('material-symbols:add', { size: 18 })" />
          </template>
          新建 MCP
        </NButton>
      </div>

      <NSpin :show="loading">
        <div v-if="filteredList.length" class="mcp-page__grid">
          <McpCard
            v-for="(item, index) in filteredList"
            :key="item.id"
            :item="item"
            :index="index"
            @edit="openEdit"
            @delete="handleDelete"
          />
        </div>
        <NEmpty v-else class="mcp-page__empty" description="暂无 MCP 服务">
          <template #extra>
            <NButton type="primary" @click="openCreate">新建 MCP</NButton>
          </template>
        </NEmpty>
      </NSpin>
    </div>

    <McpEditDrawer
      v-model:show="drawerVisible"
      :mode="drawerMode"
      :record="currentRecord"
      @saved="handleSaved"
    />
  </CommonPage>
</template>

<style scoped lang="scss">
.mcp-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 100%;
  padding: 4px 2px 20px;
}

.mcp-page__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.mcp-page__search {
  max-width: 360px;
}

.mcp-page__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 18px;
}

.mcp-page__empty {
  padding: 80px 0;
}
</style>
