<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  NAlert,
  NButton,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NInput,
  NInputNumber,
  NPagination,
  NSelect,
  NSpace,
  NSpin,
  NTag,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import SkillRunStreamModal from '@/components/skill/SkillRunStreamModal.vue'
import api from '@/api'
import { getToken } from '@/utils'
import { getModeLabel } from '@/views/ai-manage/skills/skillUtils.js'

defineOptions({ name: '执行记录' })

const route = useRoute()

const loading = ref(false)
const keyword = ref('')
const statusFilter = ref(null)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const runList = ref([])

const detailVisible = ref(false)
const detailLoading = ref(false)
const currentRun = ref(null)
const outputs = ref([])
const cleanupDays = ref(30)
const cleaning = ref(false)
const streamVisible = ref(false)
const streamRunId = ref('')

const terminalStatuses = new Set(['completed', 'failed', 'cancelled'])

const statusOptions = [
  { label: '全部状态', value: null },
  { label: '待输入', value: 'pending' },
  { label: '已校验', value: 'validated' },
  { label: '执行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '失败', value: 'failed' },
  { label: '已取消', value: 'cancelled' },
]

const statusTagType = {
  pending: 'default',
  validated: 'info',
  running: 'warning',
  completed: 'success',
  failed: 'error',
  cancelled: 'default',
}

function statusLabel(status) {
  const map = {
    pending: '待输入',
    validated: '已校验',
    running: '执行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return map[status] || status
}

async function loadList() {
  loading.value = true
  try {
    const res = await api.searchSkillRuns({
      page: page.value,
      page_size: pageSize.value,
      status: statusFilter.value || undefined,
    })
    let items = res?.data || []
    total.value = res?.total ?? items.length
    const kw = keyword.value.trim().toLowerCase()
    if (kw) {
      items = items.filter(
        (item) =>
          item.skill_name?.toLowerCase().includes(kw)
          || item.skill_key?.toLowerCase().includes(kw)
          || item.id?.toLowerCase().includes(kw),
      )
    }
    runList.value = items
  } catch (err) {
    window.$message?.error(err?.message || '加载执行记录失败')
    runList.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

/** 同步 URL 中的 run 参数，避免 router.replace 触发整页 remount */
function syncRunQuery(runId) {
  const next = runId ? String(runId) : null
  const url = new URL(window.location.href)
  const current = url.searchParams.get('run')
  if (next === current || (!next && !current)) return
  if (next) url.searchParams.set('run', next)
  else url.searchParams.delete('run')
  window.history.replaceState(window.history.state, '', url)
}

async function openDetail(id) {
  const runId = String(id)
  if (detailVisible.value && currentRun.value?.id === runId && !detailLoading.value) {
    return
  }
  detailVisible.value = true
  detailLoading.value = true
  syncRunQuery(runId)
  try {
    currentRun.value = await api.fetchSkillRun(runId)
    outputs.value = await api.fetchSkillRunOutputs(runId)
  } catch (err) {
    window.$message?.error(err?.message || '加载详情失败')
    currentRun.value = null
    outputs.value = []
  } finally {
    detailLoading.value = false
  }
}

function onDetailVisibleChange(show) {
  if (show) return
  syncRunQuery(null)
}

async function downloadOutput(path) {
  if (!currentRun.value?.id) return
  try {
    const token = getToken()
    const url = api.downloadSkillRunOutput(currentRun.value.id, path)
    const res = await fetch(url, { headers: token ? { token } : {} })
    if (!res.ok) throw new Error('下载失败')
    const blob = await res.blob()
    const objectUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = path.split('/').pop() || 'output'
    a.click()
    URL.revokeObjectURL(objectUrl)
  } catch (err) {
    window.$message?.error(err?.message || '下载失败')
  }
}

async function cancelRun() {
  if (!currentRun.value?.id) return
  try {
    currentRun.value = await api.cancelSkillRun(currentRun.value.id)
    window.$message?.success('已取消')
    await loadList()
  } catch (err) {
    window.$message?.error(err?.message || '取消失败')
  }
}

function isTerminal(status) {
  return terminalStatuses.has(status)
}

async function retryRun() {
  if (!currentRun.value?.id) return
  try {
    const res = await api.retrySkillRun(currentRun.value.id)
    window.$message?.success(res?.message || '已创建重试 Run')
    detailVisible.value = false
    await loadList()
    if (res?.new_run_id) {
      await openDetail(res.new_run_id)
    }
  } catch (err) {
    window.$message?.error(err?.message || '重试失败')
  }
}

async function deleteRun() {
  if (!currentRun.value?.id) return
  await window.$dialog?.confirm({
    title: '删除确认',
    type: 'warning',
    content: '将删除执行记录及磁盘工作区，不可恢复。确定继续？',
    positiveText: '删除',
    negativeText: '取消',
    async onPositiveClick() {
      try {
        await api.deleteSkillRun(currentRun.value.id)
        window.$message?.success('已删除')
        detailVisible.value = false
        await loadList()
      } catch (err) {
        window.$message?.error(err?.message || '删除失败')
      }
    },
  })
}

async function cleanupRuns(dryRun = false) {
  cleaning.value = true
  try {
    const res = await api.cleanupSkillRuns({
      days: cleanupDays.value,
      dry_run: dryRun,
    })
    window.$message?.success(
      res?.message
        || (dryRun
          ? `预览：${res?.scanned ?? 0} 条可清理`
          : `已清理 ${res?.deleted ?? 0} 条`),
    )
    if (!dryRun) await loadList()
  } catch (err) {
    window.$message?.error(err?.message || '清理失败')
  } finally {
    cleaning.value = false
  }
}

async function confirmCleanup() {
  await window.$dialog?.confirm({
    title: '清理过期记录',
    type: 'warning',
    content: `将删除 ${cleanupDays.value} 天前的已完成/失败/已取消记录及工作区，不可恢复。`,
    positiveText: '确认清理',
    negativeText: '取消',
    async onPositiveClick() {
      await cleanupRuns(false)
    },
  })
}

function canStartRun(run) {
  return run && ['pending', 'validated'].includes(run.status)
}

function isWizardMode(run) {
  return (run?.interaction_mode || '').toLowerCase() === 'wizard'
}

async function startRun() {
  if (!currentRun.value?.id) return
  try {
    await api.startSkillRun(currentRun.value.id)
    currentRun.value = await api.fetchSkillRun(currentRun.value.id)
    await loadList()
    if (isWizardMode(currentRun.value)) {
      streamRunId.value = currentRun.value.id
      streamVisible.value = true
    } else {
      window.$message?.success('异步任务已提交，请稍后刷新查看状态')
    }
  } catch (err) {
    window.$message?.error(err?.message || '启动失败')
  }
}

function viewProgress() {
  if (!currentRun.value?.id) return
  streamRunId.value = currentRun.value.id
  streamVisible.value = true
}

async function onStreamFinished() {
  if (currentRun.value?.id) {
    currentRun.value = await api.fetchSkillRun(currentRun.value.id)
    outputs.value = await api.fetchSkillRunOutputs(currentRun.value.id)
  }
  await loadList()
}

watch([page, statusFilter], () => {
  loadList()
})

onMounted(async () => {
  await loadList()
  const runId = route.query.run || new URLSearchParams(window.location.search).get('run')
  if (runId) {
    await openDetail(String(runId))
  }
})
</script>

<template>
  <CommonPage :show-header="false" :show-footer="false">
    <div class="skill-runs-page">
      <NAlert type="info" :bordered="false" class="skill-runs-page__tip">
        查看 Skill 向导 / 异步任务的执行记录与产物。wizard 模式可在聊天页通过「Skill 任务」发起。
      </NAlert>

      <div class="skill-runs-page__toolbar">
        <NSpace>
          <NInput
            v-model:value="keyword"
            clearable
            placeholder="搜索 Skill 名称 / key / run id"
            style="width: 280px"
            @keyup.enter="loadList"
          />
          <NSelect
            v-model:value="statusFilter"
            :options="statusOptions"
            style="width: 140px"
          />
          <NButton @click="loadList">刷新</NButton>
          <NInputNumber v-model:value="cleanupDays" :min="1" :max="365" size="small" style="width: 120px">
            <template #suffix>天</template>
          </NInputNumber>
          <NButton :loading="cleaning" @click="cleanupRuns(true)">预览清理</NButton>
          <NButton type="warning" :loading="cleaning" @click="confirmCleanup">清理过期</NButton>
        </NSpace>
      </div>

      <NSpin :show="loading">
        <div v-if="runList.length" class="run-table">
          <div class="run-table__head">
            <span>Skill</span>
            <span>Key</span>
            <span>模式</span>
            <span>状态</span>
            <span>创建时间</span>
            <span>操作</span>
          </div>
          <div v-for="row in runList" :key="row.id" class="run-table__row">
            <span class="ellipsis" :title="row.skill_name">{{ row.skill_name || '-' }}</span>
            <span class="mono ellipsis" :title="row.skill_key">{{ row.skill_key || '-' }}</span>
            <span>{{ getModeLabel(row.interaction_mode) }}</span>
            <span>
              <NTag size="small" :type="statusTagType[row.status] || 'default'" :bordered="false">
                {{ statusLabel(row.status) }}
              </NTag>
            </span>
            <span class="mono">{{ row.created_time || '-' }}</span>
            <span>
              <NButton size="small" quaternary type="info" @click="openDetail(row.id)">详情</NButton>
            </span>
          </div>
        </div>
        <NEmpty v-else description="暂无执行记录" class="skill-runs-page__empty" />

        <div v-if="total > pageSize" class="skill-runs-page__pager">
          <NPagination
            v-model:page="page"
            :page-size="pageSize"
            :item-count="total"
            size="small"
          />
        </div>
      </NSpin>
    </div>

    <NDrawer v-model:show="detailVisible" :width="560" @update:show="onDetailVisibleChange">
      <NDrawerContent title="执行详情" closable>
        <NSpin :show="detailLoading">
          <template v-if="currentRun">
            <div class="detail-grid">
              <div><span class="label">Run ID</span>{{ currentRun.id }}</div>
              <div><span class="label">Skill</span>{{ currentRun.skill_name || currentRun.skill_key }}</div>
              <div><span class="label">模式</span>{{ getModeLabel(currentRun.interaction_mode) }}</div>
              <div>
                <span class="label">状态</span>
                <NTag size="small" :type="statusTagType[currentRun.status] || 'default'">
                  {{ statusLabel(currentRun.status) }}
                </NTag>
              </div>
              <div v-if="currentRun.error_message" class="detail-error">
                <span class="label">错误</span>{{ currentRun.error_message }}
              </div>
            </div>

            <div class="detail-section">
              <div class="detail-section__title">产物</div>
              <div v-if="outputs.length" class="output-list">
                <div v-for="item in outputs" :key="item.path" class="output-item">
                  <span>{{ item.path }} ({{ item.size }} B)</span>
                  <NButton size="tiny" quaternary type="primary" @click="downloadOutput(item.path)">
                    下载
                  </NButton>
                </div>
              </div>
              <NEmpty v-else size="small" description="暂无产物" />
            </div>

            <NSpace style="margin-top: 16px">
              <NButton
                  v-if="canStartRun(currentRun)"
                  type="primary"
                  @click="startRun"
              >
                启动执行
              </NButton>
              <NButton
                  v-if="currentRun.status === 'running' && isWizardMode(currentRun)"
                  type="info"
                  @click="viewProgress"
              >
                查看进度
              </NButton>
              <NButton v-if="currentRun.status === 'running'" type="warning" @click="cancelRun">
                取消任务
              </NButton>
              <NButton
                  v-if="isTerminal(currentRun.status)"
                  type="primary"
                  @click="retryRun"
              >
                重试
              </NButton>
              <NButton
                  v-if="currentRun.status !== 'running'"
                  type="error"
                  quaternary
                  @click="deleteRun"
              >
                删除
              </NButton>
            </NSpace>
          </template>
        </NSpin>
      </NDrawerContent>
    </NDrawer>

    <SkillRunStreamModal
      v-model:show="streamVisible"
      :run-id="streamRunId"
      @finished="onStreamFinished"
    />
  </CommonPage>
</template>

<style scoped lang="scss">
.skill-runs-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px 2px 20px;
}

.skill-runs-page__tip {
  margin-bottom: 0;
}

.skill-runs-page__toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.skill-runs-page__empty {
  padding: 48px 0;
}

.skill-runs-page__pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.run-table {
  border: 1px solid #eef0f4;
  border-radius: 10px;
  overflow: hidden;
}

.run-table__head,
.run-table__row {
  display: grid;
  grid-template-columns: 1.2fr 1fr 0.8fr 0.8fr 1.2fr 0.6fr;
  gap: 8px;
  align-items: center;
  padding: 10px 14px;
  font-size: 13px;
}

.run-table__head {
  background: #f9fafb;
  font-weight: 600;
  color: #374151;
}

.run-table__row:not(:last-child) {
  border-bottom: 1px solid #eef0f4;
}

.mono {
  font-family: ui-monospace, monospace;
  font-size: 12px;
}

.ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 13px;
  margin-bottom: 20px;

  .label {
    display: inline-block;
    width: 56px;
    color: #6b7280;
    margin-right: 8px;
  }
}

.detail-error {
  color: #ef4444;
}

.detail-section__title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}

.output-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.output-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f9fafb;
  font-size: 12px;
  font-family: ui-monospace, monospace;
}
</style>

<style scoped lang="scss">
html.dark .run-table {
  border-color: rgba(255, 255, 255, 0.1);
}

html.dark .run-table__head {
  background: rgba(255, 255, 255, 0.06);
  color: #e5e7eb;
}

html.dark .run-table__row:not(:last-child) {
  border-bottom-color: rgba(255, 255, 255, 0.08);
}

html.dark .output-item {
  background: rgba(255, 255, 255, 0.06);
}
</style>
