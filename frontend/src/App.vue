<template>
  <div id="app">
    <!-- 顶栏 -->
    <header class="app-header">
      <span class="app-logo">📚</span>
      <span class="app-title">RAG 知识库问答</span>
    </header>

    <!-- 标签切换 -->
    <div class="tabs">
      <button :class="{ active: tab === 'chat' }" @click="tab = 'chat'">💬 问答(Agent)</button>
      <button :class="{ active: tab === 'workflow' }" @click="tab = 'workflow'">🔁 工作流</button>
      <button :class="{ active: tab === 'docs' }" @click="tab = 'docs'">📁 文档管理</button>
    </div>

    <!-- 页面内容 -->
    <ChatView v-if="tab === 'chat'" />
    <WorkflowChat v-if="tab === 'workflow'" />
    <DocManager v-if="tab === 'docs'" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import ChatView from '../view/ChatView.vue'
import WorkflowChat from '../view/WorkflowChat.vue'
import DocManager from '../view/DocManager.vue'

const tab = ref('chat')
</script>

<style>
/* ===== 全局重置 ===== */
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: #f0f2f5;
  color: #333;
  -webkit-font-smoothing: antialiased;
}

/* ===== 顶栏 ===== */
.app-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}
.app-logo { font-size: 28px; line-height: 1; }
.app-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

/* ===== 标签栏 ===== */
.tabs {
  display: flex;
  gap: 4px;
  padding: 12px 24px 0 24px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}
.tabs button {
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 500;
  border: none;
  background: transparent;
  color: #666;
  cursor: pointer;
  border-radius: 8px 8px 0 0;
  transition: all 0.15s;
}
.tabs button:hover {
  color: #333;
  background: #f5f5f5;
}
.tabs button.active {
  color: #4a90d9;
  background: #f0f5ff;
}
</style>
