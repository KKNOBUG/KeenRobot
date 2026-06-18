const ICON_COLORS = [
  { bg: '#e8f1ff', color: '#3b82f6' },
  { bg: '#e8faf0', color: '#22c55e' },
  { bg: '#fff4e8', color: '#f59e0b' },
  { bg: '#f3e8ff', color: '#a855f7' },
]

export function getIconStyle(name = '', index = 0) {
  return ICON_COLORS[index % ICON_COLORS.length]
}

export function getDisplayIcon(item) {
  const name = item?.knowledge_name || 'K'
  return name.slice(0, 1).toUpperCase()
}

export function formatChunkSize(kb) {
  return kb?.chunk_size ? String(kb.chunk_size) : '500(默认)'
}

export function shortModelName(model) {
  if (!model) return '-'
  const parts = model.split('/')
  return parts[parts.length - 1]
}

export function statusTagType(status) {
  if (status === 'completed') return 'success'
  if (status === 'processing') return 'warning'
  if (status === 'failed') return 'error'
  return 'default'
}

export function statusLabel(status) {
  if (status === 'completed') return '已完成'
  if (status === 'processing') return '处理中'
  if (status === 'failed') return '失败'
  return status
}

export function fileTypeLabel(type) {
  const map = { pdf: 'PDF', txt: 'TXT', docx: 'Word' }
  return map[type] || type
}

export function emptyForm() {
  return {
    id: null,
    knowledge_name: '',
    description: '',
    is_public: false,
    chunk_size: null,
    chunk_overlap: null,
  }
}

export function rowToForm(row = {}) {
  return {
    id: row.id || null,
    knowledge_name: row.knowledge_name || '',
    description: row.description || '',
    is_public: !!row.is_public,
    chunk_size: row.chunk_size ?? null,
    chunk_overlap: row.chunk_overlap ?? null,
  }
}

export function formToPayload(form) {
  return {
    knowledge_name: form.knowledge_name?.trim(),
    description: form.description?.trim() || null,
    is_public: !!form.is_public,
    chunk_size: form.chunk_size ?? null,
    chunk_overlap: form.chunk_overlap ?? null,
  }
}
