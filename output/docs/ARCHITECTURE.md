# 后端架构说明（v3.0）

## 分层结构

```
app/
├── main.py                 # 应用入口、生命周期、路由挂载
├── core/                   # 核心基础设施
│   ├── config.py           # 环境变量、TORTOISE_ORM 配置
│   └── security.py         # JWT、密码哈希
├── db/                     # 数据库连接
│   └── init_db.py          # Tortoise 初始化/关闭
├── models/                 # Tortoise ORM 实体（数据层）
├── schemas/                # Pydantic 请求/响应模型（DTO）
├── repositories/           # 数据访问层（Repository Pattern）
├── services/               # 业务逻辑层
├── api/                    # HTTP 接口层
│   ├── deps.py             # FastAPI 依赖（鉴权等）
│   └── v1/                 # API v1 路由
└── rag/                    # RAG 领域模块（检索、LLM、向量库）
```

## 各层职责

| 层级 | 职责 | 禁止 |
|------|------|------|
| **api/v1** | 参数校验、调用 Service、返回 Schema | 不写业务逻辑、不直接操作 ORM |
| **services** | 业务编排、权限校验、跨模块协调 | 不处理 HTTP 细节 |
| **repositories** | CRUD、查询封装 | 不含业务规则 |
| **models** | 表结构、关系定义 | 不含 API 逻辑 |
| **schemas** | 输入输出数据结构 | 不依赖 ORM |
| **rag** | 向量检索、Prompt、LLM 调用 | 不依赖 FastAPI |

## 技术栈

- **FastAPI** — Web 框架
- **Tortoise ORM** — 异步 ORM
- **aiomysql** — MySQL 异步驱动（通过 Tortoise）
- **Aerich** — 数据库迁移（替代 Alembic）
- **Pydantic v2** — 数据校验
- **ChromaDB** — 本地向量存储（`chroma_db/`）

## 向量库

使用 ChromaDB 持久化客户端，数据保存在项目根目录 `chroma_db/`，无需 Docker 或独立向量库服务。Embedding 仍通过外部 API（如硅基流动）生成向量后写入 Chroma。

## 数据库迁移（Aerich）

```bash
# 安装依赖
pip install -r requirements.txt

# 首次初始化 Aerich（仅需一次）
aerich init -t app.core.config.TORTOISE_ORM

# 生成初始迁移
aerich init-db

# 模型变更后
aerich migrate --name describe_change
aerich upgrade
```

`.env` 中设置 `DB_TYPE=mysql` 使用 MySQL，默认 `sqlite` 用于本地开发。

## 启动

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 扩展指南

- **新增 API**：在 `schemas/` 定义 DTO → `repositories/` 加查询 → `services/` 写逻辑 → `api/v1/` 注册路由
- **新增表**：在 `models/` 加模型 → `aerich migrate` → `aerich upgrade`
- **新增 RAG 能力**：在 `rag/` 扩展，由 `ChatService` 调用

## API 路径（与重构前兼容）

所有 REST 路径保持不变，前端无需修改：

- `/api/auth/*`
- `/api/chat/stream`
- `/api/conversations/*`
- `/api/knowledge-bases/*`
- `/api/model-configs/*`
- `/api/health`
