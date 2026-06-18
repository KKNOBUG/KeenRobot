<script setup>
import { computed } from 'vue'
import { NDropdown, NTag } from 'naive-ui'

import TheIcon from '@/components/icon/TheIcon.vue'
import { getDisplayIcon, getIconStyle, providerLabel } from '../modelUtils.js'

const props = defineProps({
  item: { type: Object, required: true },
  index: { type: Number, default: 0 },
})

const emit = defineEmits(['edit', 'delete', 'set-default'])

const displayIcon = computed(() => getDisplayIcon(props.item))
const iconStyle = computed(() => getIconStyle(props.item?.config_name, props.index))
const provider = computed(() => providerLabel(props.item?.model_provider))

const menuOptions = computed(() => {
  const options = [{ label: '编辑', key: 'edit' }]
  if (!props.item?.is_default) {
    options.push({ label: '设为默认', key: 'set-default' })
  }
  options.push({ label: '删除', key: 'delete' })
  return options
})

function handleMenuSelect(key) {
  if (key === 'edit') emit('edit', props.item)
  if (key === 'delete') emit('delete', props.item)
  if (key === 'set-default') emit('set-default', props.item)
}
</script>

<template>
  <div class="model-card" @click="emit('edit', item)">
    <div class="model-card__header">
      <div class="model-card__identity">
        <div
            class="model-card__icon"
            :style="{ background: iconStyle.bg, color: iconStyle.color }"
        >
          {{ displayIcon }}
        </div>
        <div class="model-card__title-wrap">
          <div class="model-card__title">{{ item.config_name }}</div>
          <div class="model-card__tags">
            <NTag size="small" :bordered="false" class="model-card__tag model-card__tag--provider">
              {{ provider }}
            </NTag>
            <NTag
                v-if="item.model_thinking"
                size="small"
                :bordered="false"
                class="model-card__tag model-card__tag--thinking"
            >
              思考模式
            </NTag>
          </div>
        </div>
      </div>
      <NDropdown trigger="click" :options="menuOptions" @select="handleMenuSelect" @click.stop>
        <button class="model-card__more" type="button" title="更多操作" @click.stop>
          <TheIcon icon="material-symbols:more-vert" :size="18" />
        </button>
      </NDropdown>
    </div>

    <div class="model-card__model-id">{{ item.llm_model_name }}</div>
    <div class="model-card__desc">{{ item.config_desc || '暂无描述' }}</div>

    <div class="model-card__footer">
      <span class="model-card__status" :class="item.is_default ? 'is-default' : 'is-normal'">
        <i class="model-card__status-dot" />
        {{ item.is_default ? '默认模型' : '普通配置' }}
      </span>
      <span class="model-card__meta">T {{ item.temperature }} · {{ item.max_tokens }} tokens</span>
    </div>
  </div>
</template>

<style scoped lang="scss">
.model-card {
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

.model-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.model-card__identity {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
}

.model-card__icon {
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

.model-card__title-wrap {
  min-width: 0;
}

.model-card__title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.4;
  word-break: break-all;
}

.model-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.model-card__tag {
  border-radius: 999px;
  font-size: 12px;
}

.model-card__tag--provider,
.model-card__tag--thinking {
  background: #f3f4f6 !important;
  color: #6b7280 !important;
}

.model-card__more {
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

.model-card__model-id {
  font-size: 13px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: #6b7280;
  word-break: break-all;
}

.model-card__desc {
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

.model-card__footer {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.model-card__status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;

  &.is-default {
    background: #ecfdf3;
    color: #16a34a;
  }

  &.is-normal {
    background: #f3f4f6;
    color: #6b7280;
  }
}

.model-card__status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.model-card__meta {
  padding: 4px 10px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #6b7280;
  font-size: 12px;
}
</style>

<style scoped lang="scss">
html.dark .model-card {
  background: #18181c;
  border-color: rgba(255, 255, 255, 0.1);
  box-shadow: none;
}

html.dark .model-card:hover {
  border-color: rgba(255, 255, 255, 0.16);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.28);
}

html.dark .model-card__title {
  color: #e5e7eb;
}

html.dark .model-card__model-id {
  color: #9ca3af;
}

html.dark .model-card__desc {
  color: #9ca3af;
}

html.dark .model-card__more {
  color: #cbd5e1;
}

html.dark .model-card__more:hover {
  color: #f8fafc;
  background: rgba(255, 255, 255, 0.1);
}

html.dark .model-card__tag--provider,
html.dark .model-card__tag--thinking {
  background: rgba(255, 255, 255, 0.08) !important;
  color: #cbd5e1 !important;
}

html.dark .model-card__status.is-default {
  background: rgba(34, 197, 94, 0.14);
  color: #4ade80;
}

html.dark .model-card__status.is-normal,
html.dark .model-card__meta {
  background: rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
}
</style>
