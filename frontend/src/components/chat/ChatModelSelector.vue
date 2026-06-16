<script setup>
import { computed, ref, watch } from 'vue'
import { NPopover } from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'

const props = defineProps({
  modelValue: {
    type: [String, Number],
    default: '',
  },
  items: {
    type: Array,
    default: () => [],
  },
  disabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue'])

const showPopover = ref(false)
const searchText = ref('')

const selectedItem = computed(() =>
    props.items.find((item) => item.id === props.modelValue) || null,
)

const triggerLabel = computed(() => selectedItem.value?.label || '选择模型')

const triggerTitle = computed(() => {
  if (!selectedItem.value) return '选择模型'
  const { label, sublabel } = selectedItem.value
  return sublabel ? `${label} · ${sublabel}` : label
})

const filteredItems = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  if (!keyword) return props.items
  return props.items.filter((item) =>
      (item.label || '').toLowerCase().includes(keyword)
      || (item.sublabel || '').toLowerCase().includes(keyword),
  )
})

function selectItem(id) {
  emit('update:modelValue', id)
  showPopover.value = false
}

watch(showPopover, (visible) => {
  if (!visible) {
    searchText.value = ''
  }
})
</script>

<template>
  <NPopover
      v-model:show="showPopover"
      trigger="click"
      placement="top-end"
      :show-arrow="true"
      raw
      :disabled="disabled || items.length === 0"
  >
    <template #trigger>
      <button
          type="button"
          class="chat-model-trigger"
          :class="{ 'is-open': showPopover }"
          :disabled="disabled || items.length === 0"
          :title="triggerTitle"
      >
        <span class="chat-model-trigger-label">{{ triggerLabel }}</span>
        <TheIcon
            icon="material-symbols:keyboard-arrow-down-rounded"
            :size="16"
            class="chat-model-trigger-icon"
        />
      </button>
    </template>

    <div class="chat-model-panel">
      <div class="chat-model-search">
        <TheIcon icon="material-symbols:search" :size="16" color="var(--chat-muted-text)" />
        <input
            v-model="searchText"
            class="chat-model-search-input"
            type="text"
            placeholder="搜索模型..."
            @click.stop
        />
      </div>

      <div v-if="filteredItems.length > 0" class="chat-model-list">
        <button
            v-for="item in filteredItems"
            :key="item.id"
            type="button"
            class="chat-model-item"
            :class="{ 'is-selected': item.id === modelValue }"
            @click="selectItem(item.id)"
        >
          <div class="chat-model-item-body">
            <span class="chat-model-item-name">{{ item.label }}</span>
            <span v-if="item.sublabel" class="chat-model-item-sublabel">{{ item.sublabel }}</span>
          </div>
          <TheIcon
              v-if="item.id === modelValue"
              icon="material-symbols:check"
              :size="18"
              class="chat-model-item-check"
          />
        </button>
      </div>

      <div v-else class="chat-model-empty">
        {{ searchText.trim() ? '未找到匹配的模型' : '暂无可用模型' }}
      </div>
    </div>
  </NPopover>
</template>

<style scoped>
.chat-model-trigger {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 72px;
  max-width: 180px;
  height: 28px;
  padding: 0 24px;
  border: none;
  border-radius: 999px;
  background: color-mix(in srgb, #4f6ef7 10%, #fff);
  color: #4f6ef7;
  flex-shrink: 0;
  cursor: pointer;
  transition: background-color 0.2s, box-shadow 0.2s;
}

.chat-model-trigger:hover:not(:disabled) {
  background: color-mix(in srgb, #4f6ef7 16%, #fff);
}

.chat-model-trigger.is-open {
  background: color-mix(in srgb, #4f6ef7 18%, #fff);
}

.chat-model-trigger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-model-trigger-label {
  min-width: 0;
  max-width: 100%;
  font-size: 12px;
  font-weight: 500;
  line-height: 28px;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-model-trigger-icon {
  position: absolute;
  right: 6px;
  top: 50%;
  flex-shrink: 0;
  color: #4f6ef7;
  transform: translateY(-50%);
  transition: transform 0.2s;
}

.chat-model-trigger.is-open .chat-model-trigger-icon {
  transform: translateY(-50%) rotate(180deg);
}

.chat-model-panel {
  width: 280px;
  padding: 12px;
  border-radius: 12px;
  background: var(--chat-input-surface, #fff);
  border: 1px solid var(--chat-input-border, #e8e8e8);
  box-shadow: var(--chat-input-shadow, 0 8px 24px rgba(0, 0, 0, 0.12));
}

.chat-model-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--chat-input-border, #e8e8e8);
  border-radius: 8px;
  background: var(--chat-input-surface, #fff);
}

.chat-model-search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: var(--n-text-color, #333);
}

.chat-model-search-input::placeholder {
  color: var(--chat-muted-text, #a3a3a3);
}

.chat-model-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 240px;
  margin-top: 10px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #ccc transparent;
}

.chat-model-list::-webkit-scrollbar {
  width: 5px;
}

.chat-model-list::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 3px;
}

.chat-model-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.2s;
}

.chat-model-item:hover {
  background: color-mix(in srgb, #4f6ef7 6%, var(--chat-input-surface, #fff));
}

.chat-model-item.is-selected {
  background: color-mix(in srgb, #4f6ef7 10%, var(--chat-input-surface, #fff));
}

.chat-model-item-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chat-model-item-name {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.3;
  color: var(--n-text-color, #333);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-model-item.is-selected .chat-model-item-name {
  color: #4f6ef7;
}

.chat-model-item-sublabel {
  font-size: 11px;
  line-height: 1.2;
  color: var(--chat-muted-text, #a3a3a3);
}

.chat-model-item-check {
  flex-shrink: 0;
  color: #4f6ef7;
}

.chat-model-empty {
  margin-top: 10px;
  padding: 24px 10px;
  text-align: center;
  font-size: 12px;
  color: var(--n-text-color-3, #999);
}

:global(html.dark) .chat-model-trigger {
  background: color-mix(in srgb, #4f6ef7 18%, #1f1f1f);
  color: #8ea0ff;
}

:global(html.dark) .chat-model-trigger:hover:not(:disabled),
:global(html.dark) .chat-model-trigger.is-open {
  background: color-mix(in srgb, #4f6ef7 24%, #1f1f1f);
}

:global(html.dark) .chat-model-item.is-selected .chat-model-item-name,
:global(html.dark) .chat-model-item-check,
:global(html.dark) .chat-model-trigger-icon {
  color: #8ea0ff;
}
</style>
