<script setup>
import { computed, onMounted, ref } from 'vue'
import { NAlert, NButton, NEmpty, NInput, NSpin } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import { renderIcon } from '@/utils'
import api from '@/api'

import ModelCard from './components/ModelCard.vue'
import ModelEditDrawer from './components/ModelEditDrawer.vue'

defineOptions({ name: 'ModelManage' })

const loading = ref(false)
const keyword = ref('')
const modelList = ref([])

const drawerVisible = ref(false)
const drawerMode = ref('edit')
const currentRecord = ref(null)

const filteredList = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return modelList.value
  return modelList.value.filter((item) => {
    const desc = item.config_desc || ''
    return (
      item.config_name?.toLowerCase().includes(kw) ||
      item.llm_model_name?.toLowerCase().includes(kw) ||
      item.model_provider?.toLowerCase().includes(kw) ||
      desc.toLowerCase().includes(kw)
    )
  })
})

async function loadList() {
  loading.value = true
  try {
    modelList.value = (await api.fetchModelConfigs()) || []
  } catch (err) {
    window.$message?.error(err?.message || '加载模型列表失败')
    modelList.value = []
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
    content: `确定删除模型配置「${item.config_name}」吗？`,
    positiveText: '删除',
    negativeText: '取消',
    async onPositiveClick() {
      try {
        await api.deleteModelConfig(item.id)
        window.$message?.success('删除成功')
        await loadList()
      } catch (err) {
        window.$message?.error(err?.message || '删除失败')
      }
    },
  })
}

async function handleSetDefault(item) {
  try {
    await api.setDefaultModelConfig(item.id)
    window.$message?.success('已设为默认配置')
    await loadList()
  } catch (err) {
    window.$message?.error(err?.message || '设置失败')
  }
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
    <div class="model-page">
      <NAlert type="info" :bordered="false" class="model-page__tip">
        此处管理当前登录用户自己的模型配置。未创建配置时，聊天将使用服务端 .env 中的 LLM 连接兜底。
      </NAlert>

      <div class="model-page__toolbar">
        <NInput
            v-model:value="keyword"
            clearable
            class="model-page__search"
            placeholder="搜索配置名称、模型标识或供应商"
        >
          <template #prefix>
            <span class="i-material-symbols:search text-18 text-gray-400" />
          </template>
        </NInput>
        <NButton type="primary" @click="openCreate">
          <template #icon>
            <component :is="renderIcon('material-symbols:add', { size: 18 })" />
          </template>
          新建模型
        </NButton>
      </div>

      <NSpin :show="loading">
        <div v-if="filteredList.length" class="model-page__grid">
          <ModelCard
              v-for="(item, index) in filteredList"
              :key="item.id"
              :item="item"
              :index="index"
              @edit="openEdit"
              @delete="handleDelete"
              @set-default="handleSetDefault"
          />
        </div>
        <NEmpty v-else class="model-page__empty" description="暂无模型配置">
          <template #extra>
            <NButton type="primary" @click="openCreate">新建模型</NButton>
          </template>
        </NEmpty>
      </NSpin>
    </div>

    <ModelEditDrawer
        v-model:show="drawerVisible"
        :mode="drawerMode"
        :record="currentRecord"
        @saved="handleSaved"
    />
  </CommonPage>
</template>

<style scoped lang="scss">
.model-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
  padding: 4px 2px 20px;
}

.model-page__tip {
  margin-bottom: 0;
}

.model-page__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.model-page__search {
  max-width: 360px;
}

.model-page__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 18px;
}

.model-page__empty {
  padding: 80px 0;
}
</style>
