<template>
  <div class="workflow-chat">
    <!-- 消息列表 -->
    <div class="messages" ref="msgBox">
      <div v-for="(msg, i) in messages" :key="i" class="message-row" :class="msg.role">

        <!-- 用户消息 -->
        <div v-if="msg.role === 'user'" class="bubble user-bubble">
          {{ msg.content }}
        </div>

        <!-- AI 消息 -->
        <div v-else class="bubble assistant-bubble">

          <!-- 工作流步骤 -->
          <div v-if="msg.steps && msg.steps.length" class="steps">
            <div v-for="s in msg.steps" :key="s.role" class="step-row">
              <!-- 状态图标 -->
              <span class="step-icon" :class="s.status">
                <template v-if="s.status === 'pending'">○</template>
                <template v-else-if="s.status === 'running'">◌</template>
                <template v-else-if="s.status === 'done'">✓</template>
              </span>
              <!-- 角色名 -->
              <span class="step-role">
                {{ { researcher: '🔍 研究员', writer: '✍️ 写作者', reviewer: '✅ 审查员' }[s.role] || s.role }}
              </span>
              <!-- 审查结论 -->
              <span v-if="s.role === 'reviewer' && s.passed !== null" class="step-verdict" :class="{ pass: s.passed, fail: !s.passed }">
                {{ s.passed ? '通过' : `未通过（已重写 ${s.rewriteCount} 次）` }}
              </span>
              <!-- 审查问题列表 -->
              <div v-if="s.role === 'reviewer' && s.passed === false && s.issues.length" class="step-issues">
                <div v-for="(issue, j) in s.issues" :key="j" class="issue-item">• {{ issue }}</div>
              </div>
              <!-- 工具调用记录 -->
              <div v-if="s.actions && s.actions.length" class="step-actions">
                <div v-for="(action, j) in s.actions" :key="j" class="action-item">{{ action }}</div>
              </div>
            </div>
          </div>

          <!-- 步骤与答案的分隔线 -->
          <div v-if="msg.content" class="divider"></div>

          <!-- 最终答案 -->
          <div v-if="msg.content" class="answer">
            {{ msg.content }}
          </div>

          <!-- 来源标签 -->
          <div v-if="msg.sources && msg.sources.length" class="sources">
            <span v-for="s in msg.sources" :key="s.filename" class="source-tag">
              📄 {{ s.filename }} {{ (s.score * 100).toFixed(0) }}%
            </span>
          </div>

          <!-- 错误信息 -->
          <div v-if="msg.error" class="error-msg">{{ msg.error }}</div>
        </div>
      </div>

      <!-- 加载动画 -->
      <div v-if="loading" class="message-row assistant">
        <div class="bubble loading-bubble">
          <span class="dot-pulse">思考中<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></span>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="input-area">
      <input v-model="question" @keyup.enter="send" placeholder="输入问题..." :disabled="loading" />
      <button @click="send" :disabled="loading || !question.trim()">{{ loading ? '思考中' : '发送' }}</button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'

// 消息列表：{ role, content, steps, sources, error }
const messages = ref([])
const question = ref('')
const loading = ref(false)
const msgBox = ref(null)

// 消息或 loading 变化时自动滚到底部
watch([messages, loading], async () => {
  await nextTick()
  if (msgBox.value) {
    msgBox.value.scrollTop = msgBox.value.scrollHeight
  }
}, { deep: true })

function send() {
  if (!question.value.trim()) return

  const q = question.value

  // 1. 推两条消息：用户问题 + AI 占位（含三个步骤）
  messages.value.push({ role: 'user', content: q })
  messages.value.push({
    role: 'assistant',
    content: '',
    steps: [
      { role: 'researcher', status: 'pending', actions: [], output: '' },
      { role: 'writer',     status: 'pending', actions: [], output: '' },
      { role: 'reviewer',   status: 'pending', passed: null, issues: [], rewriteCount: 0 },
    ],
    sources: [],
    error: '',
  })

  question.value = ''
  loading.value = true

  // 2. 连 SSE，每个事件对应一个前端更新
  const history = JSON.stringify(
    messages.value.slice(0, -2).map(m => ({
      role: m.role,
      content: m.content || ''
    }))
  )
  const url = `http://localhost:8000/chat/workflow/stream?question=${encodeURIComponent(q)}&history=${encodeURIComponent(history)}`
  const es = new EventSource(url)
  let doneReceived = false  // 防止 error 在 done 之前触发

  es.addEventListener('node_start', (e) => {
    const data = JSON.parse(e.data)
    const step = messages.value[messages.value.length - 1].steps.find(s => s.role === data.role)
    if (step) step.status = 'running'
  })

  es.addEventListener('node_action', (e) => {
    const data = JSON.parse(e.data)
    const step = messages.value[messages.value.length - 1].steps.find(s => s.role === data.role)
    if (step) step.actions.push(data.action)
  })

  es.addEventListener('node_end', (e) => {
    const data = JSON.parse(e.data)
    const step = messages.value[messages.value.length - 1].steps.find(s => s.role === data.role)
    if (!step) return
    step.status = 'done'
    if (data.rewrite && data.role === 'writer') {
      // 审查不通过 → Writer 被触发重写，状态先回到 pending
      step.status = 'pending'
    }
    step.output = data.output
  })

  es.addEventListener('review_result', (e) => {
    const data = JSON.parse(e.data)
    const step = messages.value[messages.value.length - 1].steps.find(s => s.role === 'reviewer')
    if (!step) return
    step.passed = data.passed
    step.issues = data.issues || []
    step.rewriteCount = data.rewrite_count || 0
    step.status = data.passed ? 'done' : 'running'
  })

  es.addEventListener('done', (e) => {
    try {
      const data = JSON.parse(e.data)
      const lastMsg = messages.value[messages.value.length - 1]
      lastMsg.content = data.answer
    } catch (err) {
      console.error('done event error:', err)
    }
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
.workflow-chat {
  max-width: 860px;
  margin: 0 auto;
  height: 80vh;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

/* ===== 消息区域 ===== */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-row { display: flex; }
.message-row.user { justify-content: flex-end; }
.message-row.assistant { justify-content: flex-start; }

/* ===== 气泡 ===== */
.bubble {
  max-width: 80%;
  padding: 12px 16px;
  border-radius: 18px;
  font-size: 15px;
  line-height: 1.6;
  word-wrap: break-word;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.user-bubble {
  background: #4a90d9;
  color: #fff;
  border-bottom-right-radius: 4px;
}
.assistant-bubble {
  background: #fff;
  color: #333;
  border-bottom-left-radius: 4px;
  border: 1px solid #e5e5e5;
}

/* ===== 工作流步骤 ===== */
.steps { margin-bottom: 4px; }
.step-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  font-size: 14px;
}
.step-icon {
  width: 18px;
  text-align: center;
  font-size: 16px;
}
.step-icon.running { color: #e67e22; }
.step-icon.done { color: #27ae60; }
.step-role { font-weight: 500; }
.step-verdict {
  font-size: 12px;
  padding: 1px 8px;
  border-radius: 10px;
}
.step-verdict.pass { background: #e8f5e9; color: #27ae60; }
.step-verdict.fail { background: #fbe9e7; color: #d32f2f; }
.step-issues {
  width: 100%;
  margin: 2px 0 0 24px;
  font-size: 12px;
  color: #d32f2f;
}
.issue-item { line-height: 1.5; }
.step-actions {
  width: 100%;
  margin: 2px 0 0 24px;
  font-size: 12px;
  color: #888;
}
.action-item { line-height: 1.5; }

/* ===== 分隔线 ===== */
.divider {
  height: 1px;
  background: #e8e8e8;
  margin: 8px 0;
}

/* ===== 最终答案 ===== */
.answer {
  font-size: 15px;
  line-height: 1.7;
}

/* ===== 来源标签 ===== */
.sources {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid #eee;
}
.source-tag {
  font-size: 11px;
  background: #f0f5ff;
  color: #555;
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
}

/* ===== 错误信息 ===== */
.error-msg {
  margin-top: 8px;
  font-size: 13px;
  color: #d32f2f;
  padding: 6px 10px;
  background: #fbe9e7;
  border-radius: 8px;
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
.input-area input:focus { border-color: #4a90d9; }
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
.input-area button:hover:not(:disabled) { background: #357abd; }
.input-area button:disabled { background: #b0c4de; cursor: not-allowed; }
</style>
