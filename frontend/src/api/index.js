import { request, getToken } from '@/utils'
import { handleUnauthorized, isUnauthorizedCode } from '@/utils/http/auth'

const API_BASE = import.meta.env.VITE_BASE_API || '/api'

function payload(res) {
  // 后端 SuccessResponse(data=null) 时 res.data 为 null；不能用 ??，否则会误返回整包响应
  if (res != null && typeof res === 'object' && Object.prototype.hasOwnProperty.call(res, 'data')) {
    return res.data
  }
  return res
}

function parseErrorDetail(detail) {
  if (!detail) return null
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message || String(item)).join('; ')
  }
  return String(detail)
}

export default {
  // 认证接口复用 /base/auth/* 路径（后端 user 模块统一认证）
  login: (data) => request.post('/base/auth/access_token', data, { noNeedToken: true }),
  register: (data) => request.post('/user/create', data, { noNeedToken: true }),
  getUserInfo: () => request.post('/base/auth/userinfo'),
  getUserMenu: () => request.post('/base/auth/usermenu'),
  getUserRouters: () => request.post('/base/auth/getUserRouters'),
  logout: () => request.post('/user/logout'),

  getUserList: (params = {}) => request.get('/user/list', { params }),
  getUserById: (params = {}) => request.get('/user/get', { params }),
  createUser: (data = {}) => request.post('/user/create', data),
  updateUser: (data = {}) => {
    const { id, user_id, roles, ...rest } = data
    return request.post('/user/update', { ...rest, user_id: user_id ?? id })
  },
  deleteUser: (params = {}) => request.delete('/user/delete', { params }),
  deleteUserBatch: (data = {}) => request.post('/user/deletes', data),
  resetPassword: (data = {}) => request.post('/user/reset_password', data),
  updatePassword: (data = {}) => request.post('/user/update_password', data),

  getRoleList: (params = {}) => request.get('/base/role/list', { params }),
  createRole: (data = {}) => request.post('/base/role/create', data),
  updateRole: (data = {}) => request.post('/base/role/update', data),
  deleteRole: (params = {}) => request.delete('/base/role/delete', { params }),
  deleteRoleBatch: (data = {}) => request.post('/base/role/deletes', data),
  updateRoleAuthorized: (data = {}) => request.post('/base/role/authorized', data),
  getRoleAuthorized: (params = {}) => request.get('/base/role/authorized', { params }),

  getMenus: (params = {}) => request.post('/base/menu/list', {}, { params }),
  createMenu: (data = {}) => request.post('/base/menu/create', data),
  updateMenu: (data = {}) => request.post('/base/menu/update', data),
  deleteMenu: (params = {}) => request.delete('/base/menu/delete', { params }),

  getRouters: (params = {}) => request.get('/base/router/list', { params }),
  createRouter: (data = {}) => request.post('/base/router/create', data),
  updateRouter: (data = {}) => request.post('/base/router/update', data),
  deleteRouter: (params = {}) => request.delete('/base/router/delete', { params }),
  refreshRouter: (data = {}) => request.post('/base/router/refresh', data),

  getAuditLogList: (params = {}) => request.get('/base/audit/list', { params }),
  deleteAuditLogBatch: (data = {}) => request.post('/base/audit/delete', data),

  fetchConversations: () => request.get('/conversations/').then(payload),
  createConversation: () => request.post('/conversations/').then(payload),
  fetchConversation: (id) => request.get(`/conversations/${id}`).then(payload),
  updateConversationBindings: (conversationId, data) =>
    request.put(`/conversations/${conversationId}/bindings`, data).then(payload),
  startSkillIntake: (conversationId, data) =>
    request.post(`/conversations/${conversationId}/skill-intake/start`, data).then(payload),
  updateSkillIntakeMessage: (conversationId, messageId, data) =>
    request.put(`/conversations/${conversationId}/messages/${messageId}/skill-intake`, data).then(payload),
  fetchActiveSkillDraft: (conversationId, skillId = null) => {
    const params = { conversation_id: conversationId }
    if (skillId) params.skill_id = skillId
    return request.get('/skill-runs/active-draft', { params }).then(payload)
  },
  deleteConversation: (id) => request.delete(`/conversations/${id}`).then(payload),

  fetchUserMemories: () => request.get('/chat/memories').then(payload),
  createUserMemory: (data) => request.post('/chat/memories', data).then(payload),
  deleteUserMemory: (id) => request.delete(`/chat/memories/${id}`).then(payload),

  fetchKnowledgeBases: (search = '') =>
      request
          .get(search ? `/knowledge-bases/?search=${encodeURIComponent(search)}` : '/knowledge-bases/')
          .then(payload),
  createKnowledgeBase: (data) => request.post('/knowledge-bases/', data).then(payload),
  updateKnowledgeBase: (id, data) => request.put(`/knowledge-bases/${id}`, data).then(payload),
  deleteKnowledgeBase: (id) => request.delete(`/knowledge-bases/${id}`).then(payload),
  fetchDocuments: (kbId) => request.get(`/knowledge-bases/${kbId}/documents`).then(payload),
  retryDocument: (kbId, docId) => request.post(`/knowledge-bases/${kbId}/documents/${docId}/retry`).then(payload),
  reindexKnowledgeBase: (kbId) => request.post(`/knowledge-bases/${kbId}/reindex`).then(payload),
  deleteDocument: (kbId, docId) => request.delete(`/knowledge-bases/${kbId}/documents/${docId}`).then(payload),
  fetchChunks: (kbId, docId) =>
      request.get(`/knowledge-bases/${kbId}/chunks?document_id=${docId}`).then(payload),

  fetchSkills: (search = '', manage = false) => {
    const params = new URLSearchParams()
    if (search) params.set('search', search)
    if (manage) params.set('manage', 'true')
    const qs = params.toString()
    return request.get(qs ? `/skills/?${qs}` : '/skills/').then(payload)
  },
  syncSkills: () => request.post('/skills/sync').then(payload),
  cleanupStaleSkillDrafts: (data = {}) =>
    request.post('/skills/cleanup-stale-drafts', data).then(payload),
  uploadSkillZip: (file, { skillKey, overwrite } = {}) => {
    const form = new FormData()
    form.append('file', file)
    if (skillKey) form.append('skill_key', skillKey)
    if (overwrite) form.append('overwrite', 'true')
    return request.post('/skills/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(payload)
  },
  fetchSkill: (id) => request.get(`/skills/${id}`).then(payload),
  previewSkill: (id) => request.get(`/skills/${id}/preview`).then(payload),
  createSkill: (data) => request.post('/skills/', data).then(payload),
  updateSkill: (id, data) => request.put(`/skills/${id}`, data).then(payload),
  deleteSkill: (id) => request.delete(`/skills/${id}`).then(payload),

  createSkillRun: (data) => request.post('/skill-runs/', data).then(payload),
  searchSkillRuns: (params = {}) =>
    request.get('/skill-runs/search', { params }).then((res) => ({
      data: res?.data ?? [],
      total: res?.total ?? 0,
    })),
  fetchSkillRun: (id) => request.get(`/skill-runs/${id}`).then(payload),
  saveSkillRunInputs: (id, fields) =>
    request.post(`/skill-runs/${id}/inputs`, { fields }).then(payload),
  uploadSkillRunFile: (id, key, file) => {
    const form = new FormData()
    form.append('key', key)
    form.append('file', file)
    return request.post(`/skill-runs/${id}/files`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(payload)
  },
  validateSkillRun: (id) => request.post(`/skill-runs/${id}/validate`).then(payload),
  startSkillRun: (id, question) =>
    request.post(`/skill-runs/${id}/start`, question ? { question } : {}).then(payload),
  cancelSkillRun: (id) => request.post(`/skill-runs/${id}/cancel`).then(payload),
  retrySkillRun: (id) => request.post(`/skill-runs/${id}/retry`).then(payload),
  deleteSkillRun: (id) => request.delete(`/skill-runs/${id}`).then(payload),
  cleanupSkillRuns: (data = {}) =>
    request.post('/skill-runs/cleanup', data).then(payload),
  fetchSkillRunOutputs: (id) => request.get(`/skill-runs/${id}/outputs`).then(payload),
  downloadSkillRunOutput: (id, filePath) =>
    `${API_BASE}/skill-runs/${id}/outputs/${encodeURIComponent(filePath)}`,

  fetchMcpServers: (search = '', manage = false) => {
    const params = new URLSearchParams()
    if (search) params.set('search', search)
    if (manage) params.set('manage', 'true')
    const qs = params.toString()
    return request.get(qs ? `/mcp-servers/?${qs}` : '/mcp-servers/').then(payload)
  },
  createMcpServer: (data) => request.post('/mcp-servers/', data).then(payload),
  updateMcpServer: (id, data) => request.put(`/mcp-servers/${id}`, data).then(payload),
  deleteMcpServer: (id) => request.delete(`/mcp-servers/${id}`).then(payload),
  fetchMcpServer: (id) => request.get(`/mcp-servers/${id}`).then(payload),
  refreshMcpTools: (id) => request.post(`/mcp-servers/${id}/tools/refresh`).then(payload),
  syncMcpServer: (id) => request.post(`/mcp-servers/${id}/sync`).then(payload),
  diagnoseMcpServer: (id) => request.post(`/mcp-servers/${id}/diagnose`).then(payload),
  searchMcpAuditLogs: (body) =>
    request.post('/mcp-servers/audit/search', body).then((res) => ({
      items: payload(res) || [],
      total: res?.total ?? 0,
    })),

  fetchModelConfigs: () => request.get('/model-configs/').then(payload),
  createModelConfig: (data) => request.post('/model-configs/', data).then(payload),
  updateModelConfig: (id, data) => request.put(`/model-configs/${id}`, data).then(payload),
  deleteModelConfig: (id) => request.delete(`/model-configs/${id}`).then(payload),
  setDefaultModelConfig: (id) => request.post(`/model-configs/${id}/default`).then(payload),

  fetchTaskCenterPresets: () => request.get('/task-center/presets').then((res) => res?.data ?? res),
  searchTasks: (data) =>
      request.post('/task-center/search', data).then((res) => ({
        data: res?.data ?? [],
        total: res?.total ?? 0,
      })),
  createTask: (data) => request.post('/task-center/create', data).then(payload),
  updateTask: (data) => request.post('/task-center/update', data).then(payload),
  deleteTask: (params) => request.delete('/task-center/delete', { params }).then(payload),
  getTask: (params) => request.get('/task-center/get', { params }).then(payload),
  /** Form：task_id */
  runTask: (formData) => request.post('/task-center/run', formData).then(payload),
  /** Form：task_id */
  startTask: (formData) => request.post('/task-center/start', formData).then(payload),
  /** Form：task_id */
  stopTask: (formData) => request.post('/task-center/stop', formData).then(payload),
  searchTaskRecords: (data) =>
      request.post('/task-center/record/search', data).then((res) => ({
        data: res?.data ?? [],
        total: res?.total ?? 0,
      })),
}

export async function uploadDocument(kbId, file) {
  const token = getToken()
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${API_BASE}/knowledge-bases/${kbId}/documents`, {
    method: 'POST',
    headers: token ? { token } : {},
    body: formData,
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({}))
    throw new Error(error.message || parseErrorDetail(error.detail) || '上传失败')
  }

  const body = await res.json()
  if (isUnauthorizedCode(body?.code)) {
    await handleUnauthorized()
    throw new Error(body?.message || '登录已过期')
  }
  if (body?.code !== '000000' || body?.status !== 'success') {
    throw new Error(body?.message || '上传失败')
  }
  return body.data ?? body
}

export function chatStream(
    question,
    conversationId,
    knowledgeBaseIds = [],
    modelConfigId = null,
    enableThinking = false,
    skillIds = null,
    mcpIds = [],
    { onToken, onReasoning, onMeta, onProcess, onDone, onError, onRetrievalEmpty, onSources }
) {
  const controller = new AbortController()
  const token = getToken()

  const payload = {
    question,
    conversation_id: conversationId,
    knowledge_base_ids: knowledgeBaseIds,
    model_config_id: modelConfigId,
    enable_thinking: enableThinking,
    mcp_ids: mcpIds,
  }
  if (skillIds !== null) {
    payload.skill_ids = skillIds
  }

  fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      token,
    },
    body: JSON.stringify(payload),
    signal: controller.signal,
  })
      .then(async (response) => {
        const contentType = response.headers.get('content-type') || ''
        if (contentType.includes('application/json')) {
          const body = await response.json().catch(() => ({}))
          if (isUnauthorizedCode(body?.code)) {
            await handleUnauthorized()
            throw new Error(body?.message || '登录已过期')
          }
          throw new Error(body?.message || parseErrorDetail(body.detail) || '请求失败')
        }

        if (!response.ok) {
          const error = await response.json().catch(() => ({}))
          if (isUnauthorizedCode(error?.code)) {
            await handleUnauthorized()
          }
          throw new Error(parseErrorDetail(error.detail) || error.message || '请求失败')
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let eventType = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop()

          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim()
            } else if (line.startsWith('data:')) {
              const dataStr = line.slice(5).trim()
              if (!dataStr) continue
              try {
                const data = JSON.parse(dataStr)
                if (eventType === 'token' && onToken) onToken(data.content)
                else if (eventType === 'reasoning' && onReasoning) onReasoning(data.content)
                else if (eventType === 'meta' && onMeta) onMeta(data)
                else if (eventType === 'process' && onProcess) onProcess(data)
                else if (eventType === 'retrieval_empty' && onRetrievalEmpty) onRetrievalEmpty(data)
                else if (eventType === 'sources' && onSources) onSources(data)
                else if (eventType === 'done' && onDone) onDone(data)
                else if (eventType === 'error' && onError) onError(new Error(data.message))
              } catch {
                // ignore parse errors
              }
            }
          }
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError' && onError) onError(err)
      })

  return { abort: () => controller.abort() }
}

export function skillRunStream(
    runId,
    { onToken, onReasoning, onMeta, onProcess, onDone, onError },
) {
  const controller = new AbortController()
  const token = getToken()

  fetch(`${API_BASE}/skill-runs/${runId}/stream`, {
    method: 'GET',
    headers: token ? { token } : {},
    signal: controller.signal,
  })
      .then(async (response) => {
        const contentType = response.headers.get('content-type') || ''
        if (contentType.includes('application/json')) {
          const body = await response.json().catch(() => ({}))
          if (isUnauthorizedCode(body?.code)) {
            await handleUnauthorized()
            throw new Error(body?.message || '登录已过期')
          }
          throw new Error(body?.message || parseErrorDetail(body.detail) || '请求失败')
        }

        if (!response.ok) {
          const error = await response.json().catch(() => ({}))
          if (isUnauthorizedCode(error?.code)) {
            await handleUnauthorized()
          }
          throw new Error(parseErrorDetail(error.detail) || error.message || '请求失败')
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let eventType = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop()

          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim()
            } else if (line.startsWith('data:')) {
              const dataStr = line.slice(5).trim()
              if (!dataStr) continue
              try {
                const data = JSON.parse(dataStr)
                if (eventType === 'token' && onToken) onToken(data.content)
                else if (eventType === 'reasoning' && onReasoning) onReasoning(data.content)
                else if (eventType === 'meta' && onMeta) onMeta(data)
                else if (eventType === 'process' && onProcess) onProcess(data)
                else if (eventType === 'done' && onDone) onDone(data)
                else if (eventType === 'error' && onError) onError(new Error(data.message))
              } catch {
                // ignore parse errors
              }
            }
          }
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError' && onError) onError(err)
      })

  return { abort: () => controller.abort() }
}
