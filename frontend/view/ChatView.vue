<template>
  <div class="chat-container">
    <!-- 消息列表 -->
    <div class="messages" ref="msgBox">
      <div v-for="(msg, i) in messages" :key="i" class="message-row" :class="msg.role">
        <div class="bubble">
          <div class="content">{{ msg.content }}</div>
          <div v-if="msg.sources && msg.sources.length" class="sources">
            <span v-for="s in msg.sources" :key="s.filename" class="source-tag">
              📄 {{ s.filename }} {{ (s.score * 100).toFixed(0) }}%
            </span>
          </div>
        </div>
      </div>
      <!-- 加载中动画 -->
      <div v-if="loading" class="message-row assistant">
        <div class="bubble loading-bubble">
          <span class="dot-pulse">思考中<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></span>
        </div>
      </div>
    </div>
    <!-- 输入区 -->
    <div class="input-area">
      <input v-model="question" @keyup.enter="send" placeholder="输入问题..." />
      <button @click="send" :disabled="loading || !question.trim()">{{ loading ? '思考中' : '发送' }}</button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'
import { chat } from '../src/api.js'

const question = ref('')
const messages = ref([])
const loading = ref(false)
const msgBox = ref(null)

// 有新消息时自动滚到底部
watch([messages, loading], async () => {
  await nextTick()
  if (msgBox.value) {
    msgBox.value.scrollTop = msgBox.value.scrollHeight
  }
}, { deep: true })

async function send() {  
  if (!question.value.trim()) return


  const q = question.value
  messages.value.push({ role: 'user', content: q })
  messages.value.push({
    role: 'assistant',
    content: '',
    sources: [],
  })
  question.value = ''
  loading.value = true

  
  const url = `http://localhost:8000/chat/agent/stream?question=${encodeURIComponent(q)}`
  const es = new EventSource(url)
  let doneReceived = false  // 防止 error 在 done 之前触发
  
   
  es.addEventListener('token', (e) => {
    const data = JSON.parse(e.data)
    const lastMsg = messages.value[messages.value.length - 1]
    lastMsg.content += data.text
  })
  
  es.addEventListener('done', (e) => {
    const data = JSON.parse(e.data)
    const lastMsg = messages.value[messages.value.length - 1]
    lastMsg.content = data.answer
    lastMsg.sources = data.sources
    doneReceived = true    
    es.close()             
    loading.value = false  
  })
  es.addEventListener('error', () => {
    if (doneReceived) return             // done 已处理，忽略无故报错
    const lastMsg = messages.value[messages.value.length - 1]
    if (lastMsg) lastMsg.error = '连接中断，请重试'
    loading.value = false
    es.close()
  })
  
  
}
</script>

<style scoped>
/* ===== 整体布局 ===== */
.chat-container {
  max-width: 860px;
  margin: 0 auto;
  height: 80vh;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

/* ===== 消息区域（可滚动） ===== */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ===== 消息行 ===== */
.message-row {
  display: flex;
}
.message-row.user {
  justify-content: flex-end;
}
.message-row.assistant {
  justify-content: flex-start;
}

/* ===== 气泡 ===== */
.bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 18px;
  font-size: 15px;
  line-height: 1.6;
  word-wrap: break-word;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
/* 用户气泡（右，蓝色） */
.user .bubble {
  background: #4a90d9;
  color: #fff;
  border-bottom-right-radius: 4px;
}
/* AI 气泡（左，白色） */
.assistant .bubble {
  background: #fff;
  color: #333;
  border-bottom-left-radius: 4px;
  border: 1px solid #e5e5e5;
}

/* ===== 来源标签 ===== */
.sources {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid rgba(0,0,0,0.06);
}
.source-tag {
  font-size: 11px;
  background: rgba(255,255,255,0.7);
  color: #555;
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
}
.user .sources {
  border-top-color: rgba(255,255,255,0.2);
}
.user .source-tag {
  background: rgba(255,255,255,0.15);
  color: #eee;
}

/* ===== 加载动画 ===== */
.loading-bubble {
  background: #fff !important;
  border: 1px solid #e5e5e5;
}
.dot-pulse { color: #999; font-size: 14px; }
.dot { animation: blink 1.4s infinite; }
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
.dot:nth-child(4) { animation-delay: 0.6s; }
@keyframes blink { 0%,100% { opacity: 0.3; } 50% { opacity: 1; } }

/* ===== 输入区 ===== */
.input-area {
  display: flex;
  gap: 10px;
  padding: 16px 20px;
  background: #fff;
  border-top: 1px solid #e0e0e0;
}
.input-area input {
  flex: 1;
  padding: 12px 16px;
  font-size: 15px;
  border: 1px solid #d0d0d0;
  border-radius: 24px;
  outline: none;
  transition: border 0.2s;
}
.input-area input:focus {
  border-color: #4a90d9;
}
.input-area button {
  padding: 12px 24px;
  font-size: 15px;
  background: #4a90d9;
  color: #fff;
  border: none;
  border-radius: 24px;
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
}
.input-area button:hover:not(:disabled) {
  background: #357abd;
}
.input-area button:disabled {
  background: #b0c4de;
  cursor: not-allowed;
}
</style>