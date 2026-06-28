const BASE = "http://localhost:8000"

/** 聊天 */
export async function chat(question, history = [],sessionId = null) {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" ,...authHeaders() },
    body: JSON.stringify({ question, history, session_id: sessionId }),
  })
  return res.json()
}

/** 文档列表（简单版：只返回文件名数组） */
export async function getDocuments() {
  const res = await fetch(`${BASE}/documents`,{headers:{...authHeaders() },})
  return res.json()
}

/** 文档列表（详细版：含大小、上传时间） */
export async function getDocumentsDetails() {
  const res = await fetch(`${BASE}/documents/details`,{headers:{...authHeaders() },})
  return res.json()
}

/** 上传文档 */
export async function uploadDocument(file) {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: form ,headers:{...authHeaders() },})
  return res.text()   // 后端返回的是字符串消息，不是 JSON
}

/** 删除文档 */
export async function deleteDocument(filename) {
  const res = await fetch(`${BASE}/delete?filename=${encodeURIComponent(filename)}`, {
    method: "DELETE",headers:{...authHeaders() },})
  return res.text()   // 后端返回的是字符串消息
}

/** 删除下拉候选（可删除的文件名列表） */
export async function getDeleteChoices() {
  const res = await fetch(`${BASE}/delete/choices`,{headers:{...authHeaders() },})
  return res.json()
}

/** NL2SQL：自然语言 → SQL → 查询结果 */
export async function nl2sql(question,history = [], sessionId = null) {
 
  const res = await fetch(`${BASE}/nl2sql`, {
    method: "POST",
    headers: { "Content-Type": "application/json" ,...authHeaders() },
    body: JSON.stringify({ question ,history, session_id: sessionId }),
  })
  return res.json()
}

export async function getSessions(mode) {
  const res = await fetch(`${BASE}/sessions?mode=${mode}`,{headers:{...authHeaders() },})
  return res.json()
}

export async function getSession(id) {
  const res = await fetch(`${BASE}/sessions/${id}`,{headers:{...authHeaders() },})
  return res.json()
}

export async function createSession(mode) {
  const res = await fetch(`${BASE}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json",...authHeaders() },
    body: JSON.stringify({ mode }),
  })
  return res.json()
}

export async function deleteSession(id) {
  const res = await fetch(`${BASE}/sessions/${id}`, { method: "DELETE" ,headers:{...authHeaders() },})
  return res.json()   
}

/**
 * 从 localStorage 取 token，拼成 Authorization 请求头。
 * 
 * 登录成功后 token 存到了 localStorage（App.vue 里的 handleLoginSuccess 存的）。
 * 每个需要鉴权的 API 请求都要带这个头，后端才能拿到当前 user_id。
 * 
 * 思路：
 *   - localStorage.getItem('token')
 *   - 有 token → 返回 { 'Authorization': 'Bearer <token>' }
 *   - 没有 → 返回 {}（空对象，这样 ...authHeaders() 展开后不影响原有 headers）
 */
function authHeaders() {
  const token = localStorage.getItem('token')
  return token ? { 'Authorization': `Bearer ${token}` } : {}
}



