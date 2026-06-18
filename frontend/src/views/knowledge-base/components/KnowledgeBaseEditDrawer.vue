<script setup>
import { computed, ref, watch } from 'vue'
import {
  NButton,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NPopconfirm,
  NSpace,
  NSpin,
  NSwitch,
  NTag,
  NUpload,
  NUploadDragger,
} from 'naive-ui'

import api, { uploadDocument } from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'
import { renderIcon } from '@/utils'
import {
  emptyForm,
  fileTypeLabel,
  formToPayload,
  rowToForm,
  shortModelName,
  statusLabel,
  statusTagType,
} from '../kbUtils.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  mode: { type: String, default: 'edit' },
  record: { type: Object, default: null },
})

const emit = defineEmits(['update:show', 'saved'])

const formRef = ref(null)
const saving = ref(false)
const form = ref(emptyForm())

const documents = ref([])
const docsLoading = ref(false)
const retryingDocId = ref(null)
const uploadFile = ref(null)
const uploading = ref(false)

const chunks = ref([])
const showChunksModal = ref(false)
const chunksLoading = ref(false)

const title = computed(() => (props.mode === 'create' ? '新建知识库' : '编辑知识库'))
const isEdit = computed(() => props.mode === 'edit' && !!form.value.id)

watch(
  () => [props.show, props.record, props.mode],
  async () => {
    if (!props.show) return
    form.value = props.mode === 'create' ? emptyForm() : rowToForm(props.record || {})
    uploadFile.value = null
    if (props.mode === 'edit' && form.value.id) {
      await loadDocuments()
    } else {
      documents.value = []
    }
  },
  { immediate: true },
)

function close() {
  emit('update:show', false)
}

async function loadDocuments() {
  if (!form.value.id) return
  docsLoading.value = true
  try {
    documents.value = (await api.fetchDocuments(form.value.id)) || []
  } catch (err) {
    window.$message?.error(err?.message || '加载文档列表失败')
    documents.value = []
  } finally {
    docsLoading.value = false
  }
}

async function handleSave() {
  await formRef.value?.validate?.()
  saving.value = true
  try {
    const payload = formToPayload(form.value)
    if (props.mode === 'create') {
      await api.createKnowledgeBase(payload)
      window.$message?.success('创建成功')
    } else {
      await api.updateKnowledgeBase(form.value.id, payload)
      window.$message?.success('保存成功')
    }
    emit('saved')
    close()
  } catch (err) {
    if (err?.message) window.$message?.error(err.message)
  } finally {
    saving.value = false
  }
}

function onFileChange({ file }) {
  uploadFile.value = file?.file ?? null
}

async function handleUpload() {
  if (!uploadFile.value || !form.value.id) return
  uploading.value = true
  try {
    await uploadDocument(form.value.id, uploadFile.value)
    uploadFile.value = null
    window.$message?.success('文档上传成功')
    await loadDocuments()
  } catch (err) {
    window.$message?.error(err?.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function handleRetryDoc(doc) {
  retryingDocId.value = doc.id
  try {
    await api.retryDocument(form.value.id, doc.id)
    window.$message?.success('文档重试处理成功')
    await loadDocuments()
  } catch (err) {
    window.$message?.error(err?.message || '重试失败')
    await loadDocuments()
  } finally {
    retryingDocId.value = null
  }
}

async function handleDeleteDoc(docId) {
  try {
    await api.deleteDocument(form.value.id, docId)
    window.$message?.success('文档已删除')
    await loadDocuments()
  } catch (err) {
    window.$message?.error(err?.message || '删除失败')
  }
}

async function viewChunks(doc) {
  chunksLoading.value = true
  showChunksModal.value = true
  chunks.value = []
  try {
    chunks.value = (await api.fetchChunks(form.value.id, doc.id)) || []
  } catch (err) {
    window.$message?.error(err?.message || '加载分块失败')
  } finally {
    chunksLoading.value = false
  }
}
</script>

<template>
  <NDrawer :show="show" :width="800" placement="right" @update:show="emit('update:show', $event)">
    <NDrawerContent :title="title" closable :native-scrollbar="false" body-content-style="padding: 0;">
      <div class="kb-edit">
        <div class="kb-edit__body cus-scroll">
          <NForm
            ref="formRef"
            label-placement="top"
            :model="form"
            require-mark-placement="right-hanging"
          >
            <section class="kb-edit__section">
              <div class="kb-edit__section-head kb-edit__section-head--basic">
                <TheIcon icon="material-symbols:library-books-outline" :size="18" />
                <span>基本配置</span>
              </div>
              <div class="kb-edit__section-body">
                <NFormItem
                    label="知识库名称"
                    path="knowledge_name"
                    :rule="{ required: true, message: '请输入知识库名称', trigger: ['input', 'blur'] }"
                >
                  <NInput v-model:value="form.knowledge_name" placeholder="如：产品文档库" />
                </NFormItem>

                <NFormItem label="描述" path="description">
                  <NInput
                      v-model:value="form.description"
                      type="textarea"
                      :rows="3"
                      placeholder="知识库用途说明（可选）"
                  />
                </NFormItem>

                <div class="kb-edit__switch-row">
                  <div class="kb-edit__switch-info">
                    <TheIcon icon="material-symbols:public" :size="18" color="#3b82f6" />
                    <div>
                      <div class="kb-edit__switch-title">公开知识库</div>
                      <div class="kb-edit__switch-desc">允许其他用户检索使用</div>
                    </div>
                  </div>
                  <NSwitch v-model:value="form.is_public" />
                </div>
              </div>
            </section>

            <section class="kb-edit__section">
              <div class="kb-edit__section-head kb-edit__section-head--chunk">
                <TheIcon icon="material-symbols:content-cut" :size="18" />
                <span>分块配置</span>
              </div>
              <div class="kb-edit__section-body">
                <div class="kb-edit__row">
                  <NFormItem label="分块大小" path="chunk_size" class="kb-edit__col">
                    <NInputNumber
                        v-model:value="form.chunk_size"
                        :min="200"
                        :max="2000"
                        placeholder="默认 500"
                        class="w-full"
                    />
                  </NFormItem>
                  <NFormItem label="分块重叠" path="chunk_overlap" class="kb-edit__col">
                    <NInputNumber
                        v-model:value="form.chunk_overlap"
                        :min="0"
                        :max="1000"
                        placeholder="默认 100"
                        class="w-full"
                    />
                  </NFormItem>
                </div>
                <p class="kb-edit__hint">留空将使用系统全局默认值；分块重叠不能超过分块大小的一半。</p>
              </div>
            </section>
          </NForm>

          <section v-if="isEdit" class="kb-edit__section kb-edit__section--docs">
            <div class="kb-edit__docs-head">
              <div>
                <div class="kb-edit__section-head kb-edit__section-head--docs">
                  <TheIcon icon="material-symbols:description-outline" :size="18" />
                  <span>文档管理</span>
                </div>
                <div class="kb-edit__docs-sub">{{ documents.length }} 个文档</div>
              </div>
            </div>

            <div class="kb-edit__upload">
              <p class="kb-edit__upload-tip">支持 PDF、TXT、Word(docx)，当前仅 PDF 可解析</p>
              <NUpload
                  :max="1"
                  accept=".pdf,.txt,.docx"
                  :default-upload="false"
                  @change="onFileChange"
              >
                <NUploadDragger>
                  <p>点击或拖拽文件到此处上传</p>
                </NUploadDragger>
              </NUpload>
              <NButton
                  type="primary"
                  class="kb-edit__upload-btn"
                  :disabled="!uploadFile"
                  :loading="uploading"
                  @click="handleUpload"
              >
                <template #icon>
                  <component :is="renderIcon('material-symbols:upload', { size: 16 })" />
                </template>
                上传文档
              </NButton>
            </div>

            <NSpin :show="docsLoading" class="kb-edit__docs-spin">
              <div v-if="documents.length" class="kb-edit__doc-list">
                <div v-for="doc in documents" :key="doc.id" class="kb-edit__doc-item">
                  <div class="kb-edit__doc-main">
                    <div class="kb-edit__doc-info">
                      <span class="kb-edit__doc-name">{{ doc.filename }}</span>
                      <NTag v-if="doc.file_type" size="small">{{ fileTypeLabel(doc.file_type) }}</NTag>
                      <span class="kb-edit__doc-size">{{ (doc.file_size / 1024).toFixed(1) }} KB</span>
                      <NTag size="small" :type="statusTagType(doc.status)">{{ statusLabel(doc.status) }}</NTag>
                      <span
                          v-if="doc.embedding_model"
                          class="kb-edit__doc-embedding"
                          :title="doc.embedding_model"
                      >
                        向量 {{ shortModelName(doc.embedding_model) }}
                      </span>
                    </div>
                    <p v-if="doc.status === 'failed' && doc.error_message" class="kb-edit__doc-error">
                      {{ doc.error_message }}
                    </p>
                  </div>
                  <div class="kb-edit__doc-actions">
                    <NButton
                        v-if="doc.status === 'failed'"
                        size="small"
                        type="warning"
                        :loading="retryingDocId === doc.id"
                        @click="handleRetryDoc(doc)"
                    >
                      重试
                    </NButton>
                    <NButton size="small" @click="viewChunks(doc)">查看分块</NButton>
                    <NPopconfirm @positive-click="handleDeleteDoc(doc.id)">
                      <template #trigger>
                        <NButton size="small" type="error" quaternary>删除</NButton>
                      </template>
                      确定删除该文档吗？
                    </NPopconfirm>
                  </div>
                </div>
              </div>
              <NEmpty v-else class="kb-edit__doc-empty" description="暂无文档，请上传文件" />
            </NSpin>
          </section>

          <section v-else class="kb-edit__section kb-edit__section--placeholder">
            <div class="kb-edit__placeholder">
              <TheIcon icon="material-symbols:folder-open-outline" :size="28" color="#9ca3af" />
              <div class="kb-edit__placeholder-title">文档管理</div>
              <div class="kb-edit__placeholder-desc">保存知识库后可上传与管理文档</div>
            </div>
          </section>
        </div>

        <div class="kb-edit__footer">
          <NSpace justify="end">
            <NButton @click="close">取消</NButton>
            <NButton type="primary" :loading="saving" @click="handleSave">
              {{ mode === 'create' ? '创建' : '保存' }}
            </NButton>
          </NSpace>
        </div>
      </div>
    </NDrawerContent>
  </NDrawer>

  <NModal
      v-model:show="showChunksModal"
      preset="card"
      title="知识块预览"
      :bordered="false"
      style="width: 640px"
  >
    <NSpin :show="chunksLoading">
      <div class="kb-edit__chunks-list">
        <div v-for="chunk in chunks" :key="chunk.id" class="kb-edit__chunk-item">
          <div class="kb-edit__chunk-index">
            #{{ chunk.chunk_index + 1 }}
            <span v-if="chunk.page_number"> · 第{{ chunk.page_number }}页</span>
          </div>
          <div class="kb-edit__chunk-content">{{ chunk.content }}</div>
        </div>
        <NEmpty v-if="!chunksLoading && chunks.length === 0" description="暂无知识块" />
      </div>
    </NSpin>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showChunksModal = false">关闭</NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped lang="scss">
.kb-edit {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px);
}

.kb-edit__body {
  flex: 1;
  min-height: 0;
  padding: 20px 24px;
  overflow-y: auto;
}

.kb-edit__section {
  margin-bottom: 16px;
  background: #fff;
  border: 1px solid #eef0f4;
  border-radius: 12px;
  overflow: hidden;
}

.kb-edit__section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 18px;
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
  border-bottom: 1px solid #f1f5f9;

  &--basic :deep(.n-icon) {
    color: #3b82f6;
  }

  &--chunk :deep(.n-icon) {
    color: #22c55e;
  }

  &--docs :deep(.n-icon) {
    color: #f59e0b;
    border-bottom: none;
  }
}

.kb-edit__section-body {
  padding: 16px 18px 6px;
}

.kb-edit__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.kb-edit__col {
  min-width: 0;
}

.kb-edit__switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  margin-bottom: 8px;
  background: #f8fafc;
  border: 1px solid #eef0f4;
  border-radius: 10px;
}

.kb-edit__switch-info {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.kb-edit__switch-title {
  font-size: 14px;
  font-weight: 500;
  color: #1f2937;
}

.kb-edit__switch-desc {
  margin-top: 2px;
  font-size: 12px;
  color: #9ca3af;
}

.kb-edit__hint {
  margin: 0 0 10px;
  font-size: 12px;
  color: #9ca3af;
  line-height: 1.5;
}

.kb-edit__section--docs {
  padding-bottom: 12px;
}

.kb-edit__docs-head {
  padding: 14px 18px 0;
}

.kb-edit__docs-sub {
  margin-top: 4px;
  padding: 0 18px 12px;
  font-size: 12px;
  color: #9ca3af;
}

.kb-edit__upload {
  padding: 0 18px 16px;
}

.kb-edit__upload-tip {
  margin: 0 0 10px;
  font-size: 12px;
  color: #9ca3af;
}

.kb-edit__upload-btn {
  margin-top: 12px;
}

.kb-edit__docs-spin {
  padding: 0 18px 6px;
}

.kb-edit__doc-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.kb-edit__doc-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  background: #f8fafc;
  border: 1px solid #eef0f4;
  border-radius: 10px;
}

.kb-edit__doc-main {
  min-width: 0;
  flex: 1;
}

.kb-edit__doc-info {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  min-width: 0;
}

.kb-edit__doc-name {
  font-weight: 500;
  color: #1f2937;
  word-break: break-all;
}

.kb-edit__doc-size,
.kb-edit__doc-embedding {
  font-size: 12px;
  color: #9ca3af;
}

.kb-edit__doc-error {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: #ef4444;
  word-break: break-word;
}

.kb-edit__doc-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.kb-edit__doc-empty {
  padding: 24px 0;
}

.kb-edit__section--placeholder {
  padding: 28px 18px;
}

.kb-edit__placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  text-align: center;
}

.kb-edit__placeholder-title {
  font-size: 15px;
  font-weight: 600;
  color: #6b7280;
}

.kb-edit__placeholder-desc {
  font-size: 13px;
  color: #9ca3af;
}

.kb-edit__footer {
  padding: 14px 24px;
  border-top: 1px solid #eef0f4;
  background: #fff;
}

.kb-edit__chunks-list {
  max-height: 60vh;
  overflow-y: auto;
}

.kb-edit__chunk-item {
  padding: 12px 0;
  border-bottom: 1px solid #eef0f4;
}

.kb-edit__chunk-index {
  font-size: 12px;
  color: #f59e0b;
  margin-bottom: 4px;
}

.kb-edit__chunk-content {
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
  color: #374151;
}

.w-full {
  width: 100%;
}
</style>

<style scoped lang="scss">
html.dark .kb-edit__section {
  background: #18181c;
  border-color: rgba(255, 255, 255, 0.1);
}

html.dark .kb-edit__section-head {
  color: #e5e7eb;
  border-bottom-color: rgba(255, 255, 255, 0.08);
}

html.dark .kb-edit__switch-row,
html.dark .kb-edit__doc-item {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.08);
}

html.dark .kb-edit__switch-title,
html.dark .kb-edit__doc-name {
  color: #e5e7eb;
}

html.dark .kb-edit__footer {
  background: #18181c;
  border-top-color: rgba(255, 255, 255, 0.08);
}

html.dark .kb-edit__chunk-content {
  color: #d1d5db;
}

html.dark .kb-edit__chunk-item {
  border-bottom-color: rgba(255, 255, 255, 0.08);
}
</style>
