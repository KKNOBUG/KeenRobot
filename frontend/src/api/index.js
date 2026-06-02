const API_BASE = '/api'

// 获取token
function getToken() {
  return localStorage.getItem('token')
}

// 通用请求封装
async function request(url, options = {}) {
  const token = getToken()
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  }
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers,
  })

  if (res.status === 401) {
    localStorage.removeItem('token')
    window.location.href = '/login'
    throw new Error('登录已过期')
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: '请求失败' }))
    throw new Error(error.detail || '请求失败')
  }

  return res.json()
}

// ========== 认证 ==========

export async function login(username, password) {
  return request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export async function register(username, email, password) {
  return request('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, email, password }),
  })
}

export async function getMe() {
  return request('/auth/me')
}

// ========== 对话历史 ==========

export async function fetchConversations() {
  return request('/conversations/')
}

export async function fetchConversation(id) {
  return request(`/conversations/${id}`)
}

export async function deleteConversation(id) {
  return request(`/conversations/${id}`, { method: 'DELETE' })
}

// ========== 知识库 ==========

export async function fetchKnowledgeBases(search = '') {
  const url = search ? `/knowledge-bases/?search=${encodeURIComponent(search)}` : '/knowledge-bases/'
  return request(url)
}

export async function createKnowledgeBase(data) {
  return request('/knowledge-bases/', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function deleteKnowledgeBase(id) {
  return request(`/knowledge-bases/${id}`, { method: 'DELETE' })
}

export async function fetchDocuments(kbId) {
  return request(`/knowledge-bases/${kbId}/documents`)
}

export async function uploadDocument(kbId, file) {
  const token = getToken()
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${API_BASE}/knowledge-bases/${kbId}/documents`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
    body: formData,
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: '上传失败' }))
    throw new Error(error.detail || '上传失败')
  }

  return res.json()
}

export async function deleteDocument(kbId, docId) {
  return request(`/knowledge-bases/${kbId}/documents/${docId}`, { method: 'DELETE' })
}

export async function fetchChunks(kbId, docId) {
  return request(`/knowledge-bases/${kbId}/chunks?doc_id=${docId}`)
}

// ========== 模型配置 ==========

export async function fetchModelConfigs() {
  return request('/model-configs/')
}

export async function createModelConfig(data) {
  return request('/model-configs/', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateModelConfig(id, data) {
  return request(`/model-configs/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteModelConfig(id) {
  return request(`/model-configs/${id}`, { method: 'DELETE' })
}

// ========== 聊天 ==========

export function chatStream(
  question,
  conversationId,
  kbIds = [],
  modelConfigId = null,
  { onToken, onMeta, onDone, onError }
) {
  const controller = new AbortController()
  const token = getToken()

  fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({
      question,
      conversation_id: conversationId,
      kb_ids: kbIds,
      model_config_id: modelConfigId,
    }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: '请求失败' }))
        throw new Error(error.detail || '请求失败')
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
              else if (eventType === 'meta' && onMeta) onMeta(data)
              else if (eventType === 'done' && onDone) onDone(data.content)
              else if (eventType === 'error' && onError) onError(new Error(data.message))
            } catch {
              // 忽略解析错误
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
