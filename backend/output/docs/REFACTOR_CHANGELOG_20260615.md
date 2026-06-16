# KeenRobot 改造记录（2026-06-15）

> 本文档汇总当日已完成的三类改造：**ModelConfig 架构重构**、**.env 变量命名统一**、**移除 admin 模型配置降级**。  
> 设计依据见 [MODEL_CONFIG_REFACTOR_DESIGN.md](./MODEL_CONFIG_REFACTOR_DESIGN.md) v2.2。

---

## 1. 改造总览

| 改造项 | 改造前现象 | 改造后现象 |
|--------|-----------|-----------|
| ModelConfig 职责与字段 | 仅存 `model_name` + 超参；LLM 连接全局锁死在 `.env`；Prompt 分散在 `chain.py` 硬编码与 `rag_config` | 用户可配接入点（URL/Key/模型名）+ Prompt 预设；连接字段空则 `.env` 兜底；Prompt 空则 `rag_config` 兜底 |
| 无用户模型配置时聊天 | 后端硬编码 `deepseek-v4-flash`，或降级使用 admin 默认 ModelConfig | 纯走 `.env`（`LLM_*`）+ 代码默认生成参数；**不再**读取 admin 配置 |
| `.env` 模型变量名 | `DEFAULT_LLM_MODEL` / `DEFAULT_EMBEDDING_MODEL` | `LLM_MODEL_NAME` / `EMBEDDING_MODEL_NAME`（不兼容旧名） |
| 任务中心部分接口 | `/run`、`/start`、`/stop` 使用 JSON Body 传 `task_id` | 改为 `Form(...)`，与 KeenRunner 一致 |
| 聊天模型选择 UI | 无独立选择器或字段语义混乱 | 新增 `ChatModelSelector`；主显 `llm_model_name`，副显 `config_name` |

---

## 2. ModelConfig 架构重构

### 2.1 为什么要改

1. **假多模型**：对话框切换 ModelConfig 改不了 LLM 接入点（Key/URL 只在 `.env`）。
2. **职责重叠**：`.env` 与 DB 双源，且 `DEFAULT_LLM_MODEL` 在聊天路径几乎不生效（曾硬编码 fallback）。
3. **命名混淆**：`name` / `model_name` / `description` 语义不清。
4. **Prompt 分散**：`rag_config.py`、`chain.py` 硬编码、`ModelConfig.system_prompt` 三处并存。
5. **初始化污染**：启动时自动 seed env 到 DB，与用户配置边界模糊。

### 2.2 改造前 vs 改造后（行为）

#### 连接与模型

| 维度 | 改造前 | 改造后 |
|------|--------|--------|
| LLM Key/URL | 仅 `.env` 全局一份 | ModelConfig 可配；字段空 → `.env` 兜底 |
| API `model` 参数 | DB 的 `model_name`，无配置时硬编码 | DB 的 `llm_model_name`，无配置 → `LLM_MODEL_NAME` |
| 切换配置是否换接入点 | 否 | 是 |
| Key 存储 | 无 | DB 加密存储；API 脱敏返回；更新时空值不覆盖 |

#### Prompt

| 场景 | 改造前 | 改造后 |
|------|--------|--------|
| 有 RAG 命中，`system_prompt` 空 | `RAG_SYSTEM_PROMPT` | 同左（不变） |
| 无 RAG 上下文，`system_prompt` 空 | `chain.py` 内硬编码 | `GENERAL_SYSTEM_PROMPT`（`rag_config.py`） |
| 寒暄类问题 | `chain.py` 内硬编码 | `GREETING_RESPONSE`（`rag_config.py`） |
| `RAG_USER_PROMPT` | 存在但未使用 | 已删除 |

#### 聊天解析（`resolve_for_chat`）

| 步骤 | 改造前 | 改造后 |
|------|--------|--------|
| 1 | 请求 `model_config_id` | 同左 |
| 2 | 当前用户默认配置 | 同左 |
| 3 | **admin 用户默认配置** | **已移除** |
| 4 | `None` → env | 同左 |

#### 深度思考

| 维度 | 改造前 | 改造后 |
|------|--------|--------|
| 展示条件 | 前端常显或按模型名推断 | 仅 `model_thinking=true` 的配置显示开关 |
| 后端生效 | 前端传即可能生效 | 须 `model_config` 存在且 `model_thinking=true` |

#### 初始化

| 维度 | 改造前 | 改造后 |
|------|--------|--------|
| `init_model_configs()` | 为 admin 自动创建默认 DeepSeek 配置 | no-op，仅打日志；用户自行在「模型管理」创建 |

### 2.3 字段对照（DB / API）

| 旧字段 | 新字段 | 说明 |
|--------|--------|------|
| `name` | `config_name` | 用户自定义配置名，与 API model 无关 |
| `description` | `config_desc` | 配置说明 |
| `model_name` | `llm_model_name` | 请求 body 中的 `model` |
| — | `model_provider` | 厂商分类，默认 `custom` |
| — | `model_thinking` | 是否展示深度思考开关 |
| — | `llm_base_url` | 空 → `LLM_BASE_URL` |
| — | `llm_api_key` | 加密入库；空 → `LLM_API_KEY` |

### 2.4 修改的文件及原因

#### 后端 — 模型与数据层

| 文件 | 修改内容 | 原因 |
|------|----------|------|
| `applications/model_config/models/model_config_model.py` | 字段重命名 + 新增连接/思考字段 | 对齐 v2.2 数据模型 |
| `migrations/models/14_20260615120000_model_config_refactor.py` | **新增** 迁移脚本 | 列重命名与新增列 |
| `applications/model_config/schemas/model_config_schema.py` | Pydantic 字段同步；`ModelConfigOut.from_model()` 脱敏 Key | API 契约与出库安全 |
| `applications/model_config/services/model_config_crud.py` | 创建/更新时加密 Key；移除 admin 降级 | 业务 CRUD + 聊天解析 |
| `applications/model_config/services/secret_utils.py` | **新增** 加解密/脱敏 | Key 安全存储 |
| `applications/model_config/services/llm_connection.py` | **新增** `resolve_llm_connection` / `resolve_chat_llm_params` | 统一连接与参数解析 |
| `applications/model_config/services/init_data.py` | 改为 no-op | 不再 seed env 到 DB |
| `applications/model_config/views/model_config_view.py` | 响应用 `from_model()` | 返回脱敏 Key |
| `services/scripts/init_model_configs.py` | 字段名更新；仅 admin 示例脚本 | 手动初始化脚本对齐新模型 |

#### 后端 — RAG / 聊天链路

| 文件 | 修改内容 | 原因 |
|------|----------|------|
| `configure/rag_config.py` | 新增 `GENERAL_SYSTEM_PROMPT`、`GREETING_RESPONSE`；删 `RAG_USER_PROMPT` | Prompt 兜底集中管理 |
| `configure/__init__.py` | 导出新常量 | 模块对外接口 |
| `applications/base/rag/chain.py` | 用 `rag_config` 替代硬编码；LLM 传入 `api_key`/`base_url` | 消除 Prompt 硬编码；支持 per-config 连接 |
| `applications/base/rag/llm.py` | 构造函数接受 `api_key`、`base_url` | 支持运行时连接参数 |
| `applications/conversation/services/conversation_crud.py` | `stream_response` 用 `resolve_chat_llm_params`；删硬编码模型；更新 `ModelConfigBrief` 字段 | 聊天主链路 |
| `applications/conversation/schemas/conversation_schema.py` | `ModelConfigBrief`: `config_name` / `config_desc` | 对话统计/详情字段对齐 |

#### 前端

| 文件 | 修改内容 | 原因 |
|------|----------|------|
| `frontend/src/views/ai-manage/model/index.vue` | 表单三分区（基本/连接/参数）；新字段名 | 模型管理页对齐 API |
| `frontend/src/views/chat/index.vue` | 模型下拉字段；深度思考条件展示；无配置时 `model_config_id=null` | 聊天体验与后端契约 |
| `frontend/src/components/chat/ChatModelSelector.vue` | **新增** 模型 pill 选择器 | 聊天 UI |

#### 设计文档

| 文件 | 修改内容 | 原因 |
|------|----------|------|
| `backend/output/docs/MODEL_CONFIG_REFACTOR_DESIGN.md` | **新增** v2.2 设计 | 改造依据与验收要点 |

---

## 3. `.env` 变量重命名

### 3.1 为什么要改

与 ModelConfig 字段命名风格统一（`*_MODEL_NAME`），避免 `DEFAULT_*` 与「兜底语义」混淆。

### 3.2 改造前 vs 改造后

| 改造前（`.env` / `ProjectConfig`） | 改造后 | 说明 |
|-----------------------------------|--------|------|
| `DEFAULT_LLM_MODEL` | `LLM_MODEL_NAME` | 无 ModelConfig 或未指定 `llm_model_name` 时的 API model |
| `DEFAULT_EMBEDDING_MODEL` | `EMBEDDING_MODEL_NAME` | 向量化与检索一致性过滤 |

**不兼容旧变量名**，需在 `.env` 中手动替换后重启服务。

### 3.3 修改的文件及原因

| 文件 | 原因 |
|------|------|
| `backend/configure/project_config.py` | `ProjectConfig` 字段定义 |
| `backend/.env` / `backend/.env.example` | 运行配置与示例 |
| `backend/applications/base/rag/llm.py` | LLM 默认 model |
| `backend/applications/model_config/services/llm_connection.py` | 连接解析 fallback |
| `backend/applications/base/rag/embeddings.py` | Embedding 默认 model |
| `backend/applications/base/rag/chain.py` | 检索结果 embedding 一致性过滤 |
| `backend/applications/knowledge_base/services/knowledge_base_crud.py` | 文档向量化写入的 model 名 |
| `README.md` | 环境变量说明表 |
| `backend/output/docs/PROJECT_GUIDE.md` | 项目指南 |
| `backend/output/docs/RAG_RETRIEVAL_QUALITY.md` | RAG 质量文档 |
| `backend/output/docs/MODEL_CONFIG_REFACTOR_DESIGN.md` | 设计文档中的变量引用 |

---

## 4. 移除 admin 模型配置降级

### 4.1 为什么要改

admin 降级与 `.env` 兜底职责重复：用户无配置时，env 已是唯一基础设施 fallback，再查 admin 会导致行为不透明（用户未配模型却走了 admin 的 Prompt/参数）。

### 4.2 改造前 vs 改造后

| 场景 | 改造前 | 改造后 |
|------|--------|--------|
| 普通用户无 ModelConfig | 可能使用 admin 的默认 ModelConfig | `model_config=None`，走 `.env` + 代码默认生成参数 |
| admin 自己有 ModelConfig | 正常使用 | 不变（仅作用于 admin 本人） |
| `GET /model-configs/default` 无配置 | 可能返回 admin 默认 | 404（仅查当前用户） |

### 4.3 修改的文件及原因

| 文件 | 原因 |
|------|------|
| `applications/model_config/services/model_config_crud.py` | `resolve_for_chat`、`get_default` 删除 admin 分支 |
| `README.md` | 更新聊天降级说明 |
| `backend/output/docs/PROJECT_GUIDE.md` | 更新架构描述与 FAQ |

---

## 5. 其他当日改动（配套）

### 5.1 任务中心接口 Form 化

| 文件 | 改造前 | 改造后 |
|------|--------|--------|
| `backend/applications/task_center/views/task_view.py` | `/run`、`/start`、`/stop` JSON Body | `Form(...)` 接收 `task_id` |
| `frontend/src/api/index.js` | JSON post | `FormData` post |
| `frontend/src/views/ai-manage/task-center/index.vue` | 调用处传 JSON | 调用处构建 `FormData` |

**原因**：与 KeenRunner 调用方式一致，便于网关/代理对 multipart 的统一处理。

---

## 6. 当前运行时行为（改造后）

### 6.1 智能聊天 — 模型解析优先级

```text
1. 请求中的 model_config_id（须属于当前登录用户）
2. 当前用户的 is_default 配置（无 default 标记则取最早一条）
3. None → resolve_chat_llm_params(None)
   ├── 连接：LLM_MODEL_NAME / LLM_BASE_URL / LLM_API_KEY（.env）
   └── 生成参数：temperature=0.7, max_tokens=4096, top_k=5, …（代码默认）
```

### 6.2 有 ModelConfig 时 — 字段级 fallback

```text
llm_model_name  有值 → 用之；否则 → LLM_MODEL_NAME
llm_base_url    有值 → 用之；否则 → LLM_BASE_URL
llm_api_key     有值 → 解密；否则 → LLM_API_KEY
system_prompt   有值 → 用之；否则 → rag_config 按场景兜底
```

### 6.3 前端表现

| 用户状态 | UI | 请求 |
|----------|-----|------|
| 无 ModelConfig | 不显示模型下拉 | `model_config_id: null` |
| 有 ModelConfig | 显示下拉；主 `llm_model_name`，副 `config_name` | 传选中 ID |
| `model_thinking=false` | 不显示深度思考开关 | `enable_thinking: false` |
| `model_thinking=true` | 显示开关 | 按用户选择传递 |

---

## 7. 部署与验收

### 7.1 部署步骤

```bash
# 1. 数据库迁移（ModelConfig 列变更）
cd backend && aerich upgrade

# 2. 更新 .env 变量名
#    DEFAULT_LLM_MODEL      → LLM_MODEL_NAME
#    DEFAULT_EMBEDDING_MODEL → EMBEDDING_MODEL_NAME

# 3. 重启后端与前端
```

### 7.2 验收清单

- [ ] 零 ModelConfig 时，凭 `.env` 可正常对话
- [ ] 创建不同 `llm_base_url` / `llm_model_name` / `system_prompt` 的配置后，聊天切换生效
- [ ] `llm_api_key` 留空时使用 `.env` Key，留空更新不覆盖已有 Key
- [ ] 普通用户无配置时**不会**使用 admin 的 ModelConfig
- [ ] `system_prompt` 为空时走 `rag_config` 兜底；`chain.py` 无 Prompt 硬编码
- [ ] Embedding 行为不变；`EMBEDDING_MODEL_NAME` 生效
- [ ] 任务中心 run/start/stop 接口 Form 提交正常

---

## 8. 相关文档

| 文档 | 说明 |
|------|------|
| [MODEL_CONFIG_REFACTOR_DESIGN.md](./MODEL_CONFIG_REFACTOR_DESIGN.md) | 设计原则与字段定义（v2.2） |
| [PROJECT_GUIDE.md](./PROJECT_GUIDE.md) | 项目整体指南（已同步 env 与降级说明） |
| [RAG_RETRIEVAL_QUALITY.md](./RAG_RETRIEVAL_QUALITY.md) | RAG 检索与 Embedding 变量说明 |

---

*文档版本：2026-06-15 · 与当日代码改造一致*
