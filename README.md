# 📚 RAG 智能问答系统

基于 **LangChain + DeepSeek + ChromaDB + Gradio** 的本地知识库问答系统。

上传文档后，AI 会自动从文档中检索相关内容来回答问题。

## ✨ 功能

- ✅ **上传文档**：支持 TXT、PDF、DOCX、MD 格式，上传后自动构建知识库
- ✅ **智能问答**：基于文档内容回答，自动标注信息来源
- ✅ **混合检索**：向量语义搜索 + 关键词匹配，结果更精准
- ✅ **天气查询**：支持查询实时天气（需要联网）
- ✅ **对话压缩**：长对话自动摘要，不占满上下文窗口
- ✅ **文档管理**：在线查看和删除已有文档

## 🖥️ 界面截图

两个标签页：
- **💬 问答** — 聊天界面，直接提问
- **📁 文档管理** — 上传/删除文档，管理知识库

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

### 3. 运行

```bash
python rag_app.py
```

浏览器会自动打开 `http://localhost:7860`

### 4. 上传文档

首次使用，在 **文档管理** 标签页上传你的文档（TXT / PDF / DOCX / MD），
系统会自动构建知识库，之后就可以在问答页面提问了。

## 📁 项目结构

```
rag-project/
├── rag_app.py              # 主程序
├── requirements.txt        # 依赖清单
├── .env                    # API 密钥（不提交到 Git）
├── data/                   # 文档存放目录
│   ├── manifest.json       # 文档清单
│   └── ...                 # 你的文档
├── chroma_db/              # 向量数据库（自动生成）
│   ├── chroma.sqlite3      # 向量存储
│   ├── chunks.json         # 文本块缓存（关键词搜索用）
│   └── sync_state.json     # 同步状态
├── modelscope_cache/       # 本地嵌入模型缓存
└── README.md
```

## 🧠 技术架构

```
用户提问
    │
    ▼
AI 代理（DeepSeek Chat）
    │
    ├─▶ search_docs 工具 ──▶ 向量检索（ChromaDB） + 关键词匹配（jieba）
    │                           │
    │                           └─▶ 本地嵌入模型（BAAI/bge-small-zh-v1.5）
    │
    └─▶ get_weather 工具 ──▶ wttr.in 天气 API
    │
    ▼
AI 回答（带信息来源）
```

## ⚙️ 技术栈

| 组件 | 技术 |
|------|------|
| 大模型 | DeepSeek Chat |
| 向量数据库 | ChromaDB |
| 嵌入模型 | BAAI/bge-small-zh-v1.5（本地运行） |
| AI 框架 | LangChain |
| 中文分词 | jieba |
| 界面 | Gradio |

## 📝 说明

- 嵌入模型已在本地缓存（ModelScope 下载），无需联网即可使用
- 所有文档处理在本地完成，文档内容不会上传到第三方
- 如果添加文档后知识库没有更新，重启程序即可

## 🔜 后续优化方向

- [ ] 统一混合检索评分（目前关键词结果排前面）
- [ ] 支持数据库作为文档源（预留了 DatabaseSource 类）
- [ ] 添加单元测试
- [ ] 支持更多文档格式
