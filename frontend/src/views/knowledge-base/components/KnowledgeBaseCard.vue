<script setup>
import { computed } from 'vue'
import { NDropdown, NTag } from 'naive-ui'

import TheIcon from '@/components/icon/TheIcon.vue'
import {
  formatChunkSize,
  getDisplayIcon,
  getIconStyle,
  shortModelName,
} from '../kbUtils.js'

const props = defineProps({
  item: { type: Object, required: true },
  index: { type: Number, default: 0 },
})

const emit = defineEmits(['edit', 'delete'])

const displayIcon = computed(() => getDisplayIcon(props.item))
const iconStyle = computed(() => getIconStyle(props.item?.knowledge_name, props.index))

const menuOptions = [
  { label: '编辑', key: 'edit' },
  { label: '删除', key: 'delete' },
]

function handleMenuSelect(key) {
  if (key === 'edit') emit('edit', props.item)
  if (key === 'delete') emit('delete', props.item)
}
</script>

<template>
  <div class="kb-card" @click="emit('edit', item)">
    <div class="kb-card__header">
      <div class="kb-card__identity">
        <div
            class="kb-card__icon"
            :style="{ background: iconStyle.bg, color: iconStyle.color }"
        >
          {{ displayIcon }}
        </div>
        <div class="kb-card__title-wrap">
          <div class="kb-card__title">{{ item.knowledge_name }}</div>
          <div class="kb-card__tags">
            <NTag
                v-if="item.is_public"
                size="small"
                :bordered="false"
                class="kb-card__tag kb-card__tag--public"
            >
              公开
            </NTag>
            <NTag size="small" :bordered="false" class="kb-card__tag kb-card__tag--docs">
              {{ item.document_count || 0 }} 个文档
            </NTag>
          </div>
        </div>
      </div>
      <NDropdown trigger="click" :options="menuOptions" @select="handleMenuSelect" @click.stop>
        <button class="kb-card__more" type="button" title="更多操作" @click.stop>
          <TheIcon icon="material-symbols:more-vert" :size="18" />
        </button>
      </NDropdown>
    </div>

    <div class="kb-card__desc">{{ item.description || '暂无描述' }}</div>

    <div class="kb-card__footer">
      <span class="kb-card__meta">分块 {{ formatChunkSize(item) }}</span>
      <span class="kb-card__meta" :title="item.default_embedding_model">
        向量 {{ shortModelName(item.default_embedding_model) }}
      </span>
    </div>
  </div>
</template>

<style scoped lang="scss">
.kb-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 168px;
  padding: 18px 18px 16px;
  background: #fff;
  border: 1px solid #eef0f4;
  border-radius: 14px;
  cursor: pointer;
  transition: box-shadow 0.2s ease, border-color 0.2s ease, transform 0.2s ease;

  &:hover {
    border-color: #dbe0e8;
    box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
    transform: translateY(-1px);
  }
}

.kb-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.kb-card__identity {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
}

.kb-card__icon {
  flex: 0 0 42px;
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
  line-height: 1;
}

.kb-card__title-wrap {
  min-width: 0;
}

.kb-card__title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.4;
  word-break: break-all;
}

.kb-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.kb-card__tag {
  border-radius: 999px;
  font-size: 12px;
}

.kb-card__tag--public,
.kb-card__tag--docs {
  background: #f3f4f6 !important;
  color: #6b7280 !important;
}

.kb-card__more {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  cursor: pointer;

  &:hover {
    background: #f3f4f6;
    color: #334155;
  }

  :deep(.n-icon) {
    color: inherit;
  }
}

.kb-card__desc {
  flex: 1;
  font-size: 13px;
  line-height: 1.6;
  color: #9ca3af;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.kb-card__footer {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.kb-card__meta {
  padding: 4px 10px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #6b7280;
  font-size: 12px;
}
</style>

<style scoped lang="scss">
html.dark .kb-card {
  background: #18181c;
  border-color: rgba(255, 255, 255, 0.1);
  box-shadow: none;
}

html.dark .kb-card:hover {
  border-color: rgba(255, 255, 255, 0.16);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.28);
}

html.dark .kb-card__title {
  color: #e5e7eb;
}

html.dark .kb-card__desc {
  color: #9ca3af;
}

html.dark .kb-card__more {
  color: #cbd5e1;
}

html.dark .kb-card__more:hover {
  color: #f8fafc;
  background: rgba(255, 255, 255, 0.1);
}

html.dark .kb-card__tag--public,
html.dark .kb-card__tag--docs,
html.dark .kb-card__meta {
  background: rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
}
</style>
