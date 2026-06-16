<script setup>
import { computed, h, onMounted, ref } from 'vue'
import {
  NAlert,
  NButton,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NPopconfirm,
  NSelect,
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

const providerOptions = [
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'OpenAI', value: 'openai' },
  { label: '智谱', value: 'zhipu' },
  { label: '通义千问', value: 'qwen' },
  { label: '自定义', value: 'custom' },
]

const $table = ref(null)
const queryItems = ref({ config_name: '' })

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
    config_name: '',
    config_desc: '',
    model_provider: 'custom',
    llm_model_name: 'deepseek-chat',
    model_thinking: false,
    llm_base_url: '',
    llm_api_key: '',
    temperature: 0.7,
    max_tokens: 4096,
    top_p: 0.95,
    system_prompt: '',
    top_k: 5,
    score_threshold: 0,
    max_history_rounds: 10,
    is_default: false,
  },
  doCreate: (form) => api.createModelConfig(buildPayload(form)),
  doDelete: (params) => api.deleteModelConfig(params.id),
  doUpdate: (form) => api.updateModelConfig(form.id, buildPayload(form, true)),
  refresh: () => $table.value?.handleSearch(),
})

function buildPayload(form, isUpdate = false) {
  const payload = {
    config_name: form.config_name,
    config_desc: form.config_desc || null,
    model_provider: form.model_provider || 'custom',
    llm_model_name: form.llm_model_name,
    model_thinking: !!form.model_thinking,
    llm_base_url: form.llm_base_url?.trim() || null,
    temperature: form.temperature,
    max_tokens: form.max_tokens,
    top_p: form.top_p,
    system_prompt: form.system_prompt || null,
    top_k: form.top_k,
    score_threshold: form.score_threshold,
    max_history_rounds: form.max_history_rounds,
    is_default: !!form.is_default,
  }
  const apiKey = form.llm_api_key?.trim()
  if (apiKey && !apiKey.includes('***')) {
    payload.llm_api_key = apiKey
  } else if (!isUpdate && apiKey) {
    payload.llm_api_key = apiKey
  }
  return payload
}

function onEditRow(row) {
  handleEdit({
    ...row,
    llm_api_key: row.llm_api_key_masked || '',
  })
}

async function fetchModelList(params) {
  const list = await api.fetchModelConfigs()
  const kw = (params.config_name || '').trim()
  const filtered = kw
      ? list.filter(
          (item) =>
              item.config_name.includes(kw) ||
              item.llm_model_name.includes(kw),
      )
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
    key: 'config_name',
    minWidth: 140,
    ellipsis: { tooltip: true },
  },
  {
    title: '模型',
    key: 'llm_model_name',
    minWidth: 140,
    ellipsis: { tooltip: true },
  },
  {
    title: '厂商',
    key: 'model_provider',
    width: 100,
    align: 'center',
  },
  {
    title: '深度思考',
    key: 'model_thinking',
    width: 90,
    align: 'center',
    render(row) {
      return row.model_thinking
          ? h(NTag, { type: 'info', size: 'small' }, { default: () => '是' })
          : h(NTag, { size: 'small' }, { default: () => '否' })
    },
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
    title: 'Top K',
    key: 'top_k',
    width: 80,
    align: 'center',
  },
  {
    title: '历史轮数',
    key: 'max_history_rounds',
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
    key: 'created_time',
    width: 170,
    align: 'center',
    render(row) {
      return formatDateTime(row.created_time)
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
              onClick: () => onEditRow(row),
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
    <NAlert type="info" :bordered="false" class="model-config-tip">
      此处管理当前登录用户自己的模型配置。未创建配置时，聊天将使用服务端 .env 中的 LLM 连接兜底；创建后可指定不同的接入地址、密钥与 Prompt。
    </NAlert>
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :query-bar-props="queryBarProps"
        :is-pagination="true"
        :remote="false"
        :scroll-x="1600"
        :columns="columns"
        :get-data="fetchModelList"
        row-key="id"
        @query-bar-create="handleAdd"
    >
      <template #queryBar>
        <QueryBarItem label="配置名称：">
          <NInput
              v-model:value="queryItems.config_name"
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
        width="680px"
        @save="handleSave"
    >
      <NForm
          ref="modalFormRef"
          label-placement="left"
          label-align="left"
          :label-width="120"
          :model="modalForm"
          :disabled="modalAction === 'view'"
      >
        <NFormItem
            label="配置名称"
            path="config_name"
            :rule="{ required: true, message: '请输入配置名称', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="modalForm.config_name" placeholder="如：客服-DeepSeek" />
        </NFormItem>
        <NFormItem label="配置说明" path="config_desc">
          <NInput
              v-model:value="modalForm.config_desc"
              type="textarea"
              :rows="2"
              placeholder="可选，描述该配置的适用场景"
          />
        </NFormItem>
        <NFormItem label="模型厂商" path="model_provider">
          <NSelect
              v-model:value="modalForm.model_provider"
              :options="providerOptions"
              placeholder="选择厂商"
          />
        </NFormItem>
        <NFormItem
            label="模型名称"
            path="llm_model_name"
            :rule="{ required: true, message: '请输入模型名称', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="modalForm.llm_model_name" placeholder="如：deepseek-chat" />
        </NFormItem>
        <NFormItem label="深度思考" path="model_thinking">
          <NSwitch v-model:value="modalForm.model_thinking" />
          <span class="field-hint">开启后，聊天页展示深度思考开关</span>
        </NFormItem>
        <NFormItem label="API Base URL" path="llm_base_url">
          <NInput
              v-model:value="modalForm.llm_base_url"
              placeholder="留空使用 .env 中的 LLM_BASE_URL"
          />
        </NFormItem>
        <NFormItem label="API Key" path="llm_api_key">
          <NInput
              v-model:value="modalForm.llm_api_key"
              type="password"
              show-password-on="click"
              :placeholder="modalForm.has_llm_api_key ? '留空则不修改已保存的 Key' : '留空使用 .env 中的 LLM_API_KEY'"
          />
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
        <NFormItem label="系统提示词" path="system_prompt">
          <NInput
              v-model:value="modalForm.system_prompt"
              type="textarea"
              :rows="4"
              placeholder="留空使用全局默认；可包含 {context} 占位符注入检索内容"
          />
        </NFormItem>
        <NFormItem label="检索条数 Top K" path="top_k">
          <NInputNumber
              v-model:value="modalForm.top_k"
              :min="1"
              :max="20"
              :step="1"
              class="w-full"
          />
        </NFormItem>
        <NFormItem label="相似度阈值" path="score_threshold">
          <NInputNumber
              v-model:value="modalForm.score_threshold"
              :min="0"
              :max="1"
              :step="0.05"
              class="w-full"
          />
        </NFormItem>
        <NFormItem label="历史对话轮数" path="max_history_rounds">
          <NInputNumber
              v-model:value="modalForm.max_history_rounds"
              :min="0"
              :max="50"
              :step="1"
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
.model-config-tip {
  margin-bottom: 12px;
}

.w-full {
  width: 100%;
}

.field-hint {
  margin-left: 8px;
  color: var(--n-text-color-3);
  font-size: 12px;
}
</style>
