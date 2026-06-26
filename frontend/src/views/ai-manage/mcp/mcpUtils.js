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

/** 从 MCP 工具的 input_schema 解析参数列表 */
export function getToolParams(tool) {
  const schema = tool?.input_schema || tool?.inputSchema || {}
  const properties = schema.properties || {}
  const required = new Set(schema.required || [])

  return Object.entries(properties).map(([name, meta]) => ({
    name,
    type: meta?.type || meta?.format || 'string',
    description: meta?.description || '',
    required: required.has(name),
  }))
}

export function hasToolParams(tool) {
  return getToolParams(tool).length > 0
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
    resources: [],
    prompts: [],
    instructions: '',
  }
}

export function rowToForm(row = {}) {
  const config = row.config || {}
  const stdio = config.stdio || {}
  const stdioSource = stdio.command ? stdio : config
  return {
    id: row.id || null,
    name: row.name || '',
    description: row.description || '',
    transport: row.transport || 'http',
    is_enabled: row.is_enabled !== false,
    icon: config.icon || '',
    category: config.category || '开发工具',
    service_url: config.url || config.endpoint || config.service_url || '',
    config_text: stdioSource.command
      ? JSON.stringify(
          {
            command: stdioSource.command,
            args: stdioSource.args || [],
            env: stdioSource.env || undefined,
            cwd: stdioSource.cwd || undefined,
          },
          null,
          2,
        )
      : '',
    tools: Array.isArray(config.tools) ? config.tools : [],
    resources: Array.isArray(config.resources) ? config.resources : [],
    prompts: Array.isArray(config.prompts) ? config.prompts : [],
    instructions: config.instructions || '',
  }
}

export function formToPayload(form) {
  const config = {
    icon: form.icon || undefined,
    category: form.category || undefined,
    tools: form.tools || [],
  }
  if (form.instructions) config.instructions = form.instructions
  if (form.resources?.length) config.resources = form.resources
  if (form.prompts?.length) config.prompts = form.prompts

  if (form.transport === 'stdio') {
    const trimmed = (form.config_text || '').trim()
    if (trimmed) {
      config.stdio = JSON.parse(trimmed)
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
