export const TRANSPORT_OPTIONS = [
  { label: 'STDIO', value: 'stdio' },
  { label: 'SSE', value: 'sse' },
  { label: 'Streamable HTTP', value: 'http' },
]

export const CATEGORY_OPTIONS = [
  { label: '开发工具', value: '开发工具' },
  { label: '云服务', value: '云服务' },
  { label: '数据分析', value: '数据分析' },
  { label: '其他', value: '其他' },
]

const ICON_COLORS = [
  { bg: '#e8f1ff', color: '#3b82f6' },
  { bg: '#e8faf0', color: '#22c55e' },
  { bg: '#fff4e8', color: '#f59e0b' },
  { bg: '#f3e8ff', color: '#a855f7' },
]

export function transportLabel(value) {
  return TRANSPORT_OPTIONS.find((item) => item.value === value)?.label || value || 'STDIO'
}

export function transportTag(value) {
  const v = (value || 'stdio').toLowerCase()
  if (v === 'http' || v === 'sse') return 'HTTP'
  return v.toUpperCase()
}

export function getIconStyle(name = '', index = 0) {
  const palette = ICON_COLORS[index % ICON_COLORS.length]
  return palette
}

export function getDisplayIcon(item) {
  const icon = item?.config?.icon
  if (icon) return icon
  const name = item?.name || 'M'
  return name.slice(0, 1)
}

export function isEmojiIcon(icon) {
  return icon && icon.length <= 4 && /\p{Extended_Pictographic}/u.test(icon)
}

export function getToolCount(item) {
  const tools = item?.config?.tools
  return Array.isArray(tools) ? tools.length : 0
}

export function emptyForm() {
  return {
    id: null,
    name: '',
    description: '',
    transport: 'http',
    is_enabled: true,
    icon: '',
    category: '开发工具',
    service_url: '',
    config_text: '',
    tools: [],
  }
}

export function rowToForm(row = {}) {
  const config = row.config || {}
  return {
    id: row.id || null,
    name: row.name || '',
    description: row.description || '',
    transport: row.transport || 'http',
    is_enabled: row.is_enabled !== false,
    icon: config.icon || '',
    category: config.category || '开发工具',
    service_url: config.url || config.endpoint || config.service_url || '',
    config_text: config.command
      ? JSON.stringify(
          {
            command: config.command,
            args: config.args || [],
            env: config.env || undefined,
            cwd: config.cwd || undefined,
          },
          null,
          2,
        )
      : '',
    tools: Array.isArray(config.tools) ? config.tools : [],
  }
}

export function formToPayload(form) {
  const config = {
    icon: form.icon || undefined,
    category: form.category || undefined,
    tools: form.tools || [],
  }

  if (form.transport === 'stdio') {
    const trimmed = (form.config_text || '').trim()
    if (trimmed) {
      Object.assign(config, JSON.parse(trimmed))
    }
  } else {
    config.url = (form.service_url || '').trim() || undefined
  }

  Object.keys(config).forEach((key) => {
    if (config[key] === undefined) delete config[key]
  })

  return {
    name: form.name,
    description: form.description || null,
    transport: form.transport || 'stdio',
    is_enabled: !!form.is_enabled,
    config: Object.keys(config).length ? config : null,
  }
}
