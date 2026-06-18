export const PROVIDER_OPTIONS = [
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'OpenAI', value: 'openai' },
  { label: '智谱', value: 'zhipu' },
  { label: '通义千问', value: 'qwen' },
  { label: '自定义', value: 'custom' },
]

const ICON_COLORS = [
  { bg: '#e8f1ff', color: '#3b82f6' },
  { bg: '#e8faf0', color: '#22c55e' },
  { bg: '#fff4e8', color: '#f59e0b' },
  { bg: '#f3e8ff', color: '#a855f7' },
]

export const MAX_TOKEN_OPTIONS = [512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 128000]

export function snapMaxTokens(value) {
  if (MAX_TOKEN_OPTIONS.includes(value)) return value
  const target = Number(value) || 4096
  return MAX_TOKEN_OPTIONS.reduce((prev, cur) =>
    (Math.abs(cur - target) < Math.abs(prev - target) ? cur : prev),
  )
}

export function clampInt(value, min, max, fallback = min) {
  const num = Number.parseInt(value, 10)
  if (Number.isNaN(num)) return fallback
  return Math.min(max, Math.max(min, num))
}
export function providerLabel(value) {
  return PROVIDER_OPTIONS.find((item) => item.value === value)?.label || value || '自定义'
}

export function getIconStyle(name = '', index = 0) {
  return ICON_COLORS[index % ICON_COLORS.length]
}

export function getDisplayIcon(item) {
  const name = item?.config_name || item?.llm_model_name || 'M'
  return name.slice(0, 1).toUpperCase()
}

export function emptyForm() {
  return {
    id: null,
    config_name: '',
    config_desc: '',
    model_provider: null,
    llm_model_name: '',
    model_thinking: false,
    llm_base_url: '',
    llm_api_key: '',
    has_llm_api_key: false,
    temperature: 0.7,
    max_tokens: 4096,
    top_p: 0.95,
    system_prompt: '',
    top_k: 5,
    score_threshold: 0,
    max_history_rounds: 10,
    is_default: false,
  }
}

export function rowToForm(row = {}) {
  return {
    id: row.id || null,
    config_name: row.config_name || '',
    config_desc: row.config_desc || '',
    model_provider: row.model_provider || 'custom',
    llm_model_name: row.llm_model_name || '',
    model_thinking: !!row.model_thinking,
    llm_base_url: row.llm_base_url || '',
    llm_api_key: row.llm_api_key_masked || '',
    has_llm_api_key: !!row.has_llm_api_key,
    temperature: row.temperature ?? 0.7,
    max_tokens: snapMaxTokens(row.max_tokens),
    top_p: row.top_p ?? 0.95,
    system_prompt: row.system_prompt || '',
    top_k: clampInt(row.top_k, 0, 100, 5),
    score_threshold: row.score_threshold ?? 0,
    max_history_rounds: clampInt(row.max_history_rounds, 0, 20, 10),
    is_default: !!row.is_default,
  }
}

export function formToPayload(form, isUpdate = false) {
  const payload = {
    config_name: form.config_name,
    config_desc: form.config_desc || null,
    model_provider: form.model_provider,
    llm_model_name: form.llm_model_name,
    model_thinking: !!form.model_thinking,
    llm_base_url: form.llm_base_url?.trim() || null,
    temperature: form.temperature,
    max_tokens: form.max_tokens,
    top_p: form.top_p,
    system_prompt: form.system_prompt || null,
    top_k: form.top_k,
    score_threshold: form.score_threshold,
    max_history_rounds: form.max_history_rounds,
    is_default: !!form.is_default,
  }
  const apiKey = form.llm_api_key?.trim()
  if (apiKey && !apiKey.includes('***')) {
    payload.llm_api_key = apiKey
  } else if (!isUpdate && apiKey) {
    payload.llm_api_key = apiKey
  }
  return payload
}
