<template>
  <div class="nl2sql-chat">
    <!-- ===== 消息列表 ===== -->
    <!--
      v-for 遍历 messages，每条消息根据 role 分两种展示：

      用户消息（role === 'user'）：
        - 右对齐，白色气泡，只显示 text

      AI 回复（role === 'assistant'）：
        - 左对齐，浅灰背景
        - 先显示 SQL（灰色代码框，monospace 字体）
        - 再显示表格（columns 做 <thead>，rows 做 <tbody>）
        - 如果 rows 为空，显示"暂无数据"
    -->

    <!-- ===== 底部输入 ===== -->
    <!--
      - 输入框 v-model 绑定 question
      - @keyup.enter 调 send()
      - 发送按钮 @click 调 send()
      - 发送中禁用按钮，显示"查询中..."
    -->
    <div class="messages" ref="msgBox">
      <div v-for="(msg, i) in messages" :key="i" class="message-row" :class="msg.role">
        <div class="bubble">
          <div class="content">{{ msg.content }}</div>
          <div v-if="msg.sql" class="sources">
              📄 <pre>{{ msg.sql}}</pre>
          </div>
          <!-- 图表：有数字列时自动显示 -->
          <VChart v-if="getChartOption(msg)" :option="getChartOption(msg)" autoresize class="chart" />
          <div v-if="msg.columns && msg.rows" class="table"> 
            <table class="table-auto w-full">
              <thead>
                <tr>
                  <th v-for="(col, j) in msg.columns" :key="j">{{ col }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in msg.rows" :key="i">
                  <td v-for="(col, j) in row" :key="j">{{ col?col:'暂无数据' }}</td>
                </tr>
              </tbody> 
            </table>
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
import { ref, computed } from 'vue'
import { nl2sql } from '../api.js'

/*
  vue-echarts 用法：
    <VChart :option="chartOption" autoresize />

    chartOption 是标准 ECharts 配置对象：
    {
      xAxis: { type: 'category', data: ['中国', '美国', ...] },  // 类别轴
      yAxis: { type: 'value' },                                   // 数值轴
      series: [{ type: 'bar', data: [5, 3, ...] }]               // 数据系列
    }
*/
import VChart from 'vue-echarts'
import 'echarts'



// 在这里写变量

const messages = ref([])
const question = ref('')
const loading = ref(false)


// 在这里写 send()
async function send() { 
  if (!question.value.trim()) return
  const q = question.value
  messages.value.push({ role: 'user', content: q })
  question.value = ''
  loading.value = true

  try {
    const res = await nl2sql(q)
    messages.value.push({
      role: 'assistant',
      sql: res.sql,
      columns: res.columns,
      rows: res.rows
    })
    getChartOption(messages.value)
  } catch (e) {
    messages.value.push({ role: 'assistant', content: '请求失败：' + e.message })
  } finally {
    loading.value = false
  }
}

// ── 图表 ──────────────────────────────────────────────
/*
  getChartOption(msg) 根据 columns/rows 判断能否画图。

  判断逻辑：
    1. rows 至少有 2 行数据
    2. 倒数第一列或倒数第二列全是数字

  如果可以画图，返回 ECharts option：
    xAxis: 用第一列的值做类别
    series: 用数字列做柱状图数据

  如果不行，返回 null，模板不显示图表。
*/
function getChartOption(msg) {
  const { columns, rows } = msg
  if (!columns || !rows || rows.length < 2) return null

  // 找到所有数字列的索引（该列的所有值都是 number 类型）
  const numColIndices = []
  for (let j = 0; j < columns.length; j++) {
    const allNum = rows.every(row => typeof row[j] === 'number')
    if (allNum) numColIndices.push(j)
  }

  // 没有数字列 → 不能画图
  if (numColIndices.length === 0) return null

  // 用第一列做 X 轴标签
  const xData = rows.map(row => String(row[0]))

  // 每个数字列做一个 series
  const series = numColIndices.map(j => ({
    name: columns[j],
    type: 'bar',
    data: rows.map(row => row[j]),
  }))

  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: xData },
    yAxis: { type: 'value' },
    series,
  }
}
</script>

<style scoped>
/* ===== 整体布局 ===== */
.nl2sql-chat {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  max-width: 900px;
  margin: 0 auto;
  background: #f5f7fa;
}

/* ===== 消息列表 ===== */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message-row {
  display: flex;
}
.message-row.user { justify-content: flex-end; }
.message-row.assistant { justify-content: flex-start; }

/* ===== 气泡 ===== */
.bubble {
  max-width: 80%;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  font-size: 14px;
}
.message-row.user .bubble {
  background: #4a90d9;
  color: #fff;
  border-bottom-right-radius: 4px;
}
.message-row.assistant .bubble {
  background: #fff;
  color: #333;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

/* ===== SQL 代码框 ===== */
.sources pre {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin-top: 8px;
}

/* ===== 图表 ===== */
.chart {
  width: 100%;
  height: 300px;
  margin-top: 12px;
}

/* ===== 表格 ===== */
.table {
  margin-top: 12px;
  overflow-x: auto;
}
.table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.table th {
  background: #f0f5ff;
  color: #4a90d9;
  font-weight: 600;
  padding: 8px 12px;
  text-align: left;
  border-bottom: 2px solid #e8e8e8;
  white-space: nowrap;
}
.table td {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
}
.table tbody tr:hover {
  background: #fafbfc;
}
.table tbody tr:nth-child(even) {
  background: #fafafa;
}

/* ===== Loading 动画 ===== */
.loading-bubble {
  background: #fff !important;
}
.dot-pulse { color: #999; font-size: 14px; }
.dot {
  animation: blink 1.4s infinite both;
}
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink {
  0%, 80%, 100% { opacity: 0; }
  40% { opacity: 1; }
}

/* ===== 输入区 ===== */
.input-area {
  display: flex;
  gap: 10px;
  padding: 16px 20px;
  background: #fff;
  border-top: 1px solid #e8e8e8;
  border-radius: 0 0 12px 12px;
}
.input-area input {
  flex: 1;
  padding: 10px 16px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}
.input-area input:focus {
  border-color: #4a90d9;
}
.input-area button {
  padding: 10px 24px;
  background: #4a90d9;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}
.input-area button:hover:not(:disabled) {
  background: #357abd;
}
.input-area button:disabled {
  background: #ccc;
  cursor: not-allowed;
}
</style>
