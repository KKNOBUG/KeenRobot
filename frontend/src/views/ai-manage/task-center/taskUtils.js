export const KWARGS_PLACEHOLDER =
  '{"write_number":100,"write_message":"测试文本：通过Celery异步执行函数..."}'

export function configToText(obj) {
  if (!obj) return '{}'
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return '{}'
  }
}

export function parseConfigText(text) {
  const trimmed = (text || '').trim()
  if (!trimmed) return {}
  return JSON.parse(trimmed)
}

export function emptyForm() {
  return {
    task_id: null,
    task_name: '',
    task_desc: '',
    task_type: '',
    task_celery_node: '',
    task_kwargs_text: '{}',
    task_celery_scheduler: null,
    task_interval_expr: 300,
    task_datetime_expr: '',
    task_crontabs_expr: '',
    task_enabled: false,
    preset_key: null,
    write_number: 100,
    write_message: '测试文本：通过Celery异步执行函数...',
  }
}

export function rowToForm(row = {}) {
  return {
    task_id: row.task_id ?? row.id ?? null,
    task_name: row.task_name || '',
    task_desc: row.task_desc || '',
    task_type: row.task_type || '',
    task_celery_node: row.task_celery_node || '',
    task_kwargs_text: configToText(row.task_kwargs),
    task_celery_scheduler: row.task_celery_scheduler || null,
    task_interval_expr: row.task_interval_expr ?? 300,
    task_datetime_expr: row.task_datetime_expr || '',
    task_crontabs_expr: row.task_crontabs_expr || '',
    task_enabled: !!row.task_enabled,
    preset_key: null,
    write_number: row.task_kwargs?.write_number ?? 100,
    write_message: row.task_kwargs?.write_message || '测试文本：通过Celery异步执行函数...',
  }
}

export function isExamplePreset(form) {
  return form?.preset_key === 'example' || form?.task_type === 'example'
}

export function applyPresetToForm(form, preset) {
  if (!preset) return form
  const kwargs = { ...(preset.task_kwargs || {}) }
  return {
    ...form,
    preset_key: preset.preset_key,
    task_name: preset.task_name,
    task_desc: preset.task_desc || '',
    task_type: preset.task_type,
    task_celery_node: preset.task_celery_node,
    task_kwargs_text: configToText(kwargs),
    write_number: kwargs.write_number ?? 100,
    write_message: kwargs.write_message || '测试文本：通过Celery异步执行函数...',
  }
}

export function syncKwargField(form, key, value) {
  if (!form.task_kwargs_text) return form
  try {
    const kwargs = parseConfigText(form.task_kwargs_text)
    if (key in kwargs) {
      kwargs[key] = value
      return { ...form, task_kwargs_text: configToText(kwargs) }
    }
  } catch {
    // ignore invalid json while typing
  }
  return form
}

export function formToPayload(form, isUpdate = false) {
  const kwargs = parseConfigText(form.task_kwargs_text)
  if (isExamplePreset(form)) {
    kwargs.write_number = form.write_number ?? 100
    if (form.write_message) {
      kwargs.write_message = form.write_message
    }
    delete kwargs.user_id
  }
  const payload = {
    task_name: form.task_name,
    task_desc: form.task_desc || null,
    task_type: form.task_type || null,
    task_celery_node: form.task_celery_node || null,
    task_kwargs: kwargs,
    task_celery_scheduler: form.task_celery_scheduler || null,
    task_interval_expr: form.task_celery_scheduler === 'interval' ? form.task_interval_expr : null,
    task_datetime_expr: form.task_celery_scheduler === 'datetime' ? form.task_datetime_expr : null,
    task_crontabs_expr: form.task_celery_scheduler === 'cron' ? form.task_crontabs_expr : null,
    task_enabled: !!form.task_enabled,
  }
  if (isUpdate) {
    payload.task_id = form.task_id
  }
  return payload
}

export function validateKwargs(_rule, value) {
  if (!value?.trim()) return true
  try {
    JSON.parse(value)
    return true
  } catch {
    return new Error('参数须为合法 JSON')
  }
}
