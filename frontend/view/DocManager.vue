<template>
  <div class="doc-manager">
    <h3 class="page-title">📁 文档管理</h3>

    <!-- 上传区域 -->
    <div class="upload-card" @click="triggerFileInput" @dragover.prevent @drop.prevent="onDrop">
      <input type="file" ref="fileInput" @change="upload" accept=".txt,.pdf,.docx,.md" hidden />
      <div class="upload-icon">📤</div>
      <div class="upload-text">
        <span class="upload-main">点击上传文档</span>
        <span class="upload-hint">支持 TXT · PDF · DOCX · MD</span>
      </div>
    </div>

    <!-- 上传中指示 -->
    <div v-if="uploading" class="uploading-bar">
      <div class="uploading-progress"></div>
      <span>正在上传并构建知识库...</span>
    </div>

    <!-- 文档列表标题 -->
    <div class="list-header">
      <span class="list-title">已上传文档（{{ docs.length }}）</span>
    </div>

    <!-- 文档列表 -->
    <div class="doc-list">
      <div v-for="(doc, i) in docs" :key="doc" class="doc-item">
        <span class="doc-index">{{ i + 1 }}</span>
        <span class="doc-icon">📄</span>
        <span class="doc-name">{{ doc }}</span>
        <button class="del-btn" @click="remove(doc)" :disabled="deleting === doc" :title="'删除 ' + doc">
          {{ deleting === doc ? '...' : '✕' }}
        </button>
      </div>
      <div v-if="docs.length === 0" class="doc-empty">
        <span class="empty-icon">📂</span>
        <span>还没有上传文档</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getDocuments, uploadDocument, deleteDocument } from '../src/api'

const docs = ref([])
const uploading = ref(false)
const deleting = ref('')   // 正在删除的文件名，空字符串表示没有在删
const fileInput = ref(null)

onMounted(async () => {
  await refreshDocs()
})

function triggerFileInput() {
  fileInput.value?.click()
}

function onDrop(e) {
  const file = e.dataTransfer.files[0]
  if (file) doUpload(file)
}

async function upload(event) {
  const file = event.target.files[0]
  if (!file) return
  await doUpload(file)
}

async function doUpload(file) {
  uploading.value = true
  try {
    await uploadDocument(file)
    await refreshDocs()
  } finally {
    uploading.value = false
  }
}

/** 删除确认后调用接口 */
async function remove(filename) {
  if (!confirm(`确定删除「${filename}」吗？`)) return
  deleting.value = filename
  try {
    await deleteDocument(filename)
    await refreshDocs()
  } finally {
    deleting.value = ''
  }
}

async function refreshDocs() {
  const res = await getDocuments()
  docs.value = res.documents || []
}
</script>

<style scoped>
.doc-manager {
  max-width: 720px;
  margin: 0 auto;
  padding: 32px 24px;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: #333;
  margin: 0 0 24px 0;
}

/* ===== 上传卡片 ===== */
.upload-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 28px 24px;
  background: #f9fafb;
  border: 2px dashed #d0d5dd;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.upload-card:hover {
  border-color: #4a90d9;
  background: #f0f5ff;
}
.upload-icon {
  font-size: 32px;
  line-height: 1;
}
.upload-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.upload-main {
  font-size: 15px;
  font-weight: 500;
  color: #333;
}
.upload-hint {
  font-size: 13px;
  color: #999;
}

/* ===== 上传进度条 ===== */
.uploading-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  padding: 12px 16px;
  background: #f0f5ff;
  border-radius: 8px;
  font-size: 14px;
  color: #4a90d9;
}
.uploading-progress {
  width: 20px;
  height: 20px;
  border: 2px solid #b0c4de;
  border-top-color: #4a90d9;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ===== 列表标题 ===== */
.list-header {
  margin: 28px 0 12px 0;
}
.list-title {
  font-size: 15px;
  font-weight: 500;
  color: #666;
}

/* ===== 文档列表 ===== */
.doc-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.doc-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: #fff;
  border: 1px solid #eee;
  border-radius: 10px;
  transition: all 0.15s;
}
.doc-item:hover {
  border-color: #d0d5dd;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.doc-index {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #999;
  background: #f5f5f5;
  border-radius: 50%;
  flex-shrink: 0;
}
.doc-icon {
  font-size: 18px;
  flex-shrink: 0;
}
.doc-name {
  flex: 1;
  font-size: 14px;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ===== 删除按钮 ===== */
.del-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: #ccc;
  font-size: 14px;
  border-radius: 50%;
  cursor: pointer;
  transition: all 0.15s;
  flex-shrink: 0;
}
.del-btn:hover:not(:disabled) {
  background: #fee2e2;
  color: #ef4444;
}
.del-btn:disabled {
  cursor: not-allowed;
}

/* ===== 空状态 ===== */
.doc-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 0;
  color: #bbb;
  font-size: 14px;
}
.empty-icon {
  font-size: 40px;
}
</style>