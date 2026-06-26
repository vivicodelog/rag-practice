<template>
  <div class="sidebar">
    <!-- 顶部：标题 + 新建按钮 -->
    <div class="sidebar-header">
      <h3>会话</h3>
      <button @click="$emit('create')">+ 新建</button>
    </div>

    <!-- 会话列表 -->
    <div class="session-list">
      <div v-for="s in sessions" :key="s.id"
        class="session-item"
        :class="{ active: s.id === currentSessionId }"
        @click="$emit('select', s.id)"
      >
        <span class="title">{{ s.title }}</span>
        <button class="delete-btn" @click.stop="$emit('delete', s.id)">×</button>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="!sessions.length" class="empty">暂无会话</div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { getSessions } from '../../src/api.js'

const props = defineProps({
  mode: String,
  currentSessionId: String,
})
const emit = defineEmits(['select', 'create', 'delete'])

const sessions = ref([])
const loading = ref(false)

// mode 变化时重新加载会话列表
watch(() => props.mode, async () => {
  // 调 getSessions(props.mode) 拿到数据
    loading.value = true
    sessions.value = await getSessions(props.mode)
    sessions.value.sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    loading.value = false
  // 赋值给 sessions.value
}, { immediate: true })
</script>

<style scoped>
.sidebar {
  width: 240px;
  height: 100%;
  background: #f0f2f5;
  border-right: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
}
.sidebar-header h3 {
  margin: 0;
  font-size: 15px;
  color: #333;
}
.sidebar-header button {
  padding: 4px 12px;
  font-size: 13px;
  background: #4a90d9;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
.sidebar-header button:hover {
  background: #357abd;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.15s;
}
.session-item:hover {
  background: #e4e7eb;
}
.session-item.active {
  background: #d4e1f9;
  font-weight: 500;
}

.session-item .title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  color: #333;
}

.delete-btn {
  opacity: 0;
  background: none;
  border: none;
  color: #999;
  font-size: 16px;
  cursor: pointer;
  padding: 0 4px;
  transition: opacity 0.15s;
}
.session-item:hover .delete-btn {
  opacity: 1;
}
.delete-btn:hover {
  color: #e74c3c;
}

.loading, .empty {
  padding: 20px;
  text-align: center;
  font-size: 13px;
  color: #999;
}
</style>
