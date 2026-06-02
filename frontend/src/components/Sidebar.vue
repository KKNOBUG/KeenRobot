<script setup>
import { defineProps, defineEmits } from 'vue'
import { deleteConversation } from '../api/index.js'

const props = defineProps({
  conversations: Array,
  activeId: String,
  collapsed: Boolean,
})

const emit = defineEmits(['select', 'new-chat', 'deleted', 'toggle'])

function formatDate(dateStr) {
  // 处理无时区的ISO格式时间（SQLite返回的UTC时间）
  // 如果日期字符串不包含时区信息，假设它是UTC时间并转换为本地时间
  let d
  if (dateStr.includes('Z') || dateStr.includes('+')) {
    // 已包含时区信息
    d = new Date(dateStr)
  } else {
    // 无时区信息，假设为UTC时间，添加Z后缀后解析
    d = new Date(dateStr + 'Z')
  }
  
  // 检查日期是否有效
  if (isNaN(d.getTime())) {
    return '未知时间'
  }
  
  const now = new Date()
  const diff = now - d
  
  // 如果时间是未来的（可能是时区问题），显示刚刚
  if (diff < 0) return '刚刚'
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`
  return d.toLocaleDateString('zh-CN')
}

async function handleDelete(e, id) {
  e.stopPropagation()
  if (!confirm('确定删除这个对话吗？')) return
  await deleteConversation(id)
  emit('deleted')
}
</script>

<template>
  <aside class="sidebar" :class="{ collapsed }">
    <div class="sidebar-header">
      <button class="toggle-btn" @click="emit('toggle')" :title="collapsed ? '展开侧栏' : '收起侧栏'">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M3 12h18M3 6h18M3 18h18"/>
        </svg>
      </button>
      <span v-if="!collapsed" class="sidebar-title">历史对话</span>
    </div>

    <button v-if="!collapsed" class="new-chat-btn" @click="emit('new-chat')">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 5v14M5 12h14"/>
      </svg>
      新对话
    </button>

    <div v-if="!collapsed" class="conversation-list">
      <div
        v-for="conv in conversations"
        :key="conv.id"
        class="conversation-item"
        :class="{ active: conv.id === activeId }"
        @click="emit('select', conv.id)"
      >
        <div class="conv-info">
          <div class="conv-title">{{ conv.title }}</div>
          <div class="conv-time">{{ formatDate(conv.updated_at) }}</div>
        </div>
        <button class="delete-btn" @click="handleDelete($event, conv.id)" title="删除对话">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>
          </svg>
        </button>
      </div>
      <div v-if="conversations.length === 0" class="empty-hint">
        暂无对话记录
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  min-width: var(--sidebar-width);
  height: 100%;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  transition: width var(--transition), min-width var(--transition);
  overflow: hidden;
}
.sidebar.collapsed {
  width: 56px;
  min-width: 56px;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid var(--border-light);
}
.sidebar-title {
  font-weight: 600;
  font-size: 15px;
  color: var(--text);
  white-space: nowrap;
}
.toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  transition: all var(--transition);
  flex-shrink: 0;
}
.toggle-btn:hover {
  background: var(--border-light);
  color: var(--text);
}

.new-chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin: 12px 16px;
  padding: 10px;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: white;
  font-weight: 500;
  font-size: 14px;
  transition: all var(--transition);
}
.new-chat-btn:hover {
  background: var(--primary-light);
  box-shadow: var(--shadow);
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conversation-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition);
  margin-bottom: 2px;
}
.conversation-item:hover {
  background: var(--border-light);
}
.conversation-item.active {
  background: var(--primary-bg);
}

.conv-info {
  flex: 1;
  min-width: 0;
}
.conv-title {
  font-size: 13.5px;
  font-weight: 500;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.conv-time {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

.delete-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  color: var(--text-muted);
  opacity: 0;
  transition: all var(--transition);
  flex-shrink: 0;
}
.conversation-item:hover .delete-btn {
  opacity: 1;
}
.delete-btn:hover {
  background: #fee2e2;
  color: var(--danger);
}

.empty-hint {
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  padding: 32px 16px;
}
</style>
