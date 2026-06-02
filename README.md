# 企业级 RAG 问答系统

基于 FastAPI + Vue 3 的企业级 RAG（检索增强生成）问答系统，支持知识库管理、智能问答、用户认证等功能。

## 🌟 功能特性

- **智能问答**：基于 RAG 技术的智能问答系统
- **知识库管理**：支持 PDF 文档上传、解析、向量化存储
- **用户认证**：完整的用户注册、登录、权限管理系统
- **多模型支持**：支持千问等多种大语言模型
- **ChromaDB 向量库**：本地持久化，无需额外服务
- **流式响应**：支持 SSE 流式输出，提升用户体验
- **前后端分离**：FastAPI 后端 + Vue 3 前端

## 📋 技术栈

### 后端
- **框架**：FastAPI
- **数据库**：MySQL / SQLite
- **向量数据库**：ChromaDB（本地 `chroma_db/` 目录）
- **RAG 框架**：LangChain
- **LLM**：千问 API（DashScope）
- **认证**：JWT + bcrypt

### 前端
- **框架**：Vue 3
- **构建工具**：Vite
- **UI**：自定义组件
- **路由**：Vue Router

## 🚀 快速开始

### 环境要求

- Python >= 3.12
- Node.js >= 16
- MySQL >= 5.7（可选，默认使用 SQLite）

### 1. 克隆项目

```bash
git clone https://gitee.com/Nianzzzz/eehqasrag.git
cd eehqasrag
```

### 2. 后端配置

#### 安装 Python 依赖

```bash
# 使用 pip
pip install -r requirements.txt

# 或使用 uv（推荐，更快）
pip install uv
uv sync
```

#### 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填写必要的配置
```

**.env 文件说明**：

```env
# 数据库配置
DATABASE_URL=mysql+aiomysql://user:password@localhost:3306/rag_db
# 或使用 SQLite
# DATABASE_URL=sqlite+aiosqlite:///./rag_system.db

# ChromaDB 本地向量库（可选，默认 chroma_db/）
CHROMA_COLLECTION=knowledge_base

# 千问 API 配置
DASHSCOPE_API_KEY=your_api_key_here

# JWT 配置
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# 服务器配置
HOST=0.0.0.0
PORT=8000
```

#### 初始化数据库

```bash
# 创建数据库表
python -m alembic upgrade head

# 初始化默认配置（可选）
python scripts/init_default_config.py

# 创建管理员账户（可选）
python scripts/init_admin.py
```

### 3. 启动后端服务

```bash
# 使用 uvicorn 启动
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 或使用 uv
uv run python -m app.main
```

后端服务启动后访问：
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health

### 4. 前端配置

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端服务启动后访问：http://localhost:3001

## 📁 项目结构

```
eehqasrag/
├── app/                    # 后端代码
│   ├── api/               # API 路由
│   │   ├── auth.py        # 认证相关
│   │   ├── chat.py        # 聊天相关
│   │   ├── history.py     # 历史记录
│   │   ├── knowledge_base.py  # 知识库管理
│   │   └── model_config.py    # 模型配置
│   ├── rag/               # RAG 核心
│   │   ├── chain.py       # RAG 链
│   │   ├── embeddings.py  # 嵌入模型
│   │   ├── llm.py         # LLM 接口
│   │   ├── loader.py      # 文档加载
│   │   ├── chroma_store.py # Chroma 本地向量存储
│   ├── config.py          # 配置文件
│   ├── database.py        # 数据库连接
│   ├── main.py            # 应用入口
│   └── models.py          # 数据模型
├── frontend/              # 前端代码
│   ├── src/
│   │   ├── api/          # API 调用
│   │   ├── components/   # 组件
│   │   ├── views/        # 页面
│   │   └── router/       # 路由
│   └── ...
├── scripts/               # 工具脚本
│   ├── build_kb.py       # 构建知识库
│   ├── init_admin.py     # 初始化管理员
│   └── ...
├── data/                  # 示例数据
├── uploads/               # 上传文件存储
├── tests/                 # 测试文件
├── images/                # 项目图片
├── requirements.txt       # Python 依赖
└── README.md             # 项目文档
```

## 🔧 使用说明

### 1. 注册用户

访问前端页面，点击"注册"按钮，填写用户名、邮箱和密码完成注册。

### 2. 登录系统

使用注册的账号登录系统。

### 3. 创建知识库

1. 进入"知识库"页面
2. 点击"创建知识库"
3. 填写知识库名称和描述
4. 上传 PDF 文档

### 4. 开始问答

1. 进入"对话"页面
2. 选择已创建的知识库
3. 输入问题，开始智能问答

## 📝 常见问题

### Q: 如何配置千问 API？

1. 访问 [阿里云 DashScope](https://dashscope.console.aliyun.com/)
2. 注册并获取 API Key
3. 在 `.env` 文件中配置 `DASHSCOPE_API_KEY`

### Q: 如何使用 MySQL 数据库？

1. 安装 MySQL 数据库
2. 创建数据库：`CREATE DATABASE rag_db;`
3. 在 `.env` 中配置数据库连接：
   ```env
   DATABASE_URL=mysql+aiomysql://user:password@localhost:3306/rag_db
   ```

### Q: 向量数据存在哪里？

ChromaDB 以本地持久化模式运行，默认目录为项目根目录下的 `chroma_db/`，无需单独部署向量数据库服务。

### Q: 端口被占用怎么办？

修改 `.env` 文件中的端口配置：

```env
# 后端端口
PORT=8000

# 前端端口（在 frontend/vite.config.js 中修改）
server: {
  port: 3001
}
```

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目仅供学习和研究使用。

## 📧 联系方式

如有问题，请提交 Issue 或通过以下方式联系：

- Gitee: https://gitee.com/Nianzzzz/eehqasrag

---

**注意**：首次使用前请确保正确配置 `.env` 文件中的各项参数，特别是 API Key 和数据库连接信息。
