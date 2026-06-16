# ModelConfig 改造设计

> v2.2 · 2026-06-15 · 待实施

---

## 1. 当前问题

| 问题 | 说明 |
|------|------|
| 职责重叠 | `.env` LLM 配置与 `ModelConfig.llm_model_name` 双源；`LLM_MODEL_NAME` 聊天路径几乎不生效 |
| 命名混淆 | `name` / `model_name` / `description` 语义不清 |
| 假多模型 | 无 `llm_base_url` / `llm_api_key`，对话框切换改不了接入点 |
| Prompt 分散 | `rag_config`、`chain.py` 硬编码、`system_prompt` 三处并存 |
| env 定位模糊 | 未与用户配置边界清晰 |

---

## 2. 改造目标

### 2.1 三层职责

```
基础设施（运维配，不入库）
├── .env LLM_*          → 无 ModelConfig 或连接字段为空时兜底
├── .env EMBEDDING_*    → 向量化固定配置，用户不可配
└── rag_config.py       → Prompt 兜底（见 2.4）

用户配置（入库）
└── ModelConfig         → Prompt 策略预设 + 模型接入（可选）

运行时
├── 有 ModelConfig → 接入 + system_prompt（空则 rag_config）
└── 无 ModelConfig → .env 连接 + rag_config
```

### 2.2 `.env` LLM — 兜底，不入库

| 变量 | 作用 |
|------|------|
| `LLM_API_KEY` / `LLM_BASE_URL` | 对应 `llm_api_key` / `llm_base_url` 为空时的兜底 |
| `LLM_MODEL_NAME` | 无 ModelConfig 或未指定 `llm_model_name` 时的 API model 参数 |

### 2.3 `.env` Embedding — 固定，用户不可配

`EMBEDDING_*` 仅用于文档向量化与检索，与 ModelConfig 无关。

### 2.4 `rag_config.py` — Prompt 兜底

| 常量 | 场景 |
|------|------|
| `RAG_SYSTEM_PROMPT` | 有 RAG 命中且 `system_prompt` 为空 |
| `GENERAL_SYSTEM_PROMPT` | 无 RAG 上下文 |
| `GREETING_RESPONSE` | 无关寒暄（不调 LLM） |

`chain.py` 硬编码迁入；删除 `RAG_USER_PROMPT`。

### 2.5 ModelConfig — 用户层

一条记录 = 可选接入 + 可选 Prompt。对话框切换 `model_config_id`。**不强制**存在记录。

### 2.6 不做

上下文计量 UI、Embedding 用户可配、env seed 进库。

---

## 3. ModelConfig 模型改造

### 3.1 命名约定

| 字段 | 含义 | 与模型的关系 |
|------|------|--------------|
| **`config_name`** | 用户自定义配置名称 | **无关** |
| **`config_desc`** | 配置说明 | **无关** |
| **`llm_model_name`** | API body 中的 `model` 参数 | **有关** |
| **`model_provider`** | 厂商分类 | 辅助展示 |

示例：`config_name` =「客服-DeepSeek」，`llm_model_name` = `deepseek-v4-flash`。

### 3.2 字段一览

| 分组 | 字段 | 类型 | 说明 |
|------|------|------|------|
| **基本** | `id` | char PK | 不变 |
| | `user_id` | FK | 不变 |
| | `config_name` | varchar(64) | 用户自定义配置名（原 `name`） |
| | `config_desc` | varchar(255)? | 配置说明（原 `description`） |
| | `model_provider` | varchar(32) | deepseek / openai / zhipu / qwen / custom（原 `provider`） |
| | `llm_model_name` | varchar(64) | API `model` 参数（原 `model_name`） |
| | `model_thinking` | bool | 是否展示深度思考（原 `supports_thinking`） |
| | `is_default` | bool | 用户默认方案 |
| **连接** | `llm_base_url` | varchar(512)? | 空 → `LLM_BASE_URL`（原 `api_base_url`） |
| | `llm_api_key` | varchar(512)? | 加密入库；空 → `LLM_API_KEY`；出库脱敏（原 `api_key`） |
| **Prompt** | `system_prompt` | text? | 空 → `rag_config` |
| **生成** | `temperature` / `top_p` / `max_tokens` | | 不变 |
| **RAG/对话** | `top_k` / `score_threshold` / `max_history_rounds` | | 不变 |
| **审计** | `created_time` / `updated_time` 等 | | 不变 |

### 3.3 迁移（旧 → 新）

| 旧字段 | 新字段 |
|--------|--------|
| `name` | `config_name` |
| `description` | `config_desc` |
| `model_name` | `llm_model_name` |
| — | `model_provider`（新增，默认 `custom`） |
| — | `llm_base_url`（新增） |
| — | `llm_api_key`（新增） |
| — | `model_thinking`（新增，默认 `false`） |

不 seed env 到 DB；`init_model_configs` 可选示例或移除。

### 3.4 运行时解析

**连接：**

```text
llm_model_name ← ModelConfig.llm_model_name 或 LLM_MODEL_NAME
llm_api_key    ← decrypt(ModelConfig.llm_api_key) 或 LLM_API_KEY
llm_base_url   ← ModelConfig.llm_base_url          or LLM_BASE_URL
```

**resolve_for_chat：**

```text
model_config_id → 用户 is_default → None（允许，走 env）
```

**Prompt：**

```text
有 RAG:   system_prompt or RAG_SYSTEM_PROMPT
无 RAG:   system_prompt or GENERAL_SYSTEM_PROMPT
寒暄:     GREETING_RESPONSE
```

**深度思考：** 仅 `model_thinking=true` 时前端展示开关并传 `enable_thinking`。

### 3.5 密钥

`llm_api_key` 加密入库；API 脱敏；更新时空值不覆盖；日志禁止明文。

---

## 4. 调用链变更（摘要）

| 模块 | 变更 |
|------|------|
| `OpenAICompatibleLLM` | `model←llm_model_name`, `api_key←llm_api_key`, `base_url←llm_base_url`，空则 env |
| `conversation_crud` | 支持 `model_config=None`；删硬编码兜底 |
| `chain._resolve_system_prompt` | ModelConfig 或 rag_config |
| 前端模型管理 | `config_name` / `config_desc` / 连接 / `llm_model_name` / prompt |
| 前端聊天 | 下拉主 `llm_model_name` + 副 `config_name`；`model_thinking` 控开关 |

---

## 5. 验收要点

1. 零 ModelConfig 时凭 `.env` 可对话。
2. 新建配置（不同 `llm_base_url` / `llm_api_key` / `llm_model_name` / prompt）后对话框切换生效。
3. `system_prompt` 为空时走 `rag_config` 兜底。
4. Embedding 行为不变。
5. `chain.py` 无 Prompt 硬编码。

---

## 6. 参考文件

`configure/project_config.py` · `configure/rag_config.py` · `model_config_model.py` · `llm.py` · `chain.py` · `conversation_crud.py`
