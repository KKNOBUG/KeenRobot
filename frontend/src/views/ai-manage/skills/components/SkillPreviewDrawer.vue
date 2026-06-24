<script setup>
import { ref, watch } from 'vue'
import { NButton, NDrawer, NDrawerContent, NEmpty, NSpin, NTree } from 'naive-ui'

import api from '@/api'

const props = defineProps({
  show: { type: Boolean, default: false },
  skillId: { type: String, default: '' },
  skillName: { type: String, default: '' },
})

const emit = defineEmits(['update:show'])

const loading = ref(false)
const preview = ref(null)

function close() {
  emit('update:show', false)
}

function treeNodeLabel(node) {
  const suffix = node.type === 'dir' ? ' /' : ''
  return `${node.name}${suffix}`
}

function mapTreeNodes(nodes = []) {
  return nodes.map((node) => ({
    key: node.path,
    label: treeNodeLabel(node),
    isLeaf: node.type !== 'dir',
    children: node.children?.length ? mapTreeNodes(node.children) : undefined,
  }))
}

async function loadPreview() {
  if (!props.skillId) {
    preview.value = null
    return
  }
  loading.value = true
  try {
    preview.value = await api.previewSkill(props.skillId)
  } catch (err) {
    preview.value = null
    window.$message?.error(err?.message || '加载预览失败')
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.show, props.skillId],
  () => {
    if (props.show && props.skillId) {
      loadPreview()
    } else {
      preview.value = null
    }
  },
  { immediate: true },
)
</script>

<template>
  <NDrawer :show="show" :width="720" @update:show="emit('update:show', $event)">
    <NDrawerContent closable :title="`预览：${skillName || 'Skill'}`">
      <NSpin :show="loading">
        <template v-if="preview">
          <div class="skill-preview__meta">
            <span>Key: {{ preview.skill_key }}</span>
            <span>Version: {{ preview.skill_version?.slice(0, 12) }}</span>
          </div>

          <div class="skill-preview__section">
            <div class="skill-preview__section-title">目录结构</div>
            <NTree
              v-if="preview.directory_tree?.length"
              block-line
              selectable
              :data="mapTreeNodes(preview.directory_tree)"
              default-expand-all
            />
            <NEmpty v-else size="small" description="空目录" />
          </div>

          <div class="skill-preview__section">
            <div class="skill-preview__section-title">SKILL.md</div>
            <pre class="skill-preview__markdown">{{ preview.skill_md }}</pre>
          </div>
        </template>
        <NEmpty v-else-if="!loading" description="暂无预览数据" />
      </NSpin>

      <template #footer>
        <NButton @click="close">关闭</NButton>
      </template>
    </NDrawerContent>
  </NDrawer>
</template>

<style scoped lang="scss">
.skill-preview__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 16px;
  font-size: 12px;
  color: var(--n-text-color-3);
  font-family: ui-monospace, monospace;
}

.skill-preview__section {
  margin-bottom: 20px;
}

.skill-preview__section-title {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--n-text-color);
}

.skill-preview__markdown {
  margin: 0;
  padding: 14px;
  max-height: 420px;
  overflow: auto;
  border-radius: 10px;
  border: 1px solid var(--n-border-color);
  background: var(--n-action-color);
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
</style>
