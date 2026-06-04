<script setup>
import { computed, h, onMounted, ref } from 'vue'
import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NPopconfirm,
  NSwitch,
  NTag,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { formatDateTime, renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
import api from '@/api'

defineOptions({ name: 'ModelManage' })

const $table = ref(null)
const queryItems = ref({ name: '' })

const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: false,
  actionMode: 'dropdown',
}

const {
  modalVisible,
  modalAction,
  modalTitle,
  modalLoading,
  handleAdd,
  handleDelete,
  handleEdit,
  handleSave,
  modalForm,
  modalFormRef,
} = useCRUD({
  name: '模型配置',
  initForm: {
    name: '',
    model_name: 'deepseek-chat',
    temperature: 0.7,
    max_tokens: 2048,
    top_p: 0.95,
    is_default: false,
  },
  doCreate: (form) => api.createModelConfig(buildPayload(form)),
  doDelete: (params) => api.deleteModelConfig(params.id),
  doUpdate: (form) => api.updateModelConfig(form.id, buildPayload(form)),
  refresh: () => $table.value?.handleSearch(),
})

function buildPayload(form) {
  return {
    name: form.name,
    model_name: form.model_name,
    temperature: form.temperature,
    max_tokens: form.max_tokens,
    top_p: form.top_p,
    is_default: !!form.is_default,
  }
}

async function fetchModelList(params) {
  const list = await api.fetchModelConfigs()
  const kw = (params.name || '').trim()
  const filtered = kw
    ? list.filter((item) => item.name.includes(kw) || item.model_name.includes(kw))
    : list
  return { data: filtered, total: filtered.length }
}

async function handleSetDefault(row) {
  try {
    await api.setDefaultModelConfig(row.id)
    window.$message?.success('已设为默认配置')
    $table.value?.handleSearch()
  } catch (err) {
    window.$message?.error(err.message || '设置失败')
  }
}

onMounted(() => {
  $table.value?.handleSearch()
})

const columns = computed(() => [
  {
    title: '配置名称',
    key: 'name',
    minWidth: 140,
    ellipsis: { tooltip: true },
  },
  {
    title: '模型名称',
    key: 'model_name',
    minWidth: 140,
    ellipsis: { tooltip: true },
  },
  {
    title: 'Temperature',
    key: 'temperature',
    width: 110,
    align: 'center',
  },
  {
    title: 'Max Tokens',
    key: 'max_tokens',
    width: 110,
    align: 'center',
  },
  {
    title: 'Top P',
    key: 'top_p',
    width: 90,
    align: 'center',
  },
  {
    title: '默认',
    key: 'is_default',
    width: 80,
    align: 'center',
    render(row) {
      return row.is_default
        ? h(NTag, { type: 'success', size: 'small' }, { default: () => '是' })
        : h(NTag, { size: 'small' }, { default: () => '否' })
    },
  },
  {
    title: '创建时间',
    key: 'created_at',
    width: 170,
    align: 'center',
    render(row) {
      return formatDateTime(row.created_at)
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 220,
    align: 'center',
    fixed: 'right',
    render(row) {
      const buttons = [
        h(
          NButton,
          {
            size: 'tiny',
            quaternary: true,
            type: 'info',
            onClick: () => handleEdit(row),
          },
          {
            default: () => '编辑',
            icon: renderIcon('material-symbols:edit-outline', { size: 16 }),
          },
        ),
      ]

      if (!row.is_default) {
        buttons.push(
          h(
            NButton,
            {
              size: 'tiny',
              quaternary: true,
              type: 'primary',
              onClick: () => handleSetDefault(row),
            },
            {
              default: () => '设为默认',
              icon: renderIcon('material-symbols:star-outline', { size: 16 }),
            },
          ),
        )
      }

      buttons.push(
        h(
          NPopconfirm,
          {
            onPositiveClick: () => handleDelete({ id: row.id }),
          },
          {
            trigger: () =>
              h(
                NButton,
                {
                  size: 'tiny',
                  quaternary: true,
                  type: 'error',
                },
                {
                  default: () => '删除',
                  icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
                },
              ),
            default: () => '确定删除该模型配置吗？',
          },
        ),
      )

      return buttons
    },
  },
])
</script>

<template>
  <CommonPage show-footer title="模型管理">
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :query-bar-props="queryBarProps"
      :is-pagination="true"
      :remote="false"
      :scroll-x="1200"
      :columns="columns"
      :get-data="fetchModelList"
      row-key="id"
      @query-bar-create="handleAdd"
    >
      <template #queryBar>
        <QueryBarItem label="配置名称：">
          <NInput
            v-model:value="queryItems.name"
            clearable
            placeholder="请输入配置名称或模型名"
            @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <CrudModal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :loading="modalLoading"
      width="560px"
      @save="handleSave"
    >
      <NForm
        ref="modalFormRef"
        label-placement="left"
        label-align="left"
        :label-width="110"
        :model="modalForm"
        :disabled="modalAction === 'view'"
      >
        <NFormItem
          label="配置名称"
          path="name"
          :rule="{ required: true, message: '请输入配置名称', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="modalForm.name" placeholder="如：默认 DeepSeek" />
        </NFormItem>
        <NFormItem
          label="模型名称"
          path="model_name"
          :rule="{ required: true, message: '请输入模型名称', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="modalForm.model_name" placeholder="如：deepseek-chat" />
        </NFormItem>
        <NFormItem label="Temperature" path="temperature">
          <NInputNumber
            v-model:value="modalForm.temperature"
            :min="0"
            :max="2"
            :step="0.1"
            class="w-full"
          />
        </NFormItem>
        <NFormItem label="Max Tokens" path="max_tokens">
          <NInputNumber
            v-model:value="modalForm.max_tokens"
            :min="1"
            :max="8192"
            :step="256"
            class="w-full"
          />
        </NFormItem>
        <NFormItem label="Top P" path="top_p">
          <NInputNumber
            v-model:value="modalForm.top_p"
            :min="0"
            :max="1"
            :step="0.05"
            class="w-full"
          />
        </NFormItem>
        <NFormItem label="设为默认" path="is_default">
          <NSwitch v-model:value="modalForm.is_default" />
        </NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>

<style scoped>
.w-full {
  width: 100%;
}
</style>
