<script setup>
import { computed, onMounted, ref } from 'vue'
import { NAlert, NButton, NEmpty, NInput, NSpin } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import { renderIcon } from '@/utils'
import api from '@/api'

import KnowledgeBaseCard from './components/KnowledgeBaseCard.vue'
import KnowledgeBaseEditDrawer from './components/KnowledgeBaseEditDrawer.vue'

defineOptions({ name: 'KnowledgeBase' })

const loading = ref(false)
const keyword = ref('')
const kbList = ref([])

const drawerVisible = ref(false)
const drawerMode = ref('edit')
const currentRecord = ref(null)

const filteredList = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return kbList.value
  return kbList.value.filter((item) => {
    const desc = item.description || ''
    const embedding = item.default_embedding_model || ''
    return (
      item.knowledge_name?.toLowerCase().includes(kw) ||
      desc.toLowerCase().includes(kw) ||
      embedding.toLowerCase().includes(kw)
    )
  })
})

async function loadList() {
  loading.value = true
  try {
    kbList.value = (await api.fetchKnowledgeBases()) || []
  } catch (err) {
    window.$message?.error(err?.message || '加载知识库列表失败')
    kbList.value = []
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
    content: `确定删除知识库「${item.knowledge_name}」吗？关联文档将一并删除。`,
    positiveText: '删除',
    negativeText: '取消',
    async onPositiveClick() {
      try {
        await api.deleteKnowledgeBase(item.id)
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
    <div class="kb-page">
      <NAlert type="info" :bordered="false" class="kb-page__tip">
        管理个人知识库与文档。上传 PDF 后将自动分块并向量化，可在智能聊天中关联检索。
      </NAlert>

      <div class="kb-page__toolbar">
        <NInput
            v-model:value="keyword"
            clearable
            class="kb-page__search"
            placeholder="搜索知识库名称、描述或向量模型"
        >
          <template #prefix>
            <span class="i-material-symbols:search text-18 text-gray-400" />
          </template>
        </NInput>
        <NButton type="primary" @click="openCreate">
          <template #icon>
            <component :is="renderIcon('material-symbols:add', { size: 18 })" />
          </template>
          新建知识库
        </NButton>
      </div>

      <NSpin :show="loading">
        <div v-if="filteredList.length" class="kb-page__grid">
          <KnowledgeBaseCard
              v-for="(item, index) in filteredList"
              :key="item.id"
              :item="item"
              :index="index"
              @edit="openEdit"
              @delete="handleDelete"
          />
        </div>
        <NEmpty v-else class="kb-page__empty" description="暂无知识库">
          <template #extra>
            <NButton type="primary" @click="openCreate">新建知识库</NButton>
          </template>
        </NEmpty>
      </NSpin>
    </div>

    <KnowledgeBaseEditDrawer
        v-model:show="drawerVisible"
        :mode="drawerMode"
        :record="currentRecord"
        @saved="handleSaved"
    />
  </CommonPage>
</template>

<style scoped lang="scss">
.kb-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
  padding: 4px 2px 20px;
}

.kb-page__tip {
  margin-bottom: 0;
}

.kb-page__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.kb-page__search {
  max-width: 360px;
}

.kb-page__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 18px;
}

.kb-page__empty {
  padding: 80px 0;
}
</style>
