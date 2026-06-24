export const INTERACTION_MODE_OPTIONS = [
  { label: '直接聊天 (chat)', value: 'chat' },
  { label: '向导 (wizard)', value: 'wizard' },
  { label: '异步任务 (async_job)', value: 'async_job' },
]

export const MODE_LABELS = {
  chat: '直接聊天',
  wizard: '向导',
  async_job: '异步任务',
}

export const MODE_TAG_TYPE = {
  chat: 'success',
  wizard: 'info',
  async_job: 'warning',
}

const DEFAULT_INPUT_SCHEMA = {
  wizard_steps: [],
  layout: {
    cwd: '.',
    input_root: 'input',
    output_root: 'output',
  },
}

const DEFAULT_EXECUTION = {
  prefer_async: false,
  estimated_duration: 'medium',
}

export function jsonToText(value) {
  if (value == null) return ''
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return ''
  }
}

export function parseJsonText(text, fieldName = 'JSON') {
  const trimmed = (text || '').trim()
  if (!trimmed) return null
  try {
    return JSON.parse(trimmed)
  } catch {
    throw new Error(`${fieldName} 须为合法 JSON`)
  }
}

export function stripExecutionForText(execution = {}) {
  const { mcp_ids: _omit, ...rest } = execution || {}
  return rest
}

export function emptyForm() {
  return {
    id: '',
    skill_key: '',
    name: '',
    description: '',
    skill_version: '',
    interaction_mode: 'chat',
    is_enabled: false,
    execution_mcp_ids: [],
    input_schema_text: jsonToText(DEFAULT_INPUT_SCHEMA),
    execution_text: jsonToText(DEFAULT_EXECUTION),
  }
}

export function rowToForm(record = {}) {
  const execution = record.execution || DEFAULT_EXECUTION
  return {
    id: record.id || '',
    skill_key: record.skill_key || '',
    name: record.name || '',
    description: record.description || '',
    skill_version: record.skill_version || '',
    interaction_mode: record.interaction_mode || 'chat',
    is_enabled: !!record.is_enabled,
    execution_mcp_ids: Array.isArray(execution.mcp_ids) ? [...execution.mcp_ids] : [],
    input_schema_text: jsonToText(record.input_schema || DEFAULT_INPUT_SCHEMA),
    execution_text: jsonToText(stripExecutionForText(execution) || DEFAULT_EXECUTION),
  }
}

export function formToPayload(form) {
  const mode = form.interaction_mode || 'chat'
  const execution = parseJsonText(form.execution_text, 'execution') || {}
  execution.mcp_ids = Array.isArray(form.execution_mcp_ids)
    ? form.execution_mcp_ids.filter(Boolean)
    : []
  const payload = {
    interaction_mode: mode,
    is_enabled: !!form.is_enabled,
    execution,
  }
  if (mode === 'wizard' || mode === 'async_job') {
    payload.input_schema = parseJsonText(form.input_schema_text, 'input_schema')
  } else {
    const schema = parseJsonText(form.input_schema_text, 'input_schema')
    payload.input_schema = schema
  }
  return payload
}

export function getModeLabel(mode) {
  return MODE_LABELS[mode] || mode || '未知'
}

export function getIconStyle(name = '', index = 0) {
  const palette = [
    { bg: '#e8f1ff', color: '#3b82f6' },
    { bg: '#e8faf0', color: '#22c55e' },
    { bg: '#fff4e8', color: '#f59e0b' },
    { bg: '#f3e8ff', color: '#a855f7' },
  ]
  const seed = (name || '').split('').reduce((acc, ch) => acc + ch.charCodeAt(0), index)
  return palette[seed % palette.length]
}
