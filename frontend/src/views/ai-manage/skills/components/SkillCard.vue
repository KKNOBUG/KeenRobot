<script setup>
import { computed } from 'vue'
import { NDropdown, NTag } from 'naive-ui'

import TheIcon from '@/components/icon/TheIcon.vue'
import { getIconStyle, getModeLabel } from '../skillUtils.js'

const props = defineProps({
  item: { type: Object, required: true },
  index: { type: Number, default: 0 },
})

const emit = defineEmits(['edit', 'preview', 'delete'])

const iconStyle = computed(() => getIconStyle(props.item?.name, props.index))
const modeLabel = computed(() => getModeLabel(props.item?.interaction_mode))

const menuOptions = [
  { label: '编辑集成配置', key: 'edit' },
  { label: '预览 SKILL.md', key: 'preview' },
  { type: 'divider', key: 'd1' },
  { label: '删除记录', key: 'delete' },
]

function handleMenuSelect(key) {
  if (key === 'edit') emit('edit', props.item)
  if (key === 'preview') emit('preview', props.item)
  if (key === 'delete') emit('delete', props.item)
}
</script>

<template>
  <div class="skill-card" @click="emit('edit', item)">
    <div class="skill-card__header">
      <div class="skill-card__identity">
        <div
          class="skill-card__icon"
          :style="{ background: iconStyle.bg, color: iconStyle.color }"
        >
          <TheIcon icon="hugeicons:magic-wand-01" :size="20" />
        </div>
        <div class="skill-card__title-wrap">
          <div class="skill-card__title">{{ item.name }}</div>
          <div class="skill-card__tags">
            <NTag size="small" :bordered="false" class="skill-card__tag skill-card__tag--key">
              {{ item.skill_key || '未同步' }}
            </NTag>
            <NTag size="small" :bordered="false" class="skill-card__tag skill-card__tag--mode">
              {{ modeLabel }}
            </NTag>
          </div>
        </div>
      </div>
      <NDropdown trigger="click" :options="menuOptions" @select="handleMenuSelect" @click.stop>
        <button class="skill-card__more" type="button" title="更多操作" @click.stop>
          <TheIcon icon="material-symbols:more-vert" :size="18" />
        </button>
      </NDropdown>
    </div>

    <div class="skill-card__desc">{{ item.description || '暂无描述' }}</div>

    <div class="skill-card__footer">
      <span class="skill-card__status" :class="item.is_enabled ? 'is-enabled' : 'is-disabled'">
        <i class="skill-card__status-dot" />
        {{ item.is_enabled ? '已启用' : '已禁用' }}
      </span>
      <span v-if="item.skill_version" class="skill-card__version">
        v{{ item.skill_version.slice(0, 8) }}
      </span>
    </div>
  </div>
</template>

<style scoped lang="scss">
.skill-card {
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

.skill-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.skill-card__identity {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
}

.skill-card__icon {
  flex: 0 0 42px;
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.skill-card__title-wrap {
  min-width: 0;
}

.skill-card__title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.4;
  word-break: break-all;
}

.skill-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.skill-card__tag {
  border-radius: 999px;
  font-size: 12px;
}

.skill-card__tag--key,
.skill-card__tag--mode {
  background: #f3f4f6 !important;
  color: #6b7280 !important;
}

.skill-card__more {
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

.skill-card__desc {
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

.skill-card__footer {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.skill-card__status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;

  &.is-enabled {
    background: #ecfdf3;
    color: #16a34a;
  }

  &.is-disabled {
    background: #f3f4f6;
    color: #9ca3af;
  }
}

.skill-card__status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.skill-card__version {
  padding: 4px 10px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #6b7280;
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
</style>

<style scoped lang="scss">
html.dark .skill-card {
  background: #18181c;
  border-color: rgba(255, 255, 255, 0.1);
  box-shadow: none;
}

html.dark .skill-card:hover {
  border-color: rgba(255, 255, 255, 0.16);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.28);
}

html.dark .skill-card__title {
  color: #e5e7eb;
}

html.dark .skill-card__desc {
  color: #9ca3af;
}

html.dark .skill-card__more {
  color: #cbd5e1;
}

html.dark .skill-card__more:hover {
  color: #f8fafc;
  background: rgba(255, 255, 255, 0.1);
}

html.dark .skill-card__tag--key,
html.dark .skill-card__tag--mode {
  background: rgba(255, 255, 255, 0.08) !important;
  color: #cbd5e1 !important;
}

html.dark .skill-card__status.is-enabled {
  background: rgba(34, 197, 94, 0.14);
  color: #4ade80;
}

html.dark .skill-card__status.is-disabled {
  background: rgba(255, 255, 255, 0.08);
  color: #94a3b8;
}

html.dark .skill-card__version {
  background: rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
}
</style>
