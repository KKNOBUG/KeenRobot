<script setup>
import { ref, onMounted } from 'vue'
import {
  fetchKnowledgeBases,
  createKnowledgeBase,
  deleteKnowledgeBase,
  uploadDocument,
  deleteDocument,
  fetchDocuments,
  fetchChunks
} from '../api/index.js'

const knowledgeBases = ref([])
const selectedKB = ref(null)
const documents = ref([])
const chunks = ref([])
const loading = ref(false)
const showCreateModal = ref(false)
const showUploadModal = ref(false)
const showChunksModal = ref(false)

const newKB = ref({ name: '', description: '', is_public: false })
const uploadFile = ref(null)

onMounted(async () => {
  await loadKnowledgeBases()
})

async function loadKnowledgeBases() {
  loading.value = true
  try {
    knowledgeBases.value = await fetchKnowledgeBases()
  } finally {
    loading.value = false
  }
}

async function handleCreateKB() {
  try {
    await createKnowledgeBase(newKB.value)
    showCreateModal.value = false
    newKB.value = { name: '', description: '', is_public: false }
    await loadKnowledgeBases()
  } catch (err) {
    alert('创建失败: ' + err.message)
  }
}

async function handleDeleteKB(id) {
  if (!confirm('确定删除该知识库吗？')) return
  try {
    await deleteKnowledgeBase(id)
    await loadKnowledgeBases()
  } catch (err) {
    alert('删除失败: ' + err.message)
  }
}

async function selectKB(kb) {
  selectedKB.value = kb
  documents.value = await fetchDocuments(kb.id)
}

async function handleUpload() {
  if (!uploadFile.value) return
  try {
    await uploadDocument(selectedKB.value.id, uploadFile.value)
    showUploadModal.value = false
    uploadFile.value = null
    documents.value = await fetchDocuments(selectedKB.value.id)
  } catch (err) {
    alert('上传失败: ' + err.message)
  }
}

async function handleDeleteDoc(docId) {
  if (!confirm('确定删除该文档吗？')) return
  try {
    await deleteDocument(selectedKB.value.id, docId)
    documents.value = await fetchDocuments(selectedKB.value.id)
  } catch (err) {
    alert('删除失败: ' + err.message)
  }
}

async function viewChunks(doc) {
  chunks.value = await fetchChunks(selectedKB.value.id, doc.id)
  showChunksModal.value = true
}

function onFileChange(e) {
  uploadFile.value = e.target.files[0]
}
</script>

<template>
  <div class="kb-page">
    <div class="kb-header">
      <h2>知识库管理</h2>
      <button class="btn-primary" @click="showCreateModal = true">
        + 新建知识库
      </button>
    </div>

    <div class="kb-content">
      <!-- 知识库列表 -->
      <div class="kb-list">
        <div
          v-for="kb in knowledgeBases"
          :key="kb.id"
          class="kb-card"
          :class="{ active: selectedKB?.id === kb.id }"
          @click="selectKB(kb)"
        >
          <h3>{{ kb.name }}</h3>
          <p class="kb-desc">{{ kb.description || '暂无描述' }}</p>
          <div class="kb-meta">
            <span>{{ kb.document_count }} 个文档</span>
            <span v-if="kb.is_public" class="public-badge">公开</span>
          </div>
          <button class="delete-btn" @click.stop="handleDeleteKB(kb.id)">删除</button>
        </div>
      </div>

      <!-- 文档列表 -->
      <div v-if="selectedKB" class="doc-section">
        <div class="doc-header">
          <h3>{{ selectedKB.name }} - 文档列表</h3>
          <button class="btn-primary" @click="showUploadModal = true">
            + 上传文档
          </button>
        </div>

        <div class="doc-list">
          <div v-for="doc in documents" :key="doc.id" class="doc-item">
            <div class="doc-info">
              <span class="doc-name">{{ doc.filename }}</span>
              <span class="doc-size">{{ (doc.file_size / 1024).toFixed(1) }} KB</span>
              <span :class="['doc-status', doc.status]">{{ doc.status }}</span>
            </div>
            <div class="doc-actions">
              <button @click="viewChunks(doc)">查看分块</button>
              <button @click="handleDeleteDoc(doc.id)">删除</button>
            </div>
          </div>
          <div v-if="documents.length === 0" class="empty">暂无文档</div>
        </div>
      </div>
    </div>

    <!-- 创建知识库弹窗 -->
    <div v-if="showCreateModal" class="modal" @click.self="showCreateModal = false">
      <div class="modal-content">
        <h3>新建知识库</h3>
        <input v-model="newKB.name" placeholder="知识库名称" />
        <textarea v-model="newKB.description" placeholder="描述（可选）" rows="3"></textarea>
        <label class="checkbox">
          <input v-model="newKB.is_public" type="checkbox" />
          公开知识库
        </label>
        <div class="modal-actions">
          <button @click="showCreateModal = false">取消</button>
          <button class="btn-primary" @click="handleCreateKB">创建</button>
        </div>
      </div>
    </div>

    <!-- 上传文档弹窗 -->
    <div v-if="showUploadModal" class="modal" @click.self="showUploadModal = false">
      <div class="modal-content">
        <h3>上传文档</h3>
        <p>仅支持 PDF 文件</p>
        <input type="file" accept=".pdf" @change="onFileChange" />
        <div class="modal-actions">
          <button @click="showUploadModal = false">取消</button>
          <button class="btn-primary" @click="handleUpload" :disabled="!uploadFile">
            上传
          </button>
        </div>
      </div>
    </div>

    <!-- 知识块弹窗 -->
    <div v-if="showChunksModal" class="modal" @click.self="showChunksModal = false">
      <div class="modal-content large">
        <h3>知识块预览</h3>
        <div class="chunks-list">
          <div v-for="chunk in chunks" :key="chunk.id" class="chunk-item">
            <div class="chunk-index">#{{ chunk.chunk_index + 1 }}</div>
            <div class="chunk-content">{{ chunk.content }}</div>
          </div>
        </div>
        <div class="modal-actions">
          <button @click="showChunksModal = false">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kb-page {
  padding: 24px;
}

.kb-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.kb-header h2 {
  font-size: 24px;
  font-weight: 600;
}

.btn-primary {
  padding: 10px 20px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
}

.btn-primary:hover {
  background: #5a67d8;
}

.kb-content {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 24px;
}

.kb-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.kb-card {
  padding: 16px;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.kb-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.kb-card.active {
  border-color: #667eea;
  background: #f7f8ff;
}

.kb-card h3 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 8px;
}

.kb-desc {
  font-size: 13px;
  color: #666;
  margin-bottom: 12px;
}

.kb-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #999;
}

.public-badge {
  background: #e3f2fd;
  color: #1976d2;
  padding: 2px 8px;
  border-radius: 4px;
}

.delete-btn {
  position: absolute;
  top: 16px;
  right: 16px;
  padding: 4px 8px;
  background: #ffebee;
  color: #c62828;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s;
}

.kb-card:hover .delete-btn {
  opacity: 1;
}

.doc-section {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 20px;
}

.doc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.doc-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.doc-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 6px;
}

.doc-info {
  display: flex;
  gap: 16px;
  align-items: center;
}

.doc-name {
  font-weight: 500;
}

.doc-size {
  font-size: 12px;
  color: #666;
}

.doc-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
}

.doc-status.completed {
  background: #e8f5e9;
  color: #2e7d32;
}

.doc-status.processing {
  background: #fff3e0;
  color: #ef6c00;
}

.doc-status.failed {
  background: #ffebee;
  color: #c62828;
}

.doc-actions {
  display: flex;
  gap: 8px;
}

.doc-actions button {
  padding: 6px 12px;
  background: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.doc-actions button:hover {
  background: #f5f5f5;
}

.empty {
  text-align: center;
  color: #999;
  padding: 40px;
}

.modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  padding: 24px;
  border-radius: 12px;
  width: 90%;
  max-width: 400px;
}

.modal-content.large {
  max-width: 600px;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-content h3 {
  margin-bottom: 16px;
}

.modal-content input,
.modal-content textarea {
  width: 100%;
  padding: 12px;
  margin-bottom: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
}

.checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.modal-actions button {
  padding: 10px 20px;
  border: 1px solid #ddd;
  background: white;
  border-radius: 6px;
  cursor: pointer;
}

.chunks-list {
  max-height: 400px;
  overflow-y: auto;
  margin-bottom: 16px;
}

.chunk-item {
  padding: 12px;
  border-bottom: 1px solid #eee;
}

.chunk-index {
  font-size: 12px;
  color: #667eea;
  margin-bottom: 4px;
}

.chunk-content {
  font-size: 14px;
  color: #333;
  line-height: 1.6;
}
</style>
