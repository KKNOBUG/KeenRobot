<script setup>
defineOptions({ name: 'KnowledgeBase' })

import { ref, onMounted } from 'vue'
import {
  NButton,
  NCheckbox,
  NEmpty,
  NInput,
  NInputNumber,
  NModal,
  NPopconfirm,
  NTag,
  NUpload,
  NUploadDragger,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import api, { uploadDocument } from '@/api'

const knowledgeBases = ref([])
const selectedKB = ref(null)
const documents = ref([])
const chunks = ref([])
const loading = ref(false)
const showCreateModal = ref(false)
const showUploadModal = ref(false)
const showChunksModal = ref(false)

const newKB = ref({
  knowledge_name: '',
  description: '',
  is_public: false,
  chunk_size: null,
  chunk_overlap: null,
})
const uploadFile = ref(null)

onMounted(async () => {
  await loadKnowledgeBases()
})

async function loadKnowledgeBases() {
  loading.value = true
  try {
    knowledgeBases.value = await api.fetchKnowledgeBases()
  } finally {
    loading.value = false
  }
}

async function handleCreateKB() {
  if (!newKB.value.knowledge_name.trim()) {
    window.$message?.warning('请输入知识库名称')
    return
  }
  try {
    await api.createKnowledgeBase(newKB.value)
    showCreateModal.value = false
    newKB.value = {
      knowledge_name: '',
      description: '',
      is_public: false,
      chunk_size: null,
      chunk_overlap: null,
    }
    window.$message?.success('知识库创建成功')
    await loadKnowledgeBases()
  } catch (err) {
    window.$message?.error('创建失败: ' + err.message)
  }
}

async function handleDeleteKB(id) {
  try {
    await api.deleteKnowledgeBase(id)
    if (selectedKB.value?.id === id) {
      selectedKB.value = null
      documents.value = []
    }
    window.$message?.success('知识库已删除')
    await loadKnowledgeBases()
  } catch (err) {
    window.$message?.error('删除失败: ' + err.message)
  }
}

async function selectKB(kb) {
  selectedKB.value = kb
  documents.value = await api.fetchDocuments(kb.id)
}

async function handleUpload() {
  if (!uploadFile.value) return
  try {
    await uploadDocument(selectedKB.value.id, uploadFile.value)
    showUploadModal.value = false
    uploadFile.value = null
    window.$message?.success('文档上传成功')
    documents.value = await api.fetchDocuments(selectedKB.value.id)
  } catch (err) {
    window.$message?.error('上传失败: ' + err.message)
  }
}

async function handleDeleteDoc(docId) {
  try {
    await api.deleteDocument(selectedKB.value.id, docId)
    window.$message?.success('文档已删除')
    documents.value = await api.fetchDocuments(selectedKB.value.id)
  } catch (err) {
    window.$message?.error('删除失败: ' + err.message)
  }
}

async function viewChunks(doc) {
  chunks.value = await api.fetchChunks(selectedKB.value.id, doc.id)
  showChunksModal.value = true
}

function onFileChange({ file }) {
  uploadFile.value = file?.file ?? null
}

function statusTagType(status) {
  if (status === 'completed') return 'success'
  if (status === 'processing') return 'warning'
  if (status === 'failed') return 'error'
  return 'default'
}

function statusLabel(status) {
  if (status === 'completed') return '已完成'
  if (status === 'processing') return '处理中'
  if (status === 'failed') return '失败'
  return status
}

function fileTypeLabel(type) {
  const map = { pdf: 'PDF', txt: 'TXT', docx: 'Word' }
  return map[type] || type
}
</script>

<template>
  <CommonPage show-footer>
    <div class="kb-page">
      <div class="kb-header">
        <h2 class="kb-title">知识库管理</h2>
        <NButton type="primary" @click="showCreateModal = true">
          + 新建知识库
        </NButton>
      </div>

      <div class="kb-content">
        <div class="kb-list">
          <div
              v-for="kb in knowledgeBases"
              :key="kb.id"
              class="kb-card"
              :class="{ active: selectedKB?.id === kb.id }"
              @click="selectKB(kb)"
          >
            <div class="kb-card-top">
              <h3>{{ kb.knowledge_name }}</h3>
              <NPopconfirm @positive-click="handleDeleteKB(kb.id)">
                <template #trigger>
                  <NButton
                      size="tiny"
                      type="error"
                      quaternary
                      class="delete-btn"
                      @click.stop
                  >
                    删除
                  </NButton>
                </template>
                确定删除该知识库吗？
              </NPopconfirm>
            </div>
            <p class="kb-desc">{{ kb.description || '暂无描述' }}</p>
            <div class="kb-meta">
              <span>{{ kb.document_count }} 个文档</span>
              <NTag v-if="kb.is_public" size="small" type="info">公开</NTag>
            </div>
          </div>
          <NEmpty v-if="!loading && knowledgeBases.length === 0" description="暂无知识库" />
        </div>

        <div v-if="selectedKB" class="doc-section">
          <div class="doc-header">
            <h3>{{ selectedKB.knowledge_name }} - 文档列表</h3>
            <NButton type="primary" @click="showUploadModal = true">
              + 上传文档
            </NButton>
          </div>

          <div class="doc-list">
            <div v-for="doc in documents" :key="doc.id" class="doc-item">
              <div class="doc-main">
                <div class="doc-info">
                  <span class="doc-name">{{ doc.filename }}</span>
                  <NTag v-if="doc.file_type" size="small">{{ fileTypeLabel(doc.file_type) }}</NTag>
                  <span class="doc-size">{{ (doc.file_size / 1024).toFixed(1) }} KB</span>
                  <NTag size="small" :type="statusTagType(doc.status)">{{ statusLabel(doc.status) }}</NTag>
                </div>
                <p v-if="doc.status === 'failed' && doc.error_msg" class="doc-error">
                  {{ doc.error_msg }}
                </p>
              </div>
              <div class="doc-actions">
                <NButton size="small" @click="viewChunks(doc)">查看分块</NButton>
                <NPopconfirm @positive-click="handleDeleteDoc(doc.id)">
                  <template #trigger>
                    <NButton size="small" type="error" quaternary>删除</NButton>
                  </template>
                  确定删除该文档吗？
                </NPopconfirm>
              </div>
            </div>
            <NEmpty v-if="documents.length === 0" description="暂无文档" />
          </div>
        </div>
        <div v-else class="doc-placeholder">
          <NEmpty description="请从左侧选择一个知识库" />
        </div>
      </div>

      <NModal
          v-model:show="showCreateModal"
          preset="card"
          title="新建知识库"
          :bordered="false"
          :mask-closable="false"
          style="width: 420px"
      >
        <NInput v-model:value="newKB.knowledge_name" placeholder="知识库名称" class="mb-12" />
        <NInput
            v-model:value="newKB.description"
            type="textarea"
            placeholder="描述（可选）"
            :rows="3"
            class="mb-12"
        />
        <NCheckbox v-model:checked="newKB.is_public" class="mb-12">公开知识库</NCheckbox>
        <div class="chunk-config">
          <label class="field-label">分块大小（可选，默认 500）</label>
          <NInputNumber
              v-model:value="newKB.chunk_size"
              :min="200"
              :max="2000"
              placeholder="留空使用全局默认"
              class="mb-12"
              style="width: 100%"
          />
          <label class="field-label">分块重叠（可选，默认 100）</label>
          <NInputNumber
              v-model:value="newKB.chunk_overlap"
              :min="0"
              :max="1000"
              placeholder="留空使用全局默认"
              style="width: 100%"
          />
        </div>
        <template #footer>
          <div class="modal-footer">
            <NButton @click="showCreateModal = false">取消</NButton>
            <NButton type="primary" @click="handleCreateKB">创建</NButton>
          </div>
        </template>
      </NModal>

      <NModal
          v-model:show="showUploadModal"
          preset="card"
          title="上传文档"
          :bordered="false"
          :mask-closable="false"
          style="width: 420px"
      >
        <p class="upload-tip">支持 PDF、TXT、Word(docx)，当前仅 PDF 可解析</p>
        <NUpload
            :max="1"
            accept=".pdf,.txt,.docx"
            :default-upload="false"
            @change="onFileChange"
        >
          <NUploadDragger>
            <p>点击或拖拽文件到此处</p>
          </NUploadDragger>
        </NUpload>
        <template #footer>
          <div class="modal-footer">
            <NButton @click="showUploadModal = false">取消</NButton>
            <NButton type="primary" :disabled="!uploadFile" @click="handleUpload">上传</NButton>
          </div>
        </template>
      </NModal>

      <NModal
          v-model:show="showChunksModal"
          preset="card"
          title="知识块预览"
          :bordered="false"
          style="width: 640px"
      >
        <div class="chunks-list">
          <div v-for="chunk in chunks" :key="chunk.id" class="chunk-item">
            <div class="chunk-index">
              #{{ chunk.chunk_index + 1 }}
              <span v-if="chunk.page_number"> · 第{{ chunk.page_number }}页</span>
            </div>
            <div class="chunk-content">{{ chunk.content }}</div>
          </div>
          <NEmpty v-if="chunks.length === 0" description="暂无知识块" />
        </div>
        <template #footer>
          <div class="modal-footer">
            <NButton @click="showChunksModal = false">关闭</NButton>
          </div>
        </template>
      </NModal>
    </div>
  </CommonPage>
</template>

<style scoped>
.kb-page {
  min-width: 0;
}

.kb-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  min-width: 0;
}

.kb-title {
  font-size: 20px;
  font-weight: 600;
  flex-shrink: 0;
}

.kb-content {
  display: grid;
  grid-template-columns: minmax(240px, 300px) minmax(0, 1fr);
  gap: 24px;
  min-width: 0;
}

.kb-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.kb-card {
  padding: 16px;
  background: var(--n-color, #fff);
  border: 1px solid var(--n-border-color, #e0e0e0);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.kb-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.kb-card.active {
  border-color: var(--primary-color, #f4511e);
  background: color-mix(in srgb, var(--primary-color, #f4511e) 8%, transparent);
}

.kb-card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.kb-card h3 {
  font-size: 16px;
  font-weight: 600;
  min-width: 0;
}

.kb-desc {
  font-size: 13px;
  color: var(--n-text-color-3, #666);
  margin-bottom: 12px;
}

.kb-meta {
  display: flex;
  gap: 12px;
  align-items: center;
  font-size: 12px;
  color: var(--n-text-color-3, #999);
}

.delete-btn {
  flex-shrink: 0;
}

.doc-section {
  background: var(--n-color, #fff);
  border: 1px solid var(--n-border-color, #e0e0e0);
  border-radius: 8px;
  padding: 20px;
  min-width: 0;
}

.doc-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--n-color, #fff);
  border: 1px solid var(--n-border-color, #e0e0e0);
  border-radius: 8px;
  min-height: 320px;
}

.doc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  min-width: 0;
}

.doc-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.doc-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  background: var(--n-color-modal, #f5f5f5);
  border-radius: 6px;
  min-width: 0;
}

.doc-main {
  min-width: 0;
  flex: 1;
}

.doc-info {
  display: flex;
  gap: 12px;
  align-items: center;
  min-width: 0;
  flex-wrap: wrap;
}

.doc-error {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--n-error-color, #d03050);
  word-break: break-word;
}

.doc-name {
  font-weight: 500;
  min-width: 0;
}

.doc-size {
  font-size: 12px;
  color: var(--n-text-color-3, #666);
}

.doc-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.chunks-list {
  max-height: 60vh;
  overflow-y: auto;
}

.chunk-item {
  padding: 12px 0;
  border-bottom: 1px solid var(--n-border-color, #eee);
}

.chunk-index {
  font-size: 12px;
  color: var(--primary-color, #f4511e);
  margin-bottom: 4px;
}

.chunk-content {
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.upload-tip {
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--n-text-color-3, #666);
}

.chunk-config {
  margin-top: 4px;
}

.field-label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--n-text-color-3, #666);
}

.mb-12 {
  margin-bottom: 12px;
}
</style>
