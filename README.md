# 📚 RAG 智能问答系统

基于 **LangChain + DeepSeek + ChromaDB + FastAPI + Vue 3** 的本地知识库问答系统。

上传文档后，AI 会自动从文档中检索相关内容来回答问题。

## ✨ 功能

- ✅ **上传文档**：支持 TXT、PDF、DOCX、MD 格式，上传后自动构建知识库
- ✅ **智能问答**：基于文档内容回答，自动标注信息来源（含匹配分数）
- ✅ **混合检索**：向量语义搜索 + 关键词匹配，结果更精准
- ✅ **对话压缩**：长对话自动摘要，不占满上下文窗口
- ✅ **文档管理**：在线查看和删除已有文档
- ✅ **健康检查**：`GET /health` 查看系统运行状态
- ✅ **Gradio 界面**（旧版保留）：`python rag_app.py` 仍可用

## 🖥️ 界面（前端）

两个标签页：
- **💬 问答** — 气泡对话界面，直接提问
- **📁 文档管理** — 上传/删除文档，管理知识库

采用 Gradio 风格 UI，深蓝气泡为用户消息，白色气泡为 AI 回答。

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API 密钥

在项目根目录创建 `.env` 文件（已存在则跳过）：

```
DEEPSEEK_API_KEY=你的deepseek_api_key
```

> 前往 [DeepSeek 官网](https://platform.deepseek.com/) 注册获取 API Key

### 3. 启动后端

```bash
uvicorn backend.main:app --port 8000
```

### 4. 启动前端（新窗口）

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173` 即可使用。

### 5. 上传文档

首次使用，在 **文档管理** 标签页上传你的文档（TXT / PDF / DOCX / MD），
系统会自动构建知识库，之后就可以在问答页面提问了。

### 6. 旧版 Gradio（可选）

```bash
python rag_app.py
```

浏览器会自动打开 `http://localhost:7860`

## 📁 项目结构

```
rag-project/
├── rag_app.py              # Gradio 版主程序（旧版保留）
├── requirements.txt        # 依赖清单
├── .env                    # API 密钥（不提交到 Git）
│
├── backend/                # FastAPI 后端
│   ├── main.py             # 应用入口，含启动事件
│   ├── router.py           # API 路由（chat/upload/delete/health）
│   ├── schemas.py          # 请求/响应数据模型
│   └── state.py            # 运行时全局状态
│
├── frontend/               # Vue 3 前端
│   ├── src/                # 源码
│   │   ├── App.vue         # 主页面（顶栏 + 标签切换）
│   │   ├── api.js          # 后端接口封装
│   │   └── main.js         # 入口
│   ├── view/               # 页面组件
│   │   ├── ChatView.vue    # 问答页面（气泡对话）
│   │   └── DocManager.vue  # 文档管理页面
│   └── package.json
│
├── rag_forge/              # RAG 核心逻辑
│   ├── service.py          # 公共服务层
│   ├── config.py           # 配置管理
│   ├── agent/              # AI 代理
│   ├── data/               # 文档加载和切分
│   ├── embedding/          # 本地嵌入模型
│   ├── retrieval/          # 混合检索（向量 + 关键词）
│   ├── evaluation/         # 评测体系
│   ├── prompts/            # 系统提示词模板
│   └── ui/                 # Gradio UI 组件
│
├── data/                   # 文档存放目录
│   └── manifest.json       # 文档清单
├── chroma_db/              # 向量数据库（自动生成）
└── modelscope_cache/       # 本地嵌入模型缓存
```

## 🧠 技术架构

```
用户提问
    │
    ▼
FastAPI → 混合检索（ChromaDB 向量 + jieba 关键词）
    │         │
    │         └─▶ 本地嵌入模型（BAAI/bge-small-zh-v1.5）
    │
    ▼
DeepSeek Chat LLM → 基于资料生成回答
    │
    ▼
返回 JSON → Vue 前端渲染气泡对话
```

## ⚙️ 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 前端框架 | Vue 3 + Vite |
| 大模型 | DeepSeek Chat |
| 向量数据库 | ChromaDB |
| 嵌入模型 | BAAI/bge-small-zh-v1.5（本地运行） |
| AI 框架 | LangChain |
| 中文分词 | jieba |
| 旧版界面 | Gradio |

## 📝 说明

- 嵌入模型已在本地缓存（ModelScope 下载），无需联网即可使用
- 所有文档处理在本地完成，文档内容不会上传到第三方
- 如果添加文档后知识库没有更新（后端未重启），调 `GET /health` 查看状态

## 🔜 后续优化方向

- [ ] 统一混合检索评分（目前关键词结果排前面）
- [ ] 支持数据库作为文档源（预留了 DatabaseSource 类）
- [ ] 添加单元测试
- [ ] 支持更多文档格式
