<script setup>
import { computed } from 'vue'
import { NDropdown, NTag } from 'naive-ui'

import TheIcon from '@/components/icon/TheIcon.vue'
import {
  getDisplayIcon,
  getIconStyle,
  getToolCount,
  isEmojiIcon,
  transportTag,
} from '../mcpUtils.js'

const props = defineProps({
  item: { type: Object, required: true },
  index: { type: Number, default: 0 },
})

const emit = defineEmits(['edit', 'delete'])

const displayIcon = computed(() => getDisplayIcon(props.item))
const iconStyle = computed(() => getIconStyle(props.item?.name, props.index))
const toolCount = computed(() => getToolCount(props.item))
const category = computed(() => props.item?.config?.category || '其他')

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
  <div class="mcp-card" @click="emit('edit', item)">
    <div class="mcp-card__header">
      <div class="mcp-card__identity">
        <div
          class="mcp-card__icon"
          :style="{ background: iconStyle.bg, color: isEmojiIcon(displayIcon) ? undefined : iconStyle.color }"
        >
          {{ displayIcon }}
        </div>
        <div class="mcp-card__title-wrap">
          <div class="mcp-card__title">{{ item.name }}</div>
          <div class="mcp-card__tags">
            <NTag size="small" :bordered="false" class="mcp-card__tag mcp-card__tag--transport">
              {{ transportTag(item.transport) }}
            </NTag>
            <NTag size="small" :bordered="false" class="mcp-card__tag mcp-card__tag--category">
              {{ category }}
            </NTag>
          </div>
        </div>
      </div>
      <NDropdown trigger="click" :options="menuOptions" @select="handleMenuSelect" @click.stop>
        <button class="mcp-card__more" type="button" title="更多操作" @click.stop>
          <TheIcon icon="material-symbols:more-vert" :size="18" />
        </button>
      </NDropdown>
    </div>

    <div class="mcp-card__desc">{{ item.description || '暂无描述' }}</div>

    <div class="mcp-card__footer">
      <span class="mcp-card__status" :class="item.is_enabled ? 'is-enabled' : 'is-disabled'">
        <i class="mcp-card__status-dot" />
        {{ item.is_enabled ? '已启用' : '已禁用' }}
      </span>
      <span v-if="toolCount > 0" class="mcp-card__tools">{{ toolCount }} 个工具</span>
    </div>
  </div>
</template>

<style scoped lang="scss">
.mcp-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
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

.mcp-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.mcp-card__identity {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
}

.mcp-card__icon {
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

.mcp-card__title-wrap {
  min-width: 0;
}

.mcp-card__title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.4;
  word-break: break-all;
}

.mcp-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.mcp-card__tag {
  border-radius: 999px;
  font-size: 12px;
}

.mcp-card__tag--transport {
  background: #f3f4f6 !important;
  color: #6b7280 !important;
}

.mcp-card__tag--category {
  background: #f3f4f6 !important;
  color: #6b7280 !important;
}

.mcp-card__more {
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

.mcp-card__desc {
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

.mcp-card__footer {
  display: flex;
  align-items: center;
  gap: 10px;
}

.mcp-card__status {
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

.mcp-card__status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.mcp-card__tools {
  padding: 4px 10px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #6b7280;
  font-size: 12px;
}
</style>

<style scoped lang="scss">
html.dark .mcp-card {
  background: #18181c;
  border-color: rgba(255, 255, 255, 0.1);
  box-shadow: none;
}

html.dark .mcp-card:hover {
  border-color: rgba(255, 255, 255, 0.16);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.28);
}

html.dark .mcp-card__title {
  color: #e5e7eb;
}

html.dark .mcp-card__desc {
  color: #9ca3af;
}

html.dark .mcp-card__more {
  color: #cbd5e1;
}

html.dark .mcp-card__more:hover {
  color: #f8fafc;
  background: rgba(255, 255, 255, 0.1);
}

html.dark .mcp-card__tag--transport,
html.dark .mcp-card__tag--category {
  background: rgba(255, 255, 255, 0.08) !important;
  color: #cbd5e1 !important;
}

html.dark .mcp-card__status.is-enabled {
  background: rgba(34, 197, 94, 0.14);
  color: #4ade80;
}

html.dark .mcp-card__status.is-disabled {
  background: rgba(255, 255, 255, 0.08);
  color: #94a3b8;
}

html.dark .mcp-card__tools {
  background: rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
}
</style>
