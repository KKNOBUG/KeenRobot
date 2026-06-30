<template>
  <CommonPage :show-header="false">
    <n-card rounded-10 class="mb-16">
      <div flex items-center>
        <img :src="userStore.avatar" h-80 w-80 rounded-full alt="avatar" />
        <div ml-20>
          <p text-20 font-semibold>{{ userStore.username }}</p>
          <p mt-8 op-60>{{ userStore.email }}</p>
        </div>
      </div>
    </n-card>

    <n-card title="我的记忆" rounded-10>
      <template #header-extra>
        <n-button size="small" type="primary" @click="openCreate">新增记忆</n-button>
      </template>
      <n-spin :show="loading">
        <n-empty v-if="!memories.length" description="暂无记忆。可在聊天中说「记住：…」保存偏好或信息。" />
        <n-list v-else bordered>
          <n-list-item v-for="item in memories" :key="item.id">
            <div flex items-start justify-between gap-12 w-full>
              <div min-w-0 flex-1>
                <n-tag v-if="item.memory_key" size="small" type="info" class="mb-8">
                  {{ item.memory_key }}
                </n-tag>
                <p whitespace-pre-wrap break-words>{{ item.content }}</p>
                <p mt-8 text-12 op-50>{{ formatTime(item.updated_time || item.created_time) }}</p>
              </div>
              <n-popconfirm @positive-click="removeMemory(item.id)">
                <template #trigger>
                  <n-button size="small" quaternary type="error">删除</n-button>
                </template>
                确定删除这条记忆吗？
              </n-popconfirm>
            </div>
          </n-list-item>
        </n-list>
      </n-spin>
    </n-card>

    <n-modal v-model:show="showCreate" preset="dialog" title="新增记忆" positive-text="保存" @positive-click="submitCreate">
      <n-input
        v-model:value="createForm.content"
        type="textarea"
        :rows="4"
        maxlength="200"
        show-count
        placeholder="例如：回答请尽量简洁；或：我在研发部门"
      />
      <n-input
        v-model:value="createForm.memory_key"
        class="mt-12"
        maxlength="64"
        placeholder="可选分类，如 preference / department"
      />
    </n-modal>
  </CommonPage>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '@/api'
import CommonPage from '@/components/page/CommonPage.vue'
import { useUserStore } from '@/store'
import { formatDateTime } from '@/utils'

const userStore = useUserStore()
const loading = ref(false)
const memories = ref([])
const showCreate = ref(false)
const createForm = ref({ content: '', memory_key: '' })

function formatTime(value) {
  return value ? formatDateTime(value) : ''
}

async function loadMemories() {
  loading.value = true
  try {
    const data = await api.fetchUserMemories()
    memories.value = Array.isArray(data) ? data : []
  } catch (e) {
    window.$message?.error(e?.message || '加载记忆失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  createForm.value = { content: '', memory_key: '' }
  showCreate.value = true
}

async function submitCreate() {
  const content = (createForm.value.content || '').trim()
  if (!content) {
    window.$message?.warning('请输入记忆内容')
    return false
  }
  try {
    await api.createUserMemory({
      content,
      memory_key: createForm.value.memory_key?.trim() || undefined,
    })
    window.$message?.success('已保存')
    showCreate.value = false
    await loadMemories()
  } catch (e) {
    window.$message?.error(e?.message || '保存失败')
    return false
  }
  return true
}

async function removeMemory(id) {
  try {
    await api.deleteUserMemory(id)
    window.$message?.success('已删除')
    memories.value = memories.value.filter((item) => item.id !== id)
  } catch (e) {
    window.$message?.error(e?.message || '删除失败')
  }
}

onMounted(loadMemories)
</script>
