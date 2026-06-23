const BASE = "http://localhost:8000"

/** 聊天 */
export async function chat(question, history = []) {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history }),
  })
  return res.json()
}

/** 文档列表（简单版：只返回文件名数组） */
export async function getDocuments() {
  const res = await fetch(`${BASE}/documents`)
  return res.json()
}

/** 文档列表（详细版：含大小、上传时间） */
export async function getDocumentsDetails() {
  const res = await fetch(`${BASE}/documents/details`)
  return res.json()
}

/** 上传文档 */
export async function uploadDocument(file) {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: form })
  return res.text()   // 后端返回的是字符串消息，不是 JSON
}

/** 删除文档 */
export async function deleteDocument(filename) {
  const res = await fetch(`${BASE}/delete?filename=${encodeURIComponent(filename)}`, {
    method: "DELETE",
  })
  return res.text()   // 后端返回的是字符串消息
}

/** 删除下拉候选（可删除的文件名列表） */
export async function getDeleteChoices() {
  const res = await fetch(`${BASE}/delete/choices`)
  return res.json()
}

/** NL2SQL：自然语言 → SQL → 查询结果 */
export async function nl2sql(question,history = []) {
 
  const res = await fetch(`${BASE}/nl2sql`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question ,history }),
  })
  return res.json()
}