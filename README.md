# KeenRobot

企业级 RAG（检索增强生成）智能问答系统。支持知识库管理、向量检索增强、SSE 流式对话、多模型接入配置、任务调度与可视化管理界面，适用于企业内部知识问答、文档助手等场景。

---

## 功能概览

| 能力 | 说明 |
|------|------|
| **智能问答** | 基于知识库的 RAG 检索增强，SSE 流式输出，支持多轮对话与历史续聊 |
| **知识库** | 上传 PDF 文档，自动解析、分块、向量化入库，问答时检索相关知识片段 |
| **模型配置** | 按用户隔离的多套 LLM 接入、Prompt 预设与生成参数；未配置时回退环境变量 |
| **用户与权限** | JWT 登录认证，用户数据（对话、知识库、配置）相互隔离 |
| **Agent 扩展** | Skills / MCP 服务注册与聊天绑定（预留扩展能力） |
| **任务中心** | 定时 / 周期 / 一次性任务编排与执行记录（需 Celery） |
| **管理界面** | Vue 3 单页应用，覆盖聊天、知识库、模型、任务等完整操作入口 |

---

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    浏览器（Vue 3 + Vite）                 │
│         登录 · 聊天 · 知识库 · 模型管理 · 任务中心          │
└───────────────────────────┬─────────────────────────────┘
                            │ HTTP / SSE（/api 代理）
                            ▼
┌─────────────────────────────────────────────────────────┐
│                   FastAPI 后端（8519）                    │
│    认证 · RAG 链 · 知识库 · ModelConfig · 任务中心 API     │
└───────┬─────────────────┬─────────────────┬─────────────┘
        │                 │                 │
        ▼                 ▼                 ▼
     MySQL            ChromaDB            Redis
   （业务数据）      （向量检索）      （Celery 队列）
        │                                   │
        └─────────── LLM / Embedding API ───┘
                    （OpenAI 兼容接口）
```

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3、Vite、Pinia、Naive UI、Axios |
| 后端 | FastAPI、Tortoise ORM、Aerich、LangChain、ChromaDB |
| 任务调度 | Celery、celery-redbeat、Redis |
| 大模型 | OpenAI 兼容 API（如 DeepSeek、硅基流动 Embedding） |

---

## 项目结构

```
KeenRobot/
├── backend/          # FastAPI 后端服务
├── frontend/         # Vue 3 前端应用
├── requirements.txt  # Python 依赖（根目录汇总）
└── README.md         # 本文件（项目总览）
```

各子目录的详细说明、接口与开发指南请参阅：

- **[backend/README.md](backend/README.md)** — 后端安装、配置、API、RAG 与任务中心
- **[frontend/README.md](frontend/README.md)** — 前端安装、代理联调、页面与组件

---

## 环境要求

| 组件 | 要求 |
|------|------|
| Python | ≥ 3.12 |
| Node.js | ≥ 18 |
| MySQL | 5.7+ / 8.x，需提前创建数据库 |
| Redis | 使用任务中心时必需 |
| 外部 API | LLM API Key；知识库检索需 Embedding API Key |

---

## 快速开始

以下步骤用于**本地开发联调**。更完整的配置说明与故障排查见子项目 README。

### 1. 克隆项目

```bash
git clone <repository-url>
cd KeenRobot
```

### 2. 启动后端

```bash
# 配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env：数据库、AUTH_SECRET_KEY、LLM/EMBEDDING Key、Redis 等

# 安装依赖（在 backend 目录）
cd backend
uv sync          # 或 pip install -e .

# 启动（默认端口 8519）
uv run python backend_main.py
```

> 后端支持**启动时自动初始化数据库与迁移**（开发环境需在 `.env` 中设置 `DATABASE_AUTO_MIGRATION=True`）。详见 [backend/README.md](backend/README.md)。

启动后可访问：

- API 文档：http://localhost:8519/KeenRobot/docs
- 健康检查：http://localhost:8519/health

### 3. 启动前端

```bash
cd frontend

# 修改联调地址（指向本机后端）
# 编辑 frontend/build/constant.js 中的 BACKEND_URL，例如：
#   export const BACKEND_URL = 'http://127.0.0.1:8519'

pnpm install     # 或 npm install
pnpm dev
```

浏览器访问开发服务器地址（默认 http://localhost:5173，以终端输出为准），进入登录页。

### 4. 登录使用

首次启动且用户表为空时，系统自动创建默认管理员：

| 用户名 | 密码 |
|--------|------|
| admin | 123456 |

登录后可进入 **智能聊天**、**知识库管理**、**模型管理** 等模块。使用前请在 `backend/.env` 中配置 LLM 与 Embedding API Key。

### 5. 任务中心（可选）

若需使用定时任务功能，除后端外还需启动 Celery Worker 与 Beat，并确保 Redis 可用。启动命令见 [backend/README.md — Celery](backend/README.md#5-启动-celery任务调度必需)。

---

## 配置要点

| 配置 | 位置 | 说明 |
|------|------|------|
| 后端环境变量 | `backend/.env` | 数据库、JWT、LLM/Embedding、Redis 等 |
| 前端 API 前缀 | `frontend/.env.development` | `VITE_BASE_API=/api` |
| 开发代理目标 | `frontend/build/constant.js` | `BACKEND_URL` 指向后端地址 |
| 生产部署 | Nginx 等 | 静态资源托管 + `/api` 反向代理到后端 |

开发环境下，前端请求 `/api/...` 经 Vite 代理转发至后端并去掉 `/api` 前缀；生产环境需在 Web 服务器配置同等规则。细节见 [frontend/README.md](frontend/README.md)。

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [backend/README.md](backend/README.md) | 后端完整指南：环境变量、接口清单、RAG 流程、任务中心、常见问题 |
| [frontend/README.md](frontend/README.md) | 前端完整指南：路由页面、API 封装、SSE 聊天、部署与联调 |

---

## 常见问题

**无法登录或接口 404**

- 确认后端已启动且 `frontend/build/constant.js` 中 `BACKEND_URL` 正确（端口 8519）
- 开发环境确认 `VITE_USE_PROXY=true`

**知识库问答不引用文档**

- 检查 `backend/.env` 是否配置 `EMBEDDING_API_KEY`
- 确认已上传 PDF 且文档处理状态为 completed

**聊天可用但无模型下拉**

- 属正常情况：当前用户未创建 ModelConfig 时，系统使用 `.env` 中的 LLM 配置

**任务不执行**

- 需同时运行 Celery Worker、Beat 与 Redis，见 backend README

更多问题请参阅子项目 README 中的「常见问题」章节。

---

## 贡献与反馈

欢迎提交 Issue 或 Pull Request。开发前请先阅读 [backend/README.md](backend/README.md) 与 [frontend/README.md](frontend/README.md)，了解各模块约定与联调方式。

---

*KeenRobot — 企业级 RAG 智能问答系统*
