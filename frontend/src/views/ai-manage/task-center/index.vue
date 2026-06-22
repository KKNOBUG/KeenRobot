<script setup>
import { computed, h, onMounted, ref } from 'vue'
import {
  NAlert,
  NButton,
  NInput,
  NPopconfirm,
  NSelect,
  NTabPane,
  NTabs,
  NTag,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { formatDateTime, renderIcon } from '@/utils'
import api from '@/api'

import TaskEditDrawer from './components/TaskEditDrawer.vue'

defineOptions({ name: 'TaskCenter' })

const activeTab = ref('tasks')
const $taskTable = ref(null)
const $recordTable = ref(null)

const presets = ref([])
const schedulerOptions = ref([])

const drawerVisible = ref(false)
const drawerMode = ref('create')
const currentRecord = ref(null)

const taskQuery = ref({ task_name: '', task_type: null, task_enabled: null })
const recordQuery = ref({ task_name: '', task_celery_status: null })

const taskQueryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: false,
  actionMode: 'dropdown',
}

const recordQueryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: false,
  addDelete: false,
  actionMode: 'dropdown',
}

const statusTypeMap = {
  等待执行: 'default',
  正在执行: 'info',
  成功: 'success',
  失败: 'error',
}

function openCreate() {
  drawerMode.value = 'create'
  currentRecord.value = null
  drawerVisible.value = true
}

function openEdit(row) {
  drawerMode.value = 'edit'
  currentRecord.value = row
  drawerVisible.value = true
}

function handleSaved() {
  $taskTable.value?.handleSearch()
}

async function loadMeta() {
  const presetRes = await api.fetchTaskCenterPresets()
  presets.value = presetRes?.presets || []
  schedulerOptions.value = (presetRes?.schedulers || []).map((s) => ({
    label: s.label,
    value: s.value,
  }))
}

async function fetchTaskList(params) {
  const res = await api.searchTasks({
    task_name: params.task_name || undefined,
    task_type: params.task_type || undefined,
    task_enabled: params.task_enabled ?? undefined,
    page: params.page || 1,
    page_size: params.pageSize || 10,
    order: ['-updated_time'],
  })
  return { data: res.data || [], total: res.total ?? 0 }
}

async function fetchRecordList(params) {
  const res = await api.searchTaskRecords({
    task_name: params.task_name || undefined,
    task_celery_status: params.task_celery_status || undefined,
    page: params.page || 1,
    page_size: params.pageSize || 10,
    order: ['-celery_start_time', '-id'],
  })
  return { data: res.data || [], total: res.total ?? 0 }
}

async function handleRunTask(row) {
  const taskId = row.task_id ?? row.id
  try {
    const fd = new FormData()
    fd.append('task_id', String(taskId))
    await api.runTask(fd)
    window.$message?.success('任务已下发执行')
    $taskTable.value?.handleSearch()
    if (activeTab.value === 'records') {
      $recordTable.value?.handleSearch()
    }
  } catch {
    // interceptor handles message
  }
}

async function handleStartTask(row) {
  const taskId = row.task_id ?? row.id
  try {
    const fd = new FormData()
    fd.append('task_id', String(taskId))
    await api.startTask(fd)
    window.$message?.success('任务调度已启动')
    $taskTable.value?.handleSearch()
  } catch {
    // interceptor handles message
  }
}

async function handleStopTask(row) {
  const taskId = row.task_id ?? row.id
  try {
    const fd = new FormData()
    fd.append('task_id', String(taskId))
    await api.stopTask(fd)
    window.$message?.success('任务调度已停止')
    $taskTable.value?.handleSearch()
  } catch {
    // interceptor handles message
  }
}

async function handleDeleteTask(row) {
  const taskId = row.task_id ?? row.id
  try {
    await api.deleteTask({ task_id: taskId })
    window.$message?.success('删除成功')
    $taskTable.value?.handleSearch()
  } catch {
    // interceptor handles message
  }
}

function onTabChange(name) {
  activeTab.value = name
  if (name === 'records') {
    $recordTable.value?.handleSearch()
  }
}

onMounted(async () => {
  await loadMeta()
  $taskTable.value?.handleSearch()
})

const enabledOptions = [
  { label: '全部', value: null },
  { label: '已启用', value: true },
  { label: '未启用', value: false },
]

const statusFilterOptions = [
  { label: '全部', value: null },
  { label: '等待执行', value: '等待执行' },
  { label: '正在执行', value: '正在执行' },
  { label: '成功', value: '成功' },
  { label: '失败', value: '失败' },
]

const taskColumns = computed(() => [
  {
    title: '任务名称',
    key: 'task_name',
    ellipsis: { tooltip: true },
  },
  {
    title: '任务类别',
    key: 'task_type',
    render(row) {
      return row.task_type || '-'
    },
  },
  {
    title: '任务调度模式',
    key: 'task_celery_scheduler',
    render(row) {
      return row.task_celery_scheduler || '-'
    },
  },
  {
    title: '任务调度节点',
    key: 'task_celery_node',
    ellipsis: { tooltip: true },
    render(row) {
      return row.task_celery_node || '-'
    },
  },
  {
    title: '任务调度状态',
    key: 'task_enabled',
    align: 'center',
    render(row) {
      return row.task_enabled
          ? h(NTag, { type: 'success', size: 'small' }, { default: () => '已启用' })
          : h(NTag, { size: 'small' }, { default: () => '未启用' })
    },
  },
  {
    title: '最新调度状态',
    key: 'task_celery_status',
    align: 'center',
    render(row) {
      if (!row.task_celery_status) return '-'
      return h(
          NTag,
          { type: statusTypeMap[row.task_celery_status] || 'default', size: 'small' },
          { default: () => row.task_celery_status },
      )
    },
  },
  {
    title: '最新调度时间',
    key: 'task_celery_time',
    align: 'center',
    render(row) {
      return row.task_celery_time ? formatDateTime(row.task_celery_time) : '-'
    },
  },
  {
    title: '最新调度版本',
    key: 'task_version',
    align: 'center',
    render(row) {
      return row.task_version ?? 0
    },
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    fixed: 'right',
    render(row) {
      return [
        h(
            NButton,
            { size: 'tiny', quaternary: true, type: 'primary', onClick: () => handleRunTask(row) },
            { default: () => '执行', icon: renderIcon('material-symbols:play-arrow', { size: 16 }) },
        ),
        row.task_enabled
            ? h(
                NButton,
                { size: 'tiny', quaternary: true, type: 'warning', onClick: () => handleStopTask(row) },
                { default: () => '停止', icon: renderIcon('material-symbols:pause', { size: 16 }) },
            )
            : h(
                NButton,
                { size: 'tiny', quaternary: true, type: 'success', onClick: () => handleStartTask(row) },
                { default: () => '启动', icon: renderIcon('material-symbols:play-circle', { size: 16 }) },
            ),
        h(
            NButton,
            { size: 'tiny', quaternary: true, type: 'info', onClick: () => openEdit(row) },
            { default: () => '编辑', icon: renderIcon('material-symbols:edit-outline', { size: 16 }) },
        ),
        h(
            NPopconfirm,
            { onPositiveClick: () => handleDeleteTask(row) },
            {
              trigger: () =>
                  h(
                      NButton,
                      { size: 'tiny', quaternary: true, type: 'error' },
                      { default: () => '删除', icon: renderIcon('material-symbols:delete-outline', { size: 16 }) },
                  ),
              default: () => `确定删除任务「${row.task_name}」吗？`,
            },
        ),
      ]
    },
  },
])

const recordColumns = computed(() => [
  {
    title: '任务名称',
    key: 'task_name',
    minWidth: 120,
    ellipsis: { tooltip: true },
  },
  {
    title: '任务版本',
    key: 'task_version',
    width: 90,
    align: 'center',
    render(row) {
      return row.task_version ?? '-'
    },
  },
  {
    title: 'Celery ID',
    key: 'celery_id',
    minWidth: 180,
    ellipsis: { tooltip: true },
  },
  {
    title: '任务调度状态',
    key: 'task_celery_status',
    width: 100,
    align: 'center',
    render(row) {
      return h(
          NTag,
          { type: statusTypeMap[row.task_celery_status] || 'default', size: 'small' },
          { default: () => row.task_celery_status || '-' },
      )
    },
  },
  {
    title: '开始时间',
    key: 'celery_start_time',
    width: 170,
    align: 'center',
    render(row) {
      return row.celery_start_time ? formatDateTime(row.celery_start_time) : '-'
    },
  },
  {
    title: '结束时间',
    key: 'celery_end_time',
    width: 170,
    align: 'center',
    render(row) {
      return row.celery_end_time ? formatDateTime(row.celery_end_time) : '-'
    },
  },
  {
    title: '耗时',
    key: 'celery_duration',
    width: 90,
    align: 'center',
    render(row) {
      return row.celery_duration || '-'
    },
  },
  {
    title: '摘要',
    key: 'task_summary',
    minWidth: 160,
    ellipsis: { tooltip: true },
    render(row) {
      return row.task_summary || row.task_error || '-'
    },
  },
])
</script>

<template>
  <CommonPage show-footer title="任务中心">
    <NAlert type="info" :bordered="false" class="manage-tip">
      管理 Celery 示例任务：支持立即执行、定时调度（间隔/Cron/一次性）与执行记录追踪。
      示例任务会向 Worker 工作目录写入 <code>task_example.txt</code>（默认 100 行）。
    </NAlert>

    <NTabs v-model:value="activeTab" type="line" @update:value="onTabChange">
      <NTabPane name="tasks" tab="任务管理">
        <CrudTable
            ref="$taskTable"
            v-model:query-items="taskQuery"
            :query-bar-props="taskQueryBarProps"
            :remote="true"
            :scroll-x="1300"
            :columns="taskColumns"
            :get-data="fetchTaskList"
            row-key="task_id"
            @query-bar-create="openCreate"
        >
          <template #queryBar>
            <QueryBarItem label="任务名称：">
              <NInput
                  v-model:value="taskQuery.task_name"
                  clearable
                  placeholder="模糊搜索"
                  @keypress.enter="$taskTable?.handleSearch()"
              />
            </QueryBarItem>
            <QueryBarItem label="调度状态：">
              <NSelect
                  v-model:value="taskQuery.task_enabled"
                  :options="enabledOptions"
                  clearable
                  style="width: 120px"
              />
            </QueryBarItem>
          </template>
        </CrudTable>
      </NTabPane>

      <NTabPane name="records" tab="执行记录">
        <CrudTable
            ref="$recordTable"
            v-model:query-items="recordQuery"
            :query-bar-props="recordQueryBarProps"
            :remote="true"
            :scroll-x="1000"
            :columns="recordColumns"
            :get-data="fetchRecordList"
            row-key="record_id"
        >
          <template #queryBar>
            <QueryBarItem label="任务名称：">
              <NInput
                  v-model:value="recordQuery.task_name"
                  clearable
                  placeholder="模糊搜索"
                  @keypress.enter="$recordTable?.handleSearch()"
              />
            </QueryBarItem>
            <QueryBarItem label="任务调度状态：">
              <NSelect
                  v-model:value="recordQuery.task_celery_status"
                  :options="statusFilterOptions"
                  clearable
                  style="width: 120px"
              />
            </QueryBarItem>
          </template>
        </CrudTable>
      </NTabPane>
    </NTabs>

    <TaskEditDrawer
        v-model:show="drawerVisible"
        :mode="drawerMode"
        :record="currentRecord"
        :presets="presets"
        :scheduler-options="schedulerOptions"
        @saved="handleSaved"
    />
  </CommonPage>
</template>

<style scoped>
.manage-tip {
  margin-bottom: 12px;
}
.manage-tip code {
  font-size: 12px;
  background: rgba(0, 0, 0, 0.06);
  padding: 1px 4px;
  border-radius: 3px;
}
</style>
