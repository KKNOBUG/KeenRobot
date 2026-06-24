<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NAlert, NButton, NCheckbox, NEmpty, NInput, NSpace, NSpin, NUpload } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import { renderIcon } from '@/utils'
import api from '@/api'

import SkillCard from './components/SkillCard.vue'
import SkillEditDrawer from './components/SkillEditDrawer.vue'
import SkillPreviewDrawer from './components/SkillPreviewDrawer.vue'

defineOptions({ name: 'SkillsManage' })

const router = useRouter()
const SKILL_RUNS_PATH = '/ai-manage/skill-runs'

function goSkillRuns() {
  router.push(SKILL_RUNS_PATH)
}

const loading = ref(false)
const syncing = ref(false)
const uploading = ref(false)
const zipOverwrite = ref(false)
const keyword = ref('')
const skillList = ref([])

const editVisible = ref(false)
const previewVisible = ref(false)
const currentRecord = ref(null)

const filteredList = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return skillList.value
  return skillList.value.filter((item) => {
    const desc = item.description || ''
    const key = item.skill_key || ''
    return (
      item.name?.toLowerCase().includes(kw) ||
      desc.toLowerCase().includes(kw) ||
      key.toLowerCase().includes(kw)
    )
  })
})

async function loadList() {
  loading.value = true
  try {
    skillList.value = (await api.fetchSkills('', true)) || []
  } catch (err) {
    window.$message?.error(err?.message || '加载 Skills 列表失败')
    skillList.value = []
  } finally {
    loading.value = false
  }
}

async function handleSync() {
  syncing.value = true
  try {
    const res = await api.syncSkills()
    skillList.value = res?.skills || []
    const parts = []
    if (res?.created) parts.push(`新增 ${res.created}`)
    if (res?.updated) parts.push(`更新 ${res.updated}`)
    if (res?.removed) parts.push(`移除 ${res.removed}`)
    window.$message?.success(parts.length ? `同步完成：${parts.join('，')}` : '同步完成，无变更')
  } catch (err) {
    window.$message?.error(err?.message || '同步失败')
  } finally {
    syncing.value = false
  }
}

function openEdit(item) {
  currentRecord.value = item
  editVisible.value = true
}

function openPreview(item) {
  currentRecord.value = item
  previewVisible.value = true
}

async function handleDelete(item) {
  await window.$dialog?.confirm({
    title: '删除确认',
    type: 'warning',
    content: `确定删除技能记录「${item.name}」吗？磁盘 Skill 包不会被删除，下次同步可能重新出现。`,
    positiveText: '删除',
    negativeText: '取消',
    async onPositiveClick() {
      try {
        await api.deleteSkill(item.id)
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

async function handleZipUpload(options) {
  const file = options.file?.file
  if (!file) return
  uploading.value = true
  try {
    const res = await api.uploadSkillZip(file, { overwrite: zipOverwrite.value })
    window.$message?.success(`Skill「${res?.name || res?.skill_key}」已安装`)
    await loadList()
  } catch (err) {
    window.$message?.error(err?.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

onMounted(async () => {
  await handleSync()
})
</script>

<template>
  <CommonPage :show-header="false" :show-footer="false">
    <div class="skills-page">
      <NAlert type="info" :bordered="false" class="skills-page__tip">
        从磁盘 <code>.claude/skills/</code> 同步 Skill 包，或上传 zip 安装（须含 SKILL.md）。
        chat 模式可在聊天中直接对话；wizard / async_job 通过聊天页「Skill 任务」或
        <a class="skills-page__link" href="javascript:void(0)" @click.prevent="goSkillRuns">执行记录</a>
        发起与查看。
      </NAlert>

      <div class="skills-page__toolbar">
        <NInput
          v-model:value="keyword"
          clearable
          class="skills-page__search"
          placeholder="搜索技能名称、描述或 skill_key"
        >
          <template #prefix>
            <span class="i-material-symbols:search text-18 text-gray-400" />
          </template>
        </NInput>
        <NSpace align="center">
          <NCheckbox v-model:checked="zipOverwrite">覆盖同名 Skill</NCheckbox>
          <NUpload
            :show-file-list="false"
            accept=".zip"
            :disabled="uploading || syncing"
            @change="handleZipUpload"
          >
            <NButton :loading="uploading">上传 zip</NButton>
          </NUpload>
          <NButton quaternary @click="goSkillRuns">执行记录</NButton>
          <NButton type="primary" :loading="syncing" @click="handleSync">
            <template #icon>
              <component :is="renderIcon('material-symbols:sync', { size: 18 })" />
            </template>
            同步磁盘 Skill
          </NButton>
        </NSpace>
      </div>

      <NSpin :show="loading || syncing">
        <div v-if="filteredList.length" class="skills-page__grid">
          <SkillCard
            v-for="(item, index) in filteredList"
            :key="item.id"
            :item="item"
            :index="index"
            @edit="openEdit"
            @preview="openPreview"
            @delete="handleDelete"
          />
        </div>
        <NEmpty v-else class="skills-page__empty" description="暂无 Skill，请确认磁盘目录后点击同步">
          <template #extra>
            <NButton type="primary" :loading="syncing" @click="handleSync">同步磁盘 Skill</NButton>
          </template>
        </NEmpty>
      </NSpin>
    </div>

    <SkillEditDrawer
      v-model:show="editVisible"
      :record="currentRecord"
      @saved="handleSaved"
      @preview="openPreview"
    />

    <SkillPreviewDrawer
      v-model:show="previewVisible"
      :skill-id="currentRecord?.id || ''"
      :skill-name="currentRecord?.name || ''"
    />
  </CommonPage>
</template>

<style scoped lang="scss">
.skills-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
  padding: 4px 2px 20px;
}

.skills-page__tip {
  margin-bottom: 0;

  code {
    padding: 0 4px;
    border-radius: 4px;
    background: #f3f4f6;
    font-size: 12px;
    color: #6b7280;
  }
}

.skills-page__link {
  color: var(--primary-color, #f4511e);
  text-decoration: none;

  &:hover {
    text-decoration: underline;
  }
}

.skills-page__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.skills-page__search {
  max-width: 360px;
}

.skills-page__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 18px;
}

.skills-page__empty {
  padding: 80px 0;
}
</style>
